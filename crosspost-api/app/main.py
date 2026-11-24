"""Likya Studios Cross-Posting API (Google Cloud Run / FastAPI).
Supports:
- Multi-channel DB-backed publishing (via account_ids from social_accounts table)
- Direct token publishing (compatible with starter Next.js API proxy)
- Both video_url (stateless Cloud Run download) and local_file_path
- Live per-platform status badges: Bekliyor | Yükleniyor | Yayında | Hata
"""
from __future__ import annotations
import asyncio
import os
import re
import time
from typing import Optional
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import db
from app.oauth import router as oauth_router
from app.services import covers as covers_svc
from app.services import scheduler as sched_svc
from app.services.instagram import publish_to_instagram
from app.services.storage import download_video_to_tmp, upload_to_gcs_and_get_signed_url
from app.services.youtube import apply_youtube_thumbnail, fetch_youtube_analytics, publish_to_youtube

app = FastAPI(title="Likya Studios Cross-Posting API", version="1.0.0")

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(oauth_router)


@app.on_event("startup")
def _startup():
    db.init_db()


def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    expected = os.getenv("API_SECRET_KEY", "").strip()
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Geçersiz X-API-Key.")


class ManualAccountIn(BaseModel):
    platform: str = Field(pattern="^(YT|IG)$")
    account_name: str
    external_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None


class PublishRequest(BaseModel):
    video_id: str
    title: str
    description: str
    ig_caption: Optional[str] = None
    local_file_path: Optional[str] = None
    video_url: Optional[str] = None
    thumb_offset_ms: Optional[int] = None
    cover_url: Optional[str] = None
    category_id: str = "24"
    privacy_status: str = "public"
    # Preferred: DB account IDs from social_accounts
    account_ids: Optional[list[int]] = None
    # Backward-compatible direct tokens (when called from Next.js proxy without DB account_ids)
    yt_access_token: Optional[str] = None
    yt_refresh_token: Optional[str] = None
    yt_client_id: Optional[str] = None
    yt_client_secret: Optional[str] = None
    ig_user_id: Optional[str] = None
    ig_access_token: Optional[str] = None


async def _run_single_target(
    log_id: int,
    platform: str,
    local_path: str,
    signed_url: Optional[str],
    req: PublishRequest,
    acc: dict,
):
    db.update_publish_log(log_id, "Yükleniyor")
    try:
        if platform == "YT":
            cid = acc.get("client_id") or os.getenv("YT_CLIENT_ID", "")
            csec = acc.get("client_secret") or os.getenv("YT_CLIENT_SECRET", "")
            acc_id = acc.get("id")
            on_refresh = (lambda tok, exp: db.update_account_token(acc_id, tok, exp)) if acc_id else None
            res = await asyncio.to_thread(
                publish_to_youtube,
                local_file_path=local_path,
                title=req.title,
                description=req.description,
                access_token=acc["access_token"],
                refresh_token=acc.get("refresh_token"),
                client_id=cid,
                client_secret=csec,
                category_id=req.category_id,
                privacy_status=req.privacy_status,
                cover_url=req.cover_url,
                on_token_refresh=on_refresh,
            )
            db.update_publish_log(log_id, "Yayında", platform_post_url=res.get("url"))
        elif platform == "IG":
            if not signed_url:
                raise RuntimeError("Instagram paylaşımı için geçerli video URL'si üretilemedi.")
            caption = req.ig_caption or f"{req.title}\n\n{req.description}"
            res = await asyncio.to_thread(
                publish_to_instagram,
                video_url=signed_url,
                caption=caption,
                ig_user_id=acc["external_id"],
                ig_access_token=acc["access_token"],
                thumb_offset_ms=req.thumb_offset_ms,
                cover_url=req.cover_url,
            )
            db.update_publish_log(log_id, "Yayında", platform_post_url=res.get("url"))
        else:
            raise RuntimeError(f"Desteklenmeyen platform: {platform}")
    except Exception as e:
        db.update_publish_log(log_id, "Hata", error_message=str(e)[:800])


