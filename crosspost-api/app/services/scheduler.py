"""Weekly rotating slot calculator (06:01 Mon -> 06:07 Sun, Europe/Istanbul UTC+3)
and Vertex AI daily autonomous Shorts story generator."""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

TR_TZ = timezone(timedelta(hours=3))  # Europe/Istanbul (permanent UTC+3)
TR_DAY_NAMES = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def weekly_slot_for_date(tr_date) -> datetime:
    """Returns the exact Turkey-time datetime for a given date:
    Monday -> 06:01, Tuesday -> 06:02, ..., Sunday -> 06:07 (resets weekly).
    """
    minute = 1 + tr_date.weekday()  # Mon=0 -> 06:01 ... Sun=6 -> 06:07
    return datetime(tr_date.year, tr_date.month, tr_date.day, 6, minute, 0, tzinfo=TR_TZ)


def format_tr_label(dt_utc_or_iso: Any) -> str:
    if isinstance(dt_utc_or_iso, str):
        dt = datetime.fromisoformat(dt_utc_or_iso.replace("Z", "+00:00"))
    else:
        dt = dt_utc_or_iso
    tr = dt.astimezone(TR_TZ)
    day_name = TR_DAY_NAMES[tr.weekday()]
    return tr.strftime(f"%d.%m.%Y {day_name} · %H:%M TR")


def next_weekly_slot(
    occupied_iso_list: Optional[list[str]] = None,
    now_utc: Optional[datetime] = None,
) -> dict[str, str]:
    """Finds the next available daily slot following the weekly 06:01-06:07 TR rule,
    skipping any calendar date (TR) that already has a scheduled post."""
    now = (now_utc or datetime.now(timezone.utc)).astimezone(TR_TZ)
    occupied_dates: set[str] = set()
    for iso in (occupied_iso_list or []):
        try:
            d = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(TR_TZ)
            occupied_dates.add(d.strftime("%Y-%m-%d"))
        except Exception:
            pass

    cand_date = now.date()
    for _ in range(365):
        slot_tr = weekly_slot_for_date(cand_date)
        date_key = cand_date.strftime("%Y-%m-%d")
        # Must be at least 2 minutes in the future and not already occupied
        if slot_tr > (now + timedelta(minutes=2)) and date_key not in occupied_dates:
            slot_utc = slot_tr.astimezone(timezone.utc)
            return {
                "scheduled_at_utc": slot_utc.isoformat(),
                "scheduled_at_tr": slot_tr.isoformat(),
                "label_tr": format_tr_label(slot_utc),
                "date_tr": date_key,
            }
        cand_date = cand_date + timedelta(days=1)

    raise RuntimeError("Uygun yayın slotu bulunamadı.")


def generate_daily_story(existing_titles: list[str], topic_hint: str = "") -> dict[str, Any]:
    """Generates a fresh, original Turkish absurd-history YouTube Short script & metadata
    using Vertex AI Gemini (gemini-2.5-flash)."""
    from google import genai
    from google.genai import types

    project = os.getenv("VERTEX_PROJECT_ID", "likyastudios")
    location = os.getenv("VERTEX_LOCATION", "us-central1")
    model = os.getenv("VERTEX_STORY_MODEL", "gemini-2.5-flash")

    avoid_block = "\n".join(f"- {t}" for t in existing_titles[:50]) if existing_titles else "(yok)"
    hint_line = f"\nÖzel konu isteği: {topic_hint}" if topic_hint.strip() else ""

    prompt = f"""Sen Türkiye'nin en yüksek izlenme oranına sahip 'AKILALMAZ' YouTube Shorts ve Instagram Reels kanalının baş senaristisin.
Gerçek ama kulağa imkânsız gelen, tarihi, bilimsel veya absürt bir GERÇEK olayı 40-48 saniyelik sürükleyici bir dikey animasyon videosu için hazırla.

KESİNLİKLE TEKRAR ETMEYECEĞİN MEVCUT VİDEOLAR:
{avoid_block}
{hint_line}

KURALLAR:
1. İlk cümle (0-3 saniye) izleyiciyi anında durduran şok edici bir kanca (hook) olmalı.
2. Toplam senaryo 95-115 kelime arası, akıcı konuşma Türkçesi, kısa cümleler.
3. Son cümlede zekice bir kapanış + hafif merak/yorum sorusu olsun ("Sence ...?").
4. Sahne planında 6-7 kısa görsel sahne başlığı ve her sahne için 1-2 kelimelik vurucu ekran metni ver.
5. Çıktıyı SADECE geçerli JSON olarak ver, başka hiçbir açıklama ekleme.

JSON ŞEMASI:
{{
  "slug_suffix": "kisa_ascii_slug_ornek",
  "title": "Kısa Çarpıcı Türkçe Başlık (max 45 karakter)",
  "script": "Seslendirilecek tam Türkçe metin (95-115 kelime, noktalama işaretleri temiz)",
  "scenes": [
    {{
      "headline": "EKRAN BAŞLIĞI (2-4 KELİME)",
      "subline": "Kısa alt bilgi (max 6 kelime)",
      "emoji": "🔥",
      "bg_hex": "#161925",
      "accent_hex": "#f2b830"
    }}
  ],
  "youtube": {{
    "title": "YouTube Shorts Başlığı #shorts",
    "description": "2 cümlelik merak uyandıran açıklama + 5 ilgili Türkçe hashtag (#shorts #ilginçbilgiler #akılalmaz ...)"
  }},
  "instagram": {{
    "caption": "Instagram Reels açıklaması + yorum sorusu + 6 hashtag"
  }},
  "flow_prompt": "Bold vertical 9:16 cartoon illustration YouTube Shorts thumbnail in vibrant comic-book vector style, dramatic lighting, high contrast, vivid colors, depicting the exact absurd historical event in vivid visual detail, no text"
}}"""

    client = genai.Client(vertexai=True, project=project, location=location)
    import time
    data = None
    for attempt in range(3):  # Model ara sıra bozuk JSON / geçici hata döndürüyor
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.85,
                    response_mime_type="application/json",
                ),
            )
            raw = (resp.text or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw).rstrip("`").strip()
            data = json.loads(raw)
            if not isinstance(data, dict) or not data.get("script") or not data.get("title"):
                raise ValueError("Model eksik senaryo döndürdü.")
            break
        except Exception as e:
            print(f"[ai] senaryo denemesi {attempt + 1}/3 başarısız: {type(e).__name__}: {e}")
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    suffix = re.sub(r"[^a-z0-9_]", "_", str(data.get("slug_suffix", "yeni_hikaye")).lower()).strip("_")
    data["slug_suffix"] = suffix[:36] or "yeni_hikaye"
    return data
