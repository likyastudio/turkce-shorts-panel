"""OAuth 2.0 multi-channel connection routes for YouTube (Google) and Instagram (Meta Graph API)."""
from __future__ import annotations
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from app import db

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

YT_CLIENT_ID = os.getenv("YT_CLIENT_ID", "")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET", "")
META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
PUBLIC_API_BASE = os.getenv("PUBLIC_API_BASE", "http://localhost:8080").rstrip("/")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://likyastudio.github.io/turkce-shorts-panel/").rstrip("/")
IG_GRAPH_BASE_URL = os.getenv("IG_GRAPH_BASE_URL", "https://graph.facebook.com/v21.0")


@router.get("/youtube/start")
def youtube_oauth_start(redirect_to: str = Query(default=FRONTEND_URL)):
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
        "state": redirect_to,
    }
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params))


@router.get("/youtube/callback")
def youtube_oauth_callback(code: str, state: str = FRONTEND_URL):
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
        raise HTTPException(status_code=400, detail=f"YouTube OAuth hatası: {tok}")

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
    ext_id = items[0]["id"] if items else "yt_default"
    name = items[0]["snippet"]["title"] if items else "YouTube Kanalı"

    db.upsert_account("YT", name, ext_id, access, refresh, expires_at)
    return RedirectResponse(f"{state}#settings?connected=YT")


@router.get("/instagram/start")
def instagram_oauth_start(redirect_to: str = Query(default=FRONTEND_URL)):
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
        "state": redirect_to,
    }
    return RedirectResponse("https://www.facebook.com/v21.0/dialog/oauth?" + urllib.parse.urlencode(params))


@router.get("/instagram/callback")
def instagram_oauth_callback(code: str, state: str = FRONTEND_URL):
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
        raise HTTPException(status_code=400, detail=f"Meta OAuth hatası: {tok}")

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

    # Fallback / supplement: pages owned or managed via Meta Business Portfolios
    biz = requests.get(
        f"{IG_GRAPH_BASE_URL}/me/businesses",
        params={
            "fields": f"id,name,owned_pages{{{page_fields}}},client_pages{{{page_fields}}}",
            "limit": 50,
            "access_token": access,
        },
        timeout=20,
    ).json()
    for b in biz.get("data", []):
        candidate_pages.extend((b.get("owned_pages") or {}).get("data", []))
        candidate_pages.extend((b.get("client_pages") or {}).get("data", []))

    seen_ig_ids: set[str] = set()
    page_names: list[str] = []
    for pg in candidate_pages:
        if pg.get("name") and pg["name"] not in page_names:
            page_names.append(pg["name"])
        ig = pg.get("instagram_business_account") or pg.get("connected_instagram_account")
        if ig and ig.get("id") and ig["id"] not in seen_ig_ids:
            uname = "@" + ig.get("username", pg.get("name", "instagram"))
            db.upsert_account("IG", uname, ig["id"], access, None, expires_at)
            seen_ig_ids.add(ig["id"])

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
    return RedirectResponse(f"{state}#settings?connected=IG")
