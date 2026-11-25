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
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import db
from app.oauth import auth_router, router as oauth_router
from app.security import verify_api_key, verify_scheduler
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(oauth_router)
app.include_router(auth_router)


@app.on_event("startup")
def _startup():
    db.init_db()


class ManualAccountIn(BaseModel):
    platform: str = Field(pattern="^(YT|IG)$")
    account_name: str
    external_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    brand: str = "akilalmaz"


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
        brand=re.sub(r"[^a-z0-9_\-]", "", body.brand.strip().lower()) or "akilalmaz",
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
        # Kanal seçilmeden "tüm markaların tüm kanallarına" yayınlamak yanlış kanala gönderir; reddet.
        if not accounts:
            raise HTTPException(status_code=400, detail="Yayınlanacak kanal seçilmedi (account_ids gerekli).")

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
        "message": "Paylaşım başlatıldı",
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


@app.get("/api/covers/{key}.jpg")
def get_cover_jpeg_endpoint(key: str):
    """Public sRGB JPEG stream required by Instagram Graph API Reels cover_url."""
    import io
    from PIL import Image

    raw_bytes = covers_svc.get_cover(key)
    if not raw_bytes:
        raise HTTPException(status_code=404, detail="Kapak görseli bulunamadı.")
    im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=92, optimize=True)
    return Response(
        content=buf.getvalue(),
        media_type="image/jpeg",
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

    if not db.claim_yt_sync(post_id):
        return  # Başka bir istek bu videoyu zaten yüklüyor (çift yükleme önlenir)

    local_path = None
    try:
        already = db.get_published_account_ids(post)
        local_path = await asyncio.to_thread(download_video_to_tmp, post["video_url"], f"ytsched_{post['video_id']}")
        last_url = post.get("yt_video_url")
        failed: list[str] = []
        for acc in yt_accs:
            if acc.get("id") in already:
                continue  # Önceki denemede bu kanala yüklenmişti
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
                    brand=post_brand,
                    on_token_refresh=on_refresh,
                )
                last_url = res.get("url")
                db.update_publish_log(log_id, res.get("status", "YT Planlandı"), platform_post_url=last_url)
            except Exception as e:
                db.update_publish_log(log_id, "Hata", error_message=str(e)[:500])
                failed.append(f"{acc.get('account_name')}: {e}")
        if failed:
            db.release_yt_sync(post_id, ("YT ön-planlama uyarısı: " + " | ".join(failed))[:400])
        else:
            db.mark_scheduled_yt_uploaded(post_id, last_url or "")
    except Exception as e:
        db.release_yt_sync(post_id, f"YT ön-planlama uyarısı: {e}"[:400])
    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass


async def _execute_scheduled_post(post: dict, manual: bool = False) -> bool:
    """Runs a due scheduled post through the cross-post pipeline.
    If already natively scheduled on YouTube (yt_uploaded=True), skips YT to avoid duplicates
    and only publishes to Instagram (if connected for this brand)."""
    post_id = post["id"]
    if not db.claim_scheduled_post(post_id, ("Planlandı", "Hata") if manual else ("Planlandı",)):
        return False  # Başka bir istek bu gönderiyi zaten yayınlıyor
    try:
        post = db.get_scheduled_post(post_id) or post  # bekleme sırasında değişmiş olabilir
        acc_ids = post.get("account_ids") or []
        post_brand = post.get("brand") or "akilalmaz"
        accounts = db.get_accounts_by_ids(acc_ids) if acc_ids else db.list_accounts(include_tokens=True, brand=post_brand)

        if post.get("yt_uploaded"):
            # YouTube already handles exact publishAt natively; only run IG targets if any
            accounts = [a for a in accounts if a.get("platform") != "YT"]
            if not accounts:
                db.update_scheduled_post(post_id, "Yayında", None)
                return True

        if not accounts:
            db.update_scheduled_post(post_id, "Hata", "Bağlı YouTube veya Instagram kanalı bulunamadı.")
            return True

        # Kısmen başarılı önceki denemelerde yayınlanan hesaplara ikinci kez gönderme
        done = db.get_published_account_ids(post)
        accounts = [a for a in accounts if a.get("id") not in done]
        if not accounts:
            db.update_scheduled_post(post_id, "Yayında", None)
            return True

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

        logs = db.get_publish_logs_by_ids([lid for lid, _ in targets])
        errs = [l["error_message"] for l in logs if l.get("status") == "Hata" and l.get("error_message")]
        if errs and len(errs) == len(targets):
            db.update_scheduled_post(post_id, "Hata", " | ".join(errs)[:400])
        else:
            db.update_scheduled_post(post_id, "Yayında", ("Kısmi hata: " + " | ".join(errs))[:400] if errs else None)
    except Exception as e:
        db.update_scheduled_post(post_id, "Hata", str(e)[:400])
    return True


