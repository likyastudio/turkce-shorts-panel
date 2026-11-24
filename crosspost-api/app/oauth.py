"""OAuth 2.0 multi-channel connection routes for YouTube (Google) and Instagram (Meta Graph API)."""
from __future__ import annotations
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
import requests
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from app import db
from app.security import is_allowed_return_url, make_state, read_state, verify_api_key

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
PUBLIC_API_BASE = os.getenv("PUBLIC_API_BASE", "http://localhost:8080").rstrip("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://studio.likyastudios.live/").rstrip("/")
IG_GRAPH_BASE_URL = os.getenv("IG_GRAPH_BASE_URL", "https://graph.facebook.com/v21.0")


class OAuthStartIn(BaseModel):
    redirect_to: str = FRONTEND_URL
    brand: str = ""


def _new_state(platform: str, body: OAuthStartIn) -> str:
    back = body.redirect_to.split("#")[0]
    if not is_allowed_return_url(back):
        raise HTTPException(status_code=400, detail="Geri dönüş adresine izin verilmiyor.")
    # Marka seçilmediyse kanal hiçbir markanın otomatik yayınına girmez; Ayarlar'dan atanır.
    brand = re.sub(r"[^a-z0-9_\-]", "", body.brand.strip().lower()) or "atanmadi"
    return make_state(platform, back, brand)


@router.post("/youtube/start", dependencies=[Depends(verify_api_key)])
def youtube_oauth_start(body: OAuthStartIn):
    """Yalnızca API anahtarı olan panel kanal bağlama başlatabilir; imzalı ve süreli 'state' üretir."""
    cid = os.getenv("YT_CLIENT_ID", YT_CLIENT_ID)
    if not cid:
        raise HTTPException(status_code=400, detail="YT_CLIENT_ID ortam değişkeni tanımlı değil.")
    base = os.getenv("PUBLIC_API_BASE", PUBLIC_API_BASE).rstrip("/")
    params = {
        "client_id": cid,
        "redirect_uri": f"{base}/api/oauth/youtube/callback",
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
        "state": _new_state("YT", body),
    }
    return {"url": "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)}


@router.get("/youtube/callback")
def youtube_oauth_callback(state: str = "", code: Optional[str] = None, error: Optional[str] = None):
    st = read_state(state, "YT")
    if error or not code:
        return RedirectResponse(f"{st['r']}#settings?cancelled=YT")
    cid = os.getenv("YT_CLIENT_ID", YT_CLIENT_ID)
    csec = os.getenv("YT_CLIENT_SECRET", YT_CLIENT_SECRET)
    base = os.getenv("PUBLIC_API_BASE", PUBLIC_API_BASE).rstrip("/")
    tok = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": cid,
            "client_secret": csec,
            "redirect_uri": f"{base}/api/oauth/youtube/callback",
            "grant_type": "authorization_code",
        },
        timeout=20,
    ).json()
    if "access_token" not in tok:
        raise HTTPException(status_code=400, detail=f"YouTube OAuth hatası: {tok.get('error_description') or tok.get('error')}")

    access = tok["access_token"]
    refresh = tok.get("refresh_token")
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(tok.get("expires_in", 3600)))).isoformat()

    ch = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "snippet", "mine": "true"},
        headers={"Authorization": f"Bearer {access}"},
        timeout=20,
    ).json()
    items = ch.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="Bu Google hesabında YouTube kanalı bulunamadı.")
    ext_id = items[0]["id"]
    name = items[0]["snippet"]["title"]

    db.upsert_account("YT", name, ext_id, access, refresh, expires_at, brand=st["b"])
    return RedirectResponse(f"{st['r']}#settings?connected=YT")


@router.post("/instagram/start", dependencies=[Depends(verify_api_key)])
def instagram_oauth_start(body: OAuthStartIn):
    """Yalnızca API anahtarı olan panel kanal bağlama başlatabilir; imzalı ve süreli 'state' üretir."""
    aid = os.getenv("META_APP_ID", META_APP_ID)
    if not aid:
        raise HTTPException(status_code=400, detail="META_APP_ID ortam değişkeni tanımlı değil.")
    base = os.getenv("PUBLIC_API_BASE", PUBLIC_API_BASE).rstrip("/")
    params = {
        "client_id": aid,
        "redirect_uri": f"{base}/api/oauth/instagram/callback",
        "response_type": "code",
        "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,business_management",
        "auth_type": "rerequest",
        "state": _new_state("IG", body),
    }
    return {"url": "https://www.facebook.com/v21.0/dialog/oauth?" + urllib.parse.urlencode(params)}


