#!/usr/bin/env python3
"""AKILALMAZ Video 21 — 1788 Karanşebeş: Kendi Kendine Savaşan 100.000 Kişilik Ordu.

v1–v20 AKILALMAZ çizgi film tarzıyla birebir uyumlu 1080x1920 30fps dikey animasyon üreticisi:
- ElevenLabs ERKAN sesi + milisaniye kelime zaman damgaları (/with-timestamps)
- 2D kalın konturlu fasulye kafalı çizgi karakterler (Avusturyalı süvari, subay, Osmanlı gözcüsü)
- 6 sahneli kurgu: Dev ahşap fıçı sahnesi + 3 kalın çerçeveli bilgi panosu + seamless loop kapanış
- Kelime senkron kalın beyaz-siyah konturlu Türkçe altyazı + 6x3 QA Sheet
- Otomatik videos.json güncellemesi, özel 9:16 kapak yükleme (/api/covers/upload) ve
  2 Aralık 2026 Çarşamba 06:03 TR (2026-12-02T03:03:00+00:00) slotuna planlama.
"""
from __future__ import annotations

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

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Video 21 Metadata & Script
# ---------------------------------------------------------------------------
SLUG = "v21_kendi_kendine_savas"
FILE_NAME = "Video21-Kendi-Kendine-Savasan-Ordu.mp4"
TITLE = "Kendi Kendine Savaşan 100.000 Kişilik Ordu"
SCHEDULED_AT_UTC = "2026-12-02T03:03:00+00:00"  # 02.12.2026 Çar · 06:03 TR

SCRIPT_TEXT = (
    "Yüz bin kişilik dev bir ordu, düşman tek bir kurşun bile atmadan karanlıkta kendi kendini yendi!\n"
    "Şaka yapmıyorum, Osmanlı ordusu iki gün sonra geldiğinde savaş çoktan bitmişti!\n"
    "Bin yedi yüz seksen sekizde Avusturya ordusu, Osmanlı ile karşılaşmak için Karanşebeş yakınlarında kamp kurdu.\n"
    "Gece keşfe çıkan süvariler nehir kıyısında birkaç fıçı içki buldu ve piyadelerle paylaşmak istemedi!\n"
    "Tartışma büyüdü, karanlıkta yanlışlıkla bir el silah patladı.\n"
    "Birileri panikle \"Türkler geldi!\" diye bağırınca yüz bin kişilik dev kampta kıyamet koptu!\n"
    "Ordu farklı diller konuşan askerlerden oluşuyordu.\n"
    "Alman subaylar \"Halt! Dur!\" diye bağırdı... ama diğer askerler bunu \"Allah! Allah!\" saldırısı sandı!\n"
    "Karanlıkta kendi süvarilerini düşman sanıp top ateşi açtılar; imparator bile atından düşüp dereye yuvarlandı!\n"
    "İki gün sonra Osmanlı ordusu kasabaya ulaştığında kimse yoktu, şehri tek kurşun sıkmadan aldı!\n"
    "Ve askeri tarih bu akılalmaz geceyi hâlâ şöyle anlatır:"
)

META = {
    "youtube": {
        "title": "Osmanlı Gelmeden Karanlıkta Kendi Kendini Yenen 100.000 Kişilik Ordu! ⚔️😂 #shorts",
        "description": (
            "1788 Karanşebeş gecesinde 100.000 kişilik Avusturya ordusu, birkaç fıçı içki yüzünden çıkan "
            "tartışmada karanlıkta kendi askerlerini düşman sanıp birbirine girdi! Alman subayların "
            "'Halt! Dur!' bağırışı 'Allah!' saldırısı sanılınca kıyamet koptu. İki gün sonra gelen "
            "Osmanlı ordusu kasabayı tek kurşun atmadan aldı!\n\n"
            "👇 Tarihin en absürt yenilgisi bu olabilir mi? Yorumlara yaz!\n\n"
            "#shorts #tarih #osmanlı #ilginçbilgiler #karanşebeş #gerçekhikaye #animasyon #keşfet"
        ),
    },
    "instagram": {
        "caption": (
            "100.000 kişilik dev ordu, düşman gelmeden KARANLIKTA KENDİ KENDİNİ YENDİ! ⚔️🛢️😂\n\n"
            "1788'de Avusturya ordusu Karanşebeş'te kamp kurdu. Süvariler birkaç fıçı içki bulup "
            "piyadelerle paylaşmayınca tartışma çıktı, yanlışlıkla bir el silah patladı.\n\n"
            "Alman subaylar 'Halt! Dur!' diye bağırınca farklı diller konuşan askerler bunu 'Allah!' "
            "saldırısı sandı! Kendi süvarilerine top açtılar, imparator bile atından dereye düştü. "
            "İki gün sonra gelen Osmanlı ordusu şehri tek kurşun sıkmadan aldı!\n\n"
            "Tarih seven arkadaşına gönder 👇\n\n"
            "#reels #keşfet #tarih #osmanlı #ilginçbilgiler #gerçekhikayeler #animasyon #komiktarih"
        ),
    },
    "cover_title": "100.000 ASKER KENDİNİ YENDİ!",
    "flow_prompt": (
        "Full-bleed vertical 9:16 cartoon comedy illustration, stylized 2D inked characters with thick "
        "dark outlines under a starry moonlit 1788 European camp night beside a river bridge and glowing "
        "campfires, two panicked Austrian soldiers colliding with a wooden barrel and brass bugle while "
        "a smiling Ottoman scout watches from a distant hill with a spyglass, vibrant colors, no text."
    ),
}

REPO_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_DIR / "files" / SLUG / "out"
WORK_DIR = REPO_DIR / "files" / SLUG / "work"
VIDEOS_JSON = REPO_DIR / "videos.json"

W, H = 1080, 1920
FPS = 30

# ---------------------------------------------------------------------------
# Font Helpers
# ---------------------------------------------------------------------------
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _find_font_path(bold: bool = True) -> str:
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
    )
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    key = ("b" if bold else "r", size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(_find_font_path(bold), size)
    return _FONT_CACHE[key]


def fit_text_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, max_size: int, min_size: int = 26, bold: bool = True):
    for sz in range(max_size, min_size - 1, -2):
        f = get_font(sz, bold=bold)
        bb = draw.textbbox((0, 0), text, font=f)
        if (bb[2] - bb[0]) <= max_w:
            return f
    return get_font(min_size, bold=bold)


