"""YouTube Data API v3 resumable Shorts upload with automatic OAuth token refresh."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import io
from typing import Callable, Optional
import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload


def _prepare_thumbnail_bytes(cover_url: str) -> tuple[bytes, str]:
    """Downloads cover image and converts to crisp JPEG under YouTube's 2 MB thumbnail limit."""
    r = requests.get(cover_url, timeout=30)
    r.raise_for_status()
    raw = r.content
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return raw, r.headers.get("Content-Type", "image/png").split(";")[0]


def _set_thumbnail_safe(youtube, yt_video_id: str, cover_url: Optional[str]) -> tuple[bool, Optional[str]]:
    if not cover_url:
        return False, None
    try:
        data, mime = _prepare_thumbnail_bytes(cover_url)
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
        youtube.thumbnails().set(videoId=yt_video_id, media_body=media).execute()
        return True, None
    except Exception as e:
        return False, str(e)[:300]


def apply_youtube_thumbnail(
    yt_video_id: str,
    cover_url: str,
    access_token: str,
    refresh_token: Optional[str],
    client_id: str,
    client_secret: str,
    on_token_refresh: Optional[Callable[[str, Optional[str]], None]] = None,
) -> dict:
    """Applies a custom thumbnail to an existing YouTube video."""
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        if on_token_refresh:
            exp = creds.expiry.isoformat() if creds.expiry else None
            on_token_refresh(creds.token, exp)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    ok, err = _set_thumbnail_safe(youtube, yt_video_id, cover_url)
    return {"ok": ok, "video_id": yt_video_id, "error": err}


def _normalize_publish_at(publish_at: Optional[str]) -> Optional[str]:
    """Converts ISO timestamp to YouTube RFC 3339 UTC format (YYYY-MM-DDTHH:MM:SSZ) if in the future."""
    if not publish_at:
        return None
    dt = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    if dt_utc <= datetime.now(timezone.utc) + timedelta(seconds=45):
        return None
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def publish_to_youtube(
    local_file_path: str,
    title: str,
    description: str,
    access_token: str,
    refresh_token: Optional[str],
    client_id: str,
    client_secret: str,
    category_id: str = "24",  # 24 = Entertainment (Shorts optimum)
    privacy_status: str = "public",
    publish_at: Optional[str] = None,
    cover_url: Optional[str] = None,
    on_token_refresh: Optional[Callable[[str, Optional[str]], None]] = None,
) -> dict:
    """Uploads an MP4 to YouTube Shorts via resumable upload.
    If publish_at is a future ISO timestamp, uploads as private + publishAt so it appears
    as 'Planlandı (Scheduled)' immediately inside YouTube Studio.
    If cover_url is given, attempts thumbnails.set safely (non-fatal if channel lacks verification).
    """
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        if on_token_refresh:
            exp = creds.expiry.isoformat() if creds.expiry else None
            on_token_refresh(creds.token, exp)

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    desc = description if "#shorts" in description.lower() else f"{description}\n\n#Shorts"
    norm_publish_at = _normalize_publish_at(publish_at)

    status_obj = {
        "privacyStatus": "private" if norm_publish_at else privacy_status,
        "selfDeclaredMadeForKids": False,
    }
    if norm_publish_at:
        status_obj["publishAt"] = norm_publish_at

    body = {
        "snippet": {
            "title": title[:100],
            "description": desc[:5000],
            "categoryId": category_id,
        },
        "status": status_obj,
    }

    media = MediaFileUpload(local_file_path, chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _status, response = req.next_chunk()

    yt_id = response.get("id")
    if not yt_id:
        raise RuntimeError(f"YouTube upload response missing video id: {response}")

    thumb_ok, thumb_err = _set_thumbnail_safe(youtube, yt_id, cover_url)

    return {
        "platform": "YT",
        "status": "YT Planlandı" if norm_publish_at else "Yayında",
        "video_id": yt_id,
        "publish_at": norm_publish_at,
        "thumbnail_applied": thumb_ok,
        "thumbnail_error": thumb_err,
        "url": f"https://youtube.com/shorts/{yt_id}",
    }


def fetch_youtube_analytics(
    access_token: str,
    refresh_token: Optional[str],
    client_id: str,
    client_secret: str,
    max_videos: int = 35,
    on_token_refresh: Optional[Callable[[str, Optional[str]], None]] = None,
) -> dict:
    """Fetches channel summary and per-video live views/likes/comments using YouTube Data API v3."""
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        if on_token_refresh:
            exp = creds.expiry.isoformat() if creds.expiry else None
            on_token_refresh(creds.token, exp)

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    ch_resp = youtube.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    ch_items = ch_resp.get("items") or []
    if not ch_items:
        return {"platform": "YT", "channel": None, "videos": []}

    ch = ch_items[0]
    ch_snip = ch.get("snippet") or {}
    ch_stats = ch.get("statistics") or {}
    uploads_pl = (ch.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
    ch_thumbs = ch_snip.get("thumbnails") or {}
    ch_thumb = (ch_thumbs.get("medium") or ch_thumbs.get("default") or {}).get("url")

    channel_info = {
        "id": ch.get("id"),
        "title": (ch_snip.get("title") or "").strip(),
        "custom_url": ch_snip.get("customUrl") or "",
        "thumbnail": ch_thumb,
        "subscribers": int(ch_stats.get("subscriberCount") or 0),
        "total_views": int(ch_stats.get("viewCount") or 0),
        "video_count": int(ch_stats.get("videoCount") or 0),
    }

    video_ids: list[str] = []
    if uploads_pl:
        pl_resp = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_pl,
            maxResults=min(50, max(1, max_videos)),
        ).execute()
        for it in pl_resp.get("items") or []:
            vid = (it.get("contentDetails") or {}).get("videoId")
            if vid:
                video_ids.append(vid)

    videos: list[dict] = []
    if video_ids:
        v_resp = youtube.videos().list(
            part="snippet,statistics,status,contentDetails",
            id=",".join(video_ids[:50]),
        ).execute()
        for item in v_resp.get("items") or []:
            vid = item.get("id")
            sn = item.get("snippet") or {}
            st = item.get("statistics") or {}
            status = item.get("status") or {}
            thumbs = sn.get("thumbnails") or {}
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
            privacy = status.get("privacyStatus") or "public"
            pub_at = status.get("publishAt")
            is_scheduled = privacy == "private" and bool(pub_at)
            views = int(st.get("viewCount") or 0)
            likes = int(st.get("likeCount") or 0)
            comments = int(st.get("commentCount") or 0)
            videos.append({
                "platform": "YT",
                "video_id": vid,
                "title": sn.get("title") or "",
                "thumbnail": thumb,
                "url": f"https://youtube.com/shorts/{vid}",
                "published_at": sn.get("publishedAt"),
                "publish_at": pub_at,
                "privacy_status": privacy,
                "state": "Planlandı" if is_scheduled else ("Yayında" if privacy == "public" else privacy),
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_rate": round(((likes + comments) / views) * 100, 2) if views > 0 else 0.0,
                "duration": (item.get("contentDetails") or {}).get("duration") or "",
            })

    return {"platform": "YT", "channel": channel_info, "videos": videos}