def _parse_schedule_time(value: str) -> str:
    """Saati doğrular, UTC'ye çevirir. Saat dilimi yazılmamışsa Türkiye saati (+03:00) kabul edilir."""
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Yayın saati anlaşılamadı.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=3)))
    dt = dt.astimezone(timezone.utc)
    if dt < datetime.now(timezone.utc) - timedelta(minutes=2):
        raise HTTPException(status_code=400, detail="Geçmiş bir saate plan yapılamaz.")
    return dt.isoformat()


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

    if any(p["video_id"] == req.video_id and p["status"] in ("Planlandı", "Yayınlanıyor") for p in existing):
        raise HTTPException(status_code=409, detail="Bu video bu marka için zaten planlı. Yayın Planı'ndan düzenleyebilirsiniz.")

    if req.auto_next_slot or not req.scheduled_at:
        slot = sched_svc.next_weekly_slot(occupied_iso_list=occupied)
        sched_iso = slot["scheduled_at_utc"]
    else:
        sched_iso = _parse_schedule_time(req.scheduled_at)

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


class EditScheduleRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    ig_caption: Optional[str] = Field(default=None, max_length=2200)
    scheduled_at: Optional[str] = None


@app.patch("/api/schedule/{post_id}", dependencies=[Depends(verify_api_key)])
def edit_schedule(post_id: int, body: EditScheduleRequest):
    """Planlı gönderinin başlığını, açıklamalarını veya saatini değiştirir."""
    post = db.get_scheduled_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Planlanmış gönderi bulunamadı.")
    if post["status"] not in ("Planlandı", "Hata"):
        raise HTTPException(status_code=409, detail="Yayınlanmış veya yayınlanmakta olan gönderi düzenlenemez.")

    fields = {}
    for k in ("title", "description", "ig_caption"):
        v = getattr(body, k)
        if v is not None and v != (post.get(k) or ""):
            fields[k] = v
    if body.scheduled_at:
        new_at = _parse_schedule_time(body.scheduled_at)
        if datetime.fromisoformat(new_at) != datetime.fromisoformat(post["scheduled_at"].replace("Z", "+00:00")):
            fields["scheduled_at"] = new_at
            fields["status"] = "Planlandı"

    if post.get("yt_uploaded") and set(fields) & {"title", "description", "scheduled_at"}:
        raise HTTPException(
            status_code=409,
            detail="Bu video YouTube'a planlı olarak yüklendi. Başlık, açıklama ve saati YouTube Studio'dan değiştirin; burada yalnızca Instagram metni değişir.",
        )
    if fields and not db.edit_scheduled_post(post_id, fields):
        raise HTTPException(status_code=409, detail="Gönderi şu anda yükleniyor. Biraz sonra tekrar deneyin.")
    return {"ok": True, "post": _enrich_sched(db.get_scheduled_post(post_id))}


@app.delete("/api/schedule/{post_id}", dependencies=[Depends(verify_api_key)])
def remove_schedule(post_id: int):
    post = db.get_scheduled_post(post_id)
    if not post or not db.delete_scheduled_post(post_id):
        raise HTTPException(status_code=404, detail="Planlanmış gönderi bulunamadı.")
    # YouTube'a yüklenen planlı video buradan silinemez (izin kapsamı yok); arayüz kullanıcıyı uyarır.
    return {"ok": True, "deleted": post_id, "yt_video_url": post.get("yt_video_url") if post["status"] == "Planlandı" else None}


@app.post("/api/schedule/{post_id}/run-now", dependencies=[Depends(verify_api_key)])
async def run_schedule_now(post_id: int, background_tasks: BackgroundTasks):
    post = db.get_scheduled_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Planlanmış gönderi bulunamadı.")
    if post["status"] not in ("Planlandı", "Hata"):
        raise HTTPException(status_code=409, detail="Bu gönderi zaten yayınlandı veya yayınlanıyor.")
    background_tasks.add_task(_execute_scheduled_post, post, True)
    return {"ok": True, "message": "Hemen yayınlanmak üzere başlatıldı.", "id": post_id}