async def process_cross_post(req: PublishRequest, targets: list[tuple[int, dict]]):
    """Background coordinator: prepares local MP4 + GCS Signed URL (if IG targeted), then publishes concurrently."""
    temp_downloaded = None
    try:
        local_path = req.local_file_path
        if not local_path or not os.path.exists(local_path):
            if not req.video_url:
                raise RuntimeError("Video dosyası (local_file_path veya video_url) sağlanmadı.")
            temp_downloaded = await asyncio.to_thread(download_video_to_tmp, req.video_url, req.video_id)
            local_path = temp_downloaded

        needs_ig = any(acc["platform"] == "IG" for _, acc in targets)
        signed_url = None
        if needs_ig:
            use_gcs = os.getenv("USE_GCS_SIGNED_URL", "true").lower() in ("1", "true", "yes")
            if use_gcs and os.getenv("GCS_BUCKET_NAME"):
                blob_name = f"temp-exports/{req.video_id}.mp4"
                signed_url = await asyncio.to_thread(upload_to_gcs_and_get_signed_url, local_path, blob_name)
            elif req.video_url:
                signed_url = req.video_url
            else:
                blob_name = f"temp-exports/{req.video_id}.mp4"
                signed_url = await asyncio.to_thread(upload_to_gcs_and_get_signed_url, local_path, blob_name)

        tasks = [
            _run_single_target(log_id, acc["platform"], local_path, signed_url, req, acc)
            for log_id, acc in targets
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        for log_id, _acc in targets:
            db.update_publish_log(log_id, "Hata", error_message=str(e)[:800])
    finally:
        if temp_downloaded and os.path.exists(temp_downloaded):
            try:
                os.remove(temp_downloaded)
            except OSError:
                pass


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "db": "postgres" if db._is_pg() else "sqlite",
        "gcs_bucket": os.getenv("GCS_BUCKET_NAME", "likya-temp-videos"),
        "oauth_youtube_ready": bool(os.getenv("YT_CLIENT_ID")),
        "oauth_instagram_ready": bool(os.getenv("META_APP_ID")),
    }


@app.get("/api/accounts", dependencies=[Depends(verify_api_key)])
def get_accounts():
    return {"accounts": db.list_accounts(include_tokens=False)}


@app.post("/api/accounts", dependencies=[Depends(verify_api_key)])
def add_account_manual(body: ManualAccountIn):
    acc = db.upsert_account(
        platform=body.platform,
        account_name=body.account_name,
        external_id=body.external_id,
        access_token=body.access_token,
        refresh_token=body.refresh_token,
        expires_at=body.expires_at,
    )
    return {"account": acc}


@app.delete("/api/accounts/{account_id}", dependencies=[Depends(verify_api_key)])
def remove_account(account_id: int):
    if not db.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Hesap bulunamadı.")
    return {"deleted": account_id}


class AccountBrandIn(BaseModel):
    brand: str


@app.patch("/api/accounts/{account_id}/brand", dependencies=[Depends(verify_api_key)])
def update_account_brand(account_id: int, body: AccountBrandIn):
    brand = re.sub(r"[^a-z0-9_\-]", "", body.brand.strip().lower()) or "akilalmaz"
    if not db.set_account_brand(account_id, brand):
        raise HTTPException(status_code=404, detail="Hesap bulunamadı.")
    return {"ok": True, "id": account_id, "brand": brand}


@app.post("/api/publish", dependencies=[Depends(verify_api_key)])
async def trigger_publish(req: PublishRequest, background_tasks: BackgroundTasks):
    if not req.video_url and (not req.local_file_path or not os.path.exists(req.local_file_path)):
        raise HTTPException(status_code=404, detail="Video dosyası bulunamadı (local_file_path veya video_url gerekli).")

    accounts: list[dict] = []
    if req.account_ids:
        accounts = db.get_accounts_by_ids(req.account_ids)
    else:
        # Backward-compatible direct tokens OR all connected DB accounts
        if req.yt_access_token:
            accounts.append({
                "id": None, "platform": "YT", "account_name": "YouTube", "external_id": "direct",
                "access_token": req.yt_access_token, "refresh_token": req.yt_refresh_token,
                "client_id": req.yt_client_id, "client_secret": req.yt_client_secret,
            })
        if req.ig_user_id and req.ig_access_token:
            accounts.append({
                "id": None, "platform": "IG", "account_name": "Instagram", "external_id": req.ig_user_id,
                "access_token": req.ig_access_token,
            })
        if not accounts:
            accounts = db.list_accounts(include_tokens=True)

    if not accounts:
        raise HTTPException(status_code=400, detail="Bağlı hedef kanal bulunamadı. Ayarlar'dan YouTube veya Instagram bağlayın.")

    targets: list[tuple[int, dict]] = []
    for acc in accounts:
        log_id = db.create_publish_log(
            video_id=req.video_id,
            platform=acc["platform"],
            account_id=acc.get("id"),
            account_name=acc.get("account_name"),
            status="Bekliyor",
        )
        targets.append((log_id, acc))

    background_tasks.add_task(process_cross_post, req, targets)
    return {
        "message": "Paylaşım kuyruğa alındı",
        "video_id": req.video_id,
        "status": "Bekliyor",
        "logs": [{"id": lid, "platform": a["platform"], "account_name": a.get("account_name"), "status": "Bekliyor"} for lid, a in targets],
    }


@app.get("/api/publish/status", dependencies=[Depends(verify_api_key)])
def get_publish_status(video_id: Optional[str] = None):
    logs = db.list_publish_logs(video_id=video_id)
    # Latest status per (video_id, platform, account_name) for clean badge rendering
    latest: dict[str, list[dict]] = {}
    seen = set()
    for row in logs:
        key = (row["video_id"], row["platform"], row.get("account_id") or row.get("account_name"))
        if key in seen:
            continue
        seen.add(key)
        latest.setdefault(row["video_id"], []).append(row)
    return {"by_video": latest, "logs": logs}


