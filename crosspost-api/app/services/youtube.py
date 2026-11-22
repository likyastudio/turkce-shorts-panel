"""YouTube Data API v3 resumable Shorts upload with automatic OAuth token refresh."""
from __future__ import annotations
from typing import Callable, Optional
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


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
    on_token_refresh: Optional[Callable[[str, Optional[str]], None]] = None,
) -> dict:
    """Uploads an MP4 to YouTube Shorts via resumable upload and returns the published Shorts URL."""
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
    body = {
        "snippet": {
            "title": title[:100],
            "description": desc[:5000],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
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
        "status": "Yayında",
        "video_id": yt_id,
        "url": f"https://youtube.com/shorts/{yt_id}",
    }
