#!/usr/bin/env python3
"""AKILALMAZ Batch 3D-Toon + 2D Çöp Adam Shorts Factory (v22–v26).

Ultra-fast hybrid architecture:
1. Launches Headless Chrome + Three.js ONCE to bake crisp 1296x2304 3D-toon environment
   & beveled 3D info-board plates with real PCFSoftShadowMap lighting.
2. Synthesizes ERKAN (erkanv2: jdpQqF5lMnLWcXlPOnAU, model: eleven_v4) expressive narration
   + tag-stripped millisecond word timestamps.
3. Synthesizes lively marimba/Rhodes/bass/drums BGM (--music-db -12.0) + synced cartoon SFX.
4. Composites 30fps smooth camera zoom/pan/shake + bespoke 2D thick-outlined stick-figure
   ("çöp adam") cartoon characters, animated props, badges, white flash cuts, and synced bold
   Turkish captions directly into FFmpeg rawvideo stdin (~45-60s per 1080x1920 30fps MP4!).
5. Supports Cloud Run /api/covers/generate (9:16 Vertex AI cover) + quota-aware YouTube/IG
   auto-slot scheduling (--covers-and-schedule).
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

REPO_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import synth_bgm_sfx  # noqa: E402

VIDEOS_JSON = REPO_DIR / "videos.json"
BAKER_HTML = SCRIPTS_DIR / "scene_baker.html"
W, H = 1080, 1920
FPS = 30
VOICE_TEMPO = 1.09
INK = (24, 23, 34)


# ---------------------------------------------------------------------------
# 5 Brand-New Viral Real Absurd History Episodes (v22–v26)
# ---------------------------------------------------------------------------
EPISODES: list[dict[str, Any]] = [
    {
        "num": 22,
        "slug": "v22_pekmez_tsunamisi",
        "file_name": "Video22-Boston-Dev-Pekmez-Tsunamisi.mp4",
        "title": "Sokakları Yutan Dev Pekmez Tsunamisi",
        "bpm": 119.0,
        "tts_script": (
            "[excited] Sokakları saatte elli altı kilometre hızla yutan, yedi buçuk metre yüksekliğinde dev bir pekmez tsunamisi yaşandığını biliyor muydunuz?\n"
            "[amused] Şaka yapmıyorum, koca bir şehir sular altında değil, yapış yapış pekmez altında kaldı!\n"
            "[storytelling] On beş Ocak bin dokuz yüz on dokuzda Boston limanında sekiz virgül yedi milyon litrelik dev pekmez tankı gürültüyle patladı!\n"
            "[curious] Tank aylardır sızdırıyordu; şirket tamir etmek yerine sızıntı belli olmasın diye dışını kahverengiye boyamıştı!\n"
            "[surprised] Hava aniden ısınınca basınç patladı ve iki katlı bina boyunda dev pekmez dalgası şehre daldı!\n"
            "[excited] Yapışkan sel demir tren raylarını büktü, koca ahşap evleri temelinden söktü, itfaiyeciler dizlerine kadar pekmeze saplandı!\n"
            "[amused, chuckles] Şehri temizlemek tam haftalar sürdü; liman suları yaz aylarına kadar kahverengi aktı!\n"
            "[storytelling] Bostonlular hâlâ çok sıcak yaz günlerinde sokaklarda hafif pekmez kokusu aldığını söyler! İşte tarihin en tatlı felaketi şöyle anlatılır:"
        ),
        "meta": {
            "youtube": {
                "title": "Sokakları 56 km Hızla Yutan Dev Pekmez Tsunamisi! 🍯🌊 #shorts",
                "description": (
                    "15 Ocak 1919'da Boston'da 8,7 milyon litrelik dev pekmez tankı patladı ve 7,5 metre yüksekliğinde "
                    "yapışkan bir pekmez tsunamisi saatte 56 km hızla sokakları yuttu! Şirket aylarca sızdıran tankı "
                    "tamir etmek yerine sızıntı görünmesin diye kahverengiye boyamıştı!\n\n"
                    "👇 Sıcak yaz günlerinde hâlâ pekmez koktuğu söylenen bu sokağa gider miydin?\n\n"
                    "#shorts #tarih #ilginçbilgiler #boston #pekmez #tsunami #gerçekhikaye #animasyon #keşfet"
                ),
            },
            "instagram": {
                "caption": (
                    "Koca bir şehir su altında değil, DEV PEKMEZ TSUNAMİSİ altında kaldı! 🍯🌊😱\n\n"
                    "1919'da Boston'daki 8,7 milyon litrelik tank aylarca sızdırdı; şirket tamir etmek yerine "
                    "sızıntı belli olmasın diye tankı kahverengiye boyadı!\n\n"
                    "Tank patlayınca 7,5 metrelik yapışkan dalga saatte 56 km hızla sokaklara daldı. Temizlemek haftalar sürdü!\n\n"
                    "Arkadaşına gönder 👇\n\n"
                    "#reels #keşfet #tarih #ilginçbilgiler #gerçekhikayeler #animasyon #akılalmaz"
                ),
            },
            "cover_title": "DEV PEKMEZ TSUNAMİSİ!",
            "flow_prompt": (
                "Playful colorful 3D Pixar-style cartoon vertical poster, 9:16 aspect ratio. A historic 1919 Boston "
                "brick street where a gigantic riveted dark steel storage tank has cracked open, unleashing a massive "
                "glossy amber-brown cartoon wave of sticky molasses surging past lampposts. On the left a comical wide-eyed "
                "cartoon inspector in a cap holding a red warning flag, on the right a funny panicked citizen holding a mop "
                "with sticky brown syrup splashes in mid-air. Vivid humorous 3D-toon animation style, warm dramatic sunlight, "
                "NO text, NO words, NO letters, NO watermark."
            ),
        },
        "baker": {
            "heroKind": "molasses_tank",
            "outdoorHero": False,
            "brickWall": True,
            "heroSkyHex": 0x3b2c22,
            "roomBgHex": 0x2c2218,
            "floorA": "#9c8770", "floorB": "#756350", "floorLine": "#473b2f",
            "wallA": "#a6543a", "wallB": "#87402a", "wallLine": "#542719",
            "plaqueTop": "BOSTON · 1919", "plaqueSub": "DEV PEKMEZ TANKI",
            "boards": [
                {"title": "15 OCAK 1919 · BOSTON", "lines": ["8,7 MİLYON LİTRE PEKMEZ TANKI", "SIZINTIYI GİZLEMEK İÇİN KAHVERENGİYE BOYADILAR!", "TAMİR ETMEDİLER, PATLADI!"], "bg": "#184c96", "accent": "#f5c531", "badge": "YAPIŞKAN FELAKET!"},
                {"title": "56 KM HIZLA PEKMEZ DALGASI!", "lines": ["7,5 METRE YÜKSEKLİĞİNDE DEV DALGA", "DEMİR TREN RAYLARI BÜKÜLDÜ!", "İTFAİYECİLER PEKMEZE SAPLANDI!"], "bg": "#a81e22", "accent": "#f5c531", "badge": "2 KATLI BİNA BOYUNDA!"},
                {"title": "HAFTALARCA TEMİZLENEMEDİ!", "lines": ["LİMAN SÜREKLİ KAHVERENGİ AKTI", "SOKAKLAR AYAKKABI YAPIŞTIRIYORDU", "SICAK GÜNLERDE HÂLÂ KOKTUĞU SÖYLENİR!"], "bg": "#156e43", "accent": "#ffd84d", "badge": "TARİHİN EN TATLI OLAYI!"},
            ],
        },
        "roles": ("inspector", "citizen_sticky", "cleaner"),
        "badges": ["YAPIŞKAN TSUNAMİ!", "15 OCAK 1919 · BOSTON", "KAHVERENGİYE BOYADILAR!", "56 KM/SAAT DALGA!", "HÂLÂ PEKMEZ KOKUYOR!"],
        "sfx_main": "boing",
    },
    {
        "num": 23,
        "slug": "v23_81_askerle_donen_ordu",
        "file_name": "Video23-80-Gidip-81-Donen-Ordu.mp4",
        "title": "80 Askerle Gidip 81 Askerle Dönen Ordu",
        "bpm": 120.0,
        "tts_script": (
            "[excited] Savaşa tam seksen askerle gidip, tek bir kayıp bile vermeden... seksen bir askerle eve dönen orduyu duymuş muydunuz?\n"
            "[amused, chuckles] Yanlış duymadınız, savaşa giderken eksilmediler, yolda bir kişi daha fazlalaştılar!\n"
            "[storytelling] Bin sekiz yüz altmış altıda Avrupa'da büyük bir savaş çıkınca, minik Lihtenştayn ülkesi dağ geçidini korumak için seksen asker gönderdi.\n"
            "[curious] Askerler Alpler'in muhteşem manzarasında mevzi aldı ve haftalarca bekledi... ama ortada tek bir düşman bile yoktu!\n"
            "[amused] Onlar da sıkılınca güneşlendi, sohbet etti, piknik yaptı ve savaş bitince tek kurşun sıkmadan dönüş yoluna geçti!\n"
            "[excited] Dönüşte yolda tanıştıkları bir Avusturyalı subay onlarla o kadar iyi anlaştı ki, kanka olup Lihtenştayn'a kadar peşlerinden geldi!\n"
            "[surprised] Kasaba meydanına girdiklerinde herkes saydı: Seksen giden ordu seksen bir kişi dönmüştü!\n"
            "[amused] Askeri tarih bunu eksi bir kayıpla biten tek sefer sayar! İşte dünyanın en huzurlu savaşı şöyle anlatılır:"
        ),
        "meta": {
            "youtube": {
                "title": "Savaşa 80 Askerle Gidip 81 Askerle Dönen Ordu! 🏔️😂 #shorts",
                "description": (
                    "1866'da minik Lihtenştayn, Avusturya-Prusya Savaşı için Alpler'e 80 asker gönderdi. Haftalarca tek "
                    "bir düşman bile görmeyen askerler dağda keyif yaptı; dönüş yolunda tanıştıkları bir Avusturyalı subay "
                    "da onlarla kanka olup ülkeye taşındı! Tarihte '-1 kayıpla' biten tek askeri sefer!\n\n"
                    "👇 En iyi savaş stratejisi bu olabilir mi? Yorumlara yaz!\n\n"
                    "#shorts #tarih #ilginçbilgiler #lihtenştayn #komiktarih #gerçekhikaye #animasyon #keşfet"
                ),
            },
            "instagram": {
                "caption": (
                    "Savaşa 80 askerle gidip 81 ASKERLE dönen ordu! 🏔️🤝😂\n\n"
                    "1866'da Lihtenştayn Alpler'e 80 asker yolladı. Tek bir düşman bile gelmeyince güneşlenip sohbet ettiler.\n\n"
                    "Eve dönerken yolda tanıştıkları bir Avusturyalı subay onlarla o kadar iyi anlaştı ki o da takıma katılıp Lihtenştayn'a geldi! Tarihin '-1 kayıplı' tek savaşı!\n\n"
                    "Kankana gönder 👇\n\n"
                    "#reels #keşfet #tarih #ilginçbilgiler #gerçekhikayeler #animasyon #akılalmaz"
                ),
            },
            "cover_title": "80 GİTTİ, 81 DÖNDÜ!",
            "flow_prompt": (
                "Playful colorful 3D Pixar-style cartoon vertical poster, 9:16 aspect ratio. A sunny picturesque 1866 "
                "Alpine mountain pass with snow-capped peaks and a cozy wooden outpost cabin. Two cheerful comical cartoon "
                "19th-century Liechtenstein soldiers in blue uniforms and plumed shako hats happily walking arm-in-arm "
                "with a smiling new Austrian officer friend in a white coat carrying a wooden mug and backpack, sunny blue sky, "
                "vivid humorous 3D-toon animation style, NO text, NO words, NO letters, NO watermark."
            ),
        },
        "baker": {
            "heroKind": "alpine_outpost",
            "outdoorHero": True,
            "brickWall": False,
            "heroSkyHex": 0x62b4e8,
            "roomBgHex": 0x26322b,
            "floorA": "#659e4c", "floorB": "#487a34", "floorLine": "#315423",
            "wallA": "#cfa060", "wallB": "#a37338", "wallLine": "#6b481f",
            "plaqueTop": "LİHTENŞTAYN · 1866", "plaqueSub": "ALPLER DAĞ GEÇİDİ",
            "boards": [
                {"title": "1866 · ALPLER'DE NÖBET", "lines": ["80 ASKER SINIRA GÖNDERİLDİ", "HAFTALARCA TEK BİR DÜŞMAN GELMEDİ!", "MANZARA İZLEYİP PİKNİK YAPTILAR"], "bg": "#184c96", "accent": "#f5c531", "badge": "0 ÇATIŞMA · %100 KEYİF!"},
                {"title": "DÖNÜŞ YOLUNDA SÜRPRİZ!", "lines": ["BİR AVUSTURYALI SUBAYLA TANIŞTILAR", "KANKA OLUP BİRLİKTE YÜRÜDÜLER", "SUBAY DA LİHTENŞTAYN'A TAŞINDI!"], "bg": "#c2590c", "accent": "#ffe066", "badge": "80 + 1 YENİ DOST!"},
                {"title": "TARİHİN EN HUZURLU SEFERİ!", "lines": ["GİDEN ASKER SAYISI: 80", "DÖNEN ASKER SAYISI: 81!", "TARİHTE '-1 KAYIPLA' BİTEN TEK SAVAŞ"], "bg": "#156e43", "accent": "#ffd84d", "badge": "EFSANE İSTATİSTİK!"},
            ],
        },
        "roles": ("soldier_blue", "soldier_red", "austrian_buddy"),
        "badges": ["80 GİTTİ, 81 DÖNDÜ!", "1866 · ALPLER", "0 DÜŞMAN!", "YENİ KANKA EKİPTE!", "-1 KAYIP REKORU!"],
        "sfx_main": "sparkle",
    },
    {
        "num": 24,
        "slug": "v24_en_kisa_saltanat",
        "file_name": "Video24-Sadece-20-Dakika-Kral-Olan-Adam.mp4",
        "title": "Sadece 20 Dakika Tahtta Kalan Kral",
        "bpm": 117.0,
        "tts_script": (
            "[excited] Tahta çıkıp daha kahvesini bile soğutmadan, sadece yirmi dakika sonra tahttan inen kralı biliyor muydunuz?\n"
            "[amused] Şaka yapmıyorum, saltanatı bir yemek siparişi gelene kadar çoktan bitmişti!\n"
            "[storytelling] İki Ağustos bin sekiz yüz otuzda Fransa'da büyük bir devrim patladı ve Kral Onuncu Charles tacı bırakmak zorunda kaldı.\n"
            "[curious] Sıra otomatik olarak oğlu Louis-Antoine'a geçti! Böylece resmen Fransa Kralı On Dokuzuncu Louis oldu!\n"
            "[amused, chuckles] Ama tek bir küçük sorun vardı: Halk onu da hiç istemiyordu!\n"
            "[surprised] Yeni kral tam yirmi dakika boyunca masanın başında ağlayarak 'Bırakın bir saat bile olsa kral kalayım!' diye yalvardı.\n"
            "[excited] Ama kimse dinlemedi! Yirminci dakikanın sonunda kalemi eline alıp tahttan çekilme belgesini imzaladı!\n"
            "[amused] Guinness Rekorlar Kitabı'na tarihin en kısa hükümdarı olarak girdi! İşte bu yirmi dakikalık rekor şöyle anlatılır:"
        ),
        "meta": {
            "youtube": {
                "title": "Sadece 20 Dakika Tahtta Kalan Tarihin En Kısa Kralı! 👑⏱️ #shorts",
                "description": (
                    "2 Ağustos 1830'da Fransa Kralı X. Charles tahttan çekilince tacı oğlu XIX. Louis'ye geçti. "
                    "Ancak devrimci kalabalık onu da istemedi! Tam 20 dakika boyunca 'Bırakın biraz daha kalayım!' "
                    "diye direnen XIX. Louis sonunda imzayı attı ve Guinness Rekorlar Kitabı'na 'tarihin en kısa saltanatı' olarak girdi!\n\n"
                    "👇 20 dakikalığına kral olsan ilk hangi yasayı çıkarırdın? Yorumlara yaz!\n\n"
                    "#shorts #tarih #ilginçbilgiler #fransa #guinness #rekor #gerçekhikaye #animasyon #keşfet"
                ),
            },
            "instagram": {
                "caption": (
                    "KAHVESİ SOĞUMADAN TAHTTAN İNDİ: Sadece 20 dakika kral kaldı! 👑⏱️😂\n\n"
                    "1830 Fransa Devrimi'nde babası çekilince XIX. Louis resmen kral oldu. Tam 20 dakika boyunca "
                    "'Bırakın biraz daha kalayım!' diye yalvardı ama kalabalık dinlemedi!\n\n"
                    "20. dakikada imzayı atıp Guinness Rekorlar Kitabı'na tarihin en kısa kralı olarak geçti!\n\n"
                    "20 dakika kral olsan ne yapardın? 👇\n\n"
                    "#reels #keşfet #tarih #ilginçbilgiler #gerçekhikayeler #animasyon #rekor"
                ),
            },
            "cover_title": "SADECE 20 DAKİKA KRAL!",
            "flow_prompt": (
                "Playful colorful 3D Pixar-style cartoon vertical poster, 9:16 aspect ratio. Inside a lavish 1830 "
                "gilded French palace throne room with red velvet carpet and a gigantic gleaming golden stopwatch clock "
                "showing 20 minutes behind a royal throne. On the left a comical teary-eyed cartoon king wearing an "
                "oversized golden crown and crimson robe desperately hugging the throne, on the right a stern cartoon "
                "French guard tapping his pocket watch impatiently. Vivid humorous 3D-toon animation style, warm dramatic "
                "lighting, NO text, NO words, NO letters, NO watermark."
            ),
        },
        "baker": {
            "heroKind": "royal_throne",
            "outdoorHero": False,
            "brickWall": False,
            "heroSkyHex": 0x3b2a1e,
            "roomBgHex": 0x332418,
            "floorA": "#c9984c", "floorB": "#9e702d", "floorLine": "#694819",
            "wallA": "#e0bc79", "wallB": "#b89048", "wallLine": "#7a5b24",
            "plaqueTop": "FRANSA · 1830", "plaqueSub": "20 DAKİKALIK SALTANAT",
            "boards": [
                {"title": "2 AĞUSTOS 1830 · PARİS", "lines": ["KRAL X. CHARLES TAHTTAN ÇEKİLDİ", "TAÇ OĞLU XIX. LOUIS'YE GEÇTİ", "RESMEN FRANSA KRALI OLDU!"], "bg": "#184c96", "accent": "#f5c531", "badge": "SÜRE BAŞLADI: 00:00!"},
                {"title": "20 DAKİKA BOYUNCA YALVARDI!", "lines": ["HALK ONU DA HİÇ İSTEMEDİ!", "'BIRAKIN BİRAZ DAHA KALAYIM!' DEDİ", "KALEMİ ELİNE ALIP İMZAYI ATTI!"], "bg": "#a81e22", "accent": "#f5c531", "badge": "SÜRE DOLDU: 00:20!"},
                {"title": "GUİNNESS TARİH REKORU!", "lines": ["TOPLAM SALTANAT: SADECE 20 DAKİKA", "BİR DİZİ BÖLÜMÜNDEN BİLE KISA!", "TARİHİN EN KISA HÜKÜMDARI"], "bg": "#156e43", "accent": "#ffd84d", "badge": "20 DAKİKALIK KRAL!"},
            ],
        },
        "roles": ("king_louis", "french_guard", "french_guard"),
        "badges": ["SADECE 20 DAKİKA!", "2 AĞUSTOS 1830 · PARİS", "00:00 BAŞLADI!", "TAHTI BIRAKMAK İSTEMEDİ!", "GUİNNESS REKORU!"],
        "sfx_main": "ding",
    },
    {
        "num": 25,
        "slug": "v25_savas_gemisi_kaya",
        "file_name": "Video25-Savas-Gemisi-Ilan-Edilen-Kaya.mp4",
        "title": "Savaş Gemisi İlan Edilen Deniz Kayası",
        "bpm": 118.0,
        "tts_script": (
            "[excited] İngiliz donanmasının, denizin ortasındaki koskoca bir taş kayayı resmen 'savaş gemisi' ilan edip içine mürettebat koyduğunu biliyor muydunuz?\n"
            "[amused] Şaka yapmıyorum, yüzmeyen bir kayaya kaptan atayıp donanma siciline kaydettiler!\n"
            "[storytelling] Bin sekiz yüz dörtte Napolyon savaşları sırasında İngilizler, Karayipler'de yüz yetmiş beş metre yüksekliğinde ıssız bir deniz kayası gördü.\n"
            "[curious] Kayanın tepesine halatlarla dev toplar çektiler ve adını resmen 'Majestelerinin Gemisi Diamond Rock' koydular!\n"
            "[excited] Yüz yirmi denizci tam on yedi ay boyunca bu kayayı gerçek gemi gibi yönetti ve Fransız gemilerine geçit vermedi!\n"
            "[amused, chuckles] Üstelik bir taş parçasının tek büyük avantajı vardı: Ne kadar vurulursa vurulsun asla batmıyordu!\n"
            "[surprised] Çileden çıkan Napolyon, tek bir kayayı geri almak için tam on altı savaş gemisi göndermek zorunda kaldı!\n"
            "[storytelling] İşte hiç batmayan bu efsane taş gemi şöyle anlatılır:"
        ),
        "meta": {
            "youtube": {
                "title": "İngilizlerin 'Savaş Gemisi' İlan Ettiği Hiç Batmayan Deniz Kayası! 🪨⚓ #shorts",
                "description": (
                    "1804'te İngiliz donanması Karayipler'deki 175 metrelik ıssız bir deniz kayasının tepesine halatlarla "
                    "dev toplar çekip onu resmen 'HMS Diamond Rock' adıyla savaş gemisi ilan etti! 120 denizci 17 ay "
                    "boyunca batmayan bu taş adadan Fransız donanmasını engelledi; Napolyon kayayı almak için 16 savaş gemisi yolladı!\n\n"
                    "👇 Hiç batmayan bir kayayı savaş gemisi yapmak dahice mi yoksa çılgınca mı? Yorumlara yaz!\n\n"
                    "#shorts #tarih #ilginçbilgiler #napolyon #denizcilik #gerçekhikaye #animasyon #keşfet"
                ),
            },
            "instagram": {
                "caption": (
                    "HİÇ BATMAYAN SAVAŞ GEMİSİ: Koskoca deniz kayasını donanmaya kaydettiler! 🪨⚓😂\n\n"
                    "1804'te İngilizler Karayipler'deki 175 metrelik kayaya halatla toplar çekip adını resmen "
                    "'HMS Diamond Rock' koydu! 120 denizci 17 ay boyunca kayayı gerçek gemi gibi yönetti.\n\n"
                    "Çileden çıkan Napolyon tek bir kayayı almak için 16 savaş gemisi yollamak zorunda kaldı!\n\n"
                    "Tarih seven arkadaşına gönder 👇\n\n"
                    "#reels #keşfet #tarih #ilginçbilgiler #gerçekhikayeler #animasyon #akılalmaz"
                ),
            },
            "cover_title": "BATMAYAN TAŞ SAVAŞ GEMİSİ!",
            "flow_prompt": (
                "Playful colorful 3D Pixar-style cartoon vertical poster, 9:16 aspect ratio. A towering jagged volcanic "
                "sea rock rising out of bright turquoise Caribbean ocean waters with iron cannons perched on ledges and "
                "a red British naval flag fluttering on top. On the left a proud smiling cartoon 1804 Royal Navy captain "
                "in a bicorne hat saluting the rock, on the right a wide-eyed shocked cartoon French admiral staring "
                "through a brass spyglass in disbelief. Vivid humorous 3D-toon animation style, sunny tropical sky, "
                "NO text, NO words, NO letters, NO watermark."
            ),
        },
        "baker": {
            "heroKind": "sea_rock_fort",
            "outdoorHero": True,
            "brickWall": False,
            "heroSkyHex": 0x55b8e8,
            "roomBgHex": 0x1a2c3b,
            "floorA": "#1c82b0", "floorB": "#126187", "floorLine": "#0d4966",
            "wallA": "#c89b5e", "wallB": "#9c7036", "wallLine": "#66461c",
            "plaqueTop": "KARAYİPLER · 1804", "plaqueSub": "HMS DIAMOND ROCK",
            "boards": [
                {"title": "1804 · HMS DIAMOND ROCK", "lines": ["175 METRELİK ISSIZ DENİZ KAYASI", "HALATLARLA TEPEYE DEV TOPLAR ÇEKTİLER", "RESMEN 'SAVAŞ GEMİSİ' İLAN EDİLDİ!"], "bg": "#184c96", "accent": "#f5c531", "badge": "120 DENİZCİ MÜRETTEBAT!"},
                {"title": "ASLA BATMAYAN GEMİ!", "lines": ["17 AY BOYUNCA FRANSIZLARA GEÇİT VERMEDİ", "NE KADAR VURULSA DA BATMIYORDU!", "NAPOLYON 16 SAVAŞ GEMİSİ YOLLADI!"], "bg": "#a81e22", "accent": "#f5c531", "badge": "16 GEMİ vs 1 KAYA!"},
                {"title": "DENİZCİLİK TARİHİNİN EFSANESİ!", "lines": ["GERÇEK GEMİ GİBİ KAPTANI VARDI", "DONANMA KAYITLARINA RESMEN GEÇTİ", "HÂLÂ 'TAŞ SAVAŞ GEMİSİ' DİYE ANILIR!"], "bg": "#156e43", "accent": "#ffd84d", "badge": "100% BATMAZ TASARIM!"},
            ],
        },
        "roles": ("navy_captain", "french_admiral", "navy_captain"),
        "badges": ["TAŞTAN SAVAŞ GEMİSİ!", "1804 · KARAYİPLER", "120 DENİZCİ!", "16 GEMİ vs 1 KAYA!", "ASLA BATMADI!"],
        "sfx_main": "axe",
    },
    {
        "num": 26,
        "slug": "v26_en_pahali_yazim_hatasi",
        "file_name": "Video26-Tek-Cizgi-Yuzunden-Patlayan-Roket.mp4",
        "title": "Tek Bir Çizgi Yüzünden Patlayan Roket",
        "bpm": 121.0,
        "tts_script": (
            "[excited] Bilgisayar kodunda sadece tek bir kısa çizgi unutulduğu için, kalkıştan beş dakika sonra patlatılan dev NASA roketini biliyor muydunuz?\n"
            "[amused] Şaka yapmıyorum, küçücük bir yazım hatası bugünün parasıyla yüz elli milyon doları küle çevirdi!\n"
            "[storytelling] Yirmi iki Temmuz bin dokuz yüz altmış ikide NASA, Venüs'e gidecek Mariner Bir uzay aracını fırlattı.\n"
            "[curious] Her şey kusursuz görünüyordu... ta ki kâğıttaki matematik formülü koda geçirilirken bir harfin üstündeki minicik çizgi unutulana kadar!\n"
            "[surprised] O tek çizgi olmayınca bilgisayar hız verilerini yanlış okudu ve dev roket gökyüzünde çılgınca dönmeye başladı!\n"
            "[excited] Roket Atlantik'teki gemilerin üstüne düşmesin diye kontrol odası tam iki yüz doksan üçüncü saniyede kendini imha düğmesine bastı!\n"
            "[amused, chuckles] Bilim yazarı Arthur Clarke buna 'tarihin en pahalı kısa çizgisi' adını taktı!\n"
            "[storytelling] İşte yazılımcıların hâlâ kâbusu olan o olay şöyle anlatılır:"
        ),
        "meta": {
            "youtube": {
                "title": "Tek Bir Kısa Çizgi Unutulduğu İçin Patlayan 150 Milyon Dolarlık NASA Roketi! 🚀💥 #shorts",
                "description": (
                    "22 Temmuz 1962'de NASA'nın Venüs'e gönderdiği Mariner 1 roketi, uçuş koduna formül aktarılırken "
                    "tek bir harfin üstündeki çizgi (tire/overbar) unutulduğu için rotasından çıktı! Kontrol merkezi "
                    "293. saniyede roketi havada patlatmak zorunda kaldı. Bugünün parasıyla ~150 milyon dolarlık tek bir yazım hatası!\n\n"
                    "👇 Senin yaptığın en pahalı veya komik yazım hatası neydi? Yorumlara yaz!\n\n"
                    "#shorts #tarih #bilim #nasa #uzay #yazılım #ilginçbilgiler #gerçekhikaye #animasyon #keşfet"
                ),
            },
            "instagram": {
                "caption": (
                    "TEK BİR KISA ÇİZGİ UNUTULDU: 150 Milyon Dolarlık NASA roketi 5 dakikada patladı! 🚀💥😱\n\n"
                    "1962'de Mariner 1 uzay aracı Venüs'e fırlatıldı. Ama kâğıttaki formül koda geçirilirken "
                    "harfin üstündeki küçücük çizgi unutulmuştu!\n\n"
                    "Roket gökyüzünde çılgınca dönünce NASA kendi roketini 293. saniyede havada patlatmak zorunda kaldı! Tarihin en pahalı yazım hatası!\n\n"
                    "Yazılımcı arkadaşına gönder 👇\n\n"
                    "#reels #keşfet #tarih #bilim #nasa #yazılım #ilginçbilgiler #animasyon"
                ),
            },
            "cover_title": "150 MİLYON DOLARLIK YAZIM HATASI!",
            "flow_prompt": (
                "Playful colorful 3D Pixar-style cartoon vertical poster, 9:16 aspect ratio. A vibrant 1962 NASA "
                "rocket launchpad with a red steel gantry tower and a white Atlas rocket wobbling wildly sideways into "
                "the bright blue sky with dramatic cartoonish orange exhaust smoke loops. In the foreground left a "
                "wide-eyed panicked cartoon 1960s NASA programmer in horn-rimmed glasses and skinny tie holding a glowing "
                "giant yellow minus-sign hyphen symbol, and on the right a shocked flight director hovering his hand over "
                "a big red button. Vivid humorous 3D-toon animation style, NO text, NO words, NO letters, NO watermark."
            ),
        },
        "baker": {
            "heroKind": "nasa_launchpad",
            "outdoorHero": True,
            "brickWall": False,
            "heroSkyHex": 0x4592d6,
            "roomBgHex": 0x1d2536,
            "floorA": "#8e96a3", "floorB": "#666e7a", "floorLine": "#3e444f",
            "wallA": "#c9a870", "wallB": "#9e7c48", "wallLine": "#664e28",
            "plaqueTop": "NASA · 1962", "plaqueSub": "MARINER 1 FIRLATMASI",
            "boards": [
                {"title": "22 TEMMUZ 1962 · MARINER 1", "lines": ["VENÜS'E GİDECEK DEV NASA ROKETİ", "FORMÜL KODA GEÇİRİLİRKEN TEK ÇİZGİ UNUTULDU", "R̄ YERİNE SADECE R YAZILDI!"], "bg": "#184c96", "accent": "#f5c531", "badge": "MİNİCİK BİR YAZIM HATASI!"},
                {"title": "293. SANİYEDE İMHA EMRİ!", "lines": ["ROKET GÖKYÜZÜNDE ÇILGINCA DÖNDÜ!", "GEMİLERE DÜŞMESİN DİYE PATLATILDI", "150 MİLYON DOLAR KÜLE DÖNDÜ!"], "bg": "#a81e22", "accent": "#f5c531", "badge": "5 DAKİKADA KÜL OLDU!"},
                {"title": "TARİHİN EN PAHALI ÇİZGİSİ!", "lines": ["SADECE TEK BİR EKSİK KARAKTER", "ARTHUR CLARKE'IN UNUTULMAZ SÖZÜ:", "'TARİHİN EN PAHALI KISA ÇİZGİSİ'"], "bg": "#156e43", "accent": "#ffd84d", "badge": "KODUNU 2 KEZ KONTROL ET!"},
            ],
        },
        "roles": ("nasa_director", "nasa_coder", "nasa_coder"),
        "badges": ["150M $ YAZIM HATASI!", "22 TEMMUZ 1962 · NASA", "TEK ÇİZGİ UNUTULDU!", "293. SANİYE · İMHA!", "KODU KONTROL ET!"],
        "sfx_main": "geiger",
    },
]


# ---------------------------------------------------------------------------
# Font & Drawing Helpers (Crisp Pillow 2D Çöp Adam + Badges + Captions)
# ---------------------------------------------------------------------------
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font_path(bold: bool = True) -> str:
    cands = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if bold
        else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]


def get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    key = ("b" if bold else "r", size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(_font_path(bold), size)
    return _FONT_CACHE[key]


def clamp(v: float, a: float, b: float) -> float:
    return max(a, min(b, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * clamp(t, 0.0, 1.0)


def ease_out_back(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * ((t - 1.0) ** 3) + c1 * ((t - 1.0) ** 2)


def ease_in_out(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 2.0 * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 2) / 2.0


def strip_v4_tags(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\[[^\]]+\]\s*", "", text)).strip()


def parse_alignment_words(align: dict[str, Any]) -> list[dict[str, Any]]:
    chars = align.get("characters") or []
    starts = align.get("character_start_times_seconds") or []
    ends = align.get("character_end_times_seconds") or []
    words: list[dict[str, Any]] = []
    cur: list[str] = []
    w_st: float | None = None
    w_en: float | None = None
    in_b = False
    for ch, st, en in zip(chars, starts, ends):
        if ch == "[":
            if cur and w_st is not None and w_en is not None:
                words.append({"word": "".join(cur), "start": w_st, "end": w_en})
                cur, w_st, w_en = [], None, None
            in_b = True
            continue
        if ch == "]":
            in_b = False
            continue
        if in_b:
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
    return [w for w in words if w["word"] and not w["word"].startswith("[")]


def synthesize_erkan_voice(text: str, out_mp3: Path) -> tuple[float, list[dict[str, Any]]]:
    import requests

    el_key = os.environ["ELEVENLABS_API_KEY"].strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "jdpQqF5lMnLWcXlPOnAU")  # erkanv2
    model_id = os.getenv("ELEVENLABS_MODEL", "eleven_v4")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {"xi-api-key": el_key, "Content-Type": "application/json"}

    payloads = [
        {"text": text, "model_id": model_id, "language_code": "tr", "voice_settings": {"stability": 0.40}},
        {"text": text, "model_id": model_id, "voice_settings": {"stability": 0.50}},
        {"text": strip_v4_tags(text), "model_id": model_id},
    ]
    data = None
    last_err = None
    for idx, payload in enumerate(payloads):
        r = requests.post(url, headers=headers, json=payload, timeout=150)
        if r.ok:
            data = r.json()
            break
        last_err = f"HTTP {r.status_code}: {r.text[:260]}"
    if data is None:
        raise RuntimeError(f"ElevenLabs failed: {last_err}")

    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    out_mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    align = data.get("alignment") or data.get("normalized_alignment") or {}
    words = parse_alignment_words(align)
    dur_str = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out_mp3)],
        text=True,
    ).strip()
    duration = float(dur_str)
    if not words:
        raw_w = strip_v4_tags(text).split()
        step = duration / max(1, len(raw_w))
        words = [{"word": w, "start": i * step, "end": (i + 1) * step} for i, w in enumerate(raw_w)]
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
# 2D Thick-Outlined Stick-Figure ("Çöp Adam") Character Drawer (Pillow)
# ---------------------------------------------------------------------------
def draw_stick_char(
    draw: ImageDraw.ImageDraw,
    role: str,
    x: float,
    foot_y: float,
    scale: float,
    t: float,
    emotion: str = "happy",
    pose: str = "idle",
    speaking: bool = False,
    facing: int = 1,
    phase: float = 0.0,
) -> None:
    def S(v: float) -> float:
        return v * scale

    bob = math.sin(t * 5.2 + phase) * S(8)
    sway = math.sin(t * 2.6 + phase) * S(5)
    cx = x + sway
    hip_y = foot_y - S(165) + bob * 0.4
    torso_top = foot_y - S(345) + bob
    head_y = foot_y - S(462) + bob
    head_r = S(108)
    w_limb = max(8, int(S(16)))
    w_ink = max(6, int(S(12)))

    # Contact shadow ellipse
    draw.ellipse([x - S(108), foot_y - S(18), x + S(108), foot_y + S(20)], fill=(25, 18, 12))

    # Stick legs + shoes
    step = math.sin(t * 18 + phase) * S(13) if pose == "panic" else 0.0
    lx1, ly1 = cx - S(36), hip_y
    lx2, ly2 = cx - S(44), foot_y + step
    rx1, ry1 = cx + S(36), hip_y
    rx2, ry2 = cx + S(44), foot_y - step
    draw.line([(lx1, ly1), (lx2, ly2)], fill=INK, width=w_limb)
    draw.line([(rx1, ry1), (rx2, ry2)], fill=INK, width=w_limb)
    draw.ellipse([lx2 - S(24), ly2 - S(11), lx2 + S(18), ly2 + S(11)], fill=INK)
    draw.ellipse([rx2 - S(18), ry2 - S(11), rx2 + S(24), ry2 + S(11)], fill=INK)

    # Arms
    if pose in ("wave", "cheer"):
        wv = math.sin(t * 11 + phase) * S(26)
        lh = (cx - S(138), torso_top - S(55) + wv)
        rh = (cx + S(138), torso_top - S(55) - wv)
    elif pose == "point_up":
        pt = math.sin(t * 7 + phase) * S(12)
        lh = (cx - S(110), torso_top + S(120))
        rh = (cx + S(136) * facing, torso_top - S(72) + pt)
    elif pose == "panic":
        sh = math.sin(t * 22 + phase) * S(15)
        lh = (cx - S(138), torso_top - S(42) + sh)
        rh = (cx + S(138), torso_top - S(42) - sh)
    elif pose == "prop_hold":
        sw = math.sin(t * 9 + phase) * S(24)
        lh = (cx - S(116), torso_top - S(22) + sw)
        rh = (cx + S(116), torso_top + S(104))
    else:
        g = (math.sin(t * 10 + phase) * S(22)) if speaking else (math.sin(t * 3 + phase) * S(8))
        lh = (cx - S(116), torso_top + S(104) + g * 0.4)
        rh = (cx + S(124), torso_top + S(58) - g)

    draw.line([(cx - S(62), torso_top + S(34)), lh], fill=INK, width=w_limb)
    draw.line([(cx + S(62), torso_top + S(34)), rh], fill=INK, width=w_limb)
    hr = S(15)
    for hx, hy in (lh, rh):
        draw.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(247, 203, 160), outline=INK, width=max(4, int(S(6))))

    # Outfit colors per role
    outfit_map = {
        "inspector": ((40, 68, 118), (244, 196, 37), "sash"),
        "citizen_sticky": ((184, 72, 54), (242, 224, 190), "vest"),
        "cleaner": ((56, 128, 86), (250, 214, 78), "vest"),
        "soldier_blue": ((30, 58, 112), (244, 196, 37), "sash"),
        "soldier_red": ((168, 38, 44), (244, 196, 37), "sash"),
        "austrian_buddy": ((240, 240, 244), (212, 42, 42), "sash"),
        "king_louis": ((162, 24, 38), (255, 214, 68), "royal"),
        "french_guard": ((28, 52, 98), (235, 58, 58), "sash"),
        "navy_captain": ((24, 44, 86), (245, 204, 64), "sash"),
        "french_admiral": ((36, 62, 116), (242, 242, 248), "sash"),
        "nasa_director": ((242, 244, 248), (34, 82, 168), "tie"),
        "nasa_coder": ((242, 244, 248), (214, 52, 48), "tie"),
    }
    body_c, acc_c, style = outfit_map.get(role, ((242, 244, 248), (214, 52, 48), "tie"))

    # Torso capsule
    tw, th = S(70), S(192)
    draw.rounded_rectangle([cx - tw, torso_top, cx + tw, torso_top + th], radius=int(S(52)), fill=body_c, outline=INK, width=w_ink)

    if style == "sash":
        draw.polygon(
            [(cx - S(52), torso_top + S(12)), (cx - S(22), torso_top + S(8)),
             (cx + S(58), torso_top + S(172)), (cx + S(28), torso_top + S(182))],
            fill=acc_c, outline=INK,
        )
        draw.rectangle([cx - S(66), torso_top + S(132), cx + S(66), torso_top + S(154)], fill=INK)
        draw.rectangle([cx - S(16), torso_top + S(130), cx + S(16), torso_top + S(156)], fill=(255, 214, 68))
    elif style == "royal":
        # Golden royal collar & ermine trim
        draw.rectangle([cx - S(20), torso_top + S(8), cx + S(20), torso_top + S(184)], fill=(250, 246, 238), outline=INK, width=max(3, int(S(5))))
        draw.ellipse([cx - S(12), torso_top + S(42), cx + S(12), torso_top + S(66)], fill=acc_c, outline=INK, width=3)
    elif style == "tie":
        draw.polygon([(cx - S(12), torso_top + S(8)), (cx + S(12), torso_top + S(8)), (cx + S(14), torso_top + S(96)), (cx, torso_top + S(114)), (cx - S(14), torso_top + S(96))], fill=acc_c, outline=INK)
        draw.rectangle([cx + S(18), torso_top + S(82), cx + S(48), torso_top + S(106)], outline=INK, width=max(3, int(S(4))))
    else:
        draw.rectangle([cx - S(64), torso_top + S(128), cx + S(64), torso_top + S(148)], fill=INK)

    # Big round peach head
    draw.ellipse([cx - head_r, head_y - head_r, cx + head_r, head_y + head_r], fill=(247, 203, 160), outline=INK, width=w_ink)

    # Sticky brown molasses splashes on face for v22 citizen!
    if role == "citizen_sticky":
        for ox, oy, r in [(-58, 22, 16), (62, -16, 14), (-22, -52, 12), (46, 44, 15)]:
            draw.ellipse([cx + S(ox - r), head_y + S(oy - r), cx + S(ox + r), head_y + S(oy + r)], fill=(86, 40, 12), outline=INK, width=3)

    # Hat / Crown / Hair per role
    if role == "king_louis":
        # Golden royal crown!
        pts = [
            (cx - S(74), head_y - S(82)), (cx - S(84), head_y - S(156)),
            (cx - S(34), head_y - S(118)), (cx, head_y - S(172)),
            (cx + S(34), head_y - S(118)), (cx + S(84), head_y - S(156)),
            (cx + S(74), head_y - S(82)),
        ]
        draw.polygon(pts, fill=(255, 214, 52), outline=INK)
        draw.line(pts + [pts[0]], fill=INK, width=max(5, int(S(8))))
        draw.ellipse([cx - S(14), head_y - S(124), cx + S(14), head_y - S(96)], fill=(214, 36, 44), outline=INK, width=4)
    elif role in ("inspector", "french_guard"):
        draw.chord([cx - S(104), head_y - S(142), cx + S(104), head_y - S(42)], 180, 360, fill=(28, 54, 102), outline=INK, width=max(5, int(S(9))))
        draw.rounded_rectangle([cx - S(106), head_y - S(92), cx + S(106), head_y - S(72)], radius=8, fill=INK)
        draw.ellipse([cx - S(16), head_y - S(124), cx + S(16), head_y - S(92)], fill=(255, 214, 68), outline=INK, width=4)
    elif role in ("soldier_blue", "soldier_red", "austrian_buddy"):
        # 1866 Shako helmet + pompom!
        hat_c = (24, 42, 82) if role != "austrian_buddy" else (48, 48, 58)
        draw.rounded_rectangle([cx - S(86), head_y - S(168), cx + S(86), head_y - S(78)], radius=14, fill=hat_c, outline=INK, width=max(5, int(S(8))))
        draw.rounded_rectangle([cx - S(104), head_y - S(88), cx + S(104), head_y - S(70)], radius=8, fill=INK)
        pom_c = (255, 214, 68) if role == "soldier_blue" else (225, 52, 52)
        draw.ellipse([cx - S(18), head_y - S(192), cx + S(18), head_y - S(156)], fill=pom_c, outline=INK, width=5)
    elif role in ("navy_captain", "french_admiral"):
        # 1804 Bicorne naval hat!
        b_c = (22, 36, 74) if role == "navy_captain" else (34, 48, 92)
        draw.chord([cx - S(136), head_y - S(165), cx + S(136), head_y - S(45)], 180, 360, fill=b_c, outline=INK, width=max(5, int(S(9))))
        draw.line([(cx - S(136), head_y - S(105)), (cx + S(136), head_y - S(105))], fill=(255, 214, 68), width=max(5, int(S(8))))
    else:
        # Cute dark/brown hair cap
        h_c = (44, 34, 28) if role in ("nasa_director", "cleaner") else (84, 52, 30)
        draw.chord([cx - head_r, head_y - head_r - S(4), cx + head_r, head_y + S(10)], 190, 350, fill=h_c, outline=INK, width=max(5, int(S(8))))

    # Eyes & Brows
    blink = ((t + phase) % 3.4) > 3.25
    exl, exr, ey = cx - S(34), cx + S(34), head_y - S(4)
    ew = max(5, int(S(8)))
    if emotion in ("happy", "smug"):
        draw.arc([exl - S(20), ey - S(12), exl + S(20), ey + S(22)], 195, 345, fill=INK, width=ew)
        draw.arc([exr - S(20), ey - S(12), exr + S(20), ey + S(22)], 195, 345, fill=INK, width=ew)
    elif blink:
        draw.line([(exl - S(18), ey), (exl + S(18), ey)], fill=INK, width=ew)
        draw.line([(exr - S(18), ey), (exr + S(18), ey)], fill=INK, width=ew)
    elif emotion in ("shock", "panic"):
        er = S(24)
        jx = math.sin(t * 24 + phase) * S(3) if emotion == "panic" else 0.0
        for ex in (exl, exr):
            draw.ellipse([ex - er, ey - er, ex + er, ey + er], fill=(255, 255, 255), outline=INK, width=ew)
            draw.ellipse([ex + jx + facing * S(4) - S(8), ey - S(8), ex + jx + facing * S(4) + S(8), ey + S(8)], fill=INK)
        draw.line([(exl - S(22), ey - S(34)), (exl + S(16), ey - S(44))], fill=INK, width=ew)
        draw.line([(exr - S(16), ey - S(44)), (exr + S(22), ey - S(34))], fill=INK, width=ew)
    else:
        er = S(20)
        for ex in (exl, exr):
            draw.ellipse([ex - er, ey - er, ex + er, ey + er], fill=(255, 255, 255), outline=INK, width=ew)
            draw.ellipse([ex + facing * S(5) - S(9), ey - S(9), ex + facing * S(5) + S(9), ey + S(9)], fill=INK)

    # Horn-rimmed NASA glasses
    if role in ("nasa_director", "nasa_coder"):
        gr = S(28)
        draw.ellipse([exl - gr, ey - gr, exl + gr, ey + gr], outline=INK, width=max(4, int(S(6))))
        draw.ellipse([exr - gr, ey - gr, exr + gr, ey + gr], outline=INK, width=max(4, int(S(6))))
        draw.line([(exl + gr, ey), (exr - gr, ey)], fill=INK, width=max(4, int(S(6))))

    # Animated lip-synced mouth
    my = head_y + S(48)
    if speaking:
        oh = S(11) + abs(math.sin(t * 21 + phase)) * S(20)
        draw.ellipse([cx - S(24), my - oh, cx + S(24), my + oh], fill=(110, 26, 36), outline=INK, width=ew)
    elif emotion in ("shock", "panic"):
        draw.ellipse([cx - S(18), my - S(22), cx + S(18), my + S(24)], fill=(110, 26, 36), outline=INK, width=ew)
    elif emotion in ("happy", "smug"):
        draw.arc([cx - S(28), my - S(34), cx + S(28), my + S(16)], 20, 160, fill=INK, width=ew)
    else:
        draw.line([(cx - S(20), my), (cx + S(20), my)], fill=INK, width=ew)

    # Sweat drop on panic / shock
    if emotion in ("panic", "shock", "nervous"):
        doff = ((t * 95 + phase * 30) % 42) * scale
        dx, dy = cx + S(80), head_y - S(42) + doff
        draw.polygon([(dx, dy - S(16)), (dx + S(13), dy + S(6)), (dx, dy + S(16)), (dx - S(13), dy + S(6))], fill=(76, 211, 255), outline=INK)

    # Bespoke handheld prop in left hand!
    if pose == "prop_hold":
        px, py = lh
        if role == "inspector":
            # Red warning flag
            draw.line([(px, py + S(30)), (px, py - S(140))], fill=(140, 86, 36), width=max(5, int(S(9))))
            draw.polygon([(px, py - S(140)), (px - S(86), py - S(110)), (px, py - S(76))], fill=(224, 38, 38), outline=INK)
        elif role == "nasa_coder":
            # Giant glowing yellow HYPHEN "-" (the $150M typo!)
            draw.rounded_rectangle([px - S(72), py - S(38), px + S(72), py + S(12)], radius=12, fill=(255, 214, 52), outline=INK, width=max(5, int(S(8))))
        elif role == "king_louis":
            # Golden stopwatch
            draw.ellipse([px - S(36), py - S(36), px + S(36), py + S(36)], fill=(255, 214, 68), outline=INK, width=max(5, int(S(7))))
            draw.ellipse([px - S(26), py - S(26), px + S(26), py + S(26)], fill=(255, 250, 232))
            draw.line([(px, py), (px + S(16), py - S(12))], fill=(217, 38, 38), width=5)
        elif role in ("navy_captain", "french_admiral"):
            # Golden brass spyglass telescope
            draw.line([(px + S(24), py + S(12)), (px - S(82), py - S(28))], fill=(242, 194, 52), width=max(10, int(S(18))))
            draw.ellipse([px - S(94), py - S(40), px - S(70), py - S(16)], fill=(120, 214, 255), outline=INK, width=5)
        elif role == "austrian_buddy":
            # Wooden alpine mug
            draw.rounded_rectangle([px - S(26), py - S(42), px + S(26), py + S(18)], radius=8, fill=(168, 108, 48), outline=INK, width=max(4, int(S(6))))
            draw.ellipse([px - S(28), py - S(52), px + S(28), py - S(32)], fill=(255, 250, 238), outline=INK, width=4)


def draw_badge(draw: ImageDraw.ImageDraw, text: str, cx: int, cy: int, bg: tuple[int, int, int], fg: tuple[int, int, int], sc: float) -> None:
    if sc <= 0.05:
        return
    f = get_font(max(22, int(42 * min(1.08, sc))), bold=True)
    bb = draw.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pw, ph = int(tw + 64 * sc), int(th + 42 * sc)
    x0, y0 = cx - pw // 2, cy - ph // 2
    draw.rounded_rectangle([x0 - 6, y0 - 6, x0 + pw + 6, y0 + ph + 6], radius=ph // 2 + 6, fill=INK)
    draw.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph // 2, fill=bg)
    draw.text((cx, cy), text, font=f, fill=fg, anchor="mm")


def draw_caption(draw: ImageDraw.ImageDraw, text: str, age: float) -> None:
    if not text:
        return
    pop = lerp(0.88, 1.04, ease_out_back(age / 0.11)) if age < 0.11 else 1.0
    base_sz = int(74 * pop)
    f = get_font(base_sz, bold=True)
    while (draw.textbbox((0, 0), text, font=f)[2] > 940) and base_sz > 44:
        base_sz -= 4
        f = get_font(base_sz, bold=True)
    cy = 1525
    # Drop shadow + crisp thick black outline + white fill (exact v1-v21 AKILALMAZ look!)
    draw.text((W // 2 + 5, cy + 8), text, font=f, fill=(0, 0, 0), anchor="mm", stroke_width=12, stroke_fill=(0, 0, 0))
    draw.text((W // 2, cy), text, font=f, fill=(255, 255, 255), anchor="mm", stroke_width=12, stroke_fill=(17, 16, 24))


def crop_camera(plate: Image.Image, zoom: float, pan_x: float, pan_y: float) -> Image.Image:
    pw, ph = plate.size
    sw = int(pw / zoom)
    sh = int(ph / zoom)
    sx = int(clamp((pw - sw) * 0.5 + pan_x, 0, pw - sw))
    sy = int(clamp((ph - sh) * 0.5 + pan_y, 0, ph - sh))
    return plate.crop((sx, sy, sx + sw, sy + sh)).resize((W, H), Image.Resampling.BILINEAR)


# ---------------------------------------------------------------------------
# Bake All 3D-Toon Plates in ONE Headless Chrome Launch (~15-20s for 5 videos!)
# ---------------------------------------------------------------------------
def bake_all_plates(selected_eps: list[dict[str, Any]], plates_root: Path) -> dict[str, dict[str, Image.Image]]:
    from playwright.sync_api import sync_playwright

    chrome_exe = next((p for p in ("/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(p)), None)
    launch_kw: dict[str, Any] = {
        "headless": True,
        "args": ["--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--no-sandbox", "--disable-dev-shm-usage"],
    }
    if chrome_exe:
        launch_kw["executable_path"] = chrome_exe

    loaded: dict[str, dict[str, Image.Image]] = {}
    with sync_playwright() as p:
        b = p.chromium.launch(**launch_kw)
        page = b.new_page(viewport={"width": 1296, "height": 2304})
        page.goto(BAKER_HTML.resolve().as_uri(), wait_until="load", timeout=60000)
        page.wait_for_function("window.BAKER_READY === true", timeout=30000)

        for ep in selected_eps:
            slug = ep["slug"]
            print(f"  [3D Baker] {slug} ortam & pano plakaları üretiliyor...", flush=True)
            res = page.evaluate("(cfg) => window.bakeEpisodePlates(cfg)", ep["baker"])
            ep_dir = plates_root / slug
            ep_dir.mkdir(parents=True, exist_ok=True)
            loaded[slug] = {}
            for k, b64_png in res.items():
                fp = ep_dir / f"{k}.png"
                fp.write_bytes(base64.b64decode(b64_png))
                loaded[slug][k] = Image.open(fp).convert("RGB")
        b.close()
    return loaded


# ---------------------------------------------------------------------------
# Produce Single Episode (~50 seconds for full 1080x1920 30fps MP4!)
# ---------------------------------------------------------------------------
def produce_episode(ep: dict[str, Any], plates: dict[str, Image.Image], music_db: float = -12.0) -> dict[str, Any]:
    slug = ep["slug"]
    out_dir = REPO_DIR / "files" / slug / "out"
    work_dir = REPO_DIR / "files" / slug / "work"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    voice_path = work_dir / "voice.mp3"
    bgm_sfx_path = work_dir / "bgm_sfx.wav"
    mp4_path = out_dir / ep["file_name"]
    qa_path = out_dir / "qa_sheet.jpg"

    print(f"\n=== [{ep['num']}] {slug}: {ep['title']} ===", flush=True)
    print("  [1/4] ElevenLabs ERKAN (eleven_v4) ses + zaman damgaları...", flush=True)
    raw_dur, raw_words = synthesize_erkan_voice(ep["tts_script"], voice_path)
    tempo = VOICE_TEMPO if (raw_dur / VOICE_TEMPO) <= 58.5 else (raw_dur / 57.5)
    duration = raw_dur / tempo
    words = [{"word": w["word"], "start": w["start"] / tempo, "end": w["end"] / tempo} for w in raw_words]
    total_dur = duration + 0.35
    total_frames = int(math.ceil(total_dur * FPS))
    chunks = group_word_chunks(words, chunk_size=2)
    print(f"    -> Süre: {duration:.2f}s (ham {raw_dur:.2f}s @ {tempo:.2f}x, {total_frames} kare), {len(words)} kelime", flush=True)

    # 6 clean scenes: Hero Hook (0-18%), Hero Setup (18-34%), Board 0 (34-52%), Board 1 (52-72%), Board 2 (72-91%), Hero Loop (91-100%)
    cuts = [0.0, 0.18, 0.34, 0.52, 0.72, 0.91, 1.01]

    print(f"  [2/4] Canlı fon müziği + SFX sentezleniyor (--music-db {music_db:.1f})...", flush=True)
    sfx_events = [
        (0.40, "pop"),
        (cuts[1] * total_dur, "whoosh"),
        (cuts[1] * total_dur + 0.35, "pop_hi"),
        (cuts[2] * total_dur, "whoosh"),
        (cuts[2] * total_dur + 0.45, "ding"),
        (cuts[3] * total_dur, "whoosh"),
        (cuts[3] * total_dur + 0.45, ep["sfx_main"]),
        (cuts[4] * total_dur, "whoosh"),
        (cuts[4] * total_dur + 0.40, "sparkle"),
        (cuts[5] * total_dur, "whoosh"),
    ]
    synth_bgm_sfx.build_music_and_sfx_wav(bgm_sfx_path, total_dur + 0.25, sfx_events, bgm_gain_db=0.0)

    print("  [3/4] 1080x1920 30fps 3D-Toon + 2D Çöp Adam doğrudan FFmpeg'e render ediliyor...", flush=True)
    t0 = time.time()
    af = (
        f"[1:a]atempo={tempo:.3f},loudnorm=I=-15.5:TP=-1.5:LRA=9,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[v];"
        f"[2:a]volume={music_db:.1f}dB,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.95[aout]"
    )
    cmd = [
        "ffmpeg", "-y", "-v", "warning",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-",
        "-i", str(voice_path),
        "-i", str(bgm_sfx_path),
        "-filter_complex", af,
        "-map", "0:v", "-map", "[aout]",
        "-t", f"{total_dur:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(mp4_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    r0, r1, r2 = ep["roles"]
    badges = ep["badges"]
    qa_indices = {int(i * (total_frames - 1) / 17) for i in range(18)}
    qa_frames: list[Image.Image] = []

    for fidx in range(total_frames):
        t = fidx / FPS
        frac = clamp(t / max(0.01, total_dur), 0.0, 0.9999)
        s_idx = 5
        start_f = cuts[5]
        lfrac = 1.0
        for i in range(6):
            if cuts[i] <= frac < cuts[i + 1]:
                s_idx = i
                start_f = cuts[i]
                lfrac = (frac - cuts[i]) / (cuts[i + 1] - cuts[i])
                break
        t_local = (frac - start_f) * total_dur
        cap, cap_age, speaking = lookup_caption(chunks, t)

        if s_idx == 0:
            zoom = lerp(1.02, 1.12, ease_in_out(lfrac))
            pan_x = math.sin(lfrac * math.pi) * 28.0
            img = crop_camera(plates["hero"], zoom, pan_x, 0.0)
            draw = ImageDraw.Draw(img)
            draw_stick_char(draw, r0, 290 - pan_x * 0.25, 1790, 1.10, t, "happy", "point_up", speaking, 1, 0.2)
            draw_stick_char(draw, r1, 790 - pan_x * 0.25, 1790, 1.10, t, "shock", "prop_hold", False, -1, 1.5)
            if t_local > 0.35:
                draw_badge(draw, badges[0], 540, 200, (217, 38, 38), (255, 255, 255), ease_out_back((t_local - 0.35) / 0.35))
        elif s_idx == 1:
            zoom = lerp(1.04, 1.13, ease_in_out(lfrac))
            pan_x = lerp(-40.0, 40.0, ease_in_out(lfrac))
            img = crop_camera(plates["hero"], zoom, pan_x, 12.0)
            draw = ImageDraw.Draw(img)
            draw_stick_char(draw, r0, 300 - pan_x * 0.3, 1795, 1.12, t, "smug", "idle", speaking, 1, 0.4)
            draw_stick_char(draw, r2, 785 - pan_x * 0.3, 1795, 1.08, t, "shock", "panic", False, -1, 2.0)
            draw_badge(draw, badges[1], 540, 200, (29, 86, 168), (255, 224, 102), ease_out_back(t_local / 0.35))
        elif s_idx == 2:
            zoom = lerp(1.02, 1.10, ease_in_out(lfrac))
            pan_x = math.sin(lfrac * math.pi) * 24.0
            img = crop_camera(plates["board0"], zoom, pan_x, 0.0)
            draw = ImageDraw.Draw(img)
            draw_stick_char(draw, r0, 295, 1805, 1.08, t, "happy", "wave", speaking, 1, 0.1)
            draw_stick_char(draw, r1, 785, 1805, 1.08, t, "panic", "panic", False, -1, 1.9)
            if t_local > 0.4:
                draw_badge(draw, badges[2], 540, 195, (255, 214, 68), INK, ease_out_back((t_local - 0.4) / 0.35))
        elif s_idx == 3:
            zoom = lerp(1.03, 1.13, ease_in_out(lfrac))
            shx = math.sin(t * 28.0) * 6.0 * clamp(lfrac * 2.0, 0.0, 1.0)
            shy = math.cos(t * 24.0) * 4.0 * clamp(lfrac * 2.0, 0.0, 1.0)
            img = crop_camera(plates["board1"], zoom, shx, shy)
            draw = ImageDraw.Draw(img)
            draw_stick_char(draw, r0, 280, 1805, 1.06, t, "nervous", "point_up", speaking, 1, 0.6)
            draw_stick_char(draw, r1, 790, 1805, 1.12, t, "shock", "prop_hold", False, -1, 0.2)
            if t_local > 0.4:
                draw_badge(draw, badges[3], 540, 195, (255, 207, 51), INK, ease_out_back((t_local - 0.4) / 0.35))
        elif s_idx == 4:
            zoom = lerp(1.02, 1.11, ease_in_out(lfrac))
            img = crop_camera(plates["board2"], zoom, 0.0, 0.0)
            draw = ImageDraw.Draw(img)
            draw_stick_char(draw, r0, 300, 1805, 1.10, t, "happy", "cheer", speaking, 1, 0.3)
            draw_stick_char(draw, r2, 780, 1805, 1.10, t, "happy", "cheer", False, -1, 1.1)
            if t_local > 0.4:
                draw_badge(draw, badges[4], 540, 195, (255, 214, 68), INK, ease_out_back((t_local - 0.4) / 0.35))
        else:
            zoom = lerp(1.08, 1.02, ease_in_out(lfrac))
            img = crop_camera(plates["hero"], zoom, 0.0, 0.0)
            draw = ImageDraw.Draw(img)
            draw_stick_char(draw, r0, 290, 1790, 1.10, t, "happy", "cheer", speaking, 1, 0.2)
            draw_stick_char(draw, r1, 790, 1790, 1.10, t, "happy", "prop_hold", False, -1, 1.5)

        # Crisp white camera-flash cut
        if s_idx > 0 and t_local < 0.15:
            alpha = int(175 * (1.0 - t_local / 0.15))
            flash = Image.new("RGBA", (W, H), (255, 250, 238, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), flash).convert("RGB")
            draw = ImageDraw.Draw(img)

        draw_caption(draw, cap, cap_age)
        proc.stdin.write(img.tobytes())
        if fidx in qa_indices:
            qa_frames.append(img.copy())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg failed on {slug} with code {rc}")
    bgm_sfx_path.unlink(missing_ok=True)

    # Save 6x3 QA Sheet
    tw, th = 270, 480
    sheet = Image.new("RGB", (6 * tw, 3 * th), (12, 12, 16))
    for pos, im in enumerate(qa_frames[:18]):
        r_i, c_i = divmod(pos, 6)
        sheet.paste(im.resize((tw, th), Image.Resampling.LANCZOS), (c_i * tw, r_i * th))
    sheet.save(qa_path, "JPEG", quality=88, optimize=True)

    size_mb = round(mp4_path.stat().st_size / (1024 * 1024), 1)
    clean_script = strip_v4_tags(ep["tts_script"])
    entry = {
        "slug": slug,
        "title": ep["title"],
        "status": "Hazır",
        "script": clean_script,
        "meta": ep["meta"],
        "words": len(clean_script.split()),
        "frames": total_frames,
        "voice": f"files/{slug}/work/voice.mp3",
        "qa": f"files/{slug}/out/qa_sheet.jpg",
        "video": f"files/{slug}/out/{ep['file_name']}",
        "fileName": ep["file_name"],
        "sizeMB": size_mb,
        "updated": datetime.now(timezone.utc).isoformat(),
        "width": W,
        "height": H,
        "duration": round(total_dur, 3),
    }
    print(f"  [4/4] ✅ {mp4_path.name} hazır ({size_mb} MB, {total_dur:.1f}s, {time.time() - t0:.1f}s render)", flush=True)
    return entry


# ---------------------------------------------------------------------------
# Cloud Run Vertex AI 9:16 Covers + Quota-Aware Auto-Slot Scheduling
# ---------------------------------------------------------------------------
def generate_covers_and_schedule(selected_eps: list[dict[str, Any]], generate_covers: bool, do_schedule: bool) -> None:
    import requests

    api_url = os.getenv("LIKYA_API_URL", "https://likya-crosspost-api-64i7umkgnq-ew.a.run.app").rstrip("/")
    api_key = os.environ["LIKYA_API_KEY"].strip()
    site_base = os.getenv("SITE_BASE_URL", "https://studio.likyastudios.live").rstrip("/")
    hdr = {"X-API-Key": api_key}

    # Check live YouTube daily quota & current schedule
    r_sch = requests.get(f"{api_url}/api/schedule", headers=hdr, params={"brand": "akilalmaz"}, timeout=30)
    r_sch.raise_for_status()
    sch_info = r_sch.json()
    yt_q = sch_info.get("yt_quota_today") or {"used": 0, "limit": 25}
    print(f"=== PANEL DURUMU: YouTube günlük kota {yt_q['used']}/{yt_q['limit']} | Sıradaki slot: {(sch_info.get('next_slot') or {}).get('label_tr')} ===", flush=True)

    if generate_covers:
        for ep in selected_eps:
            slug = ep["slug"]
            print(f"[Kapak] Vertex AI 9:16 üretiliyor ({slug})...", flush=True)
            rc = requests.post(
                f"{api_url}/api/covers/generate",
                headers={**hdr, "Content-Type": "application/json"},
                json={"key": slug, "prompt": ep["meta"]["flow_prompt"], "aspect_ratio": "9:16"},
                timeout=150,
            )
            rc.raise_for_status()
            img_url = rc.json()["image_url"]
            ir = requests.get(img_url, timeout=60)
            ir.raise_for_status()
            out_dir = REPO_DIR / "files" / slug / "out"
            out_dir.mkdir(parents=True, exist_ok=True)
            tmp_png = out_dir / "_cover_raw.png"
            tmp_png.write_bytes(ir.content)
            Image.open(tmp_png).convert("RGB").save(out_dir / "cover.jpg", "JPEG", quality=92, optimize=True)
            tmp_png.unlink(missing_ok=True)
            print(f"  -> ✅ Kapak hazır: {img_url.split('?')[0]}", flush=True)

    if do_schedule:
        # Ensure GitHub Pages serves all MP4s before scheduling
        for ep in selected_eps:
            vurl = f"{site_base}/files/{ep['slug']}/out/{ep['file_name']}"
            for attempt in range(30):
                try:
                    if requests.head(vurl, timeout=20, allow_redirects=True).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(10)
            else:
                raise SystemExit(f"Video canlıda erişilemedi: {vurl}")

        yt_quota_hit = False
        for ep in selected_eps:
            slug = ep["slug"]
            vurl = f"{site_base}/files/{slug}/out/{ep['file_name']}"
            curl = f"{api_url}/api/covers/{slug}.png"
            payload = {
                "brand": "akilalmaz",
                "video_id": slug,
                "video_url": vurl,
                "title": ep["meta"]["youtube"]["title"],
                "description": ep["meta"]["youtube"]["description"],
                "ig_caption": ep["meta"]["instagram"]["caption"],
                "cover_url": curl,
                "auto_next_slot": True,
                "sync_youtube_now": not yt_quota_hit,
            }
            sr = requests.post(
                f"{api_url}/api/schedule",
                headers={**hdr, "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            if sr.status_code == 409:
                print(f"  -> {slug}: Zaten planlı (409), atlandı.", flush=True)
                continue
            sr.raise_for_status()
            res = sr.json()
            post = res.get("post") or {}
            yt_up = bool(res.get("yt_uploaded"))
            yt_sync = res.get("yt_sync") or {}
            yt_err = str(yt_sync.get("error") or "")
            if not yt_up and ("quota" in yt_err.lower() or "exceeded" in yt_err.lower() or "limit" in yt_err.lower()):
                yt_quota_hit = True
            print(
                f"  -> ✅ #{post.get('id')} {slug} | Slot: {post.get('label_tr')} | YT yüklendi: {yt_up}"
                + (f" | YT notu: {yt_err[:120]}" if yt_err else ""),
                flush=True,
            )


def main() -> None:
    p = argparse.ArgumentParser(description="AKILALMAZ v22-v26 Batch 3D-Toon Shorts Factory")
    p.add_argument("--episodes", default="22,23,24,25,26", help="Üretilecek bölüm numaraları (virgülle)")
    p.add_argument("--music-db", type=float, default=-12.0, help="Fon müziği seviyesi (dB)")
    p.add_argument("--produce", action="store_true", help="Videoları üret ve videos.json güncelle")
    p.add_argument("--generate-covers", action="store_true", help="Cloud Run /api/covers/generate ile 9:16 kapak üret")
    p.add_argument("--schedule", action="store_true", help="Sıradaki 06:01-06:07 TR slotlarına planla ve YouTube'a yükle")
    args = p.parse_args()

    wanted = {int(x.strip()) for x in args.episodes.split(",") if x.strip()}
    selected = [ep for ep in EPISODES if ep["num"] in wanted]
    if not selected:
        sys.exit("Seçilen bölüm bulunamadı.")

    if args.produce:
        with tempfile.TemporaryDirectory(prefix="akil_plates_") as tmp:
            print(f"[Aşama 1] {len(selected)} video için Three.js 3D-toon arka plan plakaları tek seferde hazırlanıyor...", flush=True)
            plates_map = bake_all_plates(selected, Path(tmp))

            videos = json.loads(VIDEOS_JSON.read_text(encoding="utf-8")) if VIDEOS_JSON.exists() else []
            for ep in selected:
                entry = produce_episode(ep, plates_map[ep["slug"]], music_db=args.music_db)
                videos = [v for v in videos if v.get("slug") != ep["slug"]]
                videos.append(entry)
                VIDEOS_JSON.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n✅ Toplam {len(selected)} yeni video üretildi ve videos.json güncellendi ({len(videos)} toplam video).", flush=True)

    if args.generate_covers or args.schedule:
        generate_covers_and_schedule(selected, generate_covers=args.generate_covers, do_schedule=args.schedule)


if __name__ == "__main__":
    main()