class GenerateCoverRequest(BaseModel):
    key: str
    prompt: str
    aspect_ratio: str = "9:16"  # "9:16", "1:1", "16:9"


@app.post("/api/covers/generate", dependencies=[Depends(verify_api_key)])
async def generate_cover_endpoint(req: GenerateCoverRequest):
    """Generates an image via Vertex AI and saves it to GCS covers/{key}.png."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt gereklidir.")
    valid_ratios = {"9:16", "1:1", "16:9", "4:3", "3:4"}
    if req.aspect_ratio not in valid_ratios:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen en-boy oranı: {req.aspect_ratio}")

    try:
        png_bytes = await asyncio.to_thread(
            covers_svc.generate_cover_image,
            prompt=req.prompt.strip(),
            aspect_ratio=req.aspect_ratio,
        )
        safe_key = covers_svc.save_cover(req.key, png_bytes)
        public_base = os.getenv("PUBLIC_API_BASE", "").rstrip("/")
        ts = int(time.time())
        clean_url = f"{public_base}/api/covers/{safe_key}.png" if public_base else f"/api/covers/{safe_key}.png"
        img_url = f"{clean_url}?v={ts}"
        try:
            db.update_scheduled_cover_url(safe_key, clean_url)
        except Exception:
            pass
        return {
            "ok": True,
            "key": safe_key,
            "aspect_ratio": req.aspect_ratio,
            "image_url": img_url,
            "size_bytes": len(png_bytes),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kapak üretimi başarısız: {e}")


@app.get("/api/covers", dependencies=[Depends(verify_api_key)])
def list_covers_endpoint():
    """Returns map of available covers {key: url}."""
    keys = covers_svc.list_covers()
    public_base = os.getenv("PUBLIC_API_BASE", "").rstrip("/")
    covers_map = {}
    for k in keys:
        covers_map[k] = f"{public_base}/api/covers/{k}.png" if public_base else f"/api/covers/{k}.png"
    return {"ok": True, "covers": covers_map}


@app.get("/api/covers/{key}.png")
def get_cover_image_endpoint(key: str):
    """Public PNG stream for browsers, downloads, and social media platforms."""
    png_bytes = covers_svc.get_cover(key)
    if not png_bytes:
        raise HTTPException(status_code=404, detail="Kapak görseli bulunamadı.")
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


YT_DAILY_PRESYNC_LIMIT = int(os.getenv("YT_DAILY_PRESYNC_LIMIT", "5"))


class SchedulePostRequest(BaseModel):
    brand: str = "akilalmaz"
    video_id: str
    video_url: str
    title: str
    description: str = ""
    ig_caption: Optional[str] = None
    cover_url: Optional[str] = None
    thumb_offset_ms: int = 1500
    account_ids: Optional[list[int]] = None
    scheduled_at: Optional[str] = None  # ISO 8601 (UTC or +03:00); if omitted, auto_next_slot is used
    auto_next_slot: bool = False
    sync_youtube_now: bool = True


class BulkDailyItem(BaseModel):
    video_id: str
    video_url: str
    title: str
    description: str = ""
    ig_caption: Optional[str] = None
    cover_url: Optional[str] = None
    thumb_offset_ms: int = 1500


class BulkDailyRequest(BaseModel):
    brand: str = "akilalmaz"
    items: list[BulkDailyItem]
    account_ids: Optional[list[int]] = None
    sync_youtube_now: bool = True


class GenerateStoryRequest(BaseModel):
    existing_titles: list[str] = []
    topic_hint: str = ""


def _enrich_sched(row: dict) -> dict:
    row["label_tr"] = sched_svc.format_tr_label(row["scheduled_at"])
    return row


async def _sync_scheduled_post_to_youtube(post: dict):
    """Pre-uploads a scheduled Short to YouTube Studio with native publishAt (status='private' + publishAt)
    so it appears immediately as 'Planlandı' inside YouTube Studio. Respects daily YT API quota."""
    post_id = post["id"]
    if post.get("yt_uploaded"):
        return

    acc_ids = post.get("account_ids") or []
    post_brand = post.get("brand") or "akilalmaz"
    all_accs = db.get_accounts_by_ids(acc_ids) if acc_ids else db.list_accounts(include_tokens=True, brand=post_brand)
    yt_accs = [a for a in all_accs if a.get("platform") == "YT"]
    if not yt_accs:
        return  # No YouTube account connected for this brand yet

    if db.count_yt_uploads_today() >= YT_DAILY_PRESYNC_LIMIT:
        return  # Safely wait until next day's quota window; scheduler/tick will pick it up

    local_path = None
    try:
        local_path = await asyncio.to_thread(download_video_to_tmp, post["video_url"], f"ytsched_{post['video_id']}")
        last_url = None
        for acc in yt_accs:
            log_id = db.create_publish_log(
                video_id=post["video_id"],
                platform="YT",
                account_id=acc.get("id"),
                account_name=acc.get("account_name"),
                status="Yükleniyor",
            )
            try:
                cid = acc.get("client_id") or os.getenv("YT_CLIENT_ID", "")
                csec = acc.get("client_secret") or os.getenv("YT_CLIENT_SECRET", "")
                acc_id = acc.get("id")
                on_refresh = (lambda tok, exp, aid=acc_id: db.update_account_token(aid, tok, exp)) if acc_id else None
                cov_url = post.get("cover_url")
                if not cov_url and post["video_id"] in covers_svc.list_covers():
                    pbase = os.getenv("PUBLIC_API_BASE", "").rstrip("/")
                    cov_url = f"{pbase}/api/covers/{post['video_id']}.png" if pbase else None
                res = await asyncio.to_thread(
                    publish_to_youtube,
                    local_file_path=local_path,
                    title=post["title"],
                    description=post["description"],
                    access_token=acc["access_token"],
                    refresh_token=acc.get("refresh_token"),
                    client_id=cid,
                    client_secret=csec,
                    publish_at=post["scheduled_at"],
                    cover_url=cov_url,
                    on_token_refresh=on_refresh,
                )
                last_url = res.get("url")
                db.update_publish_log(log_id, res.get("status", "YT Planlandı"), platform_post_url=last_url)
            except Exception as e:
                db.update_publish_log(log_id, "Hata", error_message=str(e)[:500])
                raise
        if last_url:
            db.mark_scheduled_yt_uploaded(post_id, last_url)
    except Exception as e:
        db.update_scheduled_post(post_id, "Planlandı", f"YT ön-planlama uyarısı: {e}"[:400])
    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass


async def _execute_scheduled_post(post: dict):
    """Runs a due scheduled post through the cross-post pipeline.
    If already natively scheduled on YouTube (yt_uploaded=True), skips YT to avoid duplicates
    and only publishes to Instagram (if connected for this brand)."""
    post_id = post["id"]
    db.update_scheduled_post(post_id, "Yayınlanıyor")
    try:
        acc_ids = post.get("account_ids") or []
        post_brand = post.get("brand") or "akilalmaz"
        accounts = db.get_accounts_by_ids(acc_ids) if acc_ids else db.list_accounts(include_tokens=True, brand=post_brand)

        if post.get("yt_uploaded"):
            # YouTube already handles exact publishAt natively; only run IG targets if any
            accounts = [a for a in accounts if a.get("platform") != "YT"]
            if not accounts:
                db.update_scheduled_post(post_id, "Yayında", None)
                return

        if not accounts:
            db.update_scheduled_post(post_id, "Hata", "Bağlı YouTube veya Instagram kanalı bulunamadı.")
            return

        req = PublishRequest(
            video_id=post["video_id"],
            video_url=post["video_url"],
            title=post["title"],
            description=post["description"],
            ig_caption=post.get("ig_caption"),
            cover_url=post.get("cover_url"),
            thumb_offset_ms=post.get("thumb_offset_ms") or 1500,
            account_ids=[a["id"] for a in accounts if a.get("id")],
        )
        targets: list[tuple[int, dict]] = []
        for acc in accounts:
            log_id = db.create_publish_log(
                video_id=req.video_id,
                platform=acc["platform"],
                account_id=acc.get("id"),
                account_name=acc.get("account_name"),
                status="Bekliyor",
            )
            targets.append((log_id, acc))

        await process_cross_post(req, targets)

        logs = db.list_publish_logs(video_id=req.video_id)[: len(targets)]
        errs = [l["error_message"] for l in logs if l.get("status") == "Hata" and l.get("error_message")]
        if errs and len(errs) == len(targets):
            db.update_scheduled_post(post_id, "Hata", " | ".join(errs)[:400])
        else:
            db.update_scheduled_post(post_id, "Yayında", ("Kısmi hata: " + " | ".join(errs))[:400] if errs else None)
    except Exception as e:
        db.update_scheduled_post(post_id, "Hata", str(e)[:400])


BRANDS = ("akilalmaz", "kadimanadolu", "likyastudios", "foodballstv")


@app.get("/api/schedule", dependencies=[Depends(verify_api_key)])
def get_schedule(brand: Optional[str] = None):
    all_posts = [_enrich_sched(r) for r in db.list_scheduled_posts()]
    posts = [p for p in all_posts if p.get("brand") == brand] if brand else all_posts

    next_by_brand = {}
    for b in BRANDS:
        occ = [p["scheduled_at"] for p in all_posts if p.get("brand") == b and p["status"] in ("Planlandı", "Yayınlanıyor")]
        next_by_brand[b] = sched_svc.next_weekly_slot(occupied_iso_list=occ)

    active_brand = brand or "akilalmaz"
    nxt = next_by_brand.get(active_brand) or sched_svc.next_weekly_slot()
    used_today = db.count_yt_uploads_today()
    return {
        "ok": True,
        "posts": posts,
        "next_slot": nxt,
        "next_by_brand": next_by_brand,
        "yt_quota_today": {"used": used_today, "limit": YT_DAILY_PRESYNC_LIMIT},
        "rule": "Pzt 06:01 · Sal 06:02 · Çar 06:03 · Per 06:04 · Cum 06:05 · Cmt 06:06 · Paz 06:07 (TR, haftalık döngü)",
    }


@app.post("/api/schedule", dependencies=[Depends(verify_api_key)])
def create_schedule(req: SchedulePostRequest, background_tasks: BackgroundTasks):
    if not req.video_url:
        raise HTTPException(status_code=400, detail="video_url gereklidir.")

    brand = re.sub(r"[^a-z0-9_\-]", "", (req.brand or "akilalmaz").strip().lower()) or "akilalmaz"
    existing = db.list_scheduled_posts(brand=brand)
    occupied = [p["scheduled_at"] for p in existing if p["status"] in ("Planlandı", "Yayınlanıyor")]

    if req.auto_next_slot or not req.scheduled_at:
        slot = sched_svc.next_weekly_slot(occupied_iso_list=occupied)
        sched_iso = slot["scheduled_at_utc"]
    else:
        sched_iso = req.scheduled_at

    row = db.create_scheduled_post(
        brand=brand,
        video_id=req.video_id,
        video_url=req.video_url,
        title=req.title,
        description=req.description,
        scheduled_at_iso=sched_iso,
        ig_caption=req.ig_caption,
        cover_url=req.cover_url,
        thumb_offset_ms=req.thumb_offset_ms,
        account_ids=req.account_ids or [],
    )
    if req.sync_youtube_now:
        background_tasks.add_task(_sync_scheduled_post_to_youtube, row)
    return {"ok": True, "post": _enrich_sched(row), "yt_sync_queued": req.sync_youtube_now}


@app.post("/api/schedule/bulk-daily", dependencies=[Depends(verify_api_key)])
def bulk_schedule_daily(req: BulkDailyRequest, background_tasks: BackgroundTasks):
    brand = re.sub(r"[^a-z0-9_\-]", "", (req.brand or "akilalmaz").strip().lower()) or "akilalmaz"
    existing = db.list_scheduled_posts(brand=brand)
    already_videos = {p["video_id"] for p in existing if p["status"] in ("Planlandı", "Yayınlanıyor", "Yayında")}
    occupied = [p["scheduled_at"] for p in existing if p["status"] in ("Planlandı", "Yayınlanıyor")]

    created = []
    skipped = []
    remaining_yt_quota = max(0, YT_DAILY_PRESYNC_LIMIT - db.count_yt_uploads_today())
    yt_queued = 0

    for item in req.items:
        if item.video_id in already_videos:
            skipped.append(item.video_id)
            continue
        slot = sched_svc.next_weekly_slot(occupied_iso_list=occupied)
        occupied.append(slot["scheduled_at_utc"])
        row = db.create_scheduled_post(
            brand=brand,
            video_id=item.video_id,
            video_url=item.video_url,
            title=item.title,
            description=item.description,
            scheduled_at_iso=slot["scheduled_at_utc"],
            ig_caption=item.ig_caption,
            cover_url=item.cover_url,
            thumb_offset_ms=item.thumb_offset_ms,
            account_ids=req.account_ids or [],
        )
        created.append(_enrich_sched(row))
        already_videos.add(item.video_id)
        if req.sync_youtube_now and yt_queued < remaining_yt_quota:
            background_tasks.add_task(_sync_scheduled_post_to_youtube, row)
            yt_queued += 1

    return {
        "ok": True,
        "brand": brand,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "yt_sync_queued": yt_queued,
        "created": created,
    }


@app.post("/api/schedule/{post_id}/sync-youtube", dependencies=[Depends(verify_api_key)])
async def sync_schedule_to_youtube_now(post_id: int, background_tasks: BackgroundTasks):
    post = db.get_scheduled_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Planlanmış gönderi bulunamadı.")
    if post.get("yt_uploaded"):
        return {"ok": True, "already_uploaded": True, "yt_video_url": post.get("yt_video_url")}
    background_tasks.add_task(_sync_scheduled_post_to_youtube, post)
    return {"ok": True, "message": "YouTube Studio'ya 'Planlandı' olarak yükleme başlatıldı.", "id": post_id}


@app.delete("/api/schedule/{post_id}", dependencies=[Depends(verify_api_key)])
def remove_schedule(post_id: int):
    if not db.delete_scheduled_post(post_id):
        raise HTTPException(status_code=404, detail="Planlanmış gönderi bulunamadı.")
    return {"ok": True, "deleted": post_id}


@app.post("/api/schedule/{post_id}/run-now", dependencies=[Depends(verify_api_key)])
async def run_schedule_now(post_id: int, background_tasks: BackgroundTasks):
    post = db.get_scheduled_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Planlanmış gönderi bulunamadı.")
    background_tasks.add_task(_execute_scheduled_post, post)
    return {"ok": True, "message": "Hemen yayınlanmak üzere başlatıldı.", "id": post_id}


@app.post("/api/scheduler/tick", dependencies=[Depends(verify_api_key)])
async def scheduler_tick(background_tasks: BackgroundTasks):
    """1. Triggers due scheduled posts (skipping YT if already natively scheduled).
    2. Pre-uploads upcoming un-synced scheduled posts to YouTube Studio (within safe daily quota)."""
    due = db.get_due_scheduled_posts()
    for post in due:
        background_tasks.add_task(_execute_scheduled_post, post)

    # Auto pre-sync upcoming posts to YouTube Studio within daily quota
    remaining_quota = max(0, YT_DAILY_PRESYNC_LIMIT - db.count_yt_uploads_today())
    presync_ids = []
    if remaining_quota > 0:
        pending = db.get_pending_yt_presync_posts(limit=remaining_quota)
        for post in pending:
            background_tasks.add_task(_sync_scheduled_post_to_youtube, post)
            presync_ids.append(post["id"])

    return {
        "ok": True,
        "due_count": len(due),
        "triggered_ids": [p["id"] for p in due],
        "yt_presync_ids": presync_ids,
    }


@app.post("/api/ai/generate-story", dependencies=[Depends(verify_api_key)])
async def ai_generate_story(req: GenerateStoryRequest):
    """Generates a fresh Turkish absurd-history Short script & metadata via Vertex AI Gemini."""
    try:
        story = await asyncio.to_thread(
            sched_svc.generate_daily_story,
            existing_titles=req.existing_titles,
            topic_hint=req.topic_hint,
        )
        return {"ok": True, "story": story}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Senaryo üretimi başarısız: {e}")


@app.post("/api/schedule/sync-covers", dependencies=[Depends(verify_api_key)])
async def sync_covers_to_schedule():
    """Links all existing GCS covers to scheduled_posts and applies thumbnails.set to already-uploaded YT videos."""
    available = set(covers_svc.list_covers())
    public_base = os.getenv("PUBLIC_API_BASE", "").rstrip("/")
    posts = db.list_scheduled_posts()
    yt_accs = [a for a in db.list_accounts(include_tokens=True) if a.get("platform") == "YT"]

    linked = []
    yt_applied = []
    yt_errors = []

    for p in posts:
        vid = p["video_id"]
        if vid not in available:
            continue
        cov_url = f"{public_base}/api/covers/{vid}.png" if public_base else f"/api/covers/{vid}.png"
        if p.get("cover_url") != cov_url:
            db.update_scheduled_cover_url(vid, cov_url)
            linked.append(vid)

        yt_url = p.get("yt_video_url") or ""
        if p.get("yt_uploaded") and "/shorts/" in yt_url and yt_accs:
            yt_id = yt_url.rsplit("/", 1)[-1]
            acc = yt_accs[0]
            cid = acc.get("client_id") or os.getenv("YT_CLIENT_ID", "")
            csec = acc.get("client_secret") or os.getenv("YT_CLIENT_SECRET", "")
            acc_id = acc.get("id")
            on_refresh = (lambda tok, exp, aid=acc_id: db.update_account_token(aid, tok, exp)) if acc_id else None
            res = await asyncio.to_thread(
                apply_youtube_thumbnail,
                yt_video_id=yt_id,
                cover_url=cov_url,
                access_token=acc["access_token"],
                refresh_token=acc.get("refresh_token"),
                client_id=cid,
                client_secret=csec,
                on_token_refresh=on_refresh,
            )
            if res.get("ok"):
                yt_applied.append({"video_id": vid, "yt_id": yt_id})
            else:
                yt_errors.append({"video_id": vid, "yt_id": yt_id, "error": res.get("error")})

    return {
        "ok": True,
        "linked_covers": linked,
        "yt_thumbnails_applied": yt_applied,
        "yt_thumbnail_errors": yt_errors,
    }


@app.post("/api/media/upload", dependencies=[Depends(verify_api_key)])
async def upload_media_mp4(
    file: UploadFile = File(...),
    brand: str = Form("akilalmaz"),
    video_id: str = Form(""),
):
    """Uploads an MP4 (from Claude Code CLI or Studio Panel) to persistent GCS uploads/{brand}/{id}.mp4."""
    import tempfile
    from google.cloud import storage as gcs_storage

    safe_brand = re.sub(r"[^a-z0-9_\-]", "", (brand or "akilalmaz").strip().lower()) or "akilalmaz"
    raw_id = video_id.strip() or os.path.splitext(file.filename or "video")[0]
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_id).strip("_")[:64] or f"vid_{int(time.time())}"
    fname = f"{safe_id}.mp4"
    tmp_path = os.path.join(tempfile.gettempdir(), f"up_{safe_brand}_{int(time.time())}_{fname}")

    size_bytes = 0
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size_bytes += len(chunk)

        bucket_name = os.getenv("GCS_BUCKET_NAME", "likya-temp-videos-likyastudios")
        blob_name = f"uploads/{safe_brand}/{fname}"
        try:
            client = gcs_storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            await asyncio.to_thread(blob.upload_from_filename, tmp_path, content_type="video/mp4")
        except Exception as e:
            # Local fallback for tests/dev
            fallback_dir = os.path.join("/tmp/uploads", safe_brand)
            os.makedirs(fallback_dir, exist_ok=True)
            import shutil
            shutil.copy2(tmp_path, os.path.join(fallback_dir, fname))
            print(f"[media] GCS upload warning (saved locally): {e}")

        public_base = os.getenv("PUBLIC_API_BASE", "").rstrip("/")
        video_url = f"{public_base}/api/media/{safe_brand}/{fname}" if public_base else f"/api/media/{safe_brand}/{fname}"
        return {
            "ok": True,
            "brand": safe_brand,
            "video_id": safe_id,
            "filename": fname,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "video_url": video_url,
        }
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@app.get("/api/media/{brand}/{filename}")
def stream_media_mp4(brand: str, filename: str):
    """Public MP4 stream from GCS uploads/{brand}/{filename} for panel preview, YouTube, and Instagram."""
    from google.cloud import storage as gcs_storage

    safe_brand = re.sub(r"[^a-z0-9_\-]", "", brand.lower())
    safe_file = re.sub(r"[^a-zA-Z0-9_\-\.]", "", filename)
    if not safe_file.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Yalnızca .mp4 dosyaları desteklenir.")

    local_fallback = os.path.join("/tmp/uploads", safe_brand, safe_file)
    if os.path.exists(local_fallback):
        def _iter_file():
            with open(local_fallback, "rb") as f:
                while chunk := f.read(1024 * 512):
                    yield chunk
        return StreamingResponse(_iter_file(), media_type="video/mp4", headers={"Access-Control-Allow-Origin": "*"})

    bucket_name = os.getenv("GCS_BUCKET_NAME", "likya-temp-videos-likyastudios")
    client = gcs_storage.Client()
    blob = client.bucket(bucket_name).blob(f"uploads/{safe_brand}/{safe_file}")
    if not blob.exists():
        raise HTTPException(status_code=404, detail="Video dosyası bulunamadı.")

    def _iter_gcs():
        with blob.open("rb") as f:
            while chunk := f.read(1024 * 512):
                yield chunk

    return StreamingResponse(
        _iter_gcs(),
        media_type="video/mp4",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


_ANALYTICS_CACHE: dict[str, tuple[float, dict]] = {}


def _fetch_ig_analytics(acc: dict) -> dict:
    """Fetches Instagram Business/Creator profile and recent media metrics via Meta Graph API."""
    import requests as _req

    ig_id = acc.get("external_id")
    token = acc.get("access_token")
    base = os.getenv("IG_GRAPH_BASE_URL", "https://graph.facebook.com/v21.0").rstrip("/")
    prof = _req.get(
        f"{base}/{ig_id}",
        params={"fields": "id,username,followers_count,media_count,profile_picture_url", "access_token": token},
        timeout=20,
    ).json()
    channel = {
        "id": ig_id,
        "title": "@" + prof.get("username", acc.get("account_name", "instagram").lstrip("@")),
        "custom_url": f"https://instagram.com/{prof.get('username', '')}",
        "thumbnail": prof.get("profile_picture_url"),
        "subscribers": int(prof.get("followers_count") or 0),
        "total_views": 0,
        "video_count": int(prof.get("media_count") or 0),
    }
    media_resp = _req.get(
        f"{base}/{ig_id}/media",
        params={
            "fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count,thumbnail_url,media_url",
            "limit": 25,
            "access_token": token,
        },
        timeout=20,
    ).json()
    videos = []
    for m in media_resp.get("data") or []:
        views = 0
        try:
            ins = _req.get(
                f"{base}/{m['id']}/insights",
                params={"metric": "views,reach", "access_token": token},
                timeout=10,
            ).json()
            for item in ins.get("data") or []:
                if item.get("name") == "views":
                    vals = item.get("values") or []
                    if vals:
                        views = int(vals[0].get("value") or 0)
        except Exception:
            pass
        likes = int(m.get("like_count") or 0)
        comments = int(m.get("comments_count") or 0)
        cap = (m.get("caption") or "").strip()
        title = cap.splitlines()[0][:90] if cap else "Instagram Reels"
        channel["total_views"] += views
        videos.append({
            "platform": "IG",
            "video_id": m.get("id"),
            "title": title,
            "thumbnail": m.get("thumbnail_url") or m.get("media_url"),
            "url": m.get("permalink") or "",
            "published_at": m.get("timestamp"),
            "publish_at": None,
            "privacy_status": "public",
            "state": "Yayında",
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement_rate": round(((likes + comments) / views) * 100, 2) if views > 0 else 0.0,
            "duration": "",
        })
    return {"platform": "IG", "channel": channel, "videos": videos}


@app.get("/api/analytics", dependencies=[Depends(verify_api_key)])
async def get_analytics(brand: Optional[str] = None, refresh: bool = False):
    """Live YouTube & Instagram analytics for all connected channels and their published/scheduled videos."""
    from datetime import datetime, timezone

    cache_key = (brand or "all").strip().lower()
    now_ts = time.time()
    if not refresh and cache_key in _ANALYTICS_CACHE:
        ts, cached = _ANALYTICS_CACHE[cache_key]
        if now_ts - ts < 60:
            return cached

    accs = db.list_accounts(include_tokens=True)
    if brand and brand.strip().lower() not in ("", "all"):
        b_filt = brand.strip().lower()
        accs = [a for a in accs if (a.get("brand") or "akilalmaz").lower() == b_filt]

    # Map YT video_id -> internal scheduled post metadata (slug, brand, label_tr, cover_url)
    sched_posts = db.list_scheduled_posts()
    sched_by_yt: dict[str, dict] = {}
    for p in sched_posts:
        u = p.get("yt_video_url") or ""
        if "/shorts/" in u:
            sched_by_yt[u.rsplit("/", 1)[-1].split("?")[0]] = p

    channels: list[dict] = []
    videos: list[dict] = []
    errors: list[dict] = []

    for acc in accs:
        plat = acc.get("platform")
        acc_brand = acc.get("brand") or "akilalmaz"
        acc_id = acc.get("id")
        try:
            if plat == "YT":
                cid = acc.get("client_id") or os.getenv("YT_CLIENT_ID", "")
                csec = acc.get("client_secret") or os.getenv("YT_CLIENT_SECRET", "")
                on_refresh = (lambda tok, exp, aid=acc_id: db.update_account_token(aid, tok, exp)) if acc_id else None
                res = await asyncio.to_thread(
                    fetch_youtube_analytics,
                    access_token=acc["access_token"],
                    refresh_token=acc.get("refresh_token"),
                    client_id=cid,
                    client_secret=csec,
                    max_videos=35,
                    on_token_refresh=on_refresh,
                )
            elif plat == "IG":
                res = await asyncio.to_thread(_fetch_ig_analytics, acc)
            else:
                continue

            ch = res.get("channel")
            if ch:
                ch["platform"] = plat
                ch["brand"] = acc_brand
                ch["account_id"] = acc_id
                channels.append(ch)
            for v in res.get("videos") or []:
                v["brand"] = acc_brand
                v["account_name"] = (ch or {}).get("title") or acc.get("account_name") or ""
                sp = sched_by_yt.get(v.get("video_id") or "")
                if sp:
                    v["slug"] = sp.get("video_id")
                    v["label_tr"] = sp.get("label_tr")
                    if sp.get("cover_url"):
                        v["cover_url"] = sp.get("cover_url")
                videos.append(v)
        except Exception as e:
            errors.append({
                "account_id": acc_id,
                "platform": plat,
                "brand": acc_brand,
                "account_name": acc.get("account_name"),
                "error": str(e)[:300],
            })

    # Sort: Yayında first by views desc (then published_at desc), then Planlandı by publish_at asc
    videos.sort(key=lambda x: (0 if x.get("state") == "Yayında" else 1, -int(x.get("views") or 0), x.get("publish_at") or ""))

    pub_videos = [v for v in videos if v.get("state") == "Yayında"]
    sched_videos = [v for v in videos if v.get("state") == "Planlandı"]
    total_views = sum(int(v.get("views") or 0) for v in videos)
    total_likes = sum(int(v.get("likes") or 0) for v in videos)
    total_comments = sum(int(v.get("comments") or 0) for v in videos)
    total_subs = sum(int(c.get("subscribers") or 0) for c in channels)

    payload = {
        "ok": True,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_subscribers": total_subs,
            "published_count": len(pub_videos),
            "scheduled_count": len(sched_videos),
            "avg_views": round(total_views / len(pub_videos), 1) if pub_videos else 0.0,
            "engagement_rate": round(((total_likes + total_comments) / total_views) * 100, 2) if total_views > 0 else 0.0,
        },
        "channels": channels,
        "videos": videos,
        "errors": errors,
    }
    _ANALYTICS_CACHE[cache_key] = (now_ts, payload)
    return payload



