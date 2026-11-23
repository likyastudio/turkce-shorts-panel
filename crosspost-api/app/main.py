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
import time
from typing import Optional
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import db
from app.oauth import router as oauth_router
from app.services import covers as covers_svc
from app.services.instagram import publish_to_instagram
from app.services.storage import download_video_to_tmp, upload_to_gcs_and_get_signed_url
from app.services.youtube import publish_to_youtube

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
        img_url = f"{public_base}/api/covers/{safe_key}.png?v={ts}" if public_base else f"/api/covers/{safe_key}.png?v={ts}"
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

