#!/usr/bin/env python3
"""AKILALMAZ Video 21 — 2 Aralık 1942: Stadyum Altında Baltayla Kurulan İlk Nükleer Reaktör (Chicago Pile-1 / SCRAM).

v1–v20 AKILALMAZ 3D-toon + 2D çöp adam çizgi film tarzıyla birebir uyumlu 1080x1920 30fps üretim motoru:
- ElevenLabs ERKAN klon sesi (voice_id: gsfAMpj9oiFONXfvZJoE, model: eleven_v4) + kelime zaman damgaları
- Canlı, neşeli marimba/Rhodes/bas/davul fon müziği (--music-db -12.0) + senkron çizgi film ses efektleri
- Three.js 3D-toon sahne + kalın konturlu 2D çöp adam karakterler (Enrico Fermi, Baltalı Adam Norman Hilberry, İntihar Timi)
- Kelime senkron gömülü kalın konturlu Türkçe altyazı + 6x3 QA Sheet
- Cloud Run /api/covers/generate ile 9:16 Vertex AI kapak üretimi
- studio.likyastudios.live videos.json güncellemesi + opsiyonel 2 Aralık 2026 06:03 TR planlama
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import synth_bgm_sfx  # noqa: E402

# ---------------------------------------------------------------------------
# Video 21 Metadata & Script (2 Aralık 1942 — Chicago Pile-1 / SCRAM!)
# ---------------------------------------------------------------------------
SLUG = "v21_stadyum_nukleer_reaktor"
OLD_V21_SLUG = "v21_kendi_kendine_savas"
FILE_NAME = "Video21-Stadyum-Altindaki-Ilk-Nukleer-Reaktor.mp4"
TITLE = "Stadyum Altında Baltayla Kurulan İlk Nükleer Reaktör"
SCHEDULED_AT_UTC = "2026-12-02T03:03:00+00:00"  # 02.12.2026 Çar · 06:03 TR

# Expressive Eleven v4 narration script with inline performance direction tags
# (tags in [...] are automatically stripped before rendering Turkish captions)
TTS_SCRIPT = (
    "[excited] Dünyanın ilk nükleer reaktörünün, bir üniversite stadyumunun altında ve elinde balta tutan bir adamla çalıştırıldığını biliyor muydunuz?\n"
    "[amused] Şaka yapmıyorum, acil durum düğmesi yoktu, sadece kalın bir halat ve keskin bir balta vardı!\n"
    "[storytelling] İki Aralık bin dokuz yüz kırk ikide, Nobel ödüllü fizikçi Enrico Fermi, Chicago Üniversitesi stadyumunun altındaki eski tenis kortuna gizlice dev bir nükleer reaktör kurdu!\n"
    "[curious] Üstelik ne soğutma sistemi ne de koruma duvarı vardı; dört yüz ton grafit tuğlayı üst üste yığdılar.\n"
    "[amused, chuckles] Peki işler ters giderse ne olacaktı?\n"
    "[excited] Balkonda bekleyen güvenlik görevlisi, elindeki baltayla halatı kesip acil fren çubuğunu aşağı bırakacaktı!\n"
    "[surprised] Yetmedi; tepede üç bilim insanı ellerinde kovalarla bekliyordu! Reaktör taşarsa üzerine su döker gibi çözelti boşaltacaklardı!\n"
    "[excited] Saat üçü yirmi beş geçe nükleer çağ resmen başladı! Neyse ki baltaya gerek kalmadı ve başarıyı kâğıt bardaklarla sessizce kutladılar.\n"
    "[amused] Bugün tüm santrallerdeki \"SCRAM\" acil durdurma düğmesinin adı, hâlâ o \"Baltalı Adam\"dan gelir!\n"
    "[storytelling] İşte tarihin en çılgın deneyi şöyle anlatılır:"
)


def strip_v4_tags(text: str) -> str:
    cleaned = re.sub(r"\[[^\]]+\]\s*", "", text)
    return re.sub(r"[ \t]+", " ", cleaned).strip()


CLEAN_SCRIPT = strip_v4_tags(TTS_SCRIPT)

META = {
    "youtube": {
        "title": "Stadyum Altında Balta Tutan Adamla Kurulan İlk Nükleer Reaktör! 🪓☢️ #shorts",
        "description": (
            "2 Aralık 1942'de Nobel ödüllü fizikçi Enrico Fermi, Chicago Üniversitesi futbol stadyumunun "
            "altındaki eski squash kortunda dünyanın ilk nükleer reaktörü Chicago Pile-1'i çalıştırdı! "
            "Ne soğutma sistemi ne de radyasyon kalkanı vardı: Acil durum freni halata bağlı bir çubuktu "
            "ve balkonda elinde balta tutan Norman Hilberry bekliyordu! Bugün tüm nükleer santrallerdeki "
            "'SCRAM' acil durdurma düğmesinin adı bile işte o 'Baltalı Adam' (Safety Control Rod Axe Man) "
            "lakabından gelir!\n\n"
            "👇 2 Aralık 1942'de o stadyumun tribününde oturur muydun? Yorumlara yaz!\n\n"
            "#shorts #tarih #bilim #ilginçbilgiler #nükleer #scram #gerçekhikaye #animasyon #keşfet"
        ),
    },
    "instagram": {
        "caption": (
            "Dünyanın ilk nükleer reaktörü, bir futbol stadyumunun altında ELİNDE BALTA TUTAN BİR ADAMLA çalıştırıldı! 🪓☢️😂\n\n"
            "2 Aralık 1942'de Enrico Fermi ve ekibi Chicago Üniversitesi stadyumunun altına 400 ton grafit tuğla yığdı. "
            "Soğutma yoktu, koruma duvarı yoktu!\n\n"
            "İşler ters giderse balkondaki adam baltayla halatı kesip acil fren çubuğunu düşürecek, tepedeki 'İntihar Timi' ise "
            "kovalarla kadmiyum çözeltisi dökecekti! Bugün tüm santrallerdeki SCRAM düğmesinin adı hâlâ o 'Baltalı Adam'dan gelir!\n\n"
            "Bu absürt bilim tarihini arkadaşına gönder 👇\n\n"
            "#reels #keşfet #tarih #bilim #ilginçbilgiler #gerçekhikayeler #animasyon #akılalmaz"
        ),
    },
    "cover_title": "STADYUM ALTINDA BALTALI REAKTÖR!",
    "flow_prompt": (
        "Playful colorful 3D Pixar-style cartoon vertical poster, 9:16 aspect ratio. Inside a warm wooden "
        "1940s university stadium squash court, a gigantic stepped dark graphite-brick nuclear reactor pile "
        "glowing softly emerald green in the center with a thick red emergency control rod hanging from a "
        "taut rope above it. On the left a cheerful cartoon physicist with round glasses and white lab coat "
        "pointing excitedly, on the right a wide-eyed comical cartoon security guard in a blue cap nervously "
        "gripping a gleaming steel axe next to the rope, and two funny scientists peeking from above holding "
        "blue buckets. Vivid humorous 3D-toon animation style, warm dramatic spotlighting, NO text, NO words, "
        "NO letters, NO watermark."
    ),
}

OUT_DIR = REPO_DIR / "files" / SLUG / "out"
WORK_DIR = REPO_DIR / "files" / SLUG / "work"
VIDEOS_JSON = REPO_DIR / "videos.json"
SCENE_HTML = Path(__file__).resolve().parent / "v21_scene.html"

W, H = 1080, 1920
FPS = 30
VOICE_TEMPO = 1.10  # Snappy Shorts pacing (~58s total, comfortably under 60s!)

# Match exact sentence boundaries in scripts/v21_scene.html
SCENE_CUTS = [0.0, 0.209, 0.364, 0.465, 0.598, 0.718, 0.947]


# ---------------------------------------------------------------------------
# ElevenLabs ERKAN (eleven_v4) Voice Synthesis + Tag-Safe Word Timestamps
# ---------------------------------------------------------------------------
def parse_alignment_words(align: dict[str, Any]) -> list[dict[str, Any]]:
    """Builds clean spoken word chunks from ElevenLabs character alignment, stripping [...] tags."""
    chars = align.get("characters") or []
    starts = align.get("character_start_times_seconds") or []
    ends = align.get("character_end_times_seconds") or []

    words: list[dict[str, Any]] = []
    cur: list[str] = []
    w_st: float | None = None
    w_en: float | None = None
    in_bracket = False

    for ch, st, en in zip(chars, starts, ends):
        if ch == "[":
            if cur and w_st is not None and w_en is not None:
                words.append({"word": "".join(cur), "start": w_st, "end": w_en})
                cur, w_st, w_en = [], None, None
            in_bracket = True
            continue
        if ch == "]":
            in_bracket = False
            continue
        if in_bracket:
            continue

        if ch.strip():
            if w_st is None:
                w_st = float(st)
            cur.append(ch)
            w_en = float(en)
        else:
            if cur and w_st is not None and w_en is not None:
                words.append({"word": "".join(cur), "start": w_st, "end": w_en})
                cur, w_st, w_en = [], None, None

    if cur and w_st is not None and w_en is not None:
        words.append({"word": "".join(cur), "start": w_st, "end": w_en})

    # Safety filter against any stray bracket fragments
    return [w for w in words if w["word"] and not w["word"].startswith("[")]


def synthesize_erkan_voice(text: str, out_mp3: Path) -> tuple[float, list[dict[str, Any]]]:
    import requests

    el_key = os.environ["ELEVENLABS_API_KEY"].strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "jdpQqF5lMnLWcXlPOnAU")  # erkanv2 (ERKAN)
    model_id = os.getenv("ELEVENLABS_MODEL", "eleven_v4")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"xi-api-key": el_key, "Content-Type": "application/json"}

    # Try eleven_v4 with expressive stability (0.40); fallback cleanly to default settings if needed
    payloads = [
        {
            "text": text,
            "model_id": model_id,
            "language_code": "tr",
            "voice_settings": {"stability": 0.40},
        },
        {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.50},
        },
        {
            "text": strip_v4_tags(text),
            "model_id": model_id,
        },
    ]

    last_err = None
    data = None
    for idx, payload in enumerate(payloads):
        r = requests.post(url, headers=headers, json=payload, timeout=150)
        if r.ok:
            data = r.json()
            print(f"  -> ElevenLabs OK (model={model_id}, attempt={idx + 1})")
            break
        last_err = f"HTTP {r.status_code}: {r.text[:300]}"
        print(f"  ! ElevenLabs attempt {idx + 1} failed: {last_err}")

    if data is None:
        raise RuntimeError(f"ElevenLabs synthesis failed: {last_err}")

    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    out_mp3.write_bytes(base64.b64decode(data["audio_base64"]))

    align = data.get("alignment") or data.get("normalized_alignment") or {}
    words = parse_alignment_words(align)

    dur_str = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out_mp3)],
        text=True,
    ).strip()
    duration = float(dur_str)

    # Fallback even word distribution if alignment was empty
    if not words:
        raw_words = CLEAN_SCRIPT.split()
        step = duration / max(1, len(raw_words))
        words = [{"word": w, "start": i * step, "end": (i + 1) * step} for i, w in enumerate(raw_words)]

    return duration, words


def group_word_chunks(words: list[dict[str, Any]], chunk_size: int = 2) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    i = 0
    while i < len(words):
        grp = words[i : i + chunk_size]
        if i + 2 < len(words) and sum(len(w["word"]) for w in words[i : i + 3]) <= 17:
            grp = words[i : i + 3]
            i += 3
        else:
            i += len(grp)
        chunks.append({
            "text": " ".join(w["word"] for w in grp),
            "start": max(0.0, grp[0]["start"] - 0.03),
            "end": grp[-1]["end"] + 0.08,
        })
    return chunks


def lookup_caption(chunks: list[dict[str, Any]], t: float) -> tuple[str, float, bool]:
    for c in chunks:
        if c["start"] <= t <= c["end"]:
            return c["text"], t - c["start"], True
    return "", 0.0, False


# ---------------------------------------------------------------------------
# Headless Chrome + Three.js Parallel Frame Renderer
# ---------------------------------------------------------------------------
def _find_chrome_executable() -> str | None:
    for p in (
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ):
        if os.path.exists(p):
            return p
    return None


def _render_chunk_worker(args: tuple[int, int, int, float, list[dict[str, Any]], str, str]) -> int:
    """Renders frame range [start_f, end_f) in an isolated Headless Chrome WebGL2 instance."""
    worker_id, start_f, end_f, total_dur, chunks, frames_dir, scene_uri = args
    from playwright.sync_api import sync_playwright

    chrome_exe = _find_chrome_executable()
    launch_kwargs: dict[str, Any] = {
        "headless": True,
        "args": [
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    }
    if chrome_exe:
        launch_kwargs["executable_path"] = chrome_exe

    out_dir = Path(frames_dir)
    rendered = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": W, "height": H})
        page.goto(scene_uri, wait_until="load", timeout=60000)
        page.wait_for_function("window.AKILALMAZ_READY === true", timeout=30000)

        for fidx in range(start_f, end_f):
            t = fidx / FPS
            cap, age, speaking = lookup_caption(chunks, t)
            b64_jpg = page.evaluate(
                "([t, dur, cap, age, sp]) => window.renderFrameJpeg(t, dur, cap, age, sp)",
                [t, total_dur, cap, age, speaking],
            )
            frame_path = out_dir / f"f_{fidx:05d}.jpg"
            frame_path.write_bytes(base64.b64decode(b64_jpg))
            rendered += 1
            if rendered % 100 == 0:
                print(f"  [worker {worker_id}] {rendered}/{end_f - start_f} kare", flush=True)

        browser.close()
    return rendered


def build_qa_sheet_from_dir(frames_dir: Path, total_frames: int, out_jpg: Path) -> None:
    cols, rows = 6, 3
    tw, th = 270, 480
    sheet = Image.new("RGB", (cols * tw, rows * th), (12, 12, 16))
    indices = [int(i * (total_frames - 1) / 17) for i in range(18)]
    for pos, fidx in enumerate(indices):
        fp = frames_dir / f"f_{fidx:05d}.jpg"
        if not fp.exists():
            continue
        im = Image.open(fp).convert("RGB")
        r, c = divmod(pos, cols)
        sheet.paste(im.resize((tw, th), Image.Resampling.LANCZOS), (c * tw, r * th))
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_jpg, "JPEG", quality=88, optimize=True)


def build_sfx_timeline(total_dur: float) -> list[tuple[float, str]]:
    """Places crisp cartoon SFX on every scene cut and story highlight."""
    events: list[tuple[float, str]] = [
        (0.35, "pop"),
        (1.85, "pop_hi"),
        # Scene 1: Dec 2, 1942 Chicago Pile-1 + Geiger counter!
        (SCENE_CUTS[1] * total_dur, "whoosh"),
        (SCENE_CUTS[1] * total_dur + 0.30, "pop"),
        (SCENE_CUTS[1] * total_dur + 1.40, "geiger"),
        # Scene 2: Navy info board (No cooling, no shield)
        (SCENE_CUTS[2] * total_dur, "whoosh"),
        (SCENE_CUTS[2] * total_dur + 0.60, "ding"),
        # Scene 3: Crimson AXE MAN board + metallic axe clang!
        (SCENE_CUTS[3] * total_dur, "whoosh"),
        (SCENE_CUTS[3] * total_dur + 0.45, "axe"),
        (SCENE_CUTS[3] * total_dur + 2.80, "axe"),
        # Scene 4: Orange Bucket Squad ("İntihar Timi") + comedic boing!
        (SCENE_CUTS[4] * total_dur, "whoosh"),
        (SCENE_CUTS[4] * total_dur + 0.45, "boing"),
        # Scene 5: Emerald Victory Board (15:25 Nuclear Age + Paper Cup Toast!)
        (SCENE_CUTS[5] * total_dur, "whoosh"),
        (SCENE_CUTS[5] * total_dur + 0.40, "sparkle"),
        # Scene 6: Seamless loop return
        (SCENE_CUTS[6] * total_dur, "whoosh"),
    ]
    return events


# ---------------------------------------------------------------------------
# Full Production Pipeline
# ---------------------------------------------------------------------------
def produce_video(music_db: float = -12.0, workers: int = 4, use_existing_voice: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    voice_path = WORK_DIR / "voice.mp3"
    words_cache = WORK_DIR / "words.json"
    bgm_sfx_path = WORK_DIR / "bgm_sfx.wav"
    mp4_path = OUT_DIR / FILE_NAME
    qa_path = OUT_DIR / "qa_sheet.jpg"

    if use_existing_voice and voice_path.exists() and words_cache.exists():
        print(f"[1/5] Mevcut doğrulanmış ERKAN (eleven_v4) sesi kullanılıyor ({voice_path.name})...")
        raw_dur = float(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(voice_path)],
                text=True,
            ).strip()
        )
        raw_words = json.loads(words_cache.read_text(encoding="utf-8"))
    else:
        print(f"[1/5] ElevenLabs ERKAN (eleven_v4) sesi üretiliyor ({SLUG})...")
        raw_dur, raw_words = synthesize_erkan_voice(TTS_SCRIPT, voice_path)

    # Apply subtle 1.10x Shorts tempo so total runtime is ~58s (snappy & safely under 60s!)
    tempo = VOICE_TEMPO
    duration = raw_dur / tempo
    words = [
        {"word": w["word"], "start": w["start"] / tempo, "end": w["end"] / tempo}
        for w in raw_words
    ]
    total_dur = duration + 0.35
    total_frames = int(math.ceil(total_dur * FPS))
    chunks = group_word_chunks(words, chunk_size=2)
    print(f"  -> Süre: {duration:.2f}s (ham {raw_dur:.2f}s @ {tempo:.2f}x, {total_frames} kare), {len(words)} kelime, {len(chunks)} altyazı parçası")

    print(f"[2/5] Canlı arka plan müziği + çizgi film SFX sentezleniyor (--music-db {music_db:.1f})...")
    sfx_events = build_sfx_timeline(total_dur)
    synth_bgm_sfx.build_music_and_sfx_wav(bgm_sfx_path, total_dur + 0.25, sfx_events, bgm_gain_db=0.0)

    print(f"[3/5] 1080x1920 30fps 3D-Toon + 2D Çöp Adam sahneleri render ediliyor ({workers} paralel işçi)...")
    t0 = time.time()
    scene_uri = SCENE_HTML.resolve().as_uri()
    with tempfile.TemporaryDirectory(prefix="v21_frames_") as tmp:
        frames_dir = Path(tmp)
        n_workers = max(1, min(workers, total_frames))
        chunk_len = math.ceil(total_frames / n_workers)
        tasks = []
        for wid in range(n_workers):
            sf = wid * chunk_len
            ef = min(total_frames, sf + chunk_len)
            if sf < ef:
                tasks.append((wid, sf, ef, total_dur, chunks, str(frames_dir), scene_uri))

        with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as pool:
            futs = [pool.submit(_render_chunk_worker, t_arg) for t_arg in tasks]
            for fut in concurrent.futures.as_completed(futs):
                fut.result()

        print(f"  -> {total_frames} kare {time.time() - t0:.1f}s içinde tamamlandı.")

        print("[4/5] QA Sheet ve final MP4 (ERKAN eleven_v4 + -12dB müzik/SFX miks) oluşturuluyor...")
        build_qa_sheet_from_dir(frames_dir, total_frames, qa_path)

        # Mix normalized ERKAN voice (-15.5 LUFS @ 1.10x tempo) with lively stereo BGM+SFX at --music-db
        af = (
            f"[1:a]atempo={tempo:.3f},loudnorm=I=-15.5:TP=-1.5:LRA=9,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[v];"
            f"[2:a]volume={music_db:.1f}dB,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[m];"
            f"[v][m]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[aout]"
        )
        cmd = [
            "ffmpeg", "-y", "-v", "warning",
            "-framerate", str(FPS),
            "-i", str(frames_dir / "f_%05d.jpg"),
            "-i", str(voice_path),
            "-i", str(bgm_sfx_path),
            "-filter_complex", af,
            "-map", "0:v", "-map", "[aout]",
            "-t", f"{total_dur:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(mp4_path),
        ]
        subprocess.run(cmd, check=True)

    # Clean up temporary work files (keep voice.mp3 matching v1-v20)
    if bgm_sfx_path.exists():
        bgm_sfx_path.unlink()
    if words_cache.exists():
        words_cache.unlink()

    print("[5/5] Eski v21 temizleniyor ve videos.json güncelleniyor...")
    old_dir = REPO_DIR / "files" / OLD_V21_SLUG
    if old_dir.exists() and old_dir.is_dir():
        shutil.rmtree(old_dir)
        print(f"  -> Eski klasör kaldırıldı: {old_dir.name}")

    videos = json.loads(VIDEOS_JSON.read_text(encoding="utf-8")) if VIDEOS_JSON.exists() else []
    videos = [v for v in videos if v.get("slug") not in (SLUG, OLD_V21_SLUG)]
    size_mb = round(mp4_path.stat().st_size / (1024 * 1024), 1)
    entry = {
        "slug": SLUG,
        "title": TITLE,
        "status": "Hazır",
        "script": CLEAN_SCRIPT,
        "meta": META,
        "words": len(CLEAN_SCRIPT.split()),
        "frames": total_frames,
        "voice": f"files/{SLUG}/work/voice.mp3",
        "qa": f"files/{SLUG}/out/qa_sheet.jpg",
        "video": f"files/{SLUG}/out/{FILE_NAME}",
        "fileName": FILE_NAME,
        "sizeMB": size_mb,
        "updated": datetime.now(timezone.utc).isoformat(),
        "width": W,
        "height": H,
        "duration": round(total_dur, 3),
    }
    videos.append(entry)
    VIDEOS_JSON.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ Tamamlandı: {mp4_path} ({size_mb} MB, {total_dur:.1f}s)")


def generate_vertex_cover() -> str:
    """Calls Cloud Run /api/covers/generate to create a 9:16 Vertex AI cover and saves a local copy."""
    import requests

    api_url = os.getenv("LIKYA_API_URL", "https://likya-crosspost-api-64i7umkgnq-ew.a.run.app").rstrip("/")
    api_key = os.environ["LIKYA_API_KEY"].strip()
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    print(f"[Kapak] Cloud Run /api/covers/generate ile 9:16 Vertex AI kapak üretiliyor ({SLUG})...")
    r = requests.post(
        f"{api_url}/api/covers/generate",
        headers=headers,
        json={"key": SLUG, "prompt": META["flow_prompt"], "aspect_ratio": "9:16"},
        timeout=150,
    )
    r.raise_for_status()
    data = r.json()
    img_url = data["image_url"]
    print(f"  -> Vertex AI kapak hazır: {img_url}")

    # Save crisp JPG copy alongside video outputs so panel/git also has a local preview
    img_resp = requests.get(img_url, timeout=60)
    img_resp.raise_for_status()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_png = OUT_DIR / "_cover_raw.png"
    tmp_png.write_bytes(img_resp.content)
    im = Image.open(tmp_png).convert("RGB")
    cover_jpg = OUT_DIR / "cover.jpg"
    im.save(cover_jpg, "JPEG", quality=92, optimize=True)
    tmp_png.unlink(missing_ok=True)
    print(f"  -> Yerel önizleme kaydedildi: {cover_jpg} ({im.width}x{im.height})")
    return img_url.split("?")[0]


def schedule_for_dec2() -> None:
    """Schedules the new v21 into 2 Aralık 2026 Çarşamba 06:03 TR (replaces old v21 schedule if present)."""
    import requests

    api_url = os.getenv("LIKYA_API_URL", "https://likya-crosspost-api-64i7umkgnq-ew.a.run.app").rstrip("/")
    api_key = os.environ["LIKYA_API_KEY"].strip()
    site_base = os.getenv("SITE_BASE_URL", "https://studio.likyastudios.live").rstrip("/")
    headers = {"X-API-Key": api_key}

    # Check if old v21_kendi_kendine_savas is occupying 2026-12-02 and remove it before scheduling
    r_list = requests.get(f"{api_url}/api/schedule", headers=headers, params={"brand": "akilalmaz"}, timeout=30)
    if r_list.ok:
        for post in r_list.json().get("posts", []):
            if post.get("video_id") == OLD_V21_SLUG and post.get("status") in ("Planlandı", "Hata"):
                print(f"  -> Eski v21 plan kaydı #{post['id']} ({OLD_V21_SLUG}) kaldırılıyor...")
                requests.delete(f"{api_url}/api/schedule/{post['id']}", headers=headers, timeout=30)

    video_abs_url = f"{site_base}/files/{SLUG}/out/{FILE_NAME}"
    cover_url = f"{api_url}/api/covers/{SLUG}.png"

    print(f"[Planlama] Video yayını bekleniyor: {video_abs_url}")
    for attempt in range(40):
        try:
            hr = requests.head(video_abs_url, timeout=20, allow_redirects=True)
            if hr.status_code == 200:
                print(f"  -> Video canlıda (HTTP 200, deneme #{attempt + 1})")
                break
        except requests.RequestException:
            pass
        time.sleep(15)
    else:
        raise SystemExit("Video GitHub Pages üzerinde 10 dk içinde erişilebilir olmadı.")

    print("[Planlama] 2 Aralık 2026 Çarşamba (06:03 TR) slotuna planlanıyor...")
    payload = {
        "brand": "akilalmaz",
        "video_id": SLUG,
        "video_url": video_abs_url,
        "title": META["youtube"]["title"],
        "description": META["youtube"]["description"],
        "ig_caption": META["instagram"]["caption"],
        "cover_url": cover_url,
        "scheduled_at": SCHEDULED_AT_UTC,
        "auto_next_slot": False,
        "sync_youtube_now": True,
    }
    sr = requests.post(
        f"{api_url}/api/schedule",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
        timeout=150,
    )
    if sr.status_code == 409:
        print("  -> Video zaten planlı (409), atlandı.")
        return
    sr.raise_for_status()
    res = sr.json()
    post = res.get("post") or {}
    print(f"✅ Planlandı: #{post.get('id')} — {post.get('label_tr')} | YT yüklendi: {res.get('yt_uploaded')}")


def render_local_preview() -> None:
    """Fast local QA preview (renders 18 frames across all 7 3D-toon scenes into a 6x3 QA sheet)."""
    from playwright.sync_api import sync_playwright

    fake_dur = 52.0
    sample_caps = [
        "Dünyanın ilk", "nükleer reaktörü", "elinde balta tutan",
        "2 Aralık 1942", "Enrico Fermi,", "stadyumun altında",
        "soğutma sistemi yok,", "dört yüz ton", "grafit tuğlayı",
        "elindeki baltayla", "halatı kesip", "fren çubuğunu",
        "tepede üç", "bilim insanı", "kovalarla bekliyordu!",
        "nükleer çağ", "kâğıt bardaklarla", "şöyle anlatılır:",
    ]
    chrome_exe = _find_chrome_executable()
    launch_kwargs: dict[str, Any] = {
        "headless": True,
        "args": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--no-sandbox"],
    }
    if chrome_exe:
        launch_kwargs["executable_path"] = chrome_exe

    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        with sync_playwright() as p:
            b = p.chromium.launch(**launch_kwargs)
            page = b.new_page(viewport={"width": W, "height": H})
            page.goto(SCENE_HTML.resolve().as_uri(), wait_until="load", timeout=60000)
            page.wait_for_function("window.AKILALMAZ_READY === true", timeout=30000)
            for i in range(18):
                t = (i + 0.35) * (fake_dur / 18.0)
                page.evaluate(
                    "([t, dur, cap, age, sp]) => window.renderFrameAt(t, dur, cap, age, sp)",
                    [t, fake_dur, sample_caps[i], 0.14, (i % 2 == 0)],
                )
                page.screenshot(path=str(td / f"f_{i:05d}.jpg"), type="jpeg", quality=92)
            b.close()

        preview_path = Path(tempfile.gettempdir()) / f"{SLUG}_qa_preview.jpg"
        build_qa_sheet_from_dir(td, 18, preview_path)
        print(f"Preview QA sheet saved: {preview_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="AKILALMAZ v21 — 2 Aralık 1942 Chicago Pile-1 Üretici")
    p.add_argument("--music-db", type=float, default=-12.0, help="Arka plan müzik seviyesi (dB, varsayılan -12.0)")
    p.add_argument("--workers", type=int, default=4, help="Paralel 3D render işçi sayısı")
    p.add_argument("--use-existing-voice", action="store_true", help="Mevcut work/voice.mp3 + words.json dosyalarını kullan")
    p.add_argument("--preview", action="store_true", help="Hızlı yerel 6x3 3D-toon QA önizlemesi üret")
    p.add_argument("--generate-cover", action="store_true", help="Cloud Run /api/covers/generate ile 9:16 Vertex AI kapak üret")
    p.add_argument("--publish-schedule", action="store_true", help="2 Aralık 2026 06:03 TR slotuna planla")
    args = p.parse_args()

    if args.preview:
        render_local_preview()
    elif args.generate_cover:
        generate_vertex_cover()
    elif args.publish_schedule:
        schedule_for_dec2()
    else:
        produce_video(music_db=args.music_db, workers=args.workers, use_existing_voice=args.use_existing_voice)


if __name__ == "__main__":
    main()
