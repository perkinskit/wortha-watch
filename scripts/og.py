"""Open Graph preview images (1200x630) for link shares. Same spoiler rules as the pages:
matchups and excitement numbers only."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import ROOT

FONTS = ROOT / "assets" / "fonts"
W, H = 1200, 630
BG, SURFACE, LINE = (14, 17, 25), (23, 28, 40), (42, 49, 68)
FG, MUTED, ACCENT = (243, 245, 249), (149, 160, 182), (242, 169, 59)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def chip(img: Image.Image, x: int, y: int, size: int, a: str, a2: str, b: str, b2: str, radius: int = 14) -> None:
    """Two-team color chip: diagonal split with thin alternate-color stripes, rounded corners."""
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.rectangle([0, 0, size, size], fill=_hex(a))
    s = size
    # right/lower triangle in team B, stripes along the diagonal
    d.polygon([(s * 0.62, 0), (s, 0), (s, s), (s * 0.38, s)], fill=_hex(b))
    d.polygon([(s * 0.54, 0), (s * 0.62, 0), (s * 0.38, s), (s * 0.30, s)], fill=_hex(a2))
    d.polygon([(s * 0.62, 0), (s * 0.70, 0), (s * 0.46, s), (s * 0.38, s)], fill=_hex(b2))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.paste(tile, (x, y), mask)


def wordmark(d: ImageDraw.ImageDraw, x: int, y: int, size: int = 44) -> None:
    f = font("BarlowCondensed-ExtraBold", size)
    d.text((x, y), "wortha", font=f, fill=FG)
    w1 = d.textlength("wortha", font=f)
    d.text((x + w1, y), ".", font=f, fill=ACCENT)
    w2 = d.textlength(".", font=f)
    d.text((x + w1 + w2, y), "watch", font=f, fill=FG)


def render_card(path: Path, kicker: str, title: str, rows: list[dict], footer: str) -> None:
    """rows: up to 3 dicts with rank, matchup, index, away/home color dicts."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    wordmark(d, 64, 48)
    fk = font("BarlowCondensed-SemiBold", 30)
    kw = d.textlength(kicker, font=fk)
    d.text((W - 64 - kw, 56), kicker, font=fk, fill=MUTED)
    ft = font("BarlowCondensed-ExtraBold", 64)
    d.text((64, 118), title.upper(), font=ft, fill=FG)
    # table
    top = 214
    row_h = 104
    d.rounded_rectangle([64, top, W - 64, top + row_h * max(1, len(rows)) + 2], radius=16, fill=SURFACE, outline=LINE)
    fr = font("BarlowCondensed-SemiBold", 34)
    fm = font("BarlowCondensed-SemiBold", 46)
    fi = font("BarlowCondensed-ExtraBold", 64)
    for i, r in enumerate(rows[:3]):
        y = top + i * row_h
        if i:
            d.line([(64, y), (W - 64, y)], fill=LINE, width=2)
        d.text((96, y + 32), str(r["rank"]), font=fr, fill=MUTED)
        chip(img, 150, y + 22, 60, r["away"]["color"], r["away"]["alt"], r["home"]["color"], r["home"]["alt"])
        d.text((236, y + 26), r["matchup"], font=fm, fill=FG)
        idx = str(r["index"])
        iw = d.textlength(idx, font=fi)
        d.text((W - 100 - iw, y + 16), idx, font=fi, fill=ACCENT)
        # index bar
        bar_w = int((W - 128 - 32) * r["index"] / 100)
        d.rectangle([96, y + row_h - 8, 96 + bar_w, y + row_h - 3], fill=(120, 86, 32))
    ff = font("Barlow-SemiBold", 26)
    d.text((64, H - 70), footer, font=ff, fill=MUTED)
    fl = font("BarlowCondensed-SemiBold", 26)
    lab = "EXCITEMENT INDEX"
    lw = d.textlength(lab, font=fl)
    d.text((W - 64 - lw, H - 70), lab, font=fl, fill=ACCENT)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)


def render_default(path: Path) -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    wordmark(d, 64, 150, size=120)
    ft = font("BarlowCondensed-SemiBold", 56)
    d.text((66, 300), "WHICH GAMES WERE WORTH WATCHING?", font=ft, fill=FG)
    fb = font("Barlow-Regular", 30)
    d.text((66, 378), "Every NFL, college football, NBA and NHL game ranked by how exciting it was,", font=fb, fill=MUTED)
    d.text((66, 418), "from play-by-play win probability. No scores. No spoilers.", font=fb, fill=MUTED)
    fl = font("BarlowCondensed-SemiBold", 34)
    x = 66
    for name in ("NFL", "CFB", "NBA", "NHL"):
        w = d.textlength(name, font=fl)
        d.rounded_rectangle([x, 500, x + w + 36, 556], radius=12, fill=SURFACE, outline=LINE)
        d.text((x + 18, 508), name, font=fl, fill=FG)
        x += w + 36 + 16
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
