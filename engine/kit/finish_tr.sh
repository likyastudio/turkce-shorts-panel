#!/usr/bin/env bash
# engine/kit/finish_tr.sh — Exact AKILALMAZ v9–v20 Final Encode & QA Pipeline
# Usage: finish_tr.sh <EPISODE_DIR> <OUT_MP4_NAME>
#   Expects:
#     <EPISODE_DIR>/frames/f0000.jpg ...
#     <EPISODE_DIR>/work/mix_raw.wav
#     <EPISODE_DIR>/work/captions.ass
#   Produces:
#     <EPISODE_DIR>/work/mix_final.wav   (loudnorm I=-14 TP=-1.5 LRA=7, 48kHz stereo)
#     <EPISODE_DIR>/out/<OUT_MP4_NAME>   (1080x1920 2x Lanczos, 30fps, ASS burned, CRF 23 maxrate 2000k)
#     <EPISODE_DIR>/out/qa_sheet.jpg     (fps=0.4, scale=216:-1, tile=6x4)

set -euo pipefail

EP_DIR="${1:?Usage: finish_tr.sh <EPISODE_DIR> <OUT_MP4_NAME>}"
MP4_NAME="${2:?Usage: finish_tr.sh <EPISODE_DIR> <OUT_MP4_NAME>}"

mkdir -p "${EP_DIR}/out" "${EP_DIR}/work"

echo "[finish_tr] 1/3 Normalizing audio (loudnorm I=-14 TP=-1.5 LRA=7)..."
ffmpeg -v error -y \
  -i "${EP_DIR}/work/mix_raw.wav" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=7" \
  -ar 48000 -ac 2 \
  "${EP_DIR}/work/mix_final.wav"

echo "[finish_tr] 2/3 Encoding 1080x1920 30fps H.264 + 2x Lanczos + Turkish ASS..."
OUT_MP4="${EP_DIR}/out/${MP4_NAME}"
ASS_FILE="${EP_DIR}/work/captions.ass"

ffmpeg -v error -y \
  -framerate 30 -i "${EP_DIR}/frames/f%04d.jpg" \
  -i "${EP_DIR}/work/mix_final.wav" \
  -map 0:v:0 -map 1:a:0 \
  -vf "scale=1080:1920:flags=lanczos,ass=${ASS_FILE}" \
  -c:v libx264 -preset slow -crf 23 -maxrate 2000k -bufsize 4000k \
  -pix_fmt yuv420p -c:a aac -b:a 128k \
  -shortest -movflags +faststart \
  "${OUT_MP4}"

echo "[finish_tr] 3/3 Running QA (freezedetect, blackdetect, ebur128, 6x4 qa_sheet.jpg)..."
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

ffmpeg -v error -y -i "${OUT_MP4}" \
  -vf "fps=0.4,scale=216:-1,tile=6x4" \
  -frames:v 1 -q:v 3 \
  "${EP_DIR}/out/qa_sheet.jpg"

SIZE_MB=$(du -m "${OUT_MP4}" | awk '{print $1}')
DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${OUT_MP4}")
echo "[finish_tr] DONE: ${OUT_MP4} (${SIZE_MB} MB, ${DUR}s) + out/qa_sheet.jpg"
