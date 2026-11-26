# AKILALMAZ 3D-Toon Shorts Studio Engine (`v9–v20+`)

Bu klasör, **AKILALMAZ** Türkçe YouTube Shorts / Instagram Reels kanalının (v2, v9–v20 serisi) birebir 3D-Toon + 2D kalın çizgili karakter üretim motorunu içerir.

## Mimari Özeti
- **WebGL Sahnesi ([`kit/toonbase.js`](kit/toonbase.js)):** `540×960` 30fps `PerspectiveCamera(40)`, 2-ton cel gradient (`[92,92,92,255, 255,255,255,255]`), `PCFSoftShadowMap`, `SRGBColorSpace`, `NoToneMapping`.
  - **4 Bölge (`x = 0, 60, 120, 180`):** Dış mekan taş yol + tabela + özel 3D `heroProp` (`z = -8.6`) ve 3 iç mekan altın çerçeveli pano + ahşap masa.
  - **3 Aşamalı Post-Processing:** `rtColor` (HalfFloat) → `rtNd` (Normal+Depth) → `rtInk` (8-tap siyah mürekkep kenar çizgisi + doygunluk + vinyet + beyaz flaş geçişi) → `dofScene` (6-tap Poisson bokeh + `linearToOutputTexel`).
- **2D Karakter Motoru ([`kit/toon.js`](kit/toon.js)):** `600×1000` Canvas (`cx=300, sole=975, u=2.08, ow=9.2, INK=#1b141c`), `Card` (`CM=2.25`, `customDepthMaterial`, `cardNd`, zemin gölge blobu), 13 yüz ifadesi + alias haritası, 7 kol pozu, şapkalar, gözlükler, el aksesuarları (`axe`, `clipboard`, `geiger`, `chalk`), ter damlası, göz kırpma ve nefes bob animasyonu.
- **10 Sahneli Kesintisiz Loop Kurgusu ([`kit/story_runtime.js`](kit/story_runtime.js)):** Her sahne kesimi ElevenLabs kelime zaman damgalarındaki çapa kelimelere (`anchor`) kilitlenir; böylece anlatım ile ekrandaki sahne/pano/rozet %100 senkron kalır.
- **Headless CDP Render ([`kit/render_cdp.mjs`](kit/render_cdp.mjs)):** Node 22 yerleşik `WebSocket` ile Chromium SwiftShader CDP (`WORKERS=2`, `RESUME=1`, `VW=540`, `VH=960`, 850 karelik parçalar).
- **Ses, Altyazı & Encode:**
  - [`kit/el_tts.py`](kit/el_tts.py): ElevenLabs `eleven_v4` (`stability=0.5`, duygusal parantez etiketleri) + senkron 2–3 kelimelik Türkçe `captions.ass`.
  - [`kit/mix.py`](kit/mix.py): Neşeli prosedürel synth/marimba+ritim BGM (`--music-db -12.0`) + sahne/rozet SFX (`-6.4 dB`).
  - [`kit/finish_tr.sh`](kit/finish_tr.sh): `loudnorm=I=-14:TP=-1.5:LRA=7`, `scale=1080:1920:flags=lanczos,ass=work/captions.ass`, `libx264 -preset slow -crf 23 -maxrate 2000k`, `freezedetect`/`blackdetect`/`ebur128` QA + `6×4` `qa_sheet.jpg`.

## Hızlı Kullanım

```bash
ELEVENLABS_API_KEY="<API_KEY>" \
ELEVENLABS_VOICE_ID="jdpQqF5lMnLWcXlPOnAU" \
ELEVENLABS_MODEL="eleven_v4" \
python3 engine/build_short.py \
  --episode engine/episodes/v21_stadyum_nukleer_reaktor.json \
  --music-db -12.0 \
  --sfx-db -6.4 \
  --workers 2 \
  --sync-panel
```

> **Güvenlik:** API anahtarları hiçbir zaman kod veya JSON dosyalarına yazılmaz; daima ortam değişkenlerinden (`ELEVENLABS_API_KEY`, `LIKYA_API_KEY`) okunur.
