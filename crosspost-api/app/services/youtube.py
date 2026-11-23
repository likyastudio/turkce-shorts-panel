"""YouTube Data API v3 resumable Shorts upload with automatic OAuth token refresh."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


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
    on_token_refresh: Optional[Callable[[str, Optional[str]], None]] = None,
) -> dict:
    """Uploads an MP4 to YouTube Shorts via resumable upload.
    If publish_at is a future ISO timestamp, uploads as private + publishAt so it appears
    as 'Planlandı (Scheduled)' immediately inside YouTube Studio.
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

    return {
        "platform": "YT",
        "status": "YT Planlandı" if norm_publish_at else "Yayında",
        "video_id": yt_id,
        "publish_at": norm_publish_at,
        "url": f"https://youtube.com/shorts/{yt_id}",
    }
