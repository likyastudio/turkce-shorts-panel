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
    past = {"video_id": "v_due", "video_url": "https://example.com/due.mp4", "title": "Due Video",
            "scheduled_at": "2020-01-01T00:00:00+00:00"}
    assert client.post("/api/schedule", headers=HDR, json=past).status_code == 400
    due_id = db.create_scheduled_post("v_due", past["video_url"], "Due Video", "", past["scheduled_at"])["id"]

    with patch("app.main._execute_scheduled_post") as m_exec:
        r_tick = client.post("/api/scheduler/tick", headers=HDR)
        assert r_tick.status_code == 200
        assert due_id in r_tick.json()["triggered_ids"]
        assert m_exec.called

    # Delete scheduled item
    assert client.delete(f"/api/schedule/{p1['id']}", headers=HDR).status_code == 200


def _future(days=5):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _post(vid, brand="foodballstv", at=None, ids=None):
    return db.create_scheduled_post(vid, "https://example.com/x.mp4", "T", "D", at or _future(), brand=brand, account_ids=ids)


def test_publish_requires_channels():
    r = client.post("/api/publish", headers=HDR, json={"video_id": "x", "video_url": "https://example.com/x.mp4", "title": "t", "description": ""})
    assert r.status_code == 400


def test_missing_server_key_fails_closed():
    with patch.dict(os.environ, {"API_SECRET_KEY": ""}):
        assert client.get("/api/accounts").status_code == 503


def test_oauth_needs_key_and_signed_state():
    assert client.get("/api/oauth/youtube/start", follow_redirects=False).status_code == 405
    assert client.post("/api/oauth/youtube/start", json={}).status_code == 401
    with patch.dict(os.environ, {"YT_CLIENT_ID": "cid"}):
        bad = client.post("/api/oauth/youtube/start", headers=HDR, json={"redirect_to": "https://evil.example/"})
        assert bad.status_code == 400
        ok = client.post("/api/oauth/youtube/start", headers=HDR, json={"redirect_to": "https://studio.likyastudios.live/", "brand": "foodballstv"})
    from urllib.parse import parse_qs, urlparse
    from app.security import read_state
    state = parse_qs(urlparse(ok.json()["url"]).query)["state"][0]
    assert read_state(state, "YT")["b"] == "foodballstv"
    for s in ("", "https://evil.example/", state[:-1] + ("0" if state[-1] != "0" else "1")):
        assert client.get("/api/oauth/youtube/callback", params={"code": "c", "state": s}, follow_redirects=False).status_code == 400
    c = client.get("/api/oauth/youtube/callback", params={"error": "access_denied", "state": state}, follow_redirects=False)
    assert c.headers["location"].startswith("https://studio.likyastudios.live/#settings?cancelled")


def test_claims_are_exclusive_and_stale_recovers():
    p = _post("claim1", at="2020-01-01T00:00:00+00:00")
    assert db.claim_scheduled_post(p["id"]) is True
    assert db.claim_scheduled_post(p["id"]) is False
    with db.get_conn() as (c, _p, _g):
        c.execute("UPDATE scheduled_posts SET updated_at='2020-01-01' WHERE id=?", (p["id"],))
    assert db.fail_stale_publishing() >= 1
    assert db.get_scheduled_post(p["id"])["status"] == "Hata"
    q = _post("claim2")
    assert db.claim_yt_sync(q["id"]) is True
    assert db.claim_yt_sync(q["id"]) is False
    assert db.claim_scheduled_post(q["id"]) is False  # yükleme sürerken yayınlanmaz


def test_partial_presync_not_uploaded_twice():
    import asyncio
    from app import main
    a = db.upsert_account("YT", "A", "UCA", "t", brand="pmarka")
    b = db.upsert_account("YT", "B", "UCB", "t", brand="pmarka")
    p = _post("partial", brand="pmarka")
    calls = []

    def fake(**kw):
        calls.append(kw)
        if len(calls) == 2:
            raise RuntimeError("kota")
        return {"status": "YT Planlandı", "url": f"https://youtube.com/shorts/{len(calls)}"}

    with patch("app.main.download_video_to_tmp", return_value="/tmp/none.mp4"), patch("app.main.covers_svc.list_covers", return_value=[]), \
         patch("app.main.YT_DAILY_PRESYNC_LIMIT", 999), patch("app.main.publish_to_youtube", side_effect=fake):
        asyncio.run(main._sync_scheduled_post_to_youtube(db.get_scheduled_post(p["id"])))
        row = db.get_scheduled_post(p["id"])
        assert not row["yt_uploaded"] and "kota" in row["error_message"]
        asyncio.run(main._sync_scheduled_post_to_youtube(row))
    assert len(calls) == 3  # 2 + yalnızca başarısız hesap
    assert db.get_scheduled_post(p["id"])["yt_uploaded"]
    assert {a["id"], b["id"]} == db.get_published_account_ids(p)


