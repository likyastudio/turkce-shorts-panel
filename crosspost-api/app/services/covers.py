"""Vertex AI Image Generation Service & Cover Storage (GCS + Cache).
Generates vertical Shorts covers (9:16), channel avatars (1:1), and banners (16:9)
using Google GenAI (gemini-2.5-flash-image) on Vertex AI.
"""
from __future__ import annotations
import os
import re
from typing import Optional
from google import genai
from google.genai import types
from google.cloud import storage

VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "likyastudios")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
VERTEX_IMAGE_MODEL = os.getenv("VERTEX_IMAGE_MODEL", "gemini-2.5-flash-image")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "likya-temp-videos-likyastudios")

LOCAL_CACHE_DIR = "/tmp/covers"
os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)


def _safe_key(key: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", key.strip().lower())
    return cleaned.strip("_") or "cover"


def generate_cover_image(prompt: str, aspect_ratio: str = "9:16") -> bytes:
    """Calls Vertex AI gemini-2.5-flash-image to generate an image."""
    client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
    
    cfg = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    )
    
    response = client.models.generate_content(
        model=VERTEX_IMAGE_MODEL,
        contents=prompt,
        config=cfg,
    )
    
    if not response.candidates or not response.candidates[0].content:
        raise RuntimeError("Vertex AI görsel üretemedi (boş yanıt).")
    
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            return part.inline_data.data
            
    raise RuntimeError("Vertex AI yanıtında görsel verisi bulunamadı.")


def save_cover(key: str, data: bytes) -> str:
    """Saves generated PNG bytes to GCS under covers/{safe_key}.png and local cache."""
    safe = _safe_key(key)
    local_path = os.path.join(LOCAL_CACHE_DIR, f"{safe}.png")
    with open(local_path, "wb") as f:
        f.write(data)
        
    blob_name = f"covers/{safe}.png"
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path, content_type="image/png")
    except Exception as e:
        print(f"[covers] GCS upload warning (saved locally): {e}")
        
    return safe


def get_cover(key: str) -> Optional[bytes]:
    """Retrieves PNG bytes for given key from local cache or GCS."""
    safe = _safe_key(key)
    local_path = os.path.join(LOCAL_CACHE_DIR, f"{safe}.png")
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            return f.read()
            
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"covers/{safe}.png")
        if blob.exists():
            data = blob.download_as_bytes()
            with open(local_path, "wb") as f:
                f.write(data)
            return data
    except Exception as e:
        print(f"[covers] GCS download error for {safe}: {e}")
        
    return None


def list_covers() -> list[str]:
    """Returns list of safe keys that have saved covers in GCS and/or local cache."""
    keys = set()
    # Check local cache
    if os.path.isdir(LOCAL_CACHE_DIR):
        for fname in os.listdir(LOCAL_CACHE_DIR):
            if fname.endswith(".png"):
                keys.add(fname[:-4])
                
    # Check GCS bucket
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blobs = bucket.list_blobs(prefix="covers/")
        for b in blobs:
            base = os.path.basename(b.name)
            if base.endswith(".png"):
                keys.add(base[:-4])
    except Exception as e:
        print(f"[covers] GCS list warning: {e}")
        
    return sorted(list(keys))
