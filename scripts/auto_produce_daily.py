#!/usr/bin/env python3
"""AKILALMAZ — Tam Otonom Günlük YouTube Shorts & Instagram Reels Üreticisi.
Akış:
1. Cloud Run /api/ai/generate-story (Vertex AI Gemini) ile özgün Türkçe senaryo + metadata üretir.
2. ElevenLabs (ERKAN sesi) ile seslendirme + kelime zaman damgaları (timestamps) alır.
3. Cloud Run /api/covers/generate (Vertex AI) ile 9:16 kapak & arka plan illüstrasyonu üretir.
4. FFmpeg + Pillow ile 1080x1920 dikey, Ken Burns hareketli, senkron Türkçe altyazılı ve
   kısık fon müzikli (-12 dB) MP4 üretir.
5. videos.json dosyasını günceller ve Cloud Run /api/schedule (auto_next_slot=true) ile
   haftalık 06:01-06:07 TR kuralına göre sıradaki güne otomatik planlar.
"""
from __future__ import annotations
import base64
import json
import time
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

API_URL = os.getenv("LIKYA_API_URL", "https://likya-crosspost-api-64i7umkgnq-ew.a.run.app").rstrip("/")
API_KEY = os.environ["LIKYA_API_KEY"].strip()
EL_KEY = os.environ["ELEVENLABS_API_KEY"].strip()
EL_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "gsfAMpj9oiFONXfvZJoE")  # ERKAN
EL_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
SITE_BASE = os.getenv("SITE_BASE_URL", "https://studio.likyastudios.live").rstrip("/")
TOPIC_HINT = os.getenv("TOPIC_HINT", "").strip()
AUTO_SCHEDULE = os.getenv("AUTO_SCHEDULE", "true").lower() == "true"

REPO_DIR = Path(__file__).resolve().parent.parent
VIDEOS_JSON = REPO_DIR / "videos.json"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def load_videos() -> list[dict]:
    if VIDEOS_JSON.exists():
        return json.loads(VIDEOS_JSON.read_text(encoding="utf-8"))
    return []


def next_video_number(videos: list[dict]) -> int:
    mx = 0
    for v in videos:
        m = re.match(r"^v(\d+)_", v.get("slug", ""))
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def fetch_story(existing_titles: list[str]) -> dict:
    r = requests.post(
        f"{API_URL}/api/ai/generate-story",
        headers=HEADERS,
        json={"existing_titles": existing_titles, "topic_hint": TOPIC_HINT},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["story"]


def synthesize_elevenlabs(text: str, out_mp3: Path) -> tuple[float, list[dict]]:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOICE_ID}/with-timestamps"
    r = requests.post(
        url,
        headers={"xi-api-key": EL_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": EL_MODEL,
            "voice_settings": {"stability": 0.48, "similarity_boost": 0.80, "style": 0.35},
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    audio_bytes = base64.b64decode(data["audio_base64"])
    out_mp3.write_bytes(audio_bytes)

    # Build word-level chunks from character alignment
    align = data.get("alignment") or data.get("normalized_alignment") or {}
    chars = align.get("characters", [])
    starts = align.get("character_start_times_seconds", [])
    ends = align.get("character_end_times_seconds", [])

    words: list[dict] = []
    cur_w, w_start, w_end = [], None, None
    for ch, st, en in zip(chars, starts, ends):
        if ch.strip():
            if w_start is None:
                w_start = st
            cur_w.append(ch)
            w_end = en
        else:
            if cur_w:
                words.append({"word": "".join(cur_w), "start": w_start, "end": w_end})
                cur_w, w_start, w_end = [], None, None
    if cur_w:
        words.append({"word": "".join(cur_w), "start": w_start, "end": w_end})

    # Probe exact duration via ffprobe
    dur_str = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out_mp3)],
        text=True,
    ).strip()
    duration = float(dur_str)
    return duration, words


def generate_cover_and_download(slug: str, prompt: str, out_png: Path) -> str:
    r = requests.post(
        f"{API_URL}/api/covers/generate",
        headers=HEADERS,
        json={"key": slug, "prompt": prompt, "aspect_ratio": "9:16"},
        timeout=120,
    )
    r.raise_for_status()
    img_url = r.json()["image_url"]
    img_resp = requests.get(img_url, timeout=60)
    img_resp.raise_for_status()
    out_png.write_bytes(img_resp.content)
    return img_url


