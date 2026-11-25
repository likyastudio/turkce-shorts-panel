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


class EmptyImageError(RuntimeError):
    """Model görsel döndürmedi (çoğunlukla güvenlik filtresi: savaş/şiddet ifadeleri)."""


# Güvenlik filtresine takılan savaş promptlarını yumuşatmak için ikinci deneme eki.
SOFTEN_SUFFIX = (
    " Depict it as a tasteful museum-quality historical reenactment painting: non-graphic, no blood, no gore,"
    " no wounds, no killing shown, focus on scale, atmosphere, armor, banners, horses and landscape."
)


def generate_cover_image(prompt: str, aspect_ratio: str = "9:16", reference_image: Optional[bytes] = None) -> bytes:
    """Calls Vertex AI gemini-2.5-flash-image to generate an image.

    reference_image verilirse (ör. videodan bir kare) model sahneyi o kareden yola çıkarak yeniden çizer.
    """
    client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
    contents = prompt
    if reference_image:
        mime = "image/png" if reference_image[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        contents = [
            types.Part.from_bytes(data=reference_image, mime_type=mime),
            "Use the attached frame from the video as the scene and composition reference, "
            "and repaint it as a far more cinematic, detailed and dramatic image. " + prompt,
        ]
    
    cfg = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    )
    
    response = client.models.generate_content(
        model=VERTEX_IMAGE_MODEL,
        contents=contents,
        config=cfg,
    )
    
    cand = response.candidates[0] if response.candidates else None
    parts = (cand.content.parts if cand and cand.content else None) or []
    if not parts:
        reason = getattr(cand, "finish_reason", None) if cand else getattr(response, "prompt_feedback", None)
        raise EmptyImageError(f"Vertex AI görsel üretemedi (boş yanıt, sebep: {reason}).")

    for part in parts:
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
    """Retrieves PNG bytes for given key, GCS first (another instance may have regenerated it), local cache as fallback."""
    safe = _safe_key(key)
    local_path = os.path.join(LOCAL_CACHE_DIR, f"{safe}.png")
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

    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            return f.read()
    return None


def save_background(key: str, data: bytes) -> None:
    """Stores the text-free Vertex background so the headline can be changed later without regenerating."""
    safe = _safe_key(key)
    local_path = os.path.join(LOCAL_CACHE_DIR, f"bg__{safe}.img")
    with open(local_path, "wb") as f:
        f.write(data)
    try:
        storage.Client().bucket(GCS_BUCKET_NAME).blob(f"covers_bg/{safe}.png").upload_from_string(data, content_type="image/png")
    except Exception as e:
        print(f"[covers] GCS background upload warning (saved locally): {e}")


def get_background(key: str) -> Optional[bytes]:
    safe = _safe_key(key)
    try:
        blob = storage.Client().bucket(GCS_BUCKET_NAME).blob(f"covers_bg/{safe}.png")
        if blob.exists():
            return blob.download_as_bytes()
    except Exception as e:
        print(f"[covers] GCS background download error for {safe}: {e}")
    local_path = os.path.join(LOCAL_CACHE_DIR, f"bg__{safe}.img")
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            return f.read()
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
