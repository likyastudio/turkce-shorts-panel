#!/usr/bin/env python3
"""
engine/kit/el_tts.py — ElevenLabs eleven_v4 TTS + Word Timestamps + Synced Turkish ASS Captions
Exact AKILALMAZ v9–v20 audio/subtitle pipeline:
  - Model: eleven_v4 (default)
  - Voice: erkanv2 (jdpQqF5lMnLWcXlPOnAU) or ELEVENLABS_VOICE_ID env override
  - Stability: 0.5 (supports inline emotion tags like [excited], [amused], [surprised], [dramatic], [chuckles])
  - Outputs:
      work/voice.mp3        (128k MP3 for panel & mix)
      work/timestamps.json  (word list + exact audio duration)
      work/captions.ass     (2–3 word crisp bold white/outline Turkish ASS captions)
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import requests

DEFAULT_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "jdpQqF5lMnLWcXlPOnAU")
DEFAULT_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_v4")


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def extract_words(alignment: dict) -> list[dict]:
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])

    words = []
    cur = []
    w_start = None
    w_end = None
    in_bracket = False

    for ch, s, e in zip(chars, starts, ends):
        if ch == "[":
            in_bracket = True
            if cur:
                words.append({"word": "".join(cur), "start": w_start, "end": w_end})
                cur, w_start, w_end = [], None, None
            continue
        if ch == "]":
            in_bracket = False
            continue
        if in_bracket:
            continue

        if ch.isspace():
            if cur:
                words.append({"word": "".join(cur), "start": w_start, "end": w_end})
                cur, w_start, w_end = [], None, None
        else:
            if w_start is None:
                w_start = float(s)
            w_end = float(e)
            cur.append(ch)

    if cur:
        words.append({"word": "".join(cur), "start": w_start, "end": w_end})

    # Filter any stray empty/tag tokens
    cleaned = []
    for w in words:
        txt = re.sub(r"\[[^\]]*\]", "", w["word"]).strip()
        if txt:
            cleaned.append({"word": txt, "start": w["start"], "end": max(w["end"], w["start"] + 0.08)})
    return cleaned


def fmt_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 0
        s += 1
        if s >= 60:
            s = 0
            m += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass_captions(words: list[dict], out_ass: Path) -> list[dict]:
    """
    Groups words into 2–3 word high-impact chunks matching v15/v20 exact styling:
    Bold DejaVu Sans 64px, pure white fill, thick #000000 outline (7.5), soft shadow,
    Alignment=2, MarginV=480 (cleanly above YouTube Shorts bottom HUD, right across torso).
    """
    chunks = []
    i = 0
    while i < len(words):
        grp = [words[i]]
        i += 1
        while i < len(words) and len(grp) < 3:
            cand = grp + [words[i]]
            txt = " ".join(x["word"] for x in cand)
            # Break naturally after sentence-ending punctuation or if chunk > 20 chars
            prev_word = grp[-1]["word"]
            if prev_word.endswith((".", "!", "?", ":", ";")):
                break
            if len(txt) > 20 and len(grp) >= 2:
                break
            if words[i]["start"] - grp[-1]["end"] > 0.32:
                break
            grp.append(words[i])
            i += 1
        chunks.append({
            "text": " ".join(x["word"] for x in grp),
            "start": grp[0]["start"],
            "end": grp[-1]["end"],
        })

    # Smooth contiguous transitions so captions never flicker
    for idx in range(len(chunks) - 1):
        gap = chunks[idx + 1]["start"] - chunks[idx]["end"]
        if 0 < gap < 0.14:
            chunks[idx]["end"] = chunks[idx + 1]["start"]
        elif chunks[idx]["end"] > chunks[idx + 1]["start"]:
            chunks[idx]["end"] = max(chunks[idx]["start"] + 0.08, chunks[idx + 1]["start"])

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,64,&H00FFFFFF,&H0000D6FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7.5,2.2,2,60,60,480,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for ch in chunks:
        txt = ch["text"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        lines.append(
            f"Dialogue: 0,{fmt_ass_time(ch['start'])},{fmt_ass_time(ch['end'])},Default,,0,0,0,,{txt}"
        )
    out_ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chunks


def main():
    ap = argparse.ArgumentParser(description="ElevenLabs eleven_v4 TTS + Turkish ASS captions")
    ap.add_argument("--script", required=True, help="Path to script_v4.txt")
    ap.add_argument("--work", required=True, help="Output work directory")
    ap.add_argument("--voice-id", default=DEFAULT_VOICE_ID)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--stability", type=float, default=0.5)
    ap.add_argument("--reuse", action="store_true", help="Reuse existing voice.mp3 + timestamps.json if present")
    args = ap.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    voice_mp3 = work / "voice.mp3"
    ts_json = work / "timestamps.json"
    ass_path = work / "captions.ass"

    if args.reuse and voice_mp3.exists() and ts_json.exists():
        data = json.loads(ts_json.read_text(encoding="utf-8"))
        build_ass_captions(data["words"], ass_path)
        print(f"[el_tts] Reused existing voice ({data['duration']:.2f}s, {len(data['words'])} words)")
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    text = Path(args.script).read_text(encoding="utf-8").strip()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{args.voice_id}/with-timestamps"
    payload = {
        "text": text,
        "model_id": args.model,
        "language_code": "tr",
        "voice_settings": {
            "stability": args.stability,
            "similarity_boost": 0.78,
        },
        "output_format": "mp3_44100_128",
    }
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        print(f"ERROR: ElevenLabs HTTP {resp.status_code}: {resp.text[:400]}", file=sys.stderr)
        sys.exit(1)

    body = resp.json()
    audio_bytes = base64.b64decode(body["audio_base64"])
    raw_mp3 = work / "voice_raw.mp3"
    raw_mp3.write_bytes(audio_bytes)

    # Normalize to clean 128k 48kHz stereo MP3 for panel consistency
    subprocess.check_call(
        [
            "ffmpeg", "-v", "error", "-y",
            "-i", str(raw_mp3),
            "-ar", "48000", "-ac", "2", "-b:a", "128k",
            str(voice_mp3),
        ]
    )
    raw_mp3.unlink(missing_ok=True)

    duration = probe_duration(voice_mp3)
    alignment = body.get("normalized_alignment") or body.get("alignment") or {}
    words = extract_words(alignment)
    chunks = build_ass_captions(words, ass_path)

    meta = {
        "voice_id": args.voice_id,
        "model": args.model,
        "duration": duration,
        "words": words,
        "chunks": chunks,
    }
    ts_json.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[el_tts] Generated {voice_mp3.name} ({duration:.2f}s, {len(words)} words, {len(chunks)} ASS cues)")


if __name__ == "__main__":
    main()
