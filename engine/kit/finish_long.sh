#!/usr/bin/env bash
# engine/kit/finish_long.sh — 16:9 (1920x1080) Long-Form Final Encode & QA Pipeline
# Exact AKILALMAZ 3D-Toon quality in 16:9 widescreen:
#   - 960x540 -> 2x Lanczos 1920x1080, 30fps, Turkish ASS captions burned
#   - loudnorm I=-14 TP=-1.5 LRA=7, 48kHz stereo, AAC 160k
#   - H.264 CRF 24 maxrate 2200k bufsize 4400k (crisp for flat 3D-toon, keeps 3.5-min file ~35-48 MB)
#   - QA: freezedetect + blackdetect + ebur128 + 6x4 widescreen qa_sheet.jpg (24 evenly spaced frames)

set -euo pipefail

EP_DIR="${1:?Usage: finish_long.sh <EPISODE_DIR> <OUT_MP4_NAME>}"
MP4_NAME="${2:?Usage: finish_long.sh <EPISODE_DIR> <OUT_MP4_NAME>}"

mkdir -p "${EP_DIR}/out" "${EP_DIR}/work"

echo "[finish_long] 1/3 Normalizing audio (loudnorm I=-14 TP=-1.5 LRA=7)..."
ffmpeg -v error -y \
  -i "${EP_DIR}/work/mix_raw.wav" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=7" \
  -ar 48000 -ac 2 \
  "${EP_DIR}/work/mix_final.wav"

echo "[finish_long] 2/3 Encoding 1920x1080 (16:9) 30fps H.264 + 2x Lanczos + Turkish ASS..."
OUT_MP4="${EP_DIR}/out/${MP4_NAME}"
ASS_FILE="${EP_DIR}/work/captions.ass"

ffmpeg -v error -y \
  -framerate 30 -i "${EP_DIR}/frames/f%04d.jpg" \
  -i "${EP_DIR}/work/mix_final.wav" \
  -map 0:v:0 -map 1:a:0 \
  -vf "scale=1920:1080:flags=lanczos,ass=${ASS_FILE}" \
  -c:v libx264 -preset medium -crf 24 -maxrate 2200k -bufsize 4400k \
  -pix_fmt yuv420p -c:a aac -b:a 160k \
  -shortest -movflags +faststart \
  "${OUT_MP4}"

echo "[finish_long] 3/3 Running QA (freezedetect, blackdetect, ebur128, 6x4 16:9 qa_sheet.jpg)..."
FREEZE_BLACK=$(ffmpeg -hide_banner -i "${OUT_MP4}" -vf "freezedetect=n=0.0005:d=0.4,blackdetect=d=0.05" -f null - 2>&1 | grep -E "freeze_start|black_start" || true)
if [ -n "${FREEZE_BLACK}" ]; then
  echo "[QA WARN] Freeze/Black detected:"
  echo "${FREEZE_BLACK}"
else
  echo "[QA OK] 0 freeze frames, 0 black frames"
fi

LUFS=$(ffmpeg -hide_banner -i "${OUT_MP4}" -af ebur128=framelog=quiet -f null - 2>&1 | grep -E "I:|True peak:" | tail -n 2 || true)
echo "[QA AUDIO]"
echo "${LUFS}"

DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${OUT_MP4}")
# Compute fps so 24 tiles span the full 3–4 minute video cleanly
SHEET_FPS=$(python3 -c "d=max(10.0, float('${DUR}')); print(f'{24.0 / d:.6f}')")

ffmpeg -v error -y -i "${OUT_MP4}" \
  -vf "fps=${SHEET_FPS},scale=320:-1,tile=6x4" \
  -frames:v 1 -q:v 3 \
  "${EP_DIR}/out/qa_sheet.jpg"

SIZE_MB=$(du -m "${OUT_MP4}" | awk '{print $1}')
echo "[finish_long] DONE: ${OUT_MP4} (${SIZE_MB} MB, ${DUR}s) + out/qa_sheet.jpg"