@app.post("/api/schedule/{post_id}/reschedule", dependencies=[Depends(verify_api_key)])
async def reschedule_schedule_post(post_id: int, background_tasks: BackgroundTasks, sync_youtube_now: bool = True):
    """Moves a failed/past scheduled post to the next open weekly slot (06:01-06:07 TR) for its brand,
    resets status to 'Planlandı', clears account_ids so current brand channels are used, and triggers YT presync."""
    post = db.get_scheduled_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Planlanmış gönderi bulunamadı.")
    if post["status"] == "Yayınlanıyor":
        raise HTTPException(status_code=409, detail="Gönderi şu anda yayınlanıyor.")
    if post["status"] == "Planlandı" and post.get("yt_uploaded"):
        raise HTTPException(status_code=409, detail="Video YouTube'da planlı. Saatini YouTube Studio'dan değiştirin.")
    brand = (post.get("brand") or "akilalmaz").strip().lower()
    brand_accs = db.list_accounts(include_tokens=False, brand=brand)
    if not brand_accs:
        raise HTTPException(
            status_code=400,
            detail=f"'{brand}' markasına atanmış YouTube veya Instagram kanalı yok. Önce VI. Ayarlar'dan kanalın markasını seçin.",
        )
    existing = db.list_scheduled_posts(brand=brand)
    occupied = [p["scheduled_at"] for p in existing if p["id"] != post_id and p["status"] in ("Planlandı", "Yayınlanıyor")]
    slot = sched_svc.next_weekly_slot(occupied_iso_list=occupied)
    updated = db.reschedule_post(post_id, slot["scheduled_at_utc"], account_ids=[])
    if sync_youtube_now and updated and not updated.get("yt_uploaded"):
        background_tasks.add_task(_sync_scheduled_post_to_youtube, updated)
    return {"ok": True, "post": _enrich_sched(updated), "channels": [a["account_name"] for a in brand_accs]}


