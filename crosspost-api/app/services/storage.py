"""Google Cloud Storage upload + v4 Signed URL helper, plus HTTP video fetcher for Cloud Run."""
from __future__ import annotations
import os
import tempfile
import uuid
from datetime import timedelta
import requests
from google.cloud import storage

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "likya-temp-videos")


def download_video_to_tmp(video_url: str, video_id: str) -> str:
    """Downloads a remote MP4 (e.g., from GitHub Pages or GCS) to /tmp for Cloud Run processing."""
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in video_id)
    out_path = os.path.join(tempfile.gettempdir(), f"{safe_id}_{uuid.uuid4().hex[:8]}.mp4")
    with requests.get(video_url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 512):
                if chunk:
                    f.write(chunk)
    return out_path


def upload_to_gcs_and_get_signed_url(local_path: str, destination_blob_name: str, ttl_hours: int = 1) -> str:
    """Uploads local MP4 to GCS temp bucket and returns a v4 Signed URL for Instagram Graph API."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_path, content_type="video/mp4")

    # Signed URL (v4) when a signing key / IAM signBlob is available; fallback to public URL if bucket is public.
    try:
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=ttl_hours),
            method="GET",
        )
    except Exception:
        blob.make_public()
        return blob.public_url
