"""Meta Instagram Graph API v21.0 Reels publishing service (container -> polling -> publish -> permalink)."""
from __future__ import annotations
import os
import time
from typing import Optional
import requests

IG_GRAPH_BASE_URL = os.getenv("IG_GRAPH_BASE_URL", "https://graph.facebook.com/v21.0")


def publish_to_instagram(
    video_url: str,
    caption: str,
    ig_user_id: str,
    ig_access_token: str,
    thumb_offset_ms: Optional[int] = None,
    cover_url: Optional[str] = None,
    poll_interval_sec: float = 5.0,
    max_polls: int = 24,
) -> dict:
    """Creates an IG Reels media container, polls until FINISHED, publishes it, and returns the permalink."""
    # 1. Create Reels Media Container
    create_url = f"{IG_GRAPH_BASE_URL}/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption[:2200],
        "share_to_feed": "true",
        "access_token": ig_access_token,
    }
    if cover_url:
        ig_cover = cover_url
        if "/api/covers/" in ig_cover and ig_cover.lower().endswith(".png"):
            ig_cover = ig_cover[:-4] + ".jpg"
        payload["cover_url"] = ig_cover
    elif thumb_offset_ms is not None and thumb_offset_ms >= 0:
        payload["thumb_offset"] = str(int(thumb_offset_ms))

    res = requests.post(create_url, data=payload, timeout=30).json()
    if "id" not in res:
        raise RuntimeError(f"IG Container Hatası: {res}")
    creation_id = res["id"]

    # 2. Poll container processing status
    status_url = f"{IG_GRAPH_BASE_URL}/{creation_id}"
    for _ in range(max_polls):
        time.sleep(poll_interval_sec)
        st = requests.get(
            status_url,
            params={"fields": "status_code,status", "access_token": ig_access_token},
            timeout=20,
        ).json()
        code = st.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"IG Video İşleme Hatası: {st}")
    else:
        raise RuntimeError("IG Video işleme zaman aşımına uğradı.")

    # 3. Publish the Reels container
    pub_res = requests.post(
        f"{IG_GRAPH_BASE_URL}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": ig_access_token},
        timeout=30,
    ).json()
    if "id" not in pub_res:
        raise RuntimeError(f"IG Yayınlama Hatası: {pub_res}")
    media_id = pub_res["id"]

    # 4. Fetch permalink (best-effort)
    permalink = f"https://www.instagram.com/reel/"
    try:
        meta = requests.get(
            f"{IG_GRAPH_BASE_URL}/{media_id}",
            params={"fields": "permalink", "access_token": ig_access_token},
            timeout=15,
        ).json()
        if meta.get("permalink"):
            permalink = meta["permalink"]
    except Exception:
        pass

    return {
        "platform": "IG",
        "status": "Yayında",
        "media_id": media_id,
        "url": permalink,
    }
