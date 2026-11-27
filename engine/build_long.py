#!/usr/bin/env python3
"""
engine/build_long.py — AKILALMAZ 16:9 (1920x1080) Long-Form (3–4 min) Production Orchestrator
Uses the exact v9–v20 3D-Toon + 2D thick-inked engine in 16:9 widescreen (960x540 -> 2x Lanczos 1920x1080):
  1. Chapter-split ElevenLabs eleven_v4 TTS + shifted word timestamps + 16:9 ASS captions (kit/el_tts_long.py)
  2. Narration-anchored N-scene timeline & SFX cue resolution
  3. Upbeat cartoon BGM (-12.0 dB) + SFX (-6.4 dB) mix (kit/mix.py)
  4. Scene HTML (960x540) + story.js generation -> supports:
       --prepare-only : builds work/ + scene/ + work/meta.json (for GitHub Actions parallel matrix)
       --preview      : renders 1 sample frame from every scene into preview/ for instant visual QA
       --encode-only  : runs finish_long.sh on already-rendered frames/
       default        : renders full range locally and encodes
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
    s = s.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^a-zçğıöşü0-9]", "", s)


def find_anchor_time(words: list[dict], anchor: str, min_t: float, fallback_t: float) -> tuple[float, bool]:
    if not anchor or not words:
        return fallback_t, False
    tokens = [norm_tr(tok) for tok in anchor.split() if norm_tr(tok)]
    if not tokens:
        return fallback_t, False

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
            return max(min_t, float(words[i]["start"]) - 0.10), True
    return fallback_t, False


def resolve_timeline(ep: dict, duration: float, words: list[dict]) -> tuple[list[dict], list[dict]]:
    raw_scenes = ep["scenes"]
    n = len(raw_scenes)
    starts = [0.0]
    misses = []

    for i in range(1, n):
        sc = raw_scenes[i]
        fallback = duration * float(sc.get("fallback_frac", i / n))
        min_t = starts[-1] + 2.0
        anchor = sc.get("anchor", "")
        t_start, hit = find_anchor_time(words, anchor, min_t, fallback)
        if anchor and not hit:
            misses.append((sc.get("id", f"s{i}"), anchor))
        max_allowed = duration - (n - i) * 2.0
        t_start = max(min_t, min(t_start, max_allowed))
        starts.append(round(t_start, 3))

    if misses:
        print(f"[timeline WARN] {len(misses)} anchors fell back: {misses}")

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
            delay = float(fx_call.get("delay", 0.14))
            sfx_events.append({
                "t": round(t0 + delay, 3),
                "kind": fx_call.get("sfx", "pop"),
            })
        if item.get("sparkles"):
            sfx_events.append({"t": round(t0 + 0.25, 3), "kind": "ding"})

    return resolved, sfx_events


def write_scene_files(scene_dir: Path, payload: dict, vw: int, vh: int):
    scene_dir.mkdir(parents=True, exist_ok=True)
    html = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8" />
<title>AKILALMAZ 16:9 3D-Toon Stage</title>
<style>
  html, body {{ margin: 0; padding: 0; width: {vw}px; height: {vh}px; overflow: hidden; background: #000; }}
  canvas {{ display: block; width: {vw}px; height: {vh}px; }}
</style>
</head>
<body>
<canvas id="c" width="{vw}" height="{vh}"></canvas>
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


def main():
    ap = argparse.ArgumentParser(description="Build a 16:9 3–4 min AKILALMAZ 3D-Toon video")
    ap.add_argument("--episode", required=True)
    ap.add_argument("--build-dir", default="")
    ap.add_argument("--music-db", type=float, default=-12.0)
    ap.add_argument("--sfx-db", type=float, default=-6.4)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--reuse-voice", action="store_true")
    ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument("--preview", action="store_true", help="Render 1 sample frame per scene + contact sheet")
    ap.add_argument("--encode-only", action="store_true")
    ap.add_argument("--clean-frames", action="store_true")
    args = ap.parse_args()

    ep_path = Path(args.episode).resolve()
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    slug = ep["slug"]
    vw = int(ep.get("width", 960))
    vh = int(ep.get("height", 540))

    build_dir = Path(args.build_dir) if args.build_dir else Path("/tmp/akil_long") / slug
    work_dir = build_dir / "work"
    scene_dir = build_dir / "scene"
    frames_dir = build_dir / "frames"
    work_dir.mkdir(parents=True, exist_ok=True)

    if args.encode_only:
        subprocess.check_call(["bash", str(KIT_DIR / "finish_long.sh"), str(build_dir), ep["mp4_name"]])
        return

    if args.clean_frames and frames_dir.exists():
        shutil.rmtree(frames_dir)

    # 1. Chapter TTS + 16:9 ASS
    script_file = work_dir / "script_v4.txt"
    script_file.write_text(ep["script_v4"].strip() + "\n", encoding="utf-8")
    tts_cmd = [
        sys.executable, str(KIT_DIR / "el_tts_long.py"),
        "--script", str(script_file),
        "--work", str(work_dir),
        "--stability", str(ep.get("stability", 0.5)),
        "--gap", str(ep.get("chapter_gap", 0.42)),
    ]
    if args.reuse_voice:
        tts_cmd.append("--reuse")
    subprocess.check_call(tts_cmd)

    ts_data = json.loads((work_dir / "timestamps.json").read_text(encoding="utf-8"))
    duration = float(ts_data["duration"]) + 0.35
    total_frames = int(math.ceil(duration * 30))
    words = ts_data["words"]

    # 2. Timeline & SFX
    scenes, sfx_events = resolve_timeline(ep, duration, words)
    (work_dir / "sfx_events.json").write_text(json.dumps(sfx_events, indent=2), encoding="utf-8")

    print(f"[long] {slug}: {duration:.2f}s ({duration/60:.2f} min, {total_frames} frames), {len(scenes)} scenes:")
    for sc in scenes:
        print(f"   {sc['id']:>4}: {sc['t0']:6.2f}s -> {sc['t1']:6.2f}s ({sc['t1']-sc['t0']:4.1f}s)  {sc.get('note', '')}")

    # 3. Mix audio
    subprocess.check_call([
        sys.executable, str(KIT_DIR / "mix.py"),
        "--work", str(work_dir),
        "--events", str(work_dir / "sfx_events.json"),
        "--music-db", str(args.music_db),
        "--sfx-db", str(args.sfx_db),
        "--bpm", str(ep.get("bpm", 118)),
        "--seed", str(ep.get("music_seed", 1453)),
    ])

    # 4. Write 16:9 scene bundle + meta.json
    story_payload = {
        "slug": slug,
        "width": vw,
        "height": vh,
        "defaultFov": float(ep.get("defaultFov", 42)),
        "duration": duration,
        "totalFrames": total_frames,
        "stage": ep["stage"],
        "heroProp": ep["heroProp"],
        "characters": ep["characters"],
        "fx": ep.get("fx", {}),
        "scenes": scenes,
    }
    write_scene_files(scene_dir, story_payload, vw, vh)

    meta = {
        "slug": slug,
        "mp4_name": ep["mp4_name"],
        "width": vw,
        "height": vh,
        "out_width": vw * 2,
        "out_height": vh * 2,
        "duration": round(duration, 3),
        "total_frames": total_frames,
        "scene_count": len(scenes),
        "words": len(words),
    }
    (work_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if args.preview:
        prev_dir = build_dir / "preview"
        if prev_dir.exists():
            shutil.rmtree(prev_dir)
        prev_dir.mkdir(parents=True)
        sample_frames = []
        for sc in scenes:
            mid_t = sc["t0"] + min(1.5, (sc["t1"] - sc["t0"]) * 0.45)
            sample_frames.append(min(total_frames - 1, max(0, int(round(mid_t * 30)))))
        env = os.environ.copy()
        env["VW"] = str(vw)
        env["VH"] = str(vh)
        env["RESUME"] = "0"
        subprocess.check_call([
            "node", str(KIT_DIR / "render_cdp.mjs"),
            f"--scene={scene_dir}",
            f"--root={ENGINE_DIR}",
            f"--out={prev_dir}",
            f"--frames={','.join(str(x) for x in sample_frames)}",
        ], env=env)
        # Build quick contact sheet of all sampled scenes
        files = sorted(prev_dir.glob("f*.jpg"))
        lst = prev_dir / "list.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for p in files), encoding="utf-8")
        cols = 6
        rows = max(1, math.ceil(len(files) / cols))
        subprocess.check_call([
            "ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-vf", f"scale=320:-1,tile={cols}x{rows}", "-frames:v", "1", "-q:v", "3",
            str(build_dir / "preview_sheet.jpg"),
        ])
        print(f"✅ PREVIEW SHEET READY: {build_dir / 'preview_sheet.jpg'} ({len(files)} scenes)")
        return

    if args.prepare_only:
        print(f"✅ PREPARED: {build_dir} ({total_frames} frames, {duration:.2f}s)")
        return

    env = os.environ.copy()
    env["WORKERS"] = str(args.workers)
    env["RESUME"] = "0" if args.clean_frames else "1"
    env["VW"] = str(vw)
    env["VH"] = str(vh)
    subprocess.check_call([
        "node", str(KIT_DIR / "render_cdp.mjs"),
        f"--scene={scene_dir}",
        f"--root={ENGINE_DIR}",
        f"--out={frames_dir}",
        "--start=0",
        f"--end={total_frames}",
        f"--workers={args.workers}",
    ], env=env)

    subprocess.check_call(["bash", str(KIT_DIR / "finish_long.sh"), str(build_dir), ep["mp4_name"]])
    print(f"✅ LONG BUILD COMPLETE: {build_dir / 'out' / ep['mp4_name']}")


if __name__ == "__main__":
    main()