def build_ass_subtitles(words: list[dict], title: str, out_ass: Path) -> None:
    """Creates bold, high-contrast centered Turkish Shorts subtitles (3 words per chunk)."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,78,&H00FFFFFF,&H0030B8F2,&H000A0A0A,&H96000000,-1,0,0,0,100,100,0,0,1,6,3,2,70,70,380,1
Style: TopTag,DejaVu Sans,44,&H0030B8F2,&H00FFFFFF,&H000A0A0A,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,8,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def ts(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    lines = [header]
    total_end = (words[-1]["end"] + 0.5) if words else 45.0
    safe_title = title.replace("{", "").replace("}", "").upper()
    lines.append(f"Dialogue: 0,0:00:00.00,{ts(total_end)},TopTag,,0,0,0,,AKILALMAZ · {safe_title}\n")

    chunk_size = 3
    for i in range(0, len(words), chunk_size):
        grp = words[i : i + chunk_size]
        st = max(0.0, grp[0]["start"] - 0.04)
        en = grp[-1]["end"] + 0.06
        txt = " ".join(w["word"] for w in grp).upper().replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{ts(st)},{ts(en)},Default,,0,0,0,,{txt}\n")

    out_ass.write_text("".join(lines), encoding="utf-8")


def render_mp4(bg_png: Path, voice_mp3: Path, ass_path: Path, duration: float, out_mp4: Path) -> None:
    """Renders 1080x1920 30fps vertical Short with gentle Ken Burns zoom, subtle vignette,
    synced Turkish ASS captions, ERKAN voiceover, and soft ambient synth bed at -12 dB."""
    total_dur = duration + 0.6
    # Normalize background to crisp 1080x1920 with subtle dark bottom gradient for caption legibility
    im = Image.open(bg_png).convert("RGB")
    target_w, target_h = 1080, 1920
    scale = max(target_w / im.width, target_h / im.height)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.Resampling.LANCZOS)
    left = (im.width - target_w) // 2
    top = (im.height - target_h) // 2
    im = im.crop((left, top, left + target_w, top + target_h))

    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(int(target_h * 0.55), target_h):
        alpha = int(175 * ((y - target_h * 0.55) / (target_h * 0.45)))
        draw.line([(0, y), (target_w, y)], fill=(8, 10, 14, alpha))
    for y in range(0, 260):
        alpha = int(130 * (1 - y / 260))
        draw.line([(0, y), (target_w, y)], fill=(8, 10, 14, alpha))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    prep_png = bg_png.parent / "bg_prepared.png"
    im.save(prep_png, "PNG")

    frames = int(math.ceil(total_dur * 30))
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

    # Gentle Ken Burns zoom + ASS captions + voice + subtle warm ambient pad (-24 dB relative to 0dBFS ≈ -12dB music bed)
    vf = (
        f"scale=1200:2134,"
        f"zoompan=z='min(zoom+0.0005,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30,"
        f"ass='{ass_escaped}',format=yuv420p"
    )
    af = (
        f"[1:a]loudnorm=I=-15.5:TP=-1.5:LRA=9[v];"
        f"aevalsrc=0.04*sin(2*PI*110*t)+0.025*sin(2*PI*164.81*t)+0.02*sin(2*PI*220*t):s=44100:d={total_dur:.2f},"
        f"lowpass=f=420,volume=-12dB,afade=t=in:st=0:d=1.2,afade=t=out:st={max(0, total_dur-1.2):.2f}:d=1.2[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[aout]"
    )

    cmd = [
        "ffmpeg", "-y", "-v", "warning",
        "-loop", "1", "-i", str(prep_png),
        "-i", str(voice_mp3),
        "-filter_complex", f"[0:v]{vf}[vout];{af}",
        "-map", "[vout]", "-map", "[aout]",
        "-t", f"{total_dur:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    videos = load_videos()
    existing_titles = [v.get("title", "") for v in videos]
    vnum = next_video_number(videos)

    print(f"[1/5] Vertex AI Gemini ile Video {vnum} senaryosu üretiliyor...")
    story = fetch_story(existing_titles)
    slug = f"v{vnum}_{story['slug_suffix']}"
    title = story["title"]
    script_text = story["script"]
    print(f"  -> {slug}: {title}")

    out_dir = REPO_DIR / "files" / slug
    (out_dir / "out").mkdir(parents=True, exist_ok=True)
    (out_dir / "work").mkdir(parents=True, exist_ok=True)

    safe_fname = re.sub(r"[^a-zA-Z0-9\-]", "-", f"Video{vnum}-{story['slug_suffix']}")
    safe_fname = re.sub(r"-+", "-", safe_fname).strip("-") + ".mp4"
    mp4_path = out_dir / "out" / safe_fname
    voice_path = out_dir / "work" / "voice.mp3"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        print("[2/5] ElevenLabs (ERKAN) seslendirme üretiliyor...")
        duration, words = synthesize_elevenlabs(script_text, voice_path)
        print(f"  -> Süre: {duration:.1f}s, {len(words)} kelime")

        print("[3/5] Vertex AI 9:16 kapak & sahne görseli üretiliyor...")
        bg_png = tmp_dir / "cover.png"
        cover_url = generate_cover_and_download(slug, story["flow_prompt"], bg_png)
        print(f"  -> Kapak URL: {cover_url}")

        print("[4/5] 1080x1920 MP4 render ediliyor...")
        ass_path = tmp_dir / "captions.ass"
        build_ass_subtitles(words, title, ass_path)
        render_mp4(bg_png, voice_path, ass_path, duration, mp4_path)

    size_mb = round(mp4_path.stat().st_size / (1024 * 1024), 1)
    now_iso = datetime.now(timezone.utc).isoformat()
    video_rel = f"files/{slug}/out/{safe_fname}"
    voice_rel = f"files/{slug}/work/voice.mp3"

    entry = {
        "slug": slug,
        "title": title,
        "status": "Hazır",
        "video": video_rel,
        "fileName": safe_fname,
        "duration": round(duration + 0.6, 1),
        "width": 1080,
        "height": 1920,
        "sizeMB": size_mb,
        "words": len(script_text.split()),
        "script": script_text,
        "voice": voice_rel,
        "updated": now_iso,
        "meta": {
            "youtube": story.get("youtube", {"title": f"{title} #shorts", "description": script_text[:180]}),
            "instagram": story.get("instagram", {"caption": script_text[:180]}),
            "flow_prompt": story.get("flow_prompt", ""),
        },
    }
    videos.append(entry)
    VIDEOS_JSON.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[5/5] videos.json güncellendi ({len(videos)} video).")

    if AUTO_SCHEDULE:
        video_abs_url = f"{SITE_BASE}/{video_rel}"
        # Planlama, MP4 siteye çıktıktan sonra ayrı adımda yapılır (schedule_pending); yoksa YouTube
        # yüklemesi henüz yayında olmayan dosyayı isteyip 404 alıyordu.
        PENDING.write_text(json.dumps({
            "brand": "akilalmaz",
            "video_id": slug,
            "video_url": video_abs_url,
            "title": entry["meta"]["youtube"]["title"],
            "description": entry["meta"]["youtube"]["description"],
            "ig_caption": entry["meta"]["instagram"]["caption"],
            "cover_url": cover_url,
            "auto_next_slot": True,
        }, ensure_ascii=False), encoding="utf-8")
        print("  -> Planlama, video siteye çıkınca yapılacak.")


PENDING = Path(tempfile.gettempdir()) / "likya_pending_schedule.json"


def schedule_pending():
    if not PENDING.exists():
        print("Planlanacak video yok.")
        return
    payload = json.loads(PENDING.read_text(encoding="utf-8"))
    for _ in range(40):  # GitHub Pages yayını için en fazla ~10 dk bekle
        try:
            if requests.head(payload["video_url"], timeout=20, allow_redirects=True).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(15)
    else:
        raise SystemExit("Video siteye çıkmadı; planlama yapılmadı.")
    r = requests.post(f"{API_URL}/api/schedule", headers=HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    post = r.json()["post"]
    print(f"  -> Otomatik planlandı: {post['label_tr']} (ID #{post['id']})")


if __name__ == "__main__":
    if "--schedule-pending" in sys.argv:
        schedule_pending()
    else:
        main()