def test_edit_schedule_and_guards():
    body = {"brand": "foodballstv", "video_id": "edit1", "video_url": "https://example.com/e.mp4", "title": "Eski", "scheduled_at": _future(), "sync_youtube_now": False}
    pid = client.post("/api/schedule", headers=HDR, json=body).json()["post"]["id"]
    assert client.post("/api/schedule", headers=HDR, json=body).status_code == 409
    r = client.patch(f"/api/schedule/{pid}", headers=HDR, json={"title": "Yeni", "ig_caption": "ig", "scheduled_at": "2099-01-02T06:01:00"})
    assert r.status_code == 200 and r.json()["post"]["title"] == "Yeni"
    assert r.json()["post"]["scheduled_at"].startswith("2099-01-02T03:01")  # TR saati -> UTC
    assert client.patch(f"/api/schedule/{pid}", headers=HDR, json={"scheduled_at": "2020-01-01T00:00:00"}).status_code == 400
    db.mark_scheduled_yt_uploaded(pid, "https://youtube.com/shorts/z")
    assert client.patch(f"/api/schedule/{pid}", headers=HDR, json={"title": "Başka"}).status_code == 409
    assert client.patch(f"/api/schedule/{pid}", headers=HDR, json={"title": "Yeni", "ig_caption": "ig2"}).status_code == 200
    assert client.post(f"/api/schedule/{pid}/reschedule", headers=HDR).status_code in (400, 409)
    assert client.delete(f"/api/schedule/{pid}", headers=HDR).json()["yt_video_url"]
    done = _post("done1")
    db.update_scheduled_post(done["id"], "Yayında")
    assert client.post(f"/api/schedule/{done['id']}/run-now", headers=HDR).status_code == 409


def test_media_range(tmp_path):
    os.makedirs("/tmp/uploads/akilalmaz", exist_ok=True)
    with open("/tmp/uploads/akilalmaz/rng.mp4", "wb") as f:
        f.write(b"0123456789")
    u = "/api/media/akilalmaz/rng.mp4"
    assert client.get(u).content == b"0123456789"
    r = client.get(u, headers={"Range": "bytes=2-4"})
    assert r.status_code == 206 and r.content == b"234" and r.headers["content-range"] == "bytes 2-4/10"
    assert client.get(u, headers={"Range": "bytes=-3"}).content == b"789"
    assert client.get(u, headers={"Range": "bytes=50-"}).status_code == 416
    bad = client.post("/api/media/upload", headers=HDR, files={"file": ("a.mp4", b"not a video", "video/mp4")})
    assert bad.status_code == 400


def test_scheduler_oidc():
    env = {"SCHEDULER_SA_EMAIL": "s@x.iam", "PUBLIC_API_BASE": "https://api.example"}
    h = {"Authorization": "Bearer t"}
    v = "google.oauth2.id_token.verify_oauth2_token"
    run = lambda: client.post("/api/scheduler/tick", headers=h).status_code
    with patch("app.main.db.get_due_scheduled_posts", return_value=[]), patch("app.main.db.get_pending_yt_presync_posts", return_value=[]):
        assert run() == 401  # ayar yoksa kapalı
        with patch.dict(os.environ, env):
            assert run() == 401  # sahte token
            with patch(v, return_value={"email": "other@x", "email_verified": True}):
                assert run() == 401
            with patch(v, return_value={"email": "s@x.iam", "email_verified": True}) as m:
                assert run() == 200
                assert m.call_args.kwargs["audience"] == "https://api.example"
            assert client.get("/api/accounts", headers=h).status_code == 401  # yalnız tick


