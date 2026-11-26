#!/usr/bin/env python3
"""
engine/build_short.py — AKILALMAZ v9–v20 Exact Production Pipeline Orchestrator
Runs the complete end-to-end pipeline from an episode JSON spec:
  1. ElevenLabs eleven_v4 TTS + word timestamps + Turkish ASS captions (kit/el_tts.py)
  2. Word-aligned 10-scene timeline & SFX cue resolution (guaranteed narration <-> visual sync!)
  3. Upbeat cartoon BGM (-12.0 dB) + SFX (-6.4 dB) mix (kit/mix.py)
  4. Scene HTML + story.js generation -> Headless Chrome SwiftShader CDP render (kit/render_cdp.mjs)
  5. Loudnorm (-14 LUFS) + 2x Lanczos 1080x1920 + ASS burn + QA sheet (kit/finish_tr.sh)
  6. Optional sync into files/<slug>/ + natural-sorted videos.json update
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = ENGINE_DIR.parent
KIT_DIR = ENGINE_DIR / "kit"


def norm_tr(s: str) -> str:
    s = s.lower()
    s = s.replace("İ", "i").replace("I", "ı")
    return re.sub(r"[^a-zçğıöşü0-9]", "", s)


def find_anchor_time(words: list[dict], anchor: str, min_t: float, fallback_t: float) -> float:
    """Finds exact start timestamp of an anchor phrase/word in ElevenLabs timestamps."""
    if not anchor or not words:
        return fallback_t
    tokens = [norm_tr(tok) for tok in anchor.split() if norm_tr(tok)]
    if not tokens:
        return fallback_t

    for i in range(len(words)):
        if words[i]["start"] < min_t - 0.15:
            continue
        matched = True
        for k, tok in enumerate(tokens):
            if i + k >= len(words):
                matched = False
                break
            w = norm_tr(words[i + k]["word"])
            if not (w == tok or w.startswith(tok) or tok in w):
                matched = False
                break
        if matched:
            return max(min_t, float(words[i]["start"]) - 0.08)
    return fallback_t


def resolve_timeline(ep: dict, duration: float, words: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Resolves exact [t0, t1] boundaries for all 10 scenes based on spoken anchor phrases,
    ensuring 100% narration-to-visual alignment and zero frozen gaps.
    """
    raw_scenes = ep["scenes"]
    n = len(raw_scenes)
    starts = [0.0]

    for i in range(1, n):
        sc = raw_scenes[i]
        fallback = duration * float(sc.get("fallback_frac", i / n))
        min_t = starts[-1] + 1.15
        anchor = sc.get("anchor", "")
        t_start = find_anchor_time(words, anchor, min_t, fallback)
        # Keep monotonic and leave room for remaining scenes
        max_allowed = duration - (n - i) * 1.15
        t_start = max(min_t, min(t_start, max_allowed))
        starts.append(round(t_start, 3))

    resolved = []
    sfx_events = []
    for i, sc in enumerate(raw_scenes):
        t0 = starts[i]
        t1 = starts[i + 1] if i + 1 < n else round(duration, 3)
        item = dict(sc)
        item["t0"] = t0
        item["t1"] = t1
        resolved.append(item)

        if i > 0 and item.get("flash", True):
            sfx_events.append({"t": t0, "kind": item.get("cutSfx", "whoosh")})
        for fx_call in item.get("fx", []):
            delay = float(fx_call.get("delay", 0.12))
            sfx_events.append({
                "t": round(t0 + delay, 3),
                "kind": fx_call.get("sfx", "pop"),
            })
        if item.get("sparkles"):
            sfx_events.append({"t": round(t0 + 0.25, 3), "kind": "ding"})

    return resolved, sfx_events


def write_scene_files(scene_dir: Path, payload: dict):
    scene_dir.mkdir(parents=True, exist_ok=True)
    html = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8" />