@router.get("/instagram/callback")
def instagram_oauth_callback(state: str = "", code: Optional[str] = None, error: Optional[str] = None):
    st = read_state(state, "IG")
    if error or not code:
        return RedirectResponse(f"{st['r']}#settings?cancelled=IG")
    aid = os.getenv("META_APP_ID", META_APP_ID)
    asec = os.getenv("META_APP_SECRET", META_APP_SECRET)
    base = os.getenv("PUBLIC_API_BASE", PUBLIC_API_BASE).rstrip("/")

    # 1. Exchange code -> short-lived user token
    tok = requests.get(
        f"{IG_GRAPH_BASE_URL}/oauth/access_token",
        params={
            "client_id": aid,
            "client_secret": asec,
            "redirect_uri": f"{base}/api/oauth/instagram/callback",
            "code": code,
        },
        timeout=20,
    ).json()
    if "access_token" not in tok:
        raise HTTPException(status_code=400, detail=f"Meta OAuth hatası: {(tok.get('error') or {}).get('message') if isinstance(tok.get('error'), dict) else tok.get('error')}")

    # 2. Exchange -> 60-day long-lived user token
    ll = requests.get(
        f"{IG_GRAPH_BASE_URL}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": aid,
            "client_secret": asec,
            "fb_exchange_token": tok["access_token"],
        },
        timeout=20,
    ).json()
    access = ll.get("access_token", tok["access_token"])
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(ll.get("expires_in", 5184000)))).isoformat()

    # 3. Discover linked Instagram Business/Creator accounts via user's Facebook Pages
    page_fields = "id,name,instagram_business_account{id,username},connected_instagram_account{id,username}"
    pages = requests.get(
        f"{IG_GRAPH_BASE_URL}/me/accounts",
        params={"fields": page_fields, "limit": 100, "access_token": access},
        timeout=20,
    ).json()

    candidate_pages: list[dict] = list(pages.get("data", []))
    direct_ig_nodes: list[dict] = []

    # Fallback / supplement 1: pages & Instagram accounts owned or managed via Meta Business Portfolios
    biz = requests.get(
        f"{IG_GRAPH_BASE_URL}/me/businesses",
        params={
            "fields": (
                f"id,name,owned_pages{{{page_fields}}},client_pages{{{page_fields}}},"
                "owned_instagram_accounts{id,username},instagram_accounts{id,username}"
            ),
            "limit": 50,
            "access_token": access,
        },
        timeout=20,
    ).json()
    for b in biz.get("data", []):
        candidate_pages.extend((b.get("owned_pages") or {}).get("data", []))
        candidate_pages.extend((b.get("client_pages") or {}).get("data", []))
        direct_ig_nodes.extend((b.get("owned_instagram_accounts") or {}).get("data", []))
        direct_ig_nodes.extend((b.get("instagram_accounts") or {}).get("data", []))

    discovered: dict[str, str] = {}
    page_names: list[str] = []

    def _collect_ig(ig_id: str, username: str | None, fallback_name: str = "instagram") -> None:
        if not ig_id or ig_id in discovered:
            return
        discovered[str(ig_id)] = "@" + (username or fallback_name).lstrip("@")

    for pg in candidate_pages:
        if pg.get("name") and pg["name"] not in page_names:
            page_names.append(pg["name"])
        ig = pg.get("instagram_business_account") or pg.get("connected_instagram_account")
        if ig and ig.get("id"):
            _collect_ig(str(ig["id"]), ig.get("username"), pg.get("name", "instagram"))

    for ig in direct_ig_nodes:
        if ig and ig.get("id"):
            _collect_ig(str(ig["id"]), ig.get("username"))

    # Fallback / supplement 2: inspect granular_scopes target_ids directly granted in the Meta OAuth dialog
    try:
        dbg = requests.get(
            f"{IG_GRAPH_BASE_URL}/debug_token",
            params={"input_token": access, "access_token": f"{aid}|{asec}"},
            timeout=20,
        ).json()
        for gs in (dbg.get("data") or {}).get("granular_scopes") or []:
            if gs.get("scope") in ("instagram_basic", "instagram_content_publish"):
                for tid in gs.get("target_ids") or []:
                    tid_str = str(tid)
                    if tid_str in discovered:
                        continue
                    prof = requests.get(
                        f"{IG_GRAPH_BASE_URL}/{tid_str}",
                        params={"fields": "id,username,name", "access_token": access},
                        timeout=15,
                    ).json()
                    if prof.get("id"):
                        _collect_ig(str(prof["id"]), prof.get("username") or prof.get("name"), tid_str)
    except Exception:
        pass

    # Birden çok Instagram hesabı gelirse hangisinin seçilen marka olduğu bilinemez; atanmamış bırak.
    new_brand = st["b"] if len(discovered) == 1 else "atanmadi"
    for ig_id, uname in discovered.items():
        db.upsert_account("IG", uname, ig_id, access, None, expires_at, brand=new_brand)

    seen_ig_ids = set(discovered.keys())

    if not seen_ig_ids:
        diag_parts = []
        if pages.get("error"):
            diag_parts.append(f"me/accounts hata: {pages['error'].get('message')}")
        diag_parts.append(f"bulunan FB sayfası: {len(page_names)}" + (f" ({', '.join(page_names[:5])})" if page_names else ""))
        raise HTTPException(
            status_code=400,
            detail=(
                "Bağlı bir Instagram İşletme/İçerik Üreticisi hesabı bulunamadı "
                "(Instagram hesabınız bir Facebook Sayfasına bağlı olmalıdır). "
                f"[Tanı: {'; '.join(diag_parts)}]"
            ),
        )
    return RedirectResponse(f"{st['r']}#settings?connected=IG")