def test_google_login():
    import hashlib
    from urllib.parse import parse_qs, urlparse
    from app import security
    ver = "v" * 43
    ch = hashlib.sha256(ver.encode()).hexdigest()
    body = {"redirect_to": "https://studio.likyastudios.live/", "challenge": ch}
    assert client.post("/api/auth/google/start", json=body).status_code == 503
    with patch.dict(os.environ, {"YT_CLIENT_ID": "cid", "ALLOWED_LOGIN_EMAILS": "Ben@Example.com/iki@example.com"}):
        assert client.post("/api/auth/google/start", json={**body, "redirect_to": "https://evil.example/"}).status_code == 400
        url = client.post("/api/auth/google/start", json=body).json()["url"]
        q = parse_qs(urlparse(url).query)
        assert q["scope"] == ["openid email"]
        state = q["state"][0]

        def back(info, code="c"):
            with patch("app.oauth.requests.post") as rp, patch("google.oauth2.id_token.verify_oauth2_token", return_value=info) as vt:
                rp.return_value.json.return_value = {"id_token": "t"}
                r = client.get("/api/oauth/youtube/callback", params={"code": code, "state": state}, follow_redirects=False)
                assert vt.call_args.kwargs["audience"] == "cid"
            return r.headers["location"].split("#")[1]

        assert back({"email": "yabanci@example.com", "email_verified": True}) == "login_error=denied"
        assert back({"email": "ben@example.com", "email_verified": False}) == "login_error=denied"
        code = back({"email": "BEN@example.com", "email_verified": True}).split("login_code=")[1]
        ex = lambda c, v: client.post("/api/auth/google/exchange", json={"code": c, "verifier": v})
        assert ex(code, "x" * 43).status_code == 401  # başka tarayıcı kullanamaz
        res = ex(code, ver)
        assert res.status_code == 200 and res.json()["email"] == "ben@example.com"
        tok = res.json()["session"]
        get = lambda t: client.get("/api/accounts", headers={"X-Session": t}).status_code
        assert get(tok) == 200
        assert client.post("/api/scheduler/tick", headers={"X-Session": tok}).status_code == 200
        for bad in (code, state, tok[:-1] + ("0" if tok[-1] != "0" else "1"), "x", security.make_token("session", {"m": "yabanci@example.com"}, 60), security.make_token("session", {"m": "ben@example.com"}, -1)):
            assert get(bad) == 401
        assert ex(tok, ver).status_code == 401
        assert ex(security.make_token("login-code", {"m": "ben@example.com", "c": ch}, -1), ver).status_code == 401
        assert client.get("/api/oauth/youtube/callback", params={"error": "access_denied", "state": state}, follow_redirects=False).headers["location"].endswith("#login_error=cancelled")
        assert client.get("/api/oauth/instagram/callback", params={"code": "c", "state": state}, follow_redirects=False).status_code == 400
        assert client.get("/api/accounts", headers=HDR).status_code == 200  # otomasyon anahtarı çalışır
    with patch.dict(os.environ, {"ALLOWED_LOGIN_EMAILS": "iki@example.com"}):
        assert get(tok) == 401  # listeden çıkan hesap hemen kapanır


def _jpeg(w=768, h=1344, color=(120, 80, 40)):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