# ---------------------------------------------------------------------------
# Color & Geometry Helpers
# ---------------------------------------------------------------------------
OUTLINE = (24, 24, 34)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * ((t - 1) ** 3) + c1 * ((t - 1) ** 2)


def draw_gradient_bg(img: Image.Image, top_rgb: tuple[int, int, int], bot_rgb: tuple[int, int, int], y0: int = 0, y1: int = H):
    draw = ImageDraw.Draw(img)
    span = max(1, y1 - y0)
    # Step by 4px for blazing fast render speed (indistinguishable visually)
    for y in range(y0, y1, 4):
        f = (y - y0) / span
        c = (
            int(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * f),
            int(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * f),
            int(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * f),
        )
        draw.rectangle([0, y, W, min(y1, y + 4)], fill=c)


def draw_stage_floor(draw: ImageDraw.ImageDraw, floor_y: int = 1420, night: bool = True):
    if night:
        base = (52, 42, 34)
        plank_alt = (44, 35, 28)
        line_c = (28, 22, 18)
        top_edge = (95, 72, 48)
    else:
        base = (126, 86, 44)
        plank_alt = (112, 74, 36)
        line_c = (72, 46, 22)
        top_edge = (168, 122, 64)

    draw.rectangle([0, floor_y, W, H], fill=base)
    draw.rectangle([0, floor_y, W, floor_y + 14], fill=top_edge)
    draw.line([(0, floor_y), (W, floor_y)], fill=OUTLINE, width=6)

    # Perspective wooden planks
    cx = W // 2
    for i in range(-6, 7):
        x_top = cx + i * 115
        x_bot = cx + i * 240
        if i % 2 == 0:
            draw.polygon([(x_top, floor_y + 14), (x_top + 115, floor_y + 14), (x_bot + 240, H), (x_bot, H)], fill=plank_alt)
        draw.line([(x_top, floor_y + 14), (x_bot, H)], fill=line_c, width=4)
    for y_row in (floor_y + 110, floor_y + 260, floor_y + 420):
        draw.line([(0, y_row), (W, y_row)], fill=line_c, width=3)


def draw_wood_wall_bg(img: Image.Image, warm_tint: tuple[int, int, int] = (158, 118, 66)):
    draw_gradient_bg(
        img,
        (min(255, warm_tint[0] + 22), min(255, warm_tint[1] + 20), min(255, warm_tint[2] + 14)),
        (max(0, warm_tint[0] - 32), max(0, warm_tint[1] - 28), max(0, warm_tint[2] - 22)),
        0,
        1425,
    )
    draw = ImageDraw.Draw(img)
    for y in range(60, 1420, 95):
        draw.line([(0, y), (W, y)], fill=(max(0, warm_tint[0] - 48), max(0, warm_tint[1] - 40), max(0, warm_tint[2] - 28)), width=4)
    draw_stage_floor(draw, floor_y=1420, night=False)


