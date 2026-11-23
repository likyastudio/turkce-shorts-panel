"""Automated tests for Likya Studios Cross-Posting API (DB, OAuth, YouTube, Instagram, status badges)."""
import os
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ["SQLITE_PATH"] = os.path.join(tempfile.gettempdir(), "test_likya_crosspost.db")
os.environ["DATABASE_URL"] = ""
os.environ["API_SECRET_KEY"] = "test-secret"
os.environ["GCS_BUCKET_NAME"] = "likya-temp-videos"

if os.path.exists(os.environ["SQLITE_PATH"]):
    os.remove(os.environ["SQLITE_PATH"])

from app import db  # noqa: E402
from app.main import app  # noqa: E402

db.init_db()
client = TestClient(app)
HDR = {"X-API-Key": "test-secret"}


def test_health_and_auth():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Missing API key should be rejected on protected routes
    assert client.get("/api/accounts").status_code == 401
    assert client.get("/api/accounts", headers=HDR).status_code == 200


def test_accounts_crud_and_cross_publish(tmp_path):
    mp4 = tmp_path / "demo.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    # 1. Connect YT + IG accounts
    yt = client.post("/api/accounts", headers=HDR, json={
        "platform": "YT", "account_name": "Absürt Tarih YT", "external_id": "UC123",
        "access_token": "yt_tok", "refresh_token": "yt_ref"
    }).json()["account"]
    ig = client.post("/api/accounts", headers=HDR, json={
        "platform": "IG", "account_name": "@absurttarih", "external_id": "178414001",
        "access_token": "ig_tok"
    }).json()["account"]

    listed = client.get("/api/accounts", headers=HDR).json()["accounts"]
    assert len(listed) == 2
    assert "access_token" not in listed[0]  # tokens never leaked to frontend!

    # 2. Trigger cross-post with mocked GCS + YouTube + Instagram APIs
    with patch("app.main.upload_to_gcs_and_get_signed_url", return_value="https://storage.googleapis.com/signed/demo.mp4") as m_gcs, \
         patch("app.main.publish_to_youtube", return_value={"platform": "YT", "status": "Yayında", "url": "https://youtube.com/shorts/abc123"}) as m_yt, \
         patch("app.main.publish_to_instagram", return_value={"platform": "IG", "status": "Yayında", "url": "https://www.instagram.com/reel/xyz789/"}) as m_ig:

        res = client.post("/api/publish", headers=HDR, json={
            "video_id": "v1_limon_soyguncusu",
            "local_file_path": str(mp4),
            "title": "Limon Suyu Banka Soyguncusu",
            "description": "1995 gerçek hikâye",
            "account_ids": [yt["id"], ig["id"]],
        })
        assert res.status_code == 200
        assert res.json()["status"] == "Bekliyor"
        assert m_gcs.called and m_yt.called and m_ig.called

    # 3. Verify live per-platform status badges persisted to DB
    st = client.get("/api/publish/status?video_id=v1_limon_soyguncusu", headers=HDR).json()
    badges = {b["platform"]: b for b in st["by_video"]["v1_limon_soyguncusu"]}
    assert badges["YT"]["status"] == "Yayında"
    assert badges["YT"]["platform_post_url"] == "https://youtube.com/shorts/abc123"
    assert badges["IG"]["status"] == "Yayında"
    assert badges["IG"]["platform_post_url"] == "https://www.instagram.com/reel/xyz789/"

    # 4. Verify error badge persistence if one platform fails
    with patch("app.main.upload_to_gcs_and_get_signed_url", return_value="https://storage.googleapis.com/signed/demo.mp4"), \
         patch("app.main.publish_to_instagram", side_effect=RuntimeError("IG token expired")):
        res2 = client.post("/api/publish", headers=HDR, json={
            "video_id": "v2_ev_satan_nine",
            "local_file_path": str(mp4),
            "title": "Evini Satan Nine",
            "description": "Jeanne Calment",
            "account_ids": [ig["id"]],
        })
        assert res2.status_code == 200
    st2 = client.get("/api/publish/status?video_id=v2_ev_satan_nine", headers=HDR).json()
    ig_b = st2["by_video"]["v2_ev_satan_nine"][0]
    assert ig_b["status"] == "Hata"
    assert "IG token expired" in ig_b["error_message"]

    # 5. Delete account works
    assert client.delete(f"/api/accounts/{yt['id']}", headers=HDR).status_code == 200


