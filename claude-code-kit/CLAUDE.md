# Likya Studios — Claude Code Otomatik Yayın Talimatı

Bu klasördeki videoları bitirdiğinde kullanıcı **"yayınla"** veya **"planla"** derse,
`likya_push.py` komutunu çalıştırarak videoyu doğrudan **Likya Stüdyo (`studio.likyastudios.live`)**
ve ilgili **YouTube + Instagram** kanallarına otomatik planla.

## Markalar (`--brand`)
- `akilalmaz` → AKILALMAZ (Absürt tarih & gerçek hikâyeler)
- `kadimanadolu` → Kadim Anadolu (`@kadimanadoluu` / `@kadimanadollu`)
- `likyastudios` → Likya Studios (`@likyastudios`)
- `foodballstv` → FoodBallsTV (`@FoodBallsTV` / `@foodballstv`)

## Komut Şablonu
```bash
python3 likya_push.py \
  --brand <MARKA> \
  --video "<MP4_DOSYA_YOLU>" \
  --title "<YOUTUBE_SHORTS_BASLIGI>" \
  --desc "<YOUTUBE_ACIKLAMA_VE_HASHTAGLER>" \
  --ig "<INSTAGRAM_REELS_ACIKLAMA>" \
  --cover-file "<KAPAK_JPG_YOLU>" \
  --cover-prompt "<INGILIZCE_9_16_KAPAK_PROMPTU>"
```

## Kurallar
1. `LIKYA_API_KEY` değerini `.env` dosyasından okur; kod içine asla yazma.
2. `--scheduled-at` belirtilmezse sistem o markanın sıradaki **06:01–06:07 TR** haftalık slotunu otomatik atar.
3. Kendi tasarladığımız kapak (`kapak.jpg`, 1080x1920) varsa **her zaman `--cover-file`** ile ver; stüdyoya bu yüklenir ve YouTube küçük resmi + Instagram kapağı olur. `--cover-prompt` yalnızca yedektir (kapak dosyası yoksa veya yüklenemezse). Yayındaki/planlı bir videonun kapağını sonradan değiştirmek için: `curl -H "X-API-Key: $LIKYA_API_KEY" -F key=<video-id> -F file=@kapak.jpg $API/api/covers/upload`.
4. `--cover-prompt` her zaman İngilizce, 9:16 dikey, çarpıcı ve yazısız (`no text`) olarak yaz.