def test_cover_headline_overlay_retext_and_upload(tmp_path):
    import io
    from PIL import Image
    from app.services import cover_compose

    saved = {}
    bgs = {}

    def fake_save(key, data):
        saved[key] = data
        return key

    with patch("app.services.covers.generate_cover_image", return_value=_jpeg()) as m_gen, \
         patch("app.services.covers.save_cover", side_effect=fake_save), \
         patch("app.services.covers.save_background", side_effect=lambda k, d: bgs.__setitem__(k, d)):
        r = client.post("/api/covers/generate", headers=HDR, json={
            "key": "caldiran_test",
            "prompt": "Ottoman cannons at Chaldiran",
            "headline_top": "Yavuz Şah İsmail'i",
            "headline_bottom": "nasıl yakaladı?",
            "brand": "kadimanadolu",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["overlay"] is True
        # Model yazı yazmasın diye koruma prompta eklendi
        assert cover_compose.BACKGROUND_GUARD in m_gen.call_args.kwargs["prompt"]
        im = Image.open(io.BytesIO(saved["caldiran_test"]))
        assert im.size == (1080, 1920)
        assert "caldiran_test" in bgs

    # Başlık yoksa eski davranış: ham görsel, koruma eklenmez
    with patch("app.services.covers.generate_cover_image", return_value=_jpeg()) as m_gen, \
         patch("app.services.covers.save_cover", side_effect=fake_save):
        r = client.post("/api/covers/generate", headers=HDR, json={"key": "raw_k", "prompt": "p"})
        assert r.status_code == 200 and r.json()["overlay"] is False
        assert cover_compose.BACKGROUND_GUARD not in m_gen.call_args.kwargs["prompt"]

    # Yazıyı Vertex'e gitmeden değiştir
    with patch("app.services.covers.get_background", return_value=bgs["caldiran_test"]), \
         patch("app.services.covers.save_cover", side_effect=fake_save):
        r = client.post("/api/covers/caldiran_test/retext", headers=HDR,
                        json={"headline_top": "Şah İsmail", "headline_bottom": "tek günde"})
        assert r.status_code == 200, r.text
    with patch("app.services.covers.get_background", return_value=None):
        assert client.post("/api/covers/yok/retext", headers=HDR, json={"headline_top": "x"}).status_code == 404

    # Hazır kapak yükleme
    with patch("app.services.covers.save_cover", side_effect=fake_save):
        r = client.post("/api/covers/upload", headers=HDR, data={"key": "elle_k"},
                        files={"file": ("k.jpg", _jpeg(1080, 1920), "image/jpeg")})
        assert r.status_code == 200, r.text
        assert saved["elle_k"][:4] == b"\x89PNG"
    assert client.post("/api/covers/upload", data={"key": "x"},
                       files={"file": ("k.jpg", b"x", "image/jpeg")}).status_code == 401


def test_cover_applies_youtube_thumbnail_for_uploaded_post():
    post = {"video_id": "yt_cov_vid", "brand": "kadimanadolu", "yt_uploaded": True,
            "yt_video_url": "https://youtube.com/shorts/ABC123", "account_ids": []}
    acc = {"id": 99, "platform": "YT", "brand": "kadimanadolu", "access_token": "t"}
    with patch("app.services.covers.generate_cover_image", return_value=_jpeg()), \
         patch("app.services.covers.save_cover", side_effect=lambda k, d: k), \
         patch("app.services.covers.save_background"), \
         patch("app.db.list_scheduled_posts", return_value=[post]), \
         patch("app.db.list_accounts", return_value=[acc]), \
         patch("app.main.apply_youtube_thumbnail", return_value={"ok": True}) as m_yt:
        r = client.post("/api/covers/generate", headers=HDR, json={
            "key": "yt_cov_vid", "prompt": "battle", "headline_top": "A", "headline_bottom": "B"})
        assert r.status_code == 200, r.text
        assert r.json()["youtube"] == [{"video_id": "yt_cov_vid", "yt_id": "ABC123", "ok": True, "error": None}]
        kw = m_yt.call_args.kwargs
        assert kw["yt_video_id"] == "ABC123" and kw["image_bytes"]


def test_cover_retries_softened_prompt_when_vertex_returns_nothing():
    from app.services import covers as covers_svc
    calls = []

    def fake_gen(prompt, aspect_ratio, reference_image=None):
        calls.append(prompt)
        if len(calls) == 1:
            raise covers_svc.EmptyImageError("blocked")
        return _jpeg()

    with patch("app.services.covers.generate_cover_image", side_effect=fake_gen), \
         patch("app.services.covers.save_cover", side_effect=lambda k, d: k), \
         patch("app.services.covers.save_background"):
        r = client.post("/api/covers/generate", headers=HDR, json={
            "key": "retry_k", "prompt": "battle", "headline_bottom": "X"})
        assert r.status_code == 200, r.text
    assert len(calls) == 2 and covers_svc.SOFTEN_SUFFIX in calls[1]


def test_compose_trims_letterbox_bars():
    import io
    from PIL import Image, ImageDraw
    from app.services.cover_compose import compose_cover
    im = Image.new("RGB", (768, 1344), (200, 150, 90))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 767, 99], fill=(0, 0, 0))
    d.rectangle([0, 1244, 767, 1343], fill=(0, 0, 0))
    buf = io.BytesIO(); im.save(buf, format="PNG")
    out = Image.open(io.BytesIO(compose_cover(buf.getvalue(), "", "", "kadimanadolu")))
    assert out.size == (1080, 1920)
    # Alt kenarda siyah bant kalmamalı (vinyet koyulaştırır ama simsiyah yapmaz)
    assert max(out.crop((300, 1915, 780, 1920)).convert("L").getextrema()) > 28