def draw_night_camp_bg(img: Image.Image, t: float, show_barrel: bool = True, sunrise: bool = False):
    if sunrise:
        draw_gradient_bg(img, (48, 86, 146), (234, 174, 96), 0, 1425)
    else:
        draw_gradient_bg(img, (16, 26, 62), (46, 64, 112), 0, 1425)
    draw = ImageDraw.Draw(img)

    # Twinkling stars
    if not sunrise:
        stars = [
            (95, 90, 5), (210, 140, 4), (340, 75, 6), (480, 130, 4), (620, 82, 5),
            (790, 118, 6), (920, 72, 4), (990, 165, 5), (140, 240, 4), (880, 235, 5),
            (280, 200, 3), (710, 185, 4),
        ]
        for idx, (sx, sy, sr) in enumerate(stars):
            pulse = 0.65 + 0.35 * math.sin(t * 3.5 + idx * 1.1)
            r = max(2, int(sr * pulse))
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 246, 198))

        # Glowing crescent moon top-right
        mx, my = 865, 210
        draw.ellipse([mx - 95, my - 95, mx + 95, my + 95], fill=(64, 86, 142))
        draw.ellipse([mx - 72, my - 72, mx + 72, my + 72], fill=(255, 238, 168), outline=OUTLINE, width=6)
        draw.ellipse([mx - 42, my - 82, mx + 94, my + 58], fill=(26, 38, 82))
    else:
        # Warm rising sun
        mx, my = 540, 320
        draw.ellipse([mx - 150, my - 150, mx + 150, my + 150], fill=(255, 214, 112))
        draw.ellipse([mx - 105, my - 105, mx + 105, my + 105], fill=(255, 236, 160))

    # Distant rolling hills
    hill_c1 = (32, 48, 72) if not sunrise else (72, 108, 92)
    hill_c2 = (24, 38, 56) if not sunrise else (54, 88, 72)
    draw.ellipse([-220, 920, 740, 1520], fill=hill_c1, outline=OUTLINE, width=6)
    draw.ellipse([360, 880, 1340, 1540], fill=hill_c2, outline=OUTLINE, width=6)

    # Stylized camp tents in mid-ground
    tent_c = (212, 196, 164) if not sunrise else (238, 224, 194)
    for tx, ty, sc in [(115, 1140, 1.0), (925, 1150, 0.92)]:
        pts = [(tx, ty - int(130 * sc)), (tx - int(110 * sc), ty + int(60 * sc)), (tx + int(110 * sc), ty + int(60 * sc))]
        draw.polygon(pts, fill=tent_c, outline=OUTLINE)
        draw.line([pts[0], pts[1], pts[2], pts[0]], fill=OUTLINE, width=6)
        # Tent door
        door = [(tx, ty - int(35 * sc)), (tx - int(32 * sc), ty + int(60 * sc)), (tx + int(32 * sc), ty + int(60 * sc))]
        draw.polygon(door, fill=(46, 36, 30), outline=OUTLINE)

    # Giant iconic wooden schnapps barrel (AKILALMAZ signature hero prop like v16 bucket / v19 moon / v20 stopwatch!)
    if show_barrel:
        bob = int(math.sin(t * 2.2) * 8)
        bx, by = 540, 720 + bob
        bw, bh = 285, 390
        # Soft warm aura behind barrel
        draw.ellipse([bx - bw - 40, by - bh - 40, bx + bw + 40, by + bh + 40], fill=(72, 76, 116) if not sunrise else (246, 194, 116))
        # Barrel body
        draw.rounded_rectangle([bx - bw, by - bh, bx + bw, by + bh], radius=120, fill=(176, 112, 52), outline=OUTLINE, width=10)
        # Vertical wood stave lines & highlight
        draw.rounded_rectangle([bx - bw + 32, by - bh + 28, bx - bw + 110, by + bh - 28], radius=45, fill=(204, 138, 70))
        for dx in (-180, -90, 0, 90, 180):
            draw.line([(bx + dx, by - bh + 18), (bx + dx, by + bh - 18)], fill=(112, 68, 28), width=6)
        # Metallic iron hoops
        for hy in (-240, -105, 105, 240):
            hw = bw - (18 if abs(hy) > 200 else -4)
            draw.rounded_rectangle([bx - hw, by + hy - 22, bx + hw, by + hy + 22], radius=12, fill=(68, 76, 92), outline=OUTLINE, width=7)
            # Rivets
            for rx in (-hw + 40, -hw // 2, 0, hw // 2, hw - 40):
                draw.ellipse([bx + rx - 7, by + hy - 7, bx + rx + 7, by + hy + 7], fill=(168, 178, 196))
        # Wooden tap spout on front
        draw.ellipse([bx - 36, by - 36, bx + 36, by + 36], fill=(122, 74, 34), outline=OUTLINE, width=6)
        draw.rounded_rectangle([bx - 14, by - 14, bx + 52, by + 18], radius=10, fill=(218, 172, 72), outline=OUTLINE, width=5)

    draw_stage_floor(draw, floor_y=1420, night=not sunrise)

    # Campfire flickering glow left/right corners
    if not sunrise:
        flicker = 1.0 + 0.12 * math.sin(t * 14.0)
        fx, fy = 125, 1410
        draw.ellipse([fx - int(55 * flicker), fy - int(48 * flicker), fx + int(55 * flicker), fy + 16], fill=(246, 128, 32), outline=OUTLINE, width=5)
        draw.ellipse([fx - int(32 * flicker), fy - int(32 * flicker), fx + int(32 * flicker), fy + 8], fill=(255, 224, 88))


def draw_location_plaque(draw: ImageDraw.ImageDraw, title_top: str, title_sub: str, x: int = 58, y: int = 330):
    box = [x, y, x + 430, y + 126]
    draw.rounded_rectangle([box[0] + 6, box[1] + 8, box[2] + 6, box[3] + 8], radius=18, fill=(14, 18, 30))
    draw.rounded_rectangle(box, radius=18, fill=(20, 44, 82), outline=(245, 200, 66), width=7)
    f1 = fit_text_font(draw, title_top, 390, 40, 26, bold=True)
    f2 = fit_text_font(draw, title_sub, 390, 24, 18, bold=True)
    draw.text((x + 215, y + 42), title_top, font=f1, fill=(255, 214, 74), anchor="mm")
    draw.text((x + 215, y + 92), title_sub, font=f2, fill=(235, 242, 255), anchor="mm")


def draw_info_board(
    draw: ImageDraw.ImageDraw,
    bg_color: tuple[int, int, int],
    headline: str,
    lines: list[str],
    badge_top: str,
    badge_sub: str,
    badge_color: tuple[int, int, int],
    t_local: float,
    sparkles: bool = False,
):
    """Exact signature AKILALMAZ framed storyboard card (v16/v19/v20 style), zero text clipping."""
    pop = ease_out_back(min(1.0, t_local / 0.35))
    scale = 0.86 + 0.14 * pop
    cx, cy = W // 2, 460
    bw, bh = int(950 * scale), int(580 * scale)
    x0, y0 = cx - bw // 2, cy - bh // 2
    x1, y1 = cx + bw // 2, cy + bh // 2

    # Drop shadow
    draw.rounded_rectangle([x0 + 12, y0 + 16, x1 + 12, y1 + 16], radius=26, fill=(26, 20, 14))
    # Outer gold frame
    draw.rounded_rectangle([x0, y0, x1, y1], radius=26, fill=(246, 200, 56), outline=OUTLINE, width=8)
    # Inner colored board
    pad = 18
    draw.rounded_rectangle([x0 + pad, y0 + pad, x1 - pad, y1 - pad], radius=18, fill=bg_color, outline=OUTLINE, width=5)

    # Headline
    max_tw = (x1 - x0) - 96
    f_head = fit_text_font(draw, headline, max_tw, 62, 34, bold=True)
    draw.text((cx, y0 + int(bh * 0.22)), headline, font=f_head, fill=(255, 224, 92), anchor="mm", stroke_width=4, stroke_fill=OUTLINE)

    # Divider line
    draw.line([(x0 + 70, y0 + int(bh * 0.34)), (x1 - 70, y0 + int(bh * 0.34))], fill=(255, 224, 92), width=4)

    # 3 crisp lines
    y_positions = [0.49, 0.66, 0.83]
    for idx, line in enumerate(lines[:3]):
        color = (255, 255, 255) if idx < 2 else (255, 232, 146)
        f_line = fit_text_font(draw, line, max_tw, 38, 22, bold=True)
        draw.text((cx, y0 + int(bh * y_positions[idx])), line, font=f_line, fill=color, anchor="mm", stroke_width=3, stroke_fill=OUTLINE)

    # Mini pill badge underneath the board
    if badge_top:
        b_pop = ease_out_back(min(1.0, max(0.0, (t_local - 0.18) / 0.32)))
        if b_pop > 0.05:
            pw, ph = int(310 * b_pop), int(108 * b_pop)
            px0, py0 = cx - pw // 2, y1 + 26
            px1, py1 = cx + pw // 2, py0 + ph
            draw.rounded_rectangle([px0 + 6, py0 + 8, px1 + 6, py1 + 8], radius=20, fill=(24, 18, 12))
            draw.rounded_rectangle([px0, py0, px1, py1], radius=20, fill=badge_color, outline=OUTLINE, width=6)
            txt_c = (20, 20, 28) if sum(badge_color) > 420 else (255, 255, 255)
            f_bt = fit_text_font(draw, badge_top, pw - 28, 32, 18, bold=True)
            f_bs = fit_text_font(draw, badge_sub, pw - 28, 20, 14, bold=True)
            draw.text((cx, py0 + int(ph * 0.38)), badge_top, font=f_bt, fill=txt_c, anchor="mm")
            draw.text((cx, py0 + int(ph * 0.74)), badge_sub, font=f_bs, fill=txt_c, anchor="mm")

            if sparkles:
                for sx, sy, sr in [(px0 - 38, py0 + 20, 22), (px1 + 38, py0 + 18, 26), (px1 + 18, py1 + 10, 16)]:
                    ang = t_local * 4.0
                    s_r = int(sr * (0.85 + 0.25 * math.sin(ang + sx)))
                    pts = [
                        (sx, sy - s_r), (sx + s_r // 3, sy - s_r // 3),
                        (sx + s_r, sy), (sx + s_r // 3, sy + s_r // 3),
                        (sx, sy + s_r), (sx - s_r // 3, sy + s_r // 3),
                        (sx - s_r, sy), (sx - s_r // 3, sy - s_r // 3),
                    ]
                    draw.polygon(pts, fill=(255, 232, 82), outline=OUTLINE)


# ---------------------------------------------------------------------------
# Signature AKILALMAZ 2D Cartoon Characters (Bean Heads + Thick Outlines)
# ---------------------------------------------------------------------------
def draw_character(
    draw: ImageDraw.ImageDraw,
    cx: int,
    base_y: int,
    role: str,
    t: float,
    emotion: str = "neutral",
    speaking: bool = False,
    arm_pose: str = "idle",
    facing: int = 1,
    prop: str | None = None,
    phase: float = 0.0,
):
    """Draws an expressive AKILALMAZ 2D cartoon character with bean head, blinking eyes,
    lip-sync mouth, stick limbs, period uniform, and props."""
    bounce = int(abs(math.sin(t * 5.2 + phase)) * (16 if emotion == "panic" else 8))
    shake_x = int(math.sin(t * 28.0 + phase) * 9) if emotion == "panic" else 0
    x = cx + shake_x
    y = base_y - bounce

    # Ground shadow
    draw.ellipse([cx - 105, base_y - 18, cx + 105, base_y + 26], fill=(22, 18, 16))

    # Role palette
    if role == "austrian_cavalry":
        coat = (236, 236, 242)
        sash = (212, 42, 42)
        hat_c = (28, 44, 78)
        hat_trim = (242, 198, 56)
        skin = (245, 206, 168)
    elif role == "austrian_officer":
        coat = (36, 56, 98)
        sash = (242, 198, 56)
        hat_c = (24, 34, 58)
        hat_trim = (242, 198, 56)
        skin = (242, 200, 162)
    else:  # ottoman_scout
        coat = (18, 118, 86)
        sash = (168, 36, 46)
        hat_c = (246, 244, 236)
        hat_trim = (186, 36, 46)
        skin = (236, 190, 148)

    # Legs & boots (stick limbs with thick outlines)
    leg_swing = int(math.sin(t * 9.0 + phase) * 18) if emotion == "panic" else 0
    hip_y = y - 145
    l_foot = (x - 42 - leg_swing, base_y + 2)
    r_foot = (x + 42 + leg_swing, base_y + 2)
    draw.line([(x - 32, hip_y), l_foot], fill=OUTLINE, width=18)
    draw.line([(x + 32, hip_y), r_foot], fill=OUTLINE, width=18)
    draw.rounded_rectangle([l_foot[0] - 28, l_foot[1] - 18, l_foot[0] + 22, l_foot[1] + 10], radius=10, fill=(32, 28, 36), outline=OUTLINE, width=5)
    draw.rounded_rectangle([r_foot[0] - 22, r_foot[1] - 18, r_foot[0] + 28, r_foot[1] + 10], radius=10, fill=(32, 28, 36), outline=OUTLINE, width=5)

    # Torso (rounded trapezoid / bean tunic)
    torso_top = y - 355
    torso_bot = y - 135
    draw.rounded_rectangle([x - 86, torso_top, x + 86, torso_bot], radius=48, fill=coat, outline=OUTLINE, width=8)
    # Diagonal military sash
    draw.line([(x - 66, torso_top + 28), (x + 68, torso_bot - 22)], fill=sash, width=28)
    draw.line([(x - 66, torso_top + 14), (x + 68, torso_bot - 36)], fill=OUTLINE, width=4)
    draw.line([(x - 66, torso_top + 42), (x + 68, torso_bot - 8)], fill=OUTLINE, width=4)
    # Gold belt buckle / buttons
    for by_btn in (torso_top + 65, torso_top + 115, torso_top + 165):
        draw.ellipse([x - 7, by_btn - 7, x + 7, by_btn + 7], fill=(246, 202, 62), outline=OUTLINE, width=3)

    # Arms (expressive poses)
    sh_y = torso_top + 52
    wave = int(math.sin(t * 10.0 + phase) * 28)
    if arm_pose == "panic":
        l_hand = (x - 145, sh_y - 120 + wave)
        r_hand = (x + 145, sh_y - 115 - wave)
    elif arm_pose == "hold_barrel":
        l_hand = (x - 55, sh_y + 42)
        r_hand = (x + 55, sh_y + 42)
    elif arm_pose == "point":
        l_hand = (x - 130, sh_y + 50)
        r_hand = (x + 160 * facing, sh_y - 55 + wave // 2)
    elif arm_pose == "spyglass":
        l_hand = (x - 110, sh_y + 55)
        r_hand = (x - 52, sh_y - 95)
    elif arm_pose == "cheer":
        l_hand = (x - 140, sh_y - 105 + wave // 2)
        r_hand = (x + 140, sh_y - 105 - wave // 2)
    else:
        l_hand = (x - 125, sh_y + 55 + wave // 3)
        r_hand = (x + 125, sh_y + 35 - wave // 3)

    draw.line([(x - 74, sh_y), l_hand], fill=OUTLINE, width=16)
    draw.line([(x + 74, sh_y), r_hand], fill=OUTLINE, width=16)
    draw.ellipse([l_hand[0] - 18, l_hand[1] - 18, l_hand[0] + 18, l_hand[1] + 18], fill=skin, outline=OUTLINE, width=5)
    draw.ellipse([r_hand[0] - 18, r_hand[1] - 18, r_hand[0] + 18, r_hand[1] + 18], fill=skin, outline=OUTLINE, width=5)

    # Mini held prop
    if prop == "mini_barrel":
        mx, my = x, sh_y + 48
        draw.rounded_rectangle([mx - 58, my - 66, mx + 58, my + 66], radius=24, fill=(176, 112, 52), outline=OUTLINE, width=6)
        draw.line([(mx - 55, my - 26), (mx + 55, my - 26)], fill=(70, 78, 92), width=10)
        draw.line([(mx - 55, my + 26), (mx + 55, my + 26)], fill=(70, 78, 92), width=10)
    elif prop == "bugle":
        bx, by = r_hand[0], r_hand[1] - 10
        draw.polygon([(bx, by), (bx - 95, by - 40), (bx - 95, by + 26)], fill=(244, 198, 58), outline=OUTLINE)
        draw.line([(bx, by), (bx - 95, by - 40), (bx - 95, by + 26), (bx, by)], fill=OUTLINE, width=5)
    elif prop == "spyglass":
        sx, sy = r_hand[0] - 10, r_hand[1] - 12
        draw.line([(sx + 25, sy + 12), (sx - 92, sy - 22)], fill=(238, 190, 56), width=26)
        draw.line([(sx + 25, sy + 12), (sx - 92, sy - 22)], fill=OUTLINE, width=5)
        draw.ellipse([sx - 108, sy - 38, sx - 76, sy - 6], fill=(130, 212, 245), outline=OUTLINE, width=5)

    # Head (signature bean/oval cartoon head)
    head_cy = torso_top - 96
    head_rx, head_ry = 98, 108
    draw.ellipse([x - head_rx, head_cy - head_ry, x + head_rx, head_cy + head_ry], fill=skin, outline=OUTLINE, width=8)
    # Soft cheek blush
    draw.ellipse([x - 74, head_cy + 14, x - 44, head_cy + 34], fill=(242, 166, 152))
    draw.ellipse([x + 44, head_cy + 14, x + 74, head_cy + 34], fill=(242, 166, 152))

    # Eyes (blinking + emotional sizing)
    blink_cycle = (t + phase) % 3.6
    is_blink = 3.42 < blink_cycle < 3.56 and emotion != "panic"
    ex_off = 34
    ey = head_cy - 12
    erx = 24 if emotion == "panic" else 20
    ery = 30 if emotion == "panic" else 25
    look_x = 6 * facing

    for sgn in (-1, 1):
        ex = x + sgn * ex_off
        if is_blink:
            draw.line([(ex - 18, ey), (ex + 18, ey)], fill=OUTLINE, width=7)
        elif emotion == "happy":
            draw.arc([ex - 20, ey - 14, ex + 20, ey + 18], start=190, end=350, fill=OUTLINE, width=7)
        else:
            draw.ellipse([ex - erx, ey - ery, ex + erx, ey + ery], fill=(255, 255, 255), outline=OUTLINE, width=5)
            pr = 7 if emotion == "panic" else 9
            draw.ellipse([ex + look_x - pr, ey - pr, ex + look_x + pr, ey + pr], fill=OUTLINE)
            draw.ellipse([ex + look_x - 3, ey - 5, ex + look_x + 2, ey], fill=(255, 255, 255))

    # Eyebrows
    if emotion == "angry":
        draw.line([(x - 56, ey - 38), (x - 14, ey - 24)], fill=OUTLINE, width=8)
        draw.line([(x + 56, ey - 38), (x + 14, ey - 24)], fill=OUTLINE, width=8)
    elif emotion == "panic":
        draw.arc([x - 62, ey - 54, x - 12, ey - 24], start=190, end=350, fill=OUTLINE, width=7)
        draw.arc([x + 12, ey - 54, x + 62, ey - 24], start=190, end=350, fill=OUTLINE, width=7)
    elif emotion == "amused":
        draw.line([(x - 56, ey - 34), (x - 16, ey - 38)], fill=OUTLINE, width=7)
        draw.arc([x + 12, ey - 48, x + 58, ey - 22], start=190, end=350, fill=OUTLINE, width=7)

    # Ottoman mustache for scout
    if role == "ottoman_scout":
        draw.arc([x - 42, head_cy + 16, x + 2, head_cy + 46], start=190, end=350, fill=(44, 30, 22), width=10)
        draw.arc([x - 2, head_cy + 16, x + 42, head_cy + 46], start=190, end=350, fill=(44, 30, 22), width=10)

    # Mouth (speaking lip-sync or emotional expression)
    my = head_cy + 44
    mouth_open = speaking and (math.sin(t * 22.0 + phase) > -0.15)
    if emotion == "panic":
        mh = 30 if mouth_open else 22
        draw.ellipse([x - 24, my - mh // 2, x + 24, my + mh], fill=(138, 32, 42), outline=OUTLINE, width=6)
        draw.arc([x - 14, my + 4, x + 14, my + mh], start=180, end=360, fill=(235, 110, 118), width=6)
    elif mouth_open:
        draw.ellipse([x - 22, my - 10, x + 22, my + 24], fill=(138, 32, 42), outline=OUTLINE, width=6)
    elif emotion in ("happy", "amused"):
        draw.arc([x - 32, my - 18, x + 32, my + 24], start=15, end=165, fill=OUTLINE, width=7)
    else:
        draw.arc([x - 26, my - 12, x + 26, my + 16], start=15, end=165, fill=OUTLINE, width=6)

    # Hat / Turban
    hat_y = head_cy - 68
    if role == "ottoman_scout":
        # Classic stylized Ottoman turban
        draw.ellipse([x - 108, hat_y - 78, x + 108, hat_y + 34], fill=hat_c, outline=OUTLINE, width=8)
        draw.ellipse([x - 52, hat_y - 94, x + 52, hat_y - 16], fill=hat_trim, outline=OUTLINE, width=7)
        draw.line([(x - 86, hat_y - 26), (x + 86, hat_y - 2)], fill=(208, 202, 190), width=6)
        draw.ellipse([x - 14, hat_y - 52, x + 14, hat_y - 24], fill=(246, 202, 58), outline=OUTLINE, width=5)
    else:
        # 18th-century Austrian bicorne military hat
        pts = [
            (x - 134, hat_y + 18),
            (x - 74, hat_y - 78),
            (x, hat_y - 96),
            (x + 74, hat_y - 78),
            (x + 134, hat_y + 18),
        ]
        draw.polygon(pts, fill=hat_c, outline=OUTLINE)
        draw.line(pts + [pts[0]], fill=OUTLINE, width=8)
        draw.line([(x - 114, hat_y + 6), (x, hat_y - 74), (x + 114, hat_y + 6)], fill=hat_trim, width=8)
        # Cockade badge
        draw.ellipse([x - 18, hat_y - 54, x + 18, hat_y - 18], fill=(224, 48, 48), outline=OUTLINE, width=4)
        draw.ellipse([x - 8, hat_y - 44, x + 8, hat_y - 28], fill=(255, 255, 255))


def draw_floating_badge(draw: ImageDraw.ImageDraw, x: int, y: int, symbol: str, t: float, fill=(255, 214, 56)):
    r = 46 + int(math.sin(t * 7.0) * 5)
    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=OUTLINE, width=7)
    f = get_font(54, bold=True)
    draw.text((x, y + 2), symbol, font=f, fill=OUTLINE, anchor="mm")


def draw_captions(draw: ImageDraw.ImageDraw, text: str, t_in_chunk: float):
    """Bold AKILALMAZ captions centered in the safe lower-middle zone (matching v16–v20)."""
    if not text.strip():
        return
    pop = 0.92 + 0.08 * ease_out_back(min(1.0, t_in_chunk / 0.14))
    max_sz = int(68 * pop)
    f = fit_text_font(draw, text, W - 130, max_sz, 38, bold=True)
    draw.text((W // 2, 1048), text, font=f, fill=(255, 255, 255), anchor="mm", stroke_width=10, stroke_fill=(16, 16, 24))


# ---------------------------------------------------------------------------
# Scene Choreography (6 Dynamic Scenes across full duration)
# ---------------------------------------------------------------------------
def build_scene_boundaries(total_dur: float) -> list[tuple[float, float, str]]:
    """Splits the video proportionally to the narration beats."""
    return [
        (0.00 * total_dur, 0.17 * total_dur, "hook"),
        (0.17 * total_dur, 0.38 * total_dur, "barrel_fight"),
        (0.38 * total_dur, 0.58 * total_dur, "halt_misunderstanding"),
        (0.58 * total_dur, 0.77 * total_dur, "friendly_fire"),
        (0.77 * total_dur, 0.93 * total_dur, "ottoman_victory"),
        (0.93 * total_dur, 1.05 * total_dur, "loop_outro"),
    ]


def render_frame(t: float, total_dur: float, active_caption: str, caption_age: float, speaking: bool) -> Image.Image:
    scenes = build_scene_boundaries(total_dur)
    scene_name = "hook"
    s_start = 0.0
    for st, en, name in scenes:
        if st <= t < en:
            scene_name = name
            s_start = st
            break
    t_local = max(0.0, t - s_start)

    img = Image.new("RGB", (W, H), (20, 26, 48))

    if scene_name == "hook":
        draw_night_camp_bg(img, t, show_barrel=True, sunrise=False)
        draw = ImageDraw.Draw(img)
        draw_location_plaque(draw, "AVUSTURYA · 1788", "KARANŞEBEŞ GECESİ", x=56, y=280)
        draw_floating_badge(draw, 880, 420, "!", t, fill=(255, 206, 54))
        draw_character(draw, 330, 1790, "austrian_cavalry", t, emotion="panic", speaking=speaking, arm_pose="hold_barrel", facing=1, prop="mini_barrel", phase=0.2)
        draw_character(draw, 760, 1790, "austrian_officer", t, emotion="panic", speaking=False, arm_pose="panic", facing=-1, phase=1.7)

    elif scene_name == "barrel_fight":
        draw_night_camp_bg(img, t, show_barrel=True, sunrise=False)
        draw = ImageDraw.Draw(img)
        draw_location_plaque(draw, "AVUSTURYA · 1788", "NEHİR KENARI KAMPI", x=48, y=280)
        # Pop-in date card cleanly beside location plaque (zero overlap)
        dp = ease_out_back(min(1.0, t_local / 0.35))
        if dp > 0.1:
            dx0, dy0 = 515, 268
            draw.rounded_rectangle([dx0 + 6, dy0 + 8, dx0 + 276, dy0 + 154], radius=22, fill=(14, 18, 30))
            draw.rounded_rectangle([dx0, dy0, dx0 + 270, dy0 + 146], radius=22, fill=(248, 250, 255), outline=OUTLINE, width=7)
            draw.rounded_rectangle([dx0, dy0, dx0 + 270, dy0 + 46], radius=16, fill=(28, 66, 122), outline=OUTLINE, width=5)
            draw.text((dx0 + 135, dy0 + 23), "KARANŞEBEŞ", font=get_font(20, True), fill=(255, 224, 92), anchor="mm")
            draw.text((dx0 + 135, dy0 + 96), "1788", font=get_font(58, True), fill=OUTLINE, anchor="mm")
        draw_floating_badge(draw, 895, 342, "?", t, fill=(255, 214, 56))
        draw_character(draw, 325, 1790, "austrian_cavalry", t, emotion="angry", speaking=speaking, arm_pose="hold_barrel", facing=1, prop="mini_barrel", phase=0.5)
        draw_character(draw, 760, 1790, "austrian_officer", t, emotion="angry", speaking=not speaking, arm_pose="point", facing=-1, prop="bugle", phase=2.0)

    elif scene_name == "halt_misunderstanding":
        draw_wood_wall_bg(img, warm_tint=(162, 122, 68))
        draw = ImageDraw.Draw(img)
        draw_info_board(
            draw,
            bg_color=(16, 62, 114),
            headline="1788 KARANŞEBEŞ!",
            lines=[
                'ALMAN SUBAY: "HALT! DUR!" DEDİ',
                'ASKERLER "ALLAH!" SALDIRISI SANDI',
                "100.000 ASKER KARANLIKTA KARIŞTI",
            ],
            badge_top="BÜYÜK PANİK!",
            badge_sub="100.000 ASKER",
            badge_color=(250, 206, 54),
            t_local=t_local,
        )
        draw_character(draw, 325, 1790, "austrian_cavalry", t, emotion="panic", speaking=False, arm_pose="panic", facing=1, phase=0.3)
        draw_character(draw, 760, 1790, "austrian_officer", t, emotion="angry", speaking=speaking, arm_pose="point", facing=-1, prop="bugle", phase=1.4)

    elif scene_name == "friendly_fire":
        draw_wood_wall_bg(img, warm_tint=(134, 88, 52))
        draw = ImageDraw.Draw(img)
        draw_info_board(
            draw,
            bg_color=(164, 24, 30),
            headline="KENDİ KENDİNE SAVAŞ!",
            lines=[
                "KENDİ SÜVARİLERİNE TOP AÇTILAR",
                "İMPARATOR ATINDAN DEREYE DÜŞTÜ",
                "ORTADA TEK BİR DÜŞMAN YOKTU!",
            ],
            badge_top="0 DÜŞMAN!",
            badge_sub="KARANLIKTA KAOS",
            badge_color=(42, 188, 224),
            t_local=t_local,
        )
        # Dramatic comic sparks below captions
        for idx, (sx, sy) in enumerate([(120, 1265), (960, 1265), (540, 1345)]):
            r = 24 + int(abs(math.sin(t * 12 + idx)) * 16)
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 146, 36), outline=OUTLINE, width=5)
            draw.ellipse([sx - r // 2, sy - r // 2, sx + r // 2, sy + r // 2], fill=(255, 236, 98))
        draw_character(draw, 315, 1790, "austrian_cavalry", t, emotion="panic", speaking=speaking, arm_pose="panic", facing=1, phase=0.1)
        draw_character(draw, 770, 1790, "austrian_officer", t, emotion="panic", speaking=speaking, arm_pose="panic", facing=-1, phase=2.2)

    elif scene_name == "ottoman_victory":
        draw_wood_wall_bg(img, warm_tint=(144, 118, 66))
        draw = ImageDraw.Draw(img)
        draw_info_board(
            draw,
            bg_color=(14, 108, 82),
            headline="2 GÜN SONRA OSMANLI GELDİ!",
            lines=[
                "SAVAŞ ÇOKTAN BİTMİŞTİ",
                "KASABA TEK KURŞUNSUZ ALINDI",
                "TARİHİN EN ABSÜRT YENİLGİSİ",
            ],
            badge_top="TEK KURŞUNSUZ!",
            badge_sub="OSMANLI ZAFERİ",
            badge_color=(250, 206, 54),
            t_local=t_local,
            sparkles=True,
        )
        draw_character(draw, 325, 1790, "austrian_cavalry", t, emotion="panic", speaking=False, arm_pose="idle", facing=1, phase=0.8)
        draw_character(draw, 755, 1790, "ottoman_scout", t, emotion="amused", speaking=speaking, arm_pose="spyglass", facing=-1, prop="spyglass", phase=1.2)

    else:  # loop_outro (returns seamlessly to opening visual!)
        draw_night_camp_bg(img, t, show_barrel=True, sunrise=False)
        draw = ImageDraw.Draw(img)
        draw_location_plaque(draw, "AVUSTURYA · 1788", "KARANŞEBEŞ GECESİ", x=56, y=280)
        draw_character(draw, 330, 1790, "austrian_cavalry", t, emotion="happy", speaking=speaking, arm_pose="cheer", facing=1, phase=0.2)
        draw_character(draw, 760, 1790, "austrian_officer", t, emotion="amused", speaking=False, arm_pose="idle", facing=-1, phase=1.7)

    # Crisp white flash transition at scene cuts (matching v16/v19/v20!)
    if t > 0.25 and t_local < 0.16:
        alpha = int(175 * (1.0 - t_local / 0.16))
        flash = Image.new("RGBA", (W, H), (255, 250, 238, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), flash).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Active Turkish captions
    draw_captions(draw, active_caption, caption_age)
    return img


# ---------------------------------------------------------------------------
# ElevenLabs ERKAN Voice Synthesis + Word Timestamps
# ---------------------------------------------------------------------------
def synthesize_erkan_voice(text: str, out_mp3: Path) -> tuple[float, list[dict[str, Any]]]:
    import requests

    el_key = os.environ["ELEVENLABS_API_KEY"].strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "gsfAMpj9oiFONXfvZJoE")  # ERKAN
    model_id = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    r = requests.post(
        url,
        headers={"xi-api-key": el_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.48, "similarity_boost": 0.80, "style": 0.35},
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    out_mp3.write_bytes(base64.b64decode(data["audio_base64"]))

    align = data.get("alignment") or data.get("normalized_alignment") or {}
    chars = align.get("characters", [])
    starts = align.get("character_start_times_seconds", [])
    ends = align.get("character_end_times_seconds", [])

    words: list[dict[str, Any]] = []
    cur: list[str] = []
    w_st, w_en = None, None
    for ch, st, en in zip(chars, starts, ends):
        if ch.strip():
            if w_st is None:
                w_st = float(st)
            cur.append(ch)
            w_en = float(en)
        else:
            if cur:
                words.append({"word": "".join(cur), "start": w_st, "end": w_en})
                cur, w_st, w_en = [], None, None
    if cur:
        words.append({"word": "".join(cur), "start": w_st, "end": w_en})

    dur_str = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out_mp3)],
        text=True,
    ).strip()
    return float(dur_str), words


def group_word_chunks(words: list[dict[str, Any]], chunk_size: int = 2) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    i = 0
    while i < len(words):
        grp = words[i : i + chunk_size]
        # Allow 3 short words together if total length <= 18 chars
        if i + 2 < len(words) and sum(len(w["word"]) for w in words[i : i + 3]) <= 16:
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


def build_qa_sheet(sample_frames: list[Image.Image], out_jpg: Path):
    cols = 6
    rows = max(1, math.ceil(len(sample_frames) / cols))
    tw, th = 270, 480
    sheet = Image.new("RGB", (cols * tw, rows * th), (12, 12, 16))
    for idx, im in enumerate(sample_frames):
        r, c = divmod(idx, cols)
        sheet.paste(im.resize((tw, th), Image.Resampling.LANCZOS), (c * tw, r * th))
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_jpg, "JPEG", quality=88, optimize=True)


# ---------------------------------------------------------------------------
# Full Production Render (Pipes raw RGB to FFmpeg + mixes ERKAN + music)
# ---------------------------------------------------------------------------
def produce_video():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    voice_path = WORK_DIR / "voice.mp3"
    mp4_path = OUT_DIR / FILE_NAME
    qa_path = OUT_DIR / "qa_sheet.jpg"

    print(f"[1/4] ElevenLabs ERKAN sesi üretiliyor ({SLUG})...")
    duration, words = synthesize_erkan_voice(SCRIPT_TEXT, voice_path)
    total_dur = duration + 0.45
    total_frames = int(math.ceil(total_dur * FPS))
    chunks = group_word_chunks(words, chunk_size=2)
    print(f"  -> Süre: {duration:.2f}s ({total_frames} kare), {len(words)} kelime, {len(chunks)} altyazı parçası")

    print("[2/4] 1080x1920 30fps 2D çizgi film render ediliyor...")
    af = (
        f"[1:a]loudnorm=I=-15.5:TP=-1.5:LRA=9[v];"
        f"aevalsrc=0.035*sin(2*PI*110*t)+0.022*sin(2*PI*164.81*t)+0.018*sin(2*PI*220*t)+0.012*sin(2*PI*329.63*t)*abs(sin(PI*2*t)):s=44100:d={total_dur:.2f},"
        f"lowpass=f=480,volume=-13dB,afade=t=in:st=0:d=1.0,afade=t=out:st={max(0, total_dur - 1.0):.2f}:d=1.0[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[aout]"
    )
    cmd = [
        "ffmpeg", "-y", "-v", "warning",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-",
        "-i", str(voice_path),
        "-filter_complex", af,
        "-map", "0:v", "-map", "[aout]",
        "-t", f"{total_dur:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(mp4_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    qa_indices = {int(i * (total_frames - 1) / 17) for i in range(18)}
    qa_frames: list[Image.Image] = []

    for fidx in range(total_frames):
        t = fidx / FPS
        cap, age, speaking = lookup_caption(chunks, t)
        frame = render_frame(t, total_dur, cap, age, speaking)
        proc.stdin.write(frame.tobytes())
        if fidx in qa_indices:
            qa_frames.append(frame.copy())
        if fidx % 300 == 0:
            print(f"  -> Kare {fidx}/{total_frames} ({int(100 * fidx / total_frames)}%)")

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exit code {rc}")

    print("[3/4] QA Sheet oluşturuluyor...")
    build_qa_sheet(qa_frames, qa_path)

    print("[4/4] videos.json güncelleniyor...")
    videos = json.loads(VIDEOS_JSON.read_text(encoding="utf-8")) if VIDEOS_JSON.exists() else []
    videos = [v for v in videos if v.get("slug") != SLUG]
    size_mb = round(mp4_path.stat().st_size / (1024 * 1024), 1)
    entry = {
        "slug": SLUG,
        "title": TITLE,
        "status": "Hazır",
        "script": SCRIPT_TEXT,
        "meta": META,
        "words": len(SCRIPT_TEXT.split()),
        "frames": total_frames,
        "voice": f"files/{SLUG}/work/voice.mp3",
        "qa": f"files/{SLUG}/out/qa_sheet.jpg",
        "video": f"files/{SLUG}/out/{FILE_NAME}",
        "fileName": FILE_NAME,
        "sizeMB": size_mb,
        "updated": datetime.now(timezone.utc).isoformat(),
        "width": W,
        "height": H,
        "duration": round(total_dur, 3),
    }
    videos.append(entry)
    VIDEOS_JSON.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ Tamamlandı: {mp4_path} ({size_mb} MB, {total_dur:.1f}s)")


def upload_cover_and_schedule():
    import requests

    api_url = os.getenv("LIKYA_API_URL", "https://likya-crosspost-api-64i7umkgnq-ew.a.run.app").rstrip("/")
    api_key = os.environ["LIKYA_API_KEY"].strip()
    site_base = os.getenv("SITE_BASE_URL", "https://studio.likyastudios.live").rstrip("/")
    headers = {"X-API-Key": api_key}

    cover_path = OUT_DIR / "cover.jpg"
    cover_url = f"{api_url}/api/covers/{SLUG}.png"

    # 1. Upload our bespoke 9:16 cartoon cover to Cloud Run GCS
    if cover_path.exists():
        print(f"[1/3] Özel 9:16 kapak yükleniyor ({cover_path.name})...")
        with cover_path.open("rb") as fh:
            r = requests.post(
                f"{api_url}/api/covers/upload",
                headers=headers,
                data={"key": SLUG},
                files={"file": (cover_path.name, fh, "image/jpeg")},
                timeout=90,
            )
            r.raise_for_status()
            up = r.json()
            cover_url = up.get("image_url") or cover_url
            print(f"  -> Kapak GCS'de hazır: {cover_url}")

    # 2. Wait for GitHub Pages to serve the new MP4
    video_abs_url = f"{site_base}/files/{SLUG}/out/{FILE_NAME}"
    print(f"[2/3] Video yayını bekleniyor: {video_abs_url}")
    for attempt in range(40):
        try:
            hr = requests.head(video_abs_url, timeout=20, allow_redirects=True)
            if hr.status_code == 200:
                print(f"  -> Video canlıda (HTTP 200, deneme #{attempt + 1})")
                break
        except requests.RequestException:
            pass
        time.sleep(15)
    else:
        raise SystemExit("Video GitHub Pages üzerinde 10 dk içinde erişilebilir olmadı.")

    # 3. Schedule for 02.12.2026 Çar · 06:03 TR
    print(f"[3/3] 2 Aralık 2026 (06:03 TR) slotuna planlanıyor...")
    payload = {
        "brand": "akilalmaz",
        "video_id": SLUG,
        "video_url": video_abs_url,
        "title": META["youtube"]["title"],
        "description": META["youtube"]["description"],
        "ig_caption": META["instagram"]["caption"],
        "cover_url": cover_url,
        "scheduled_at": SCHEDULED_AT_UTC,
        "auto_next_slot": False,
        "sync_youtube_now": True,
    }
    sr = requests.post(
        f"{api_url}/api/schedule",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if sr.status_code == 409:
        print("  -> Video zaten planlı (409), atlandı.")
        return
    sr.raise_for_status()
    res = sr.json()
    post = res.get("post") or {}
    print(f"✅ Planlandı: #{post.get('id')} — {post.get('label_tr')} | YT yüklendi: {res.get('yt_uploaded')}")


def render_local_preview():
    """Fast local QA preview (no ElevenLabs/ffmpeg required) to visually inspect all 6 scenes."""
    fake_dur = 50.0
    sample_caps = [
        "Yüz bin kişilik", "dev bir ordu,", "Osmanlı ordusu",
        "iki gün sonra", "Avusturya ordusu,", "birkaç fıçı içki",
        "Tartışma büyüdü,", "Halt! Dur! diye", "Allah! saldırısı sandı!",
        "kendi süvarilerini", "top ateşi açtılar;", "dereye yuvarlandı!",
        "İki gün sonra", "Osmanlı ordusu", "tek kurşun sıkmadan",
        "şehri aldı!", "Ve askeri tarih", "hâlâ şöyle anlatır:",
    ]
    frames = []
    for i in range(18):
        t = i * (fake_dur / 17.5)
        frames.append(render_frame(t, fake_dur, sample_caps[i], 0.15, speaking=(i % 2 == 0)))
    preview_path = Path(tempfile.gettempdir()) / f"{SLUG}_qa_preview.jpg"
    build_qa_sheet(frames, preview_path)
    print(f"Preview QA sheet saved: {preview_path}")


if __name__ == "__main__":
    if "--preview" in sys.argv:
        render_local_preview()
    elif "--publish-schedule" in sys.argv:
        upload_cover_and_schedule()
    else:
        produce_video()