@app.post("/api/scheduler/tick", dependencies=[Depends(verify_scheduler)])
async def scheduler_tick():
    """1. Triggers due scheduled posts (skipping YT if already natively scheduled).
    2. Pre-uploads upcoming un-synced scheduled posts to YouTube Studio (within safe daily quota).
    İş, yanıt dönmeden bitirilir: Cloud Run yanıttan sonra işlemciyi kıstığı için arka plan işi yarım kalabiliyordu."""
    deadline = time.monotonic() + 200  # Cloud Run 300 sn sınırından önce yeni iş başlatmayı bırak
    stale = db.fail_stale_publishing()
    due = db.get_due_scheduled_posts()
    triggered = []
    for post in due:
        if time.monotonic() > deadline:
            break  # kalanlar sonraki çağrıda
        if await _execute_scheduled_post(post) is not False:
            triggered.append(post["id"])

    remaining_quota = max(0, YT_DAILY_PRESYNC_LIMIT - db.count_yt_uploads_today())
    presync_ids = []
    for post in db.get_pending_yt_presync_posts(limit=remaining_quota) if remaining_quota else []:
        if time.monotonic() > deadline:
            break
        await _sync_scheduled_post_to_youtube(post)
        presync_ids.append(post["id"])

    return {
        "ok": True,
        "due_count": len(due),
        "triggered_ids": triggered,
        "yt_presync_ids": presync_ids,
        "stale_failed": stale,
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
        print(f"[ai] generate-story hata: {type(e).__name__}: {e}")
        raise HTTPException(status_code=502, detail=f"Senaryo üretimi başarısız: {e}")


@app.post("/api/schedule/sync-covers", dependencies=[Depends(verify_api_key)])
async def sync_covers_to_schedule():
    """Links all existing GCS covers to scheduled_posts and applies thumbnails.set to already-uploaded YT videos."""
    available = set(covers_svc.list_covers())
    public_base = os.getenv("PUBLIC_API_BASE", "").rstrip("/")
    posts = db.list_scheduled_posts()
    all_yt = [a for a in db.list_accounts(include_tokens=True) if a.get("platform") == "YT"]

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
        # Kapak, videonun yüklendiği kanalın hesabıyla uygulanmalı (başka markanın hesabıyla değil)
        ids = p.get("account_ids") or []
        yt_accs = [a for a in all_yt if (a["id"] in ids if ids else (a.get("brand") or "akilalmaz") == p.get("brand"))]
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
    safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_id).strip("_")[:52] or "vid"
    if not video_id.strip():
        safe_id = f"{safe_id}_{int(time.time())}"  # aynı adlı iki dosya birbirini ezmesin
    if not (file.filename or "").lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Yalnızca .mp4 dosyası yüklenebilir.")
    fname = f"{safe_id}.mp4"
    tmp_path = os.path.join(tempfile.gettempdir(), f"up_{safe_brand}_{int(time.time())}_{fname}")

    size_bytes = 0
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                if size_bytes == 0 and chunk[4:8] != b"ftyp":
                    raise HTTPException(status_code=400, detail="Dosya geçerli bir MP4 değil.")
                out.write(chunk)
                size_bytes += len(chunk)
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="Dosya boş.")

        bucket_name = os.getenv("GCS_BUCKET_NAME", "likya-temp-videos-likyastudios")
        blob_name = f"uploads/{safe_brand}/{fname}"
        try:
            client = gcs_storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            await asyncio.to_thread(blob.upload_from_filename, tmp_path, content_type="video/mp4")
        except Exception as e:
            if os.getenv("K_SERVICE"):
                # Cloud Run diski geçicidir; video kaybolmasın diye hatayı gizleme
                raise HTTPException(status_code=502, detail=f"Video depoya yüklenemedi: {e}")
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
def stream_media_mp4(brand: str, filename: str, request: Request):
    """Public MP4 stream from GCS uploads/{brand}/{filename} for panel preview, YouTube, and Instagram.
    iPhone/Safari önizlemesi için Range isteklerini destekler."""
    from google.cloud import storage as gcs_storage

    safe_brand = re.sub(r"[^a-z0-9_\-]", "", brand.lower())
    safe_file = re.sub(r"[^a-zA-Z0-9_\-\.]", "", filename)
    if not safe_file.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Yalnızca .mp4 dosyaları desteklenir.")

    local_fallback = os.path.join("/tmp/uploads", safe_brand, safe_file)
    if os.path.exists(local_fallback):
        size = os.path.getsize(local_fallback)

        def _open():
            return open(local_fallback, "rb")
    else:
        bucket_name = os.getenv("GCS_BUCKET_NAME", "likya-temp-videos-likyastudios")
        blob = gcs_storage.Client().bucket(bucket_name).get_blob(f"uploads/{safe_brand}/{safe_file}")
        if blob is None:
            raise HTTPException(status_code=404, detail="Video dosyası bulunamadı.")
        size = blob.size

        def _open():
            return blob.open("rb")

    start, end, code = 0, size - 1, 200
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (request.headers.get("range") or "").strip())
    if m and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1))
            end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
        else:
            start = max(0, size - int(m.group(2)))
        if start >= size or start > end:
            raise HTTPException(status_code=416, detail="Geçersiz aralık.", headers={"Content-Range": f"bytes */{size}"})
        code = 206

    def _iter():
        left = end - start + 1
        with _open() as f:
            f.seek(start)
            while left > 0 and (chunk := f.read(min(left, 512 * 1024))):
                left -= len(chunk)
                yield chunk

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
        "Cache-Control": "public, max-age=3600",
        "Access-Control-Allow-Origin": "*",
    }
    if code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(_iter(), status_code=code, media_type="video/mp4", headers=headers)


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
    sched_posts = [_enrich_sched(r) for r in db.list_scheduled_posts()]
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
                v["account_id"] = acc_id
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

    # Include queued/scheduled posts for every connected YT & IG channel (especially Instagram,
    # which has no native future-scheduled media endpoint, and YT posts awaiting presync quota).
    existing_yt_ids_by_acc: dict[int, set[str]] = {}
    for v in videos:
        aid = v.get("account_id")
        if aid is not None:
            existing_yt_ids_by_acc.setdefault(aid, set()).add(v.get("video_id") or "")
            if v.get("slug"):
                existing_yt_ids_by_acc[aid].add(v["slug"])

    ch_title_by_acc = {c.get("account_id"): c.get("title") for c in channels if c.get("account_id") is not None}
    for sp in sched_posts:
        if sp.get("status") not in ("Planlandı", "Yayınlanıyor"):
            continue
        sp_brand = (sp.get("brand") or "akilalmaz").lower()
        sp_acc_ids = sp.get("account_ids") or []
        yt_vid_id = ""
        u = sp.get("yt_video_url") or ""
        if "/shorts/" in u:
            yt_vid_id = u.rsplit("/", 1)[-1].split("?")[0]

        for acc in accs:
            aid = acc.get("id")
            plat = acc.get("platform")
            acc_brand = (acc.get("brand") or "akilalmaz").lower()
            if sp_acc_ids:
                if aid not in sp_acc_ids:
                    continue
            else:
                if acc_brand != sp_brand:
                    continue

            seen_for_acc = existing_yt_ids_by_acc.get(aid, set())
            if plat == "YT" and ((yt_vid_id and yt_vid_id in seen_for_acc) or (sp.get("video_id") in seen_for_acc)):
                continue

            videos.append({
                "platform": plat,
                "brand": acc_brand,
                "account_id": aid,
                "account_name": ch_title_by_acc.get(aid) or acc.get("account_name") or "",
                "video_id": yt_vid_id if (plat == "YT" and yt_vid_id) else f"sched_{sp.get('id')}_{plat}",
                "slug": sp.get("video_id"),
                "title": sp.get("title") or sp.get("video_id") or "Planlı Video",
                "thumbnail": sp.get("cover_url") or "",
                "cover_url": sp.get("cover_url") or "",
                "url": sp.get("yt_video_url") if plat == "YT" else "",
                "published_at": None,
                "publish_at": sp.get("scheduled_at"),
                "label_tr": sp.get("label_tr"),
                "privacy_status": "scheduled",
                "state": "Planlandı",
                "views": 0,
                "likes": 0,
                "comments": 0,
                "engagement_rate": 0.0,
                "duration": "",
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