<title>AKILALMAZ 3D-Toon Stage</title>
<style>
  html, body { margin: 0; padding: 0; width: 540px; height: 960px; overflow: hidden; background: #000; }
  canvas { display: block; width: 540px; height: 960px; }
</style>
</head>
<body>
<canvas id="c" width="540" height="960"></canvas>
<script type="module" src="./story.js"></script>
</body>
</html>
"""
    (scene_dir / "index.html").write_text(html, encoding="utf-8")

    story_js = (
        "import { bootEpisode } from '/engine/kit/story_runtime.js';\n"
        f"const EPISODE = {json.dumps(payload, ensure_ascii=False, indent=2)};\n"
        "bootEpisode(EPISODE);\n"
    )
    (scene_dir / "story.js").write_text(story_js, encoding="utf-8")


def natural_sort_key(v: dict):
    slug = v.get("slug", "")
    m = re.match(r"v(\d+)", slug)
    return (int(m.group(1)) if m else 9999, slug)


def sync_to_panel(ep: dict, ep_dir: Path, duration: float):
    from datetime import datetime, timezone
    slug = ep["slug"]
    mp4_name = ep["mp4_name"]
    dest_root = REPO_ROOT / "files" / slug
    dest_out = dest_root / "out"
    dest_work = dest_root / "work"
    dest_out.mkdir(parents=True, exist_ok=True)
    dest_work.mkdir(parents=True, exist_ok=True)

    shutil.copy2(ep_dir / "out" / mp4_name, dest_out / mp4_name)
    shutil.copy2(ep_dir / "out" / "qa_sheet.jpg", dest_out / "qa_sheet.jpg")
    shutil.copy2(ep_dir / "work" / "voice.mp3", dest_work / "voice.mp3")

    vjson_path = REPO_ROOT / "videos.json"
    videos = json.loads(vjson_path.read_text(encoding="utf-8"))
    size_mb = round((dest_out / mp4_name).stat().st_size / (1024 * 1024), 1)
    clean_script = re.sub(r"\[[^\]]+\]\s*", "", ep.get("script_v4", "")).strip()
    words_count = len(clean_script.split())
    frames_count = int(math.ceil(duration * 30))
    now_iso = datetime.now(timezone.utc).isoformat()

    entry_fields = {
        "slug": slug,
        "title": ep["title"],
        "status": "Hazır",
        "script": clean_script,
        "meta": {
            "youtube": {
                "title": ep.get("youtube_title", ep["title"]),
                "description": ep.get("youtube_desc", ""),
            },
            "instagram": {
                "caption": ep.get("ig_caption", ep.get("youtube_desc", "")),
            },
            "cover_title": ep.get("cover_title", ep["title"].upper()),
            "flow_prompt": ep.get("flow_prompt", ""),
        },
        "words": words_count,
        "frames": frames_count,
        "voice": f"files/{slug}/work/voice.mp3",
        "qa": f"files/{slug}/out/qa_sheet.jpg",
        "video": f"files/{slug}/out/{mp4_name}",
        "fileName": mp4_name,
        "sizeMB": size_mb,
        "updated": now_iso,
        "width": 1080,
        "height": 1920,
        "duration": round(duration, 3),
    }

    found = False
    for idx, v in enumerate(videos):
        if v.get("slug") == slug:
            # Preserve existing flow_prompt / cover_title if not overridden in ep
            old_meta = v.get("meta") or {}
            if not entry_fields["meta"]["flow_prompt"] and old_meta.get("flow_prompt"):
                entry_fields["meta"]["flow_prompt"] = old_meta["flow_prompt"]
            if not ep.get("cover_title") and old_meta.get("cover_title"):
                entry_fields["meta"]["cover_title"] = old_meta["cover_title"]
            videos[idx] = entry_fields
            found = True
            break

    if not found:
        videos.append(entry_fields)

    videos.sort(key=natural_sort_key)
    vjson_path.write_text(json.dumps(videos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[panel] Synced {slug} -> files/{slug}/ & updated videos.json ({size_mb} MB, {duration:.2f}s)")


def main():
    ap = argparse.ArgumentParser(description="Build an AKILALMAZ 3D-Toon Short with exact v9–v20 engine")
    ap.add_argument("--episode", required=True, help="Path to episode JSON file")
    ap.add_argument("--build-dir", default="", help="Working build directory (default: /tmp/akil_build/<slug>)")
    ap.add_argument("--music-db", type=float, default=-12.0)
    ap.add_argument("--sfx-db", type=float, default=-6.4)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--reuse-voice", action="store_true")
    ap.add_argument("--clean-frames", action="store_true")
    ap.add_argument("--sync-panel", action="store_true", help="Copy outputs to files/<slug>/ and update videos.json")
    args = ap.parse_args()

    ep_path = Path(args.episode).resolve()
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    slug = ep["slug"]

    build_dir = Path(args.build_dir) if args.build_dir else Path("/tmp/akil_build") / slug
    work_dir = build_dir / "work"
    scene_dir = build_dir / "scene"
    frames_dir = build_dir / "frames"
    work_dir.mkdir(parents=True, exist_ok=True)

    if args.clean_frames and frames_dir.exists():
        shutil.rmtree(frames_dir)

    # 1. Write script_v4.txt & generate TTS + ASS captions
    script_file = work_dir / "script_v4.txt"
    script_file.write_text(ep["script_v4"].strip() + "\n", encoding="utf-8")

    tts_cmd = [
        sys.executable, str(KIT_DIR / "el_tts.py"),
        "--script", str(script_file),
        "--work", str(work_dir),
        "--stability", str(ep.get("stability", 0.5)),
    ]
    if args.reuse_voice:
        tts_cmd.append("--reuse")
    subprocess.check_call(tts_cmd)

    ts_data = json.loads((work_dir / "timestamps.json").read_text(encoding="utf-8"))
    duration = float(ts_data["duration"]) + 0.25
    total_frames = int(math.ceil(duration * 30))
    words = ts_data["words"]

    # 2. Resolve narration-aligned 10-scene timeline & SFX events
    scenes, sfx_events = resolve_timeline(ep, duration, words)
    (work_dir / "sfx_events.json").write_text(json.dumps(sfx_events, indent=2), encoding="utf-8")

    print(f"[timeline] {slug}: {duration:.2f}s ({total_frames} frames), {len(scenes)} aligned scenes:")
    for sc in scenes:
        print(f"   {sc['id']:>3}: {sc['t0']:5.2f}s -> {sc['t1']:5.2f}s  ({sc.get('note', '')})")

    # 3. Mix voice + upbeat BGM (-12.0 dB) + SFX (-6.4 dB)
    subprocess.check_call([
        sys.executable, str(KIT_DIR / "mix.py"),
        "--work", str(work_dir),
        "--events", str(work_dir / "sfx_events.json"),
        "--music-db", str(args.music_db),
        "--sfx-db", str(args.sfx_db),
        "--bpm", str(ep.get("bpm", 122)),
        "--seed", str(ep.get("music_seed", 21)),
    ])

    # 4. Generate scene/index.html + story.js & render frames via Chrome SwiftShader CDP
    story_payload = {
        "slug": slug,
        "duration": duration,
        "totalFrames": total_frames,
        "stage": ep["stage"],
        "heroProp": ep["heroProp"],
        "characters": ep["characters"],
        "fx": ep.get("fx", {}),
        "scenes": scenes,
    }
    write_scene_files(scene_dir, story_payload)

    env = os.environ.copy()
    env["WORKERS"] = str(args.workers)
    env["RESUME"] = "0" if args.clean_frames else "1"
    env["VW"] = "540"
    env["VH"] = "960"
    subprocess.check_call([
        "node", str(KIT_DIR / "render_cdp.mjs"),
        f"--scene={scene_dir}",
        f"--root={ENGINE_DIR}",
        f"--out={frames_dir}",
        "--start=0",
        f"--end={total_frames}",
        f"--workers={args.workers}",
    ], env=env)

    # 5. Final encode + loudnorm + 2x Lanczos + ASS burn + QA sheet
    subprocess.check_call([
        "bash", str(KIT_DIR / "finish_tr.sh"),
        str(build_dir),
        ep["mp4_name"],
    ])

    if args.sync_panel:
        sync_to_panel(ep, build_dir, duration)

    print(f"\n✅ BUILD COMPLETE: {build_dir / 'out' / ep['mp4_name']}")


if __name__ == "__main__":
    main()
