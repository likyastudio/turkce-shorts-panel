"""Kapak birleştirici: Vertex AI arka planı + sabit marka yazı stili (1080x1920).

Model Türkçe harfleri güvenilir yazamadığı için yazı her zaman sunucuda, Pillow ile
basılır. Stil Kadim Anadolu CapCut kapak standardının birebir karşılığıdır:
- Montserrat Black, hepsi BÜYÜK HARF
- 1. satır beyaz #FFFFFF, 2. satır sarı #FFD400 (2. satır >= 1. satır)
- Siyah kontur + %60 siyah gölge
- Marka yazısı "KADİM ANADOLU" Montserrat Bold, altın #F5C83C, harf aralıklı
- Yazı bloğunun ortası ekranın üstten ~%30'u; alt %25 her zaman boş
"""
from __future__ import annotations

import io
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1920
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
FONT_BLACK = os.path.join(FONT_DIR, "MontserratBlack.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "MontserratBold.ttf")

WHITE = (255, 255, 255)
YELLOW = (255, 212, 0)
GOLD = (245, 200, 60)
BLACK = (0, 0, 0)

BRAND_LABELS = {
    "kadimanadolu": "KADİM ANADOLU",
    "akilalmaz": "AKILALMAZ",
    "likyastudios": "LIKYA STUDIOS",
    "foodballstv": "FOODBALLS TV",
}

# Arka plan üretilirken prompta eklenen koruma: yazıyı biz basıyoruz, model yazmasın.
BACKGROUND_GUARD = (
    " Absolutely no text, letters, numbers, captions, logos or watermarks anywhere in the image."
    " Historically accurate for the period: no modern national flags, no crescent-and-star flags, no modern"
    " uniforms or firearms unless the era had them; banners must be plain period-appropriate cloth or tamgas."
    " Keep the upper third of the frame slightly calmer and darker (sky, smoke or dust) so a bold title can sit there,"
    " and place the main action and faces in the middle of the frame."
)


def tr_upper(s: str) -> str:
    """Türkçe doğru büyük harf: i -> İ, ı -> I."""
    return (s or "").replace("i", "İ").replace("ı", "I").upper().strip()


def _trim_letterbox(img: Image.Image) -> Image.Image:
    """Modelin bazen çizdiği siyah sinema bantlarını (üst/alt/yan) kırpar."""
    gray = img.convert("L")
    w, h = gray.size

    def dark_row(y):
        row = gray.crop((0, y, w, y + 1)).getextrema()
        return row[1] < 28

    def dark_col(x):
        col = gray.crop((x, 0, x + 1, h)).getextrema()
        return col[1] < 28

    top = 0
    while top < h // 4 and dark_row(top):
        top += 1
    bottom = h
    while bottom > h * 3 // 4 and dark_row(bottom - 1):
        bottom -= 1
    left = 0
    while left < w // 4 and dark_col(left):
        left += 1
    right = w
    while right > w * 3 // 4 and dark_col(right - 1):
        right -= 1
    if (top, bottom, left, right) == (0, h, 0, w):
        return img
    pad = 2  # bant kenarındaki yumuşak geçişi de at
    return img.crop((left + (pad if left else 0), top + (pad if top else 0),
                     right - (pad if right < w else 0), bottom - (pad if bottom < h else 0)))


def _fit_cover(img: Image.Image) -> Image.Image:
    """Görseli 1080x1920 tuvale 'cover' kırpma ile oturtur, yumuşak keskinleştirir."""
    img = _trim_letterbox(img.convert("RGB"))
    scale = max(W / img.width, H / img.height)
    nw, nh = max(W, round(img.width * scale)), max(H, round(img.height * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    img = img.crop((left, top, left + W, top + H))
    if scale > 1.05:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    return img


def _grade(img: Image.Image) -> Image.Image:
    """Parlaklık -10 ve vinyet +25 (CapCut talimatının karşılığı) + üstte okunurluk gölgesi."""
    img = ImageEnhance.Brightness(img).enhance(0.92)
    img = ImageEnhance.Contrast(img).enhance(1.06)

    # Vinyet: kenarlara doğru koyulaşan radyal maske
    small = Image.new("L", (W // 8, H // 8), 0)
    d = ImageDraw.Draw(small)
    cx, cy = small.width / 2, small.height / 2
    for i in range(40):
        t = i / 40
        rx, ry = cx * (1.45 - t * 0.75), cy * (1.25 - t * 0.6)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=int(255 * t))
    mask = small.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
    dark = Image.new("RGB", (W, H), BLACK)
    vign = Image.composite(img, Image.blend(img, dark, 0.45), mask)

    # Üst bölgede yazının arkasına hafif koyu gradyan
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        a = 0
        if y < 1050:
            a = int(120 * (1 - y / 1050) ** 1.4)
        grad.putpixel((0, y), a)
    grad = grad.resize((W, H))
    return Image.composite(dark, vign, grad)


def _font_for_width(text: str, path: str, max_w: int, max_cap: int, min_size: int = 40) -> ImageFont.FreeTypeFont:
    """Satırı max_w genişliğine yayan, büyük harf yüksekliği max_cap'i aşmayan boyut."""
    size = 400
    while size > min_size:
        f = ImageFont.truetype(path, size)
        l, t, r, b = f.getbbox(text)
        cap = f.getbbox("H")[3] - f.getbbox("H")[1]
        if r - l <= max_w and cap <= max_cap:
            return f
        size -= 4
    return ImageFont.truetype(path, min_size)


def _draw_line(base: Image.Image, text: str, font: ImageFont.FreeTypeFont, cy: int, fill, stroke: int,
               spacing: int = 0) -> tuple[int, int]:
    """Ortalanmış satırı kontur + gölgeyle çizer. (üst, alt) piksel sınırlarını döner."""
    def measure(txt):
        if not spacing:
            l, t, r, b = font.getbbox(txt, stroke_width=stroke)
            return r - l, t, b
        w = sum(font.getlength(c) for c in txt) + spacing * (len(txt) - 1) + 2 * stroke
        _, t, _, b = font.getbbox(txt, stroke_width=stroke)
        return int(w), t, b

    w, t, b = measure(text)
    x0 = (W - w) // 2
    y0 = cy - (t + b) // 2

    def paint(draw, dx, dy, color, stroke_color):
        if not spacing:
            draw.text((x0 + dx - font.getbbox(text, stroke_width=stroke)[0], y0 + dy), text, font=font,
                      fill=color, stroke_width=stroke, stroke_fill=stroke_color)
            return
        x = x0 + dx + stroke
        for c in text:
            draw.text((x, y0 + dy), c, font=font, fill=color, stroke_width=stroke, stroke_fill=stroke_color)
            x += font.getlength(c) + spacing

    # Gölge: siyah %60, mesafe ~4, bulanıklık ~6
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    paint(ImageDraw.Draw(shadow), 5, 7, (0, 0, 0, 153), (0, 0, 0, 153))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    base.alpha_composite(shadow)
    paint(ImageDraw.Draw(base), 0, 0, fill, BLACK)
    return y0 + t, y0 + b


def compose_cover(background: bytes, line1: str = "", line2: str = "", brand: str = "kadimanadolu",
                  fmt: str = "PNG") -> bytes:
    """Arka plan + iki satır başlık + marka yazısı -> 1080x1920 kapak baytları."""
    img = _grade(_fit_cover(Image.open(io.BytesIO(background)))).convert("RGBA")
    l1, l2 = tr_upper(line1), tr_upper(line2)
    if not l1 and l2:
        l1, l2 = l2, ""
    margin_w = W - 120  # iki yanda ~60 px

    if l1:
        f1 = _font_for_width(l1, FONT_BLACK, margin_w, 110)
        f2 = _font_for_width(l2, FONT_BLACK, margin_w, 140) if l2 else None
        if f2 and f2.size < f1.size:  # 2. satır 1. satırdan küçük olmasın
            f1 = ImageFont.truetype(FONT_BLACK, f2.size)
        cap1 = f1.getbbox("H")[3] - f1.getbbox("H")[1]
        cap2 = (f2.getbbox("H")[3] - f2.getbbox("H")[1]) if f2 else 0
        gap = int(max(cap1, cap2) * 0.55) if f2 else 0
        block = cap1 + gap + cap2
        top = int(H * 0.30) - block // 2
        stroke1 = max(6, f1.size // 14)
        t1, _ = _draw_line(img, l1, f1, top + cap1 // 2, WHITE, stroke1)
        if f2:
            _draw_line(img, l2, f2, top + cap1 + gap + cap2 // 2, YELLOW, max(7, f2.size // 13))
        label = BRAND_LABELS.get(brand, "")
        if label:
            fb = ImageFont.truetype(FONT_BOLD, 40)
            cap_b = fb.getbbox("H")[3] - fb.getbbox("H")[1]
            _draw_line(img, label, fb, t1 - 60 - cap_b // 2, GOLD, 3, spacing=10)

    out = io.BytesIO()
    rgb = img.convert("RGB")
    if fmt.upper() == "JPEG":
        rgb.save(out, format="JPEG", quality=92, optimize=True)
    else:
        rgb.save(out, format="PNG", optimize=True)
    return out.getvalue()
