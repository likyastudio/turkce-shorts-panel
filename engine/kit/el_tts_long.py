#!/usr/bin/env python3
"""
engine/kit/el_tts_long.py — Long-form (3–4 min) ElevenLabs eleven_v4 chapter TTS + 16:9 Turkish ASS captions
Same voice/model/settings as el_tts.py (erkanv2 jdpQqF5lMnLWcXlPOnAU, eleven_v4, stability 0.5, tr).

  - Script is split into chapters on blank lines (each chapter = 1 API request, avoids per-request limits)
  - Chapter MP3s are concatenated with a natural GAP (default 0.45 s) of silence
  - Word timestamps are shifted per chapter -> one continuous timeline
  - Captions: 16:9 PlayRes 1920x1080, bottom-center cinema position, up to 5 words / 34 chars per cue

Outputs (same names as el_tts.py so mix.py / build pipeline work unchanged):
  work/voice.mp3, work/timestamps.json, work/captions.ass
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from el_tts import DEFAULT_MODEL, DEFAULT_VOICE_ID, extract_words, fmt_ass_time, probe_duration  # noqa: E402


def build_ass_16x9(words: list[dict], out_ass: Path, max_words: int = 5, max_chars: int = 34) -> list[dict]:
    chunks = []
    i = 0
    while i < len(words):
        grp = [words[i]]
        i += 1
        while i < len(words) and len(grp) < max_words:
            prev = grp[-1]["word"]
            if prev.endswith((".", "!", "?", ":", ";", "…")):
                break
            cand = " ".join(x["word"] for x in grp + [words[i]])
            if len(cand) > max_chars and len(grp) >= 2:
                break
            if words[i]["start"] - grp[-1]["end"] > 0.35:
                break
            if prev.endswith(",") and len(grp) >= 3:
                break
            grp.append(words[i])
            i += 1
        chunks.append({"text": " ".join(x["word"] for x in grp), "start": grp[0]["start"], "end": grp[-1]["end"]})

    for idx in range(len(chunks) - 1):
        gap = chunks[idx + 1]["start"] - chunks[idx]["end"]
        if 0 < gap < 0.18:
            chunks[idx]["end"] = chunks[idx + 1]["start"]
        elif chunks[idx]["end"] > chunks[idx + 1]["start"]:
            chunks[idx]["end"] = max(chunks[idx]["start"] + 0.08, chunks[idx + 1]["start"])

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,62,&H00FFFFFF,&H0000D6FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6.5,2.0,2,120,120,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for ch in chunks:
        txt = ch["text"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        lines.append(f"Dialogue: 0,{fmt_ass_time(ch['start'])},{fmt_ass_time(ch['end'])},Default,,0,0,0,,{txt}")
    out_ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chunks


def tts_chapter(text: str, out_mp3: Path, voice_id: str, model: str, stability: float, api_key: str) -> list[dict]:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    payload = {
        "text": text,
        "model_id": model,
        "language_code": "tr",
        "voice_settings": {"stability": stability, "similarity_boost": 0.78},
        "output_format": "mp3_44100_128",
    }
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        if resp.status_code == 200:
            break
        print(f"[el_tts_long] HTTP {resp.status_code} (attempt {attempt + 1}): {resp.text[:300]}", file=sys.stderr)
    else:
        sys.exit(1)
    body = resp.json()
    out_mp3.write_bytes(base64.b64decode(body["audio_base64"]))
    alignment = body.get("normalized_alignment") or body.get("alignment") or {}
    return extract_words(alignment)


def main():
    ap = argparse.ArgumentParser(description="Long-form chapter TTS + 16:9 ASS captions")
    ap.add_argument("--script", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--voice-id", default=DEFAULT_VOICE_ID)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--stability", type=float, default=0.5)
    ap.add_argument("--gap", type=float, default=0.45)
    ap.add_argument("--reuse", action="store_true")
    args = ap.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    voice_mp3 = work / "voice.mp3"
    ts_json = work / "timestamps.json"
    ass_path = work / "captions.ass"

    if args.reuse and voice_mp3.exists() and ts_json.exists():
        data = json.loads(ts_json.read_text(encoding="utf-8"))
        build_ass_16x9(data["words"], ass_path)
        print(f"[el_tts_long] Reused voice ({data['duration']:.2f}s, {len(data['words'])} words)")
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY environment variable is required.", file=sys.stderr)
        sys.exit(1)

    text = Path(args.script).read_text(encoding="utf-8").strip()
    chapters = [c.strip().replace("\n", " ") for c in text.split("\n\n") if c.strip()]
    print(f"[el_tts_long] {len(chapters)} chapters, {len(text)} chars")

    chap_dir = work / "chapters"
    chap_dir.mkdir(exist_ok=True)
    all_words = []
    wavs = []
    offset = 0.0
    sil = chap_dir / "gap.wav"
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                           "-t", f"{args.gap:.3f}", str(sil)])
    for ci, chap in enumerate(chapters):
        mp3 = chap_dir / f"ch{ci:02d}.mp3"
        wav = chap_dir / f"ch{ci:02d}.wav"
        words = tts_chapter(chap, mp3, args.voice_id, args.model, args.stability, api_key)
        subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ar", "48000", "-ac", "2", str(wav)])
        dur = probe_duration(wav)
        for w in words:
            all_words.append({"word": w["word"], "start": round(w["start"] + offset, 3), "end": round(w["end"] + offset, 3)})
        print(f"[el_tts_long]  ch{ci:02d}: {dur:.2f}s, {len(words)} words (offset {offset:.2f}s)")
        wavs.append(wav)
        offset += dur
        if ci < len(chapters) - 1:
            wavs.append(sil)
            offset += args.gap

    lst = chap_dir / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in wavs), encoding="utf-8")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                           "-ar", "48000", "-ac", "2", "-b:a", "128k", str(voice_mp3)])
    duration = probe_duration(voice_mp3)
    chunks = build_ass_16x9(all_words, ass_path)
    ts_json.write_text(json.dumps({
        "voice_id": args.voice_id, "model": args.model, "duration": duration,
        "words": all_words, "chunks": chunks, "chapters": len(chapters),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[el_tts_long] voice.mp3 {duration:.2f}s, {len(all_words)} words, {len(chunks)} ASS cues")


if __name__ == "__main__":
    main()
