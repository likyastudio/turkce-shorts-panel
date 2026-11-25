#!/usr/bin/env python3
"""Likya Studios Multi-Brand Claude Code Publisher CLI.
Uploads a locally rendered MP4 to Likya Cloud Run + GCS, uploads our own designed cover
(--cover-file, preferred) or generates a 9:16 Vertex AI cover thumbnail (--cover-prompt), schedules it into the brand's weekly 06:01-06:07 TR slot,
and immediately pre-schedules it in YouTube Studio (publishAt + custom thumbnail).

Usage:
  export LIKYA_API_KEY="YOUR_API_KEY"
  python3 likya_push.py \
    --brand kadimanadolu \
    --video out/video.mp4 \
    --title "Göbeklitepe'nin Gizli Sırrı! #shorts" \
    --desc "12 bin yıllık tapınak hakkında kimsenin bilmediği gerçek..." \
    --ig "12 bin yıllık sır! Kaydet & paylaş 👇 #reels #tarih #kadimanadolu" \
    --cover-file out/kapak.jpg \
    --cover-prompt "Dramatic 9:16 editorial illustration of ancient Gobeklitepe stone pillars at golden sunset, cinematic lighting, no text"
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
import requests

API_URL = os.getenv("LIKYA_API_URL", "https://likya-crosspost-api-64i7umkgnq-ew.a.run.app").rstrip("/")
VALID_BRANDS = ("akilalmaz", "kadimanadolu", "likyastudios", "foodballstv")


def load_api_key(cli_key: str) -> str:
    if cli_key:
        return cli_key.strip()
    if os.getenv("LIKYA_API_KEY"):
        return os.environ["LIKYA_API_KEY"].strip()
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("LIKYA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("HATA: LIKYA_API_KEY ortam değişkeni veya --api-key parametresi gerekli.")


def main() -> None:
    p = argparse.ArgumentParser(description="Likya Studios 4-Marka Otomatik Video Yükleyici (Claude Code CLI)")
    p.add_argument("--brand", required=True, choices=VALID_BRANDS, help="Hedef marka")
    p.add_argument("--video", required=True, help="Yerel .mp4 dosya yolu")
    p.add_argument("--title", required=True, help="YouTube Shorts başlığı")
    p.add_argument("--desc", default="", help="YouTube Shorts açıklaması")
    p.add_argument("--ig", default="", help="Instagram Reels açıklaması (boşsa YT açıklaması kullanılır)")
    p.add_argument("--video-id", default="", help="Özel video slug (opsiyonel)")
    p.add_argument("--cover-file", default="", help="Kendi tasarım kapağımız (kapak.jpg/png, 1080x1920). Verilirse stüdyoya bu yüklenir; öncelikli.")
    p.add_argument("--cover-prompt", default="", help="Yedek: Vertex AI 9:16 kapak promptu (kapak dosyası yoksa veya yüklenemezse kullanılır)")
    p.add_argument("--scheduled-at", default="", help="Özel ISO tarih/saat (örn. 2026-11-26T06:04:00+03:00). Boşsa 06:01-06:07 TR otomatik seçilir.")
    p.add_argument("--no-yt-sync", action="store_true", help="YouTube Studio ön-yüklemesini atla")
    p.add_argument("--api-key", default="", help="X-API-Key (opsiyonel, LIKYA_API_KEY env'den okunur)")
    args = p.parse_args()

    mp4 = Path(args.video)
    if not mp4.is_file():
        sys.exit(f"HATA: Video dosyası bulunamadı: {mp4}")

    api_key = load_api_key(args.api_key)
    hdr = {"X-API-Key": api_key}

    print(f"[1/3] MP4 yükleniyor ({args.brand} · {mp4.name})...")
    with mp4.open("rb") as f:
        r_up = requests.post(
            f"{API_URL}/api/media/upload",
            headers=hdr,
            data={"brand": args.brand, "video_id": args.video_id},
            files={"file": (mp4.name, f, "video/mp4")},
            timeout=300,
        )
    r_up.raise_for_status()
    up = r_up.json()
    vid = up["video_id"]
    video_url = up["video_url"]
    print(f"  ✓ Yüklendi ({up['size_mb']} MB): {video_url}")

    cover_url = None
    if args.cover_file.strip():
        cov = Path(args.cover_file)
        if not cov.is_file():
            sys.exit(f"HATA: Kapak dosyası bulunamadı: {cov}")
        print(f"[2/3] Kendi kapağımız yükleniyor ({cov.name} → {vid})...")
        mime = "image/png" if cov.suffix.lower() == ".png" else "image/jpeg"
        with cov.open("rb") as f:
            r_cov = requests.post(
                f"{API_URL}/api/covers/upload",
                headers=hdr,
                data={"key": vid},
                files={"file": (cov.name, f, mime)},
                timeout=120,
            )
        if r_cov.status_code == 404 or r_cov.status_code == 405:
            print("  ! Stüdyo API'sinde /api/covers/upload henüz yok (yeni sürüm yayına alınmamış).")
        else:
            r_cov.raise_for_status()
            cover_url = r_cov.json()["image_url"].split("?")[0]
            print(f"  ✓ Kapak yüklendi: {cover_url}")

    if cover_url is None and args.cover_prompt.strip():
        print(f"[2/3] Vertex AI 9:16 kapak üretiliyor ({vid})...")
        r_cov = requests.post(
            f"{API_URL}/api/covers/generate",
            headers={**hdr, "Content-Type": "application/json"},
            json={"key": vid, "prompt": args.cover_prompt.strip(), "aspect_ratio": "9:16"},
            timeout=120,
        )
        r_cov.raise_for_status()
        cover_url = r_cov.json()["image_url"].split("?")[0]
        print(f"  ✓ Kapak hazır: {cover_url}")
    elif cover_url is None:
        print("[2/3] Kapak verilmedi, atlandı.")

    print(f"[3/3] {args.brand} yayın kuyruğuna planlanıyor...")
    payload = {
        "brand": args.brand,
        "video_id": vid,
        "video_url": video_url,
        "title": args.title,
        "description": args.desc or args.title,
        "ig_caption": args.ig or args.desc or args.title,
        "cover_url": cover_url,
        "auto_next_slot": not bool(args.scheduled_at),
        "scheduled_at": args.scheduled_at or None,
        "sync_youtube_now": not args.no_yt_sync,
    }
    r_sch = requests.post(
        f"{API_URL}/api/schedule",
        headers={**hdr, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    r_sch.raise_for_status()
    post = r_sch.json()["post"]
    print(f"  ✓ Planlandı! Marka: {post['brand']} | Saat: {post['label_tr']} | Kayıt #{post['id']}")
    print("  ✓ YouTube Studio ön-planlama + 7/24 Instagram zamanlayıcı aktif!")


if __name__ == "__main__":
    main()
