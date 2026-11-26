#!/usr/bin/env python3
"""AKILALMAZ Cinematic v1-Style Multi-Location 12-Shot 3D-Toon + 2D Çöp Adam Director (v22–v26).

Matches the exact viral visual dynamism of v1 (Limon Suyu) and v3 (Büyük Emu Savaşı):
- 4–5 distinct 3D-toon camera angles & locations per video (wide hero, high-angle overhead,
  interior office/desk with hanging lamp, dramatic action zone, finale green chalkboard)
- 12 rapid cinematic cuts (new shot/angle/insert every 3–4 seconds — zero static screen!)
- Characters actually walk, run, jump, facepalm, cry, point with chalk sticks, and zoom into
  tight solo reaction close-ups (scale 1.6x)
- Full-screen animated prop inserts (cracking tank & thermometer, Alpine map, live ticking
  20-min stopwatch, Royal Navy stamp document, 1962 NASA CRT code monitor showing missing '-',
  and classic v1-style '● SON DAKİKA!' retro TV news screen with scanlines!)
- Live foreground motion props (rising glossy molasses tsunami wave, flying cannonballs,
  wildly looping rocket + comic 'GÜM!' burst, glowing lightbulb, red alert siren)
- Reuses verified ERKAN eleven_v4 voice + lively -12.0 dB BGM & synced cartoon SFX!
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

REPO_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import batch_produce_akilalmaz as base  # noqa: E402
import synth_bgm_sfx  # noqa: E402

CINEMATIC_BAKER_HTML = SCRIPTS_DIR / "cinematic_baker.html"
W, H = 1080, 1920
FPS = 30
INK = (24, 23, 34)


# ---------------------------------------------------------------------------
# Cinematic Multi-Location Config per Episode (v22–v26)
# ---------------------------------------------------------------------------
CINEMATIC_EXTRAS: dict[int, dict[str, Any]] = {
    22: {
        "baker_extra": {
            "gridFloor": True,
            "intWallA": "#b58b58", "intWallB": "#8c6538", "intWindowHex": 0xd99b66,
            "actSkyHex": 0x452818, "actLightHex": 0xffcfa8,
            "actFloorA": "#54270d", "actFloorB": "#381806", "actPropHex": 0x6b3a24,
            "chalkboard": {
                "title": "1919 BOSTON PEKMEZ SELİ",
                "bigStat": "56 KM/SAAT · 7,5 METRE!",
                "subLines": [
                    "8,7 MİLYON LİTRE YAPIŞKAN DALGA",
                    "TAMİR YERİNE KAHVERENGİYE BOYADILAR!",
                    "SICAK GÜNLERDE HÂLÂ PEKMEZ KOKAR",
                ],
            },
        },
        "tv_headline": "SON DAKİKA: DEV PEKMEZ SELİ!",
        "tv_sub": "BOSTON SOKAKLARI 56 KM/SAAT PEKMEZ ALTINDA!",
        "insert_mode": "molasses_crack",
        "action_mode": "molasses_wave",
        "climax_mode": "molasses_stuck",
        "loop_label": "BOSTON · 1919",
    },
    23: {
        "baker_extra": {
            "gridFloor": False,
            "intWallA": "#4c6652", "intWallB": "#334738", "intWindowHex": 0x8fd1ff,
            "actSkyHex": 0x5fb8f0, "actLightHex": 0xfff5d6,
            "actFloorA": "#66a34c", "actFloorB": "#4a7d35", "actPropHex": 0x3b6e52,
            "chalkboard": {
                "title": "1866 LİHTENŞTAYN SEFERİ",
                "bigStat": "GİDEN: 80  ->  DÖNEN: 81!",
                "subLines": [
                    "GÖRÜLEN DÜŞMAN SAYISI: 0",
                    "KAZANILAN YENİ KANKA: +1 SUBAY",
                    "TARİHTE '-1 KAYIPLA' BİTEN TEK SAVAŞ!",
                ],
            },
        },
        "tv_headline": "SON DAKİKA: 80 GİTTİ 81 DÖNDÜ!",
        "tv_sub": "LİHTENŞTAYN ORDUSU YOLDA YENİ ASKER KAZANDI!",
        "insert_mode": "alpine_map",
        "action_mode": "alpine_picnic",
        "climax_mode": "alpine_march81",
        "loop_label": "LİHTENŞTAYN · 1866",
    },
    24: {
        "baker_extra": {
            "gridFloor": True,
            "intWallA": "#7a262e", "intWallB": "#52171d", "intWindowHex": 0xffc88a,
            "actSkyHex": 0x42241c, "actLightHex": 0xffd6a8,
            "actFloorA": "#b5853f", "actFloorB": "#8c6226", "actPropHex": 0x6e2b2b,
            "chalkboard": {
                "title": "GUİNNESS TARİH REKORU",
                "bigStat": "EN KISA SALTANAT: 20 DK!",
                "subLines": [
                    "FRANSA KRALI XIX. LOUIS (1830)",
                    "KAHVESİ SOĞUMADAN TAHTTAN İNDİ!",
                    "BİR DİZİ BÖLÜMÜNDEN BİLE KISA!",
                ],
            },
        },
        "tv_headline": "SON DAKİKA: 20 DAKİKALIK KRAL!",
        "tv_sub": "XIX. LOUIS AĞLAYARAK TAHTTAN ÇEKİLDİ!",
        "insert_mode": "stopwatch_20",
        "action_mode": "king_crying",
        "climax_mode": "abdication_doc",
        "loop_label": "FRANSA · 1830",
    },
    25: {
        "baker_extra": {
            "gridFloor": False,
            "intWallA": "#264666", "intWallB": "#182e45", "intWindowHex": 0x76d4f5,
            "actSkyHex": 0x3b9ed6, "actLightHex": 0xfff0cc,
            "actFloorA": "#167ba8", "actFloorB": "#0e5a7d", "actPropHex": 0x525259,
            "chalkboard": {
                "title": "HMS DIAMOND ROCK · 1804",
                "bigStat": "16 GEMİ  vs  1 TAŞ KAYA!",
                "subLines": [
                    "120 DENİZCİ · 17 AY KESİNTİSİZ DİRENİŞ",
                    "RESMEN SAVAŞ GEMİSİ İLAN EDİLDİ",
                    "BATMA SAYISI: 0 (ASLA BATMADI!)",
                ],
            },
        },
        "tv_headline": "SON DAKİKA: TAŞ GEMİ BATMIYOR!",
        "tv_sub": "NAPOLYON 1 KAYA İÇİN 16 SAVAŞ GEMİSİ YOLLADI!",
        "insert_mode": "navy_cert",
        "action_mode": "cannon_battle",
        "climax_mode": "rock_bounce",
        "loop_label": "KARAYİPLER · 1804",
    },
    26: {
        "baker_extra": {
            "gridFloor": True,
            "intWallA": "#2d3b4e", "intWallB": "#1c2633", "intWindowHex": 0x58e69a,
            "actSkyHex": 0x2c6eb8, "actLightHex": 0xffe4b8,
            "actFloorA": "#727b87", "actFloorB": "#4e5560", "actPropHex": 0x9e2b27,
            "chalkboard": {
                "title": "MARINER 1 · NASA (1962)",
                "bigStat": "1 KISA ÇİZGİ = 150.000.000 $!",
                "subLines": [
                    "FORMÜLDEKİ TEK ÜST ÇİZGİ UNUTULDU",
                    "293. SANİYEDE HAVADA İMHA EDİLDİ",
                    "TARİHİN EN PAHALI YAZIM HATASI!",
                ],
            },
        },
        "tv_headline": "SON DAKİKA: 150M $ YAZIM HATASI!",
        "tv_sub": "TEK BİR KISA ÇİZGİ NASA ROKETİNİ PATLATTI!",
        "insert_mode": "nasa_crt",
        "action_mode": "rocket_spin",
        "climax_mode": "nasa_boom",
        "loop_label": "NASA · 1962",
    },
}


# ---------------------------------------------------------------------------
# Extra Expressive Cartoon Drawing Primitives (v1 / v3 Viral Polish!)
# ---------------------------------------------------------------------------
def draw_floating_icon(draw: ImageDraw.ImageDraw, sym: str, cx: int, cy: int, r: int, bg: tuple[int, int, int], fg: tuple[int, int, int], sc: float) -> None:
    if sc <= 0.05:
        return
    rr = int(r * min(1.12, sc))
    draw.ellipse([cx - rr - 7, cy - rr - 7, cx + rr + 7, cy + rr + 7], fill=INK)
    draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=bg)
    f = base.get_font(max(24, int(rr * 1.25)), bold=True)
    draw.text((cx, cy + 2), sym, font=f, fill=fg, anchor="mm")


def draw_lightbulb(draw: ImageDraw.ImageDraw, cx: int, cy: int, t: float, sc: float) -> None:
    if sc <= 0.05:
        return
    r = int(56 * min(1.1, sc))
    # Rays pulsing!
    for i in range(8):
        a = i * math.pi / 4 + t * 1.2
        r1, r2 = r + 14, r + 34 + int(8 * math.sin(t * 10 + i))
        draw.line([(cx + math.cos(a) * r1, cy + math.sin(a) * r1), (cx + math.cos(a) * r2, cy + math.sin(a) * r2)], fill=(255, 224, 68), width=10)
    draw.ellipse([cx - r - 7, cy - r - 7, cx + r + 7, cy + r + 7], fill=INK)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 232, 76))
    draw.rounded_rectangle([cx - r // 2, cy + r - 8, cx + r // 2, cy + r + 28], radius=8, fill=(175, 185, 198), outline=INK, width=6)


def draw_tv_news_insert(img: Image.Image, headline: str, sub: str, role: str, t: float, t_local: float) -> None:
    """Classic v1 '● CCTV 01 — SON DAKİKA!' full-screen retro TV monitor insert!"""
    draw = ImageDraw.Draw(img)
    # Dark studio background behind TV
    draw.rectangle([0, 0, W, H], fill=(20, 26, 38))
    # TV Bezel
    draw.rounded_rectangle([46, 260, W - 46, 1320], radius=46, fill=(42, 48, 62), outline=INK, width=14)
    # Bright screen
    draw.rounded_rectangle([78, 294, W - 78, 1286], radius=28, fill=(224, 236, 248), outline=INK, width=8)

    # Top-left blinking red LIVE / REC dot
    if int(t * 4) % 2 == 0:
        draw.ellipse([112, 330, 146, 364], fill=(235, 36, 36))
    draw.text((164, 347), "CANLI HABER · 01", font=base.get_font(34, True), fill=(30, 36, 48), anchor="lm")

    # Giant cartoon portrait inside TV!
    base.draw_stick_char(draw, role, W // 2, 1180, 1.38, t, emotion="shock", pose="panic", speaking=False, facing=1, phase=0.5)

    # Subtle retro scanlines across TV screen
    for y in range(304, 1276, 16):
        draw.line([(84, y), (W - 84, y)], fill=(180, 195, 212), width=2)

    # Bold RED Breaking News Banner across bottom of TV!
    draw.rectangle([78, 1085, W - 78, 1286], fill=(208, 26, 34), outline=INK, width=8)
    f_h = base.get_font(46, True)
    while draw.textbbox((0, 0), headline, font=f_h)[2] > 880:
        f_h = base.get_font(f_h.size - 3, True)
    draw.text((W // 2, 1148), headline, font=f_h, fill=(255, 232, 76), anchor="mm")
    f_s = base.get_font(30, True)
    while draw.textbbox((0, 0), sub, font=f_s)[2] > 880:
        f_s = base.get_font(f_s.size - 2, True)
    draw.text((W // 2, 1226), sub, font=f_s, fill=(255, 255, 255), anchor="mm")


def draw_prop_insert(img: Image.Image, mode: str, t: float, lfrac: float) -> None:
    """Full-screen animated story prop insert (zero static wall posters — pure v1 visual storytelling!)."""
    draw = ImageDraw.Draw(img)
    sc = base.ease_out_back(min(1.0, lfrac * 3.8))

    if mode == "molasses_crack":
        # Close-up dark riveted steel tank wall cracking open + thermometer shooting red hot!
        draw.rectangle([0, 0, W, H], fill=(58, 66, 78))
        for y in range(200, 1700, 260):
            draw.line([(0, y), (W, y)], fill=(36, 40, 48), width=10)
            for x in range(80, W, 130):
                draw.ellipse([x - 16, y - 40, x + 16, y - 8], fill=(82, 92, 106), outline=INK, width=5)
        # Expanding jagged crack leaking glossy brown molasses!
        crack_w = int(12 + 48 * lfrac)
        pts = [(490, 320), (545, 520), (470, 740), (570, 960), (485, 1190), (535, 1360)]
        draw.line(pts, fill=(76, 34, 10), width=crack_w + 18)
        draw.line(pts, fill=INK, width=crack_w)
        # Dripping molasses blobs
        for i in range(6):
            dy = int((t * 320 + i * 170) % 720)
            draw.ellipse([480 + (i % 3) * 32, 560 + dy, 524 + (i % 3) * 32, 622 + dy], fill=(104, 48, 14), outline=INK, width=6)
        # Giant Thermometer on right shooting RED!
        draw.rounded_rectangle([830, 360, 940, 1120], radius=55, fill=(242, 244, 248), outline=INK, width=12)
        draw.ellipse([800, 1020, 970, 1190], fill=(228, 36, 36), outline=INK, width=12)
        fill_top = int(base.lerp(960, 420, lfrac))
        draw.rounded_rectangle([858, fill_top, 912, 1090], radius=24, fill=(228, 36, 36))
        base.draw_badge(draw, "BASINÇ PATLIYOR!", 420, 250, (224, 38, 38), (255, 255, 255), sc)

    elif mode == "alpine_map":
        # Full-screen 1866 Vintage Alpine Tactical Map (80 ASKER -> 0 DÜŞMAN!)
        draw.rectangle([0, 0, W, H], fill=(116, 78, 42))
        draw.rounded_rectangle([70, 250, W - 70, 1310], radius=24, fill=(242, 228, 192), outline=INK, width=12)
        # Mountain triangles on map
        for mx, my in [(280, 620), (460, 540), (650, 610), (790, 560), (520, 780)]:
            draw.polygon([(mx, my - 95), (mx - 85, my + 55), (mx + 85, my + 55)], fill=(154, 186, 134), outline=INK)
            draw.polygon([(mx, my - 95), (mx - 32, my - 35), (mx + 32, my - 35)], fill=(255, 255, 255))
        # Animated dashed marching arrow from Liechtenstein -> Alps
        steps = int(base.lerp(1, 10, lfrac))
        for i in range(steps):
            px = int(200 + i * 64)
            py = int(1020 - i * 32)
            draw.ellipse([px - 14, py - 14, px + 14, py + 14], fill=(28, 86, 176), outline=INK, width=4)
        draw.text((W // 2, 340), "ALPLER ASKERÎ HARİTA · 1866", font=base.get_font(44, True), fill=(44, 32, 22), anchor="mm")
        if lfrac > 0.35:
            base.draw_badge(draw, "80 ASKER · 0 DÜŞMAN!", 540, 1140, (28, 136, 72), (255, 255, 255), base.ease_out_back((lfrac - 0.35) * 3))

    elif mode == "stopwatch_20":
        # Extreme Close-Up Giant Live-Ticking Golden Stopwatch (00:00 -> 00:20!)
        draw.rectangle([0, 0, W, H], fill=(82, 22, 28))
        cx, cy, r = W // 2, 790, 390
        draw.rounded_rectangle([cx - 65, cy - r - 95, cx + 65, cy - r + 10], radius=24, fill=(242, 192, 46), outline=INK, width=12)
        draw.ellipse([cx - r - 32, cy - r - 32, cx + r + 32, cy + r + 32], fill=(242, 192, 46), outline=INK, width=14)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 250, 232), outline=INK, width=10)
        # Live sweeping red 20-minute wedge!
        mins = int(base.lerp(0, 20, lfrac))
        ang_deg = -90 + int(120 * lfrac)
        draw.pieslice([cx - r + 28, cy - r + 28, cx + r - 28, cy + r - 28], -90, ang_deg, fill=(235, 92, 92))
        for i in range(12):
            a = i * math.pi / 6
            draw.line([(cx + math.cos(a) * (r - 58), cy + math.sin(a) * (r - 58)), (cx + math.cos(a) * (r - 18), cy + math.sin(a) * (r - 18))], fill=INK, width=12 if i % 3 == 0 else 6)
        rad = math.radians(ang_deg)
        draw.line([(cx, cy), (cx + math.cos(rad) * (r - 75), cy + math.sin(rad) * (r - 75))], fill=(214, 28, 32), width=18)
        draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=INK)
        base.draw_badge(draw, f"SALTANAT SÜRESİ: 00:{mins:02d}", W // 2, 230, (255, 214, 52), INK, sc)

    elif mode == "navy_cert":
        # Official Royal Navy Ship Registry Document + Slamming Red Stamp "SAVAŞ GEMİSİ!"
        draw.rectangle([0, 0, W, H], fill=(28, 52, 86))
        draw.rounded_rectangle([85, 240, W - 85, 1320], radius=24, fill=(250, 242, 216), outline=INK, width=14)
        draw.rounded_rectangle([118, 274, W - 118, 1286], radius=16, outline=(196, 152, 46), width=8)
        draw.text((W // 2, 375), "KRALİYET DONANMASI", font=base.get_font(48, True), fill=(24, 48, 92), anchor="mm")
        draw.text((W // 2, 445), "RESMÎ SAVAŞ GEMİSİ SİCİLİ · 1804", font=base.get_font(30, True), fill=(112, 82, 38), anchor="mm")
        draw.line([(160, 495), (W - 160, 495)], fill=(196, 152, 46), width=6)
        draw.text((W // 2, 600), "GEMİ ADI: HMS DIAMOND ROCK", font=base.get_font(38, True), fill=INK, anchor="mm")
        draw.text((W // 2, 690), "TÜRÜ: 175 METRELİK TAŞ KAYA!", font=base.get_font(38, True), fill=(186, 36, 36), anchor="mm")
        draw.text((W // 2, 780), "MÜRETTEBAT: 120 DENİZCİ + 5 TOP", font=base.get_font(36, True), fill=INK, anchor="mm")
        if lfrac > 0.35:
            st_sc = base.ease_out_back((lfrac - 0.35) * 3.5)
            base.draw_badge(draw, "RESMEN GEMİ ONAYLANDI!", W // 2, 1040, (206, 34, 38), (255, 255, 255), st_sc)

    elif mode == "nasa_crt":
        # Retro 1962 Green-Phosphor NASA CRT Computer Screen showing the $150M Missing Hyphen!
        draw.rectangle([0, 0, W, H], fill=(28, 34, 44))
        draw.rounded_rectangle([60, 240, W - 60, 1320], radius=48, fill=(58, 66, 78), outline=INK, width=14)
        draw.rounded_rectangle([100, 285, W - 100, 1275], radius=30, fill=(12, 34, 22), outline=INK, width=10)
        for y in range(295, 1265, 14):
            draw.line([(106, y), (W - 106, y)], fill=(18, 48, 30), width=2)
        draw.text((W // 2, 385), "NASA MARINER-1 UÇUŞ KODU", font=base.get_font(42, True), fill=(92, 255, 148), anchor="mm")
        draw.text((W // 2, 540), "DOĞRU FORMÜL:   R̄  (ÜST ÇİZGİLİ)", font=base.get_font(38, True), fill=(162, 255, 188), anchor="mm")
        # Giant blinking error comparison
        blink_on = int(t * 6) % 2 == 0
        err_c = (255, 76, 76) if blink_on else (255, 214, 68)
        draw.rounded_rectangle([165, 650, W - 165, 980], radius=24, fill=(36, 16, 18), outline=err_c, width=10)
        draw.text((W // 2, 755), "YAZILAN KOD:  R", font=base.get_font(66, True), fill=(255, 255, 255), anchor="mm")
        draw.text((W // 2, 885), "EKSİK:  [ - ]  TEK KISA ÇİZGİ!", font=base.get_font(44, True), fill=err_c, anchor="mm")
        if lfrac > 0.35:
            base.draw_badge(draw, "SİSTEM HATASI: -150M $!", W // 2, 1140, (224, 34, 38), (255, 255, 255), base.ease_out_back((lfrac - 0.35) * 3.5))


def draw_live_action_overlay(img: Image.Image, mode: str, t: float, lfrac: float, r0: str, r1: str, r2: str, speaking: bool) -> None:
    """High-energy dynamic moving action shots where props & characters MOVE across the frame!"""
    draw = ImageDraw.Draw(img)

    if mode == "molasses_wave":
        # Giant glossy brown molasses wave SURGING from left to right while citizens RUN!
        run_x0 = base.lerp(220, 760, lfrac)
        run_x1 = base.lerp(520, 1020, lfrac)
        base.draw_stick_char(draw, r0, run_x0, 1760, 1.02, t, "panic", "panic", speaking, 1, 0.2)
        base.draw_stick_char(draw, r1, run_x1, 1780, 1.06, t, "shock", "panic", False, 1, 1.4)
        # Rising curling brown tsunami wave chasing from left!
        wave_edge = int(base.lerp(180, 680, lfrac))
        pts = [(0, H), (0, 680)]
        for i in range(12):
            wy = 680 + i * 110
            wx = wave_edge + int(math.sin(t * 10 + i * 0.8) * 55) - int((i - 4) ** 2 * 6)
            pts.append((wx, wy))
        pts.append((wave_edge + 140, H))
        draw.polygon(pts, fill=(92, 42, 12), outline=INK)
        draw.line(pts[1:-1], fill=(148, 78, 28), width=14)
        # Flying glossy droplets
        for k in range(7):
            dx = wave_edge + 40 + ((int(t * 260) + k * 95) % 280)
            dy = 760 + k * 110 + int(math.sin(t * 8 + k) * 35)
            draw.ellipse([dx - 18, dy - 18, dx + 18, dy + 18], fill=(112, 52, 16), outline=INK, width=5)
        base.draw_badge(draw, "56 KM/SAAT PEKMEZ SELİ!", W // 2, 210, (214, 38, 38), (255, 255, 255), 1.0)

    elif mode == "molasses_stuck":
        # Stuck waist-deep in brown molasses + bent rails!
        draw.rectangle([0, 1340, W, H], fill=(88, 40, 12))
        draw.line([(0, 1340), (W, 1340)], fill=INK, width=12)
        # Bent curved iron rail sticking out!
        draw.arc([120, 880, 960, 1520], 195, 345, fill=(138, 146, 158), width=26)
        base.draw_stick_char(draw, r1, 340, 1790, 1.15, t, "shock", "panic", speaking, 1, 0.3)
        base.draw_stick_char(draw, r2, 740, 1790, 1.15, t, "happy", "wave", False, -1, 1.1)
        # Redraw sticky wave over legs so they look stuck knee-deep!
        draw.rectangle([0, 1590, W, H], fill=(88, 40, 12))
        draw.line([(0, 1590), (W, 1590)], fill=(138, 70, 22), width=12)
        base.draw_badge(draw, "HAFTALARCA TEMİZLENEMEDİ!", W // 2, 210, (255, 214, 52), INK, 1.0)

    elif mode == "alpine_picnic":
        # Sunny golden sunbeams + two soldiers relaxing happily while Austrian buddy WALKS IN!
        for i in range(6):
            a = 0.2 + i * 0.25 + math.sin(t * 2) * 0.05
            draw.line([(920, 160), (920 - int(math.cos(a) * 850), 160 + int(math.sin(a) * 850))], fill=(255, 238, 132), width=18)
        draw.ellipse([810, 60, 1020, 270], fill=(255, 222, 64), outline=INK, width=10)
        buddy_x = base.lerp(1140, 770, base.ease_in_out(lfrac))
        base.draw_stick_char(draw, r0, 290, 1780, 1.12, t, "happy", "cheer", speaking, 1, 0.2)
        base.draw_stick_char(draw, r2, buddy_x, 1780, 1.12, t, "happy", "prop_hold", False, -1, 1.1)
        base.draw_badge(draw, "SIFIR DÜŞMAN · YENİ KANKA!", W // 2, 220, (28, 136, 72), (255, 255, 255), 1.0)

    elif mode == "alpine_march81":
        # Animated Roll Call counter ticking 78 -> 79 -> 80 -> 81?! while 3 soldiers march right!
        mx = int(base.lerp(-90, 130, lfrac))
        base.draw_stick_char(draw, r0, 240 + mx, 1790, 1.02, t, "happy", "cheer", speaking, 1, 0.1)
        base.draw_stick_char(draw, r1, 520 + mx, 1790, 1.02, t, "happy", "wave", False, 1, 0.9)
        base.draw_stick_char(draw, r2, 800 + mx, 1790, 1.06, t, "happy", "prop_hold", False, 1, 1.7)
        count_val = 78 + min(3, int(lfrac * 4.2))
        col_bg = (224, 38, 38) if count_val == 81 else (28, 86, 176)
        base.draw_badge(draw, f"SAYIM: {count_val} ASKER!", W // 2, 320, col_bg, (255, 232, 76), 1.15)

    elif mode == "king_crying":
        # King Louis XIX crying giant blue cartoon tear streams while guard taps watch!
        base.draw_stick_char(draw, r0, 350, 1790, 1.24, t, "panic", "panic", speaking, 1, 0.2)
        # Animated streaming blue tears!
        for ox in (-42, 42):
            ty = 1230 + int((t * 280) % 160)
            draw.ellipse([350 + ox - 14, ty, 350 + ox + 14, ty + 34], fill=(64, 198, 255), outline=INK, width=4)
            draw.ellipse([350 + ox - 12, ty + 85, 350 + ox + 12, ty + 112], fill=(64, 198, 255), outline=INK, width=4)
        base.draw_stick_char(draw, r1, 790, 1790, 1.12, t, "nervous", "point_up", False, -1, 1.3)
        base.draw_badge(draw, "'BIRAKIN BİRAZ DAHA KALAYIM!'", W // 2, 220, (214, 34, 42), (255, 255, 255), 0.96)

    elif mode == "abdication_doc":
        # Signing the Abdication Parchment live with red stamp "00:20 BİTTİ!"
        draw.rounded_rectangle([110, 320, W - 110, 1180], radius=24, fill=(252, 244, 218), outline=INK, width=12)
        draw.text((W // 2, 430), "TAHTTAN ÇEKİLME BELGESİ", font=base.get_font(44, True), fill=INK, anchor="mm")
        draw.line([(180, 490), (W - 180, 490)], fill=(180, 140, 58), width=6)
        draw.text((W // 2, 620), "KRAL XIX. LOUIS", font=base.get_font(54, True), fill=(168, 26, 36), anchor="mm")
        # Animated squiggly signature drawing progressively!
        sig_n = max(2, int(lfrac * 24))
        sig_pts = [(260 + i * 24, 790 + int(math.sin(i * 1.4) * 26)) for i in range(sig_n)]
        draw.line(sig_pts, fill=(26, 48, 124), width=10)
        if lfrac > 0.45:
            base.draw_badge(draw, "İMZALANDI · 00:20 BİTTİ!", W // 2, 1010, (214, 34, 38), (255, 232, 76), base.ease_out_back((lfrac - 0.45) * 3))
        base.draw_stick_char(draw, r0, 540, 1840, 0.92, t, "shock", "idle", speaking, 1, 0.4)

    elif mode == "cannon_battle":
        # Flying cannonballs + smoke clouds crossing the Caribbean sea!
        base.draw_stick_char(draw, r0, 270, 1790, 1.12, t, "happy", "cheer", speaking, 1, 0.2)
        base.draw_stick_char(draw, r1, 810, 1790, 1.12, t, "panic", "panic", False, -1, 1.4)
        for k in range(3):
            prog = (lfrac * 2.2 + k * 0.34) % 1.0
            bx = int(base.lerp(240, 880, prog))
            by = int(680 - math.sin(prog * math.pi) * 260 + k * 70)
            draw.ellipse([bx - 26, by - 26, bx + 26, by + 26], fill=(32, 36, 44), outline=INK, width=6)
            draw.ellipse([bx - 64, by - 14, bx - 30, by + 18], fill=(238, 242, 248), outline=INK, width=4)
        base.draw_badge(draw, "17 AY GEÇİT VERMEDİ!", W // 2, 210, (214, 38, 38), (255, 255, 255), 1.0)

    elif mode == "rock_bounce":
        # Giant stone rock in center — French cannonball BOUNCES right off ("TINK!")!
        draw.polygon([(360, 1280), (420, 580), (560, 440), (700, 620), (740, 1280)], fill=(116, 118, 124), outline=INK)
        prog = (lfrac * 1.8) % 1.0
        if prog < 0.5:
            bx = int(base.lerp(1020, 680, prog * 2))
            by = int(base.lerp(720, 660, prog * 2))
        else:
            bx = int(base.lerp(680, 1020, (prog - 0.5) * 2))
            by = int(base.lerp(660, 960, (prog - 0.5) * 2))
        draw.ellipse([bx - 28, by - 28, bx + 28, by + 28], fill=(30, 32, 38), outline=INK, width=6)
        if 0.42 < prog < 0.68:
            base.draw_badge(draw, "TİNK! ASLA BATMIYOR!", 540, 320, (255, 214, 52), INK, 1.1)
        base.draw_stick_char(draw, r0, 240, 1810, 1.06, t, "happy", "cheer", speaking, 1, 0.2)
        base.draw_stick_char(draw, r1, 840, 1810, 1.06, t, "shock", "panic", False, -1, 1.2)

    elif mode == "rocket_spin":
        # White NASA Atlas rocket tumbling & looping wildly across sky with curly orange smoke!
        cx = int(540 + math.cos(t * 4.5) * 240)
        cy = int(680 + math.sin(t * 6.0) * 190)
        # Curly smoke trail
        for i in range(18):
            tt = t - i * 0.045
            sx = int(540 + math.cos(tt * 4.5) * 240)
            sy = int(680 + math.sin(tt * 6.0) * 190)
            sr = max(14, 54 - i * 2)
            draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 194, 118) if i % 2 == 0 else (240, 242, 246))
        # Rocket body
        draw.rounded_rectangle([cx - 34, cy - 95, cx + 34, cy + 95], radius=16, fill=(248, 250, 254), outline=INK, width=8)
        draw.polygon([(cx - 34, cy - 85), (cx, cy - 155), (cx + 34, cy - 85)], fill=(214, 38, 38), outline=INK)
        draw.polygon([(cx - 28, cy + 95), (cx, cy + 165), (cx + 28, cy + 95)], fill=(255, 140, 24))
        base.draw_stick_char(draw, r0, 280, 1820, 1.02, t, "shock", "panic", speaking, 1, 0.2)
        base.draw_stick_char(draw, r1, 800, 1820, 1.02, t, "panic", "prop_hold", False, -1, 1.4)
        base.draw_badge(draw, "ROKET ROTADAN ÇIKTI!", W // 2, 200, (224, 34, 38), (255, 255, 255), 1.0)

    elif mode == "nasa_boom":
        # Flashing red siren + slamming big RED BUTTON + giant comic "GÜM!" explosion!
        if lfrac < 0.5:
            # Red emergency siren flash
            if int(t * 8) % 2 == 0:
                draw.rectangle([0, 0, W, 190], fill=(224, 34, 38))
            base.draw_stick_char(draw, r0, 540, 1790, 1.25, t, "panic", "panic", speaking, 1, 0.2)
            # Giant Red Self-Destruct Button in center!
            draw.rounded_rectangle([340, 960, 740, 1120], radius=24, fill=(76, 82, 92), outline=INK, width=10)
            draw.ellipse([410, 860, 670, 1020], fill=(235, 32, 32), outline=INK, width=10)
            draw.text((540, 940), "İMHA", font=base.get_font(48, True), fill=(255, 255, 255), anchor="mm")
            base.draw_badge(draw, "293. SANİYE · İMHA EMRİ!", W // 2, 230, (255, 214, 52), INK, 1.05)
        else:
            # Giant Comic Explosion Cloud "GÜM!" (exact v3 style!)
            bsc = base.ease_out_back((lfrac - 0.5) * 3.0)
            cx, cy = W // 2, 740
            pts = []
            for i in range(16):
                a = i * math.pi / 8 + t * 0.5
                rr = int((360 if i % 2 == 0 else 210) * min(1.15, bsc))
                pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
            draw.polygon(pts, fill=(255, 132, 26), outline=INK)
            pts2 = [(cx + math.cos(i * math.pi / 8) * int((240 if i % 2 == 0 else 140) * min(1.15, bsc)), cy + math.sin(i * math.pi / 8) * int((240 if i % 2 == 0 else 140) * min(1.15, bsc))) for i in range(16)]
            draw.polygon(pts2, fill=(255, 232, 72))
            draw.text((cx, cy), "GÜM!", font=base.get_font(120, True), fill=(214, 24, 28), anchor="mm", stroke_width=14, stroke_fill=INK)
            base.draw_stick_char(draw, r1, 540, 1840, 1.05, t, "shock", "panic", speaking, 1, 0.8)


# ---------------------------------------------------------------------------
# Bake All 5 Distinct 3D-Toon Locations per Episode in ONE Chrome Launch
# ---------------------------------------------------------------------------
def bake_cinematic_plates(selected_eps: list[dict[str, Any]], plates_root: Path) -> dict[str, dict[str, Image.Image]]:
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
        page.goto(CINEMATIC_BAKER_HTML.resolve().as_uri(), wait_until="load", timeout=60000)
        page.wait_for_function("window.BAKER_READY === true", timeout=30000)

        for ep in selected_eps:
            slug = ep["slug"]
            cfg = {**ep["baker"], **CINEMATIC_EXTRAS[ep["num"]]["baker_extra"]}
            print(f"  [3D Cinematic Baker] {slug} — 5 farklı 3D mekan/kamera açısı üretiliyor...", flush=True)
            res = page.evaluate("(cfg) => window.bakeCinematicLocations(cfg)", cfg)
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
# Render 12-Shot Dynamic v1-Style Episode (~105s per video!)
# ---------------------------------------------------------------------------
def render_cinematic_episode(ep: dict[str, Any], plates: dict[str, Image.Image], music_db: float = -12.0) -> dict[str, Any]:
    slug = ep["slug"]
    ex = CINEMATIC_EXTRAS[ep["num"]]
    out_dir = REPO_DIR / "files" / slug / "out"
    work_dir = REPO_DIR / "files" / slug / "work"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    voice_path = work_dir / "voice.mp3"
    words_cache = work_dir / "words.json"
    bgm_sfx_path = work_dir / "bgm_sfx.wav"
    mp4_path = out_dir / ep["file_name"]
    qa_path = out_dir / "qa_sheet.jpg"

    print(f"\n=== [SİNEMATİK {ep['num']}] {slug}: {ep['title']} ===", flush=True)
    if voice_path.exists() and words_cache.exists():
        print("  [1/4] Mevcut doğrulanmış ERKAN (eleven_v4) sesi + kelime zamanları kullanılıyor...", flush=True)
        raw_dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(voice_path)], text=True).strip())
        raw_words = json.loads(words_cache.read_text(encoding="utf-8"))
    else:
        print("  [1/4] ElevenLabs ERKAN (eleven_v4) ses + kelime zaman damgaları alınıyor...", flush=True)
        raw_dur, raw_words = base.synthesize_erkan_voice(ep["tts_script"], voice_path)
        words_cache.write_text(json.dumps(raw_words, ensure_ascii=False), encoding="utf-8")

    tempo = base.VOICE_TEMPO if (raw_dur / base.VOICE_TEMPO) <= 58.5 else (raw_dur / 57.5)
    duration = raw_dur / tempo
    words = [{"word": w["word"], "start": w["start"] / tempo, "end": w["end"] / tempo} for w in raw_words]
    total_dur = duration + 0.35
    total_frames = int(math.ceil(total_dur * FPS))
    chunks = base.group_word_chunks(words, chunk_size=2)
    print(f"    -> Süre: {duration:.2f}s ({total_frames} kare), 12 dinamik sahne (~{total_dur/12:.1f}s/sahne)", flush=True)

    # 12 Rapid v1-Style Cinematic Shots (new angle/location/insert every ~3.5-4.5 seconds!)
    cuts = [0.00, 0.08, 0.16, 0.24, 0.32, 0.41, 0.50, 0.61, 0.70, 0.78, 0.85, 0.93, 1.01]

    print(f"  [2/4] Canlı fon müziği + 12 sahneye senkron SFX sentezleniyor (--music-db {music_db:.1f})...", flush=True)
    sfx_events = [
        (0.25, "pop"),
        (cuts[1] * total_dur, "whoosh"),
        (cuts[2] * total_dur, "whoosh"),
        (cuts[3] * total_dur, "pop_hi"),
        (cuts[4] * total_dur, "whoosh"),
        (cuts[4] * total_dur + 0.35, "ding"),
        (cuts[5] * total_dur, "whoosh"),
        (cuts[6] * total_dur, ep["sfx_main"]),
        (cuts[7] * total_dur, "whoosh"),
        (cuts[7] * total_dur + 0.30, ep["sfx_main"]),
        (cuts[8] * total_dur, "whoosh"),
        (cuts[8] * total_dur + 0.25, "ding"),
        (cuts[9] * total_dur, "pop"),
        (cuts[10] * total_dur, "whoosh"),
        (cuts[10] * total_dur + 0.30, "sparkle"),
        (cuts[11] * total_dur, "whoosh"),
    ]
    synth_bgm_sfx.build_music_and_sfx_wav(bgm_sfx_path, total_dur + 0.25, sfx_events, bgm_gain_db=0.0)

    print("  [3/4] 12-sahnelli 1080x1920 30fps sinematik 3D-Toon + 2D Çöp Adam render ediliyor...", flush=True)
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
    qa_indices = {int(i * (total_frames - 1) / 17) for i in range(18)}
    qa_frames: list[Image.Image] = []

    for fidx in range(total_frames):
        t = fidx / FPS
        frac = base.clamp(t / max(0.01, total_dur), 0.0, 0.9999)
        s_idx = 11
        start_f = cuts[11]
        lfrac = 1.0
        for i in range(12):
            if cuts[i] <= frac < cuts[i + 1]:
                s_idx = i
                start_f = cuts[i]
                lfrac = (frac - cuts[i]) / (cuts[i + 1] - cuts[i])
                break
        t_local = (frac - start_f) * total_dur
        cap, cap_age, speaking = base.lookup_caption(chunks, t)

        if s_idx == 0:
            # SHOT 0: TIGHT SOLO CLOSE-UP HOOK (exact v1 00:00 style!)
            img = base.crop_camera(plates["wide"], base.lerp(1.16, 1.24, lfrac), base.lerp(-40, 20, lfrac), 40)
            draw = ImageDraw.Draw(img)
            enter_y = base.lerp(2120, 1980, base.ease_out_back(min(1.0, lfrac * 3.0)))
            base.draw_stick_char(draw, r0, 540, enter_y, 1.58, t, "happy", "wave", speaking, 1, 0.2)
            draw_floating_icon(draw, "!", 880, 420 + int(math.sin(t * 6) * 14), 68, (255, 214, 52), INK, base.ease_out_back(min(1.0, t_local * 3)))

        elif s_idx == 1:
            # SHOT 1: HIGH-ANGLE OVERHEAD 3D CAMERA — Character WALKING across the floor! (v1 00:02!)
            img = base.crop_camera(plates["overhead"], base.lerp(1.02, 1.12, lfrac), base.lerp(-60, 60, lfrac), 0)
            draw = ImageDraw.Draw(img)
            walk_x = base.lerp(180, 740, base.ease_in_out(lfrac))
            base.draw_stick_char(draw, r1, walk_x, 1690, 1.14, t, "shock", "panic", speaking, 1, 0.6)
            base.draw_badge(draw, ep["badges"][0], 540, 210, (217, 38, 38), (255, 255, 255), base.ease_out_back(min(1.0, t_local * 3)))

        elif s_idx == 2:
            # SHOT 2: WIDE 3D HERO ESTABLISHING SHOT — Two characters reacting dynamically!
            img = base.crop_camera(plates["wide"], base.lerp(1.00, 1.09, lfrac), base.lerp(35, -35, lfrac), -10)
            draw = ImageDraw.Draw(img)
            base.draw_stick_char(draw, r0, base.lerp(240, 310, lfrac), 1780, 1.06, t, "happy", "point_up", speaking, 1, 0.1)
            base.draw_stick_char(draw, r1, base.lerp(840, 770, lfrac), 1780, 1.06, t, "shock", "prop_hold", False, -1, 1.4)

        elif s_idx == 3:
            # SHOT 3: TIGHT REACTION CLOSE-UP + BOUNCING '?' (exact v1 00:06 bank teller!)
            img = base.crop_camera(plates["wide"], base.lerp(1.20, 1.14, lfrac), 70, 50)
            draw = ImageDraw.Draw(img)
            base.draw_stick_char(draw, r1, 540, 1990, 1.56, t, "shock", "panic", speaking, -1, 1.1)
            draw_floating_icon(draw, "?", 540, 320 + int(math.sin(t * 7) * 16), 74, (255, 214, 52), INK, base.ease_out_back(min(1.0, t_local * 3.5)))

        elif s_idx == 4:
            # SHOT 4: LOCATION 2 — INTERIOR OFFICE / HQ DESK + GLOWING LIGHTBULB 💡! (v1 00:15!)
            img = base.crop_camera(plates["interior"], base.lerp(1.03, 1.13, lfrac), base.lerp(-35, 35, lfrac), 0)
            draw = ImageDraw.Draw(img)
            base.draw_stick_char(draw, r0, 540, 1860, 1.32, t, "smug", "cheer", speaking, 1, 0.3)
            draw_lightbulb(draw, 540, 420, t, base.ease_out_back(min(1.0, max(0.0, t_local - 0.25) * 3.2)))

        elif s_idx == 5:
            # SHOT 5: FULL-SCREEN ANIMATED PROP / DOCUMENT / CRT INSERT (Zero characters — pure visual hook!)
            img = Image.new("RGB", (W, H), (24, 24, 34))
            draw_prop_insert(img, ex["insert_mode"], t, lfrac)
            draw = ImageDraw.Draw(img)

        elif s_idx == 6:
            # SHOT 6: LOCATION 3 — HIGH-ENERGY MOVING ACTION / CHAOS SCENE!
            shx = math.sin(t * 24) * 10
            shy = math.cos(t * 20) * 6
            img = base.crop_camera(plates["action"], base.lerp(1.02, 1.14, lfrac), shx, shy)
            draw_live_action_overlay(img, ex["action_mode"], t, lfrac, r0, r1, r2, speaking)
            draw = ImageDraw.Draw(img)

        elif s_idx == 7:
            # SHOT 7: CLIMAX COMEDY ACTION / EXPLOSION / STAMP SHOT!
            img = base.crop_camera(plates["action"], base.lerp(1.10, 1.03, lfrac), base.lerp(-30, 30, lfrac), 0)
            draw_live_action_overlay(img, ex["climax_mode"], t, lfrac, r0, r1, r2, speaking)
            draw = ImageDraw.Draw(img)

        elif s_idx == 8:
            # SHOT 8: CLASSIC v1 RETRO TV "● SON DAKİKA!" BREAKING NEWS INSERT!
            img = Image.new("RGB", (W, H), (20, 26, 38))
            draw_tv_news_insert(img, ex["tv_headline"], ex["tv_sub"], r1, t, t_local)
            draw = ImageDraw.Draw(img)

        elif s_idx == 9:
            # SHOT 9: INTERIOR DESK REACTION / DISBELIEF TWO-SHOT (exact v1 police room!)
            img = base.crop_camera(plates["interior"], base.lerp(1.06, 1.15, lfrac), base.lerp(30, -30, lfrac), 15)
            draw = ImageDraw.Draw(img)
            base.draw_stick_char(draw, r1, 310, 1810, 1.14, t, "panic", "panic", False, 1, 0.5)
            base.draw_stick_char(draw, r2, 770, 1810, 1.14, t, "nervous", "point_up", speaking, -1, 1.5)
            draw_floating_icon(draw, "!", 310, 560 + int(math.sin(t * 8) * 12), 54, (230, 44, 44), (255, 255, 255), base.ease_out_back(min(1.0, t_local * 3.5)))

        elif s_idx == 10:
            # SHOT 10: LOCATION 4 — CLASSIC v1/v3 GREEN CHALKBOARD FINALE + POINTER STICK!
            img = base.crop_camera(plates["chalkboard"], base.lerp(1.02, 1.18, base.ease_in_out(lfrac)), 0, base.lerp(0, -45, lfrac))
            draw = ImageDraw.Draw(img)
            base.draw_stick_char(draw, r0, 290, 1835, 1.06, t, "happy", "point_up", speaking, 1, 0.2)
            base.draw_stick_char(draw, r2, 790, 1835, 1.06, t, "happy", "cheer", False, -1, 1.2)
            # White chalk pointer stick aimed at chalkboard!
            draw.line([(415, 1410), (545, 1080)], fill=(250, 245, 225), width=12)

        else:
            # SHOT 11: TIGHT CLOSE-UP SEAMLESS LOOP BACK INTO SHOT 0!
            img = base.crop_camera(plates["wide"], base.lerp(1.10, 1.16, lfrac), base.lerp(20, -40, lfrac), 40)
            draw = ImageDraw.Draw(img)
            base.draw_stick_char(draw, r0, 540, 1980, base.lerp(1.42, 1.58, lfrac), t, "happy", "wave", speaking, 1, 0.2)

        # Snappy white camera-flash cut between major scene changes
        if s_idx > 0 and t_local < 0.12:
            alpha = int(165 * (1.0 - t_local / 0.12))
            flash = Image.new("RGBA", (W, H), (255, 250, 238, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), flash).convert("RGB")
            draw = ImageDraw.Draw(img)

        base.draw_caption(draw, cap, cap_age)
        proc.stdin.write(img.tobytes())
        if fidx in qa_indices:
            qa_frames.append(img.copy())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"FFmpeg failed on {slug} with exit code {rc}")
    bgm_sfx_path.unlink(missing_ok=True)
    words_cache.unlink(missing_ok=True)

    # Save 6x3 QA Sheet
    tw, th = 270, 480
    sheet = Image.new("RGB", (6 * tw, 3 * th), (12, 12, 16))
    for pos, im in enumerate(qa_frames[:18]):
        ri, ci = divmod(pos, 6)
        sheet.paste(im.resize((tw, th), Image.Resampling.LANCZOS), (ci * tw, ri * th))
    sheet.save(qa_path, "JPEG", quality=88, optimize=True)

    size_mb = round(mp4_path.stat().st_size / (1024 * 1024), 1)
    clean_script = base.strip_v4_tags(ep["tts_script"])
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
    print(f"  [4/4] ✅ SİNEMATİK {mp4_path.name} hazır ({size_mb} MB, {total_dur:.1f}s, {time.time() - t0:.1f}s render)", flush=True)
    return entry


def main() -> None:
    p = argparse.ArgumentParser(description="AKILALMAZ Cinematic v1-Style Multi-Location Director (v22-v26)")
    p.add_argument("--episodes", default="22,23,24,25,26", help="Bölüm numaraları")
    p.add_argument("--music-db", type=float, default=-12.0, help="Arka plan müzik seviyesi (dB)")
    args = p.parse_args()

    wanted = {int(x.strip()) for x in args.episodes.split(",") if x.strip()}
    selected = [ep for ep in base.EPISODES if ep["num"] in wanted]
    if not selected:
        sys.exit("Seçilen bölüm bulunamadı.")

    with tempfile.TemporaryDirectory(prefix="akil_cine_") as tmp:
        print(f"[Aşama 1] {len(selected)} video için 5'er farklı 3D-toon mekan/kamera açısı hazırlanıyor...", flush=True)
        plates_map = bake_cinematic_plates(selected, Path(tmp))

        videos = json.loads(base.VIDEOS_JSON.read_text(encoding="utf-8")) if base.VIDEOS_JSON.exists() else []
        for ep in selected:
            entry = render_cinematic_episode(ep, plates_map[ep["slug"]], music_db=args.music_db)
            videos = [v for v in videos if v.get("slug") != ep["slug"]]
            videos.append(entry)
            base.VIDEOS_JSON.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n✅ {len(selected)} sinematik video güncellendi!", flush=True)


if __name__ == "__main__":
    main()