def test_covers_endpoints():
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"

    # Missing API key check
    assert client.post("/api/covers/generate", json={"key": "test_k", "prompt": "test"}).status_code == 401

    with patch("app.services.covers.generate_cover_image", return_value=fake_png) as m_gen, \
         patch("app.services.covers.save_cover", return_value="v1_test_cover"):
        r = client.post("/api/covers/generate", headers=HDR, json={
            "key": "v1_test_cover",
            "prompt": "Test cover cartoon prompt",
            "aspect_ratio": "9:16",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["key"] == "v1_test_cover"
        assert "/api/covers/v1_test_cover.png" in data["image_url"]

    # Public stream test
    with patch("app.services.covers.get_cover", return_value=fake_png):
        r_img = client.get("/api/covers/v1_test_cover.png")
        assert r_img.status_code == 200
        assert r_img.headers["content-type"] == "image/png"
        assert r_img.content == fake_png

    # List covers test
    with patch("app.services.covers.list_covers", return_value=["v1_test_cover", "brand_logo"]):
        r_list = client.get("/api/covers", headers=HDR)
        assert r_list.status_code == 200
        assert "v1_test_cover" in r_list.json()["covers"]
        assert "brand_logo" in r_list.json()["covers"]


def test_weekly_slots_and_scheduler():
    from datetime import date
    from app.services.scheduler import weekly_slot_for_date

    # Monday -> 06:01, Tuesday -> 06:02 ... Sunday -> 06:07, next Monday -> 06:01
    mon = date(2026, 11, 23)  # Monday
    assert weekly_slot_for_date(mon).strftime("%H:%M") == "06:01"
    assert weekly_slot_for_date(date(2026, 11, 24)).strftime("%H:%M") == "06:02"
    assert weekly_slot_for_date(date(2026, 11, 29)).strftime("%H:%M") == "06:07"
    assert weekly_slot_for_date(date(2026, 11, 30)).strftime("%H:%M") == "06:01"

    # Bulk daily schedule 2 videos
    r_bulk = client.post("/api/schedule/bulk-daily", headers=HDR, json={
        "items": [
            {"video_id": "v1_demo", "video_url": "https://example.com/v1.mp4", "title": "Video 1"},
            {"video_id": "v2_demo", "video_url": "https://example.com/v2.mp4", "title": "Video 2"},
        ]
    })
    assert r_bulk.status_code == 200
    assert r_bulk.json()["created_count"] == 2
    p1, p2 = r_bulk.json()["created"]
    assert p1["scheduled_at"] != p2["scheduled_at"]

    # List schedule
    r_get = client.get("/api/schedule", headers=HDR)
    assert r_get.status_code == 200
    assert len(r_get.json()["posts"]) >= 2

    # Schedule past due item and trigger tick
    r_due = client.post("/api/schedule", headers=HDR, json={
        "video_id": "v_due",
        "video_url": "https://example.com/due.mp4",
        "title": "Due Video",
        "scheduled_at": "2020-01-01T00:00:00+00:00",
    })
    assert r_due.status_code == 200
    due_id = r_due.json()["post"]["id"]

    with patch("app.main._execute_scheduled_post") as m_exec:
        r_tick = client.post("/api/scheduler/tick", headers=HDR)
        assert r_tick.status_code == 200
        assert due_id in r_tick.json()["triggered_ids"]
        assert m_exec.called

    # Delete scheduled item
    assert client.delete(f"/api/schedule/{p1['id']}", headers=HDR).status_code == 200


