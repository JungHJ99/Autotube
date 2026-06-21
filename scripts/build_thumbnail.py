#!/usr/bin/env python3
"""Build a 1280x720 YouTube thumbnail for an autotube run.

Design philosophy (post 2026-05-21 competitor analysis): real K-culture
commentary thumbnails always carry (a) a real photo background, (b) a 2-line
high-contrast headline with accent words, (c) a small corner taegukgi (not a
giant flag), (d) a top-left authority label, and (e) a wordmark badge. This
module renders all of those in PIL.

Two modes:

1. **Default mode** — reads `youtube.thumbnail_copy` / `youtube.thumbnail_subcopy`
   from segments.json. Background = first stock clip frame. Auto-builds 2 lines
   from the copy if needed. Backward-compatible with all prior runs.

2. **Spec mode** (`--spec path/to/thumbnail_spec.json`) — full override from
   the `/youtube thumbnail` brief output (Stage 11 of the gukppong-pipeline).
   See `thumbnail_spec.schema.md` (next to this script) for the full schema.

Usage:
    python3 scripts/build_thumbnail.py \\
        --segments output/<run>/segments.json \\
        --out output/<run>/thumbnail.png \\
        [--spec output/<run>/thumbnail_spec.json] \\
        [--bg path/to/image.png] [--bg-darken 0.45]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


W, H = 1280, 720

FONT_BLACK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

KR_RED = (205, 46, 58)
KR_BLUE = (0, 71, 159)
JP_RED = (188, 0, 45)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (255, 220, 0)
LABEL_RED = (220, 38, 38)


# ============================================================================
# Color helpers
# ============================================================================

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    s = hex_str.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


# ============================================================================
# Flags
# ============================================================================

def draw_korean_flag(out_w: int = 96, out_h: int = 64) -> Image.Image:
    """Procedural taegukgi. Default is now corner-icon sized."""
    s = 4
    W_, H_ = out_w * s, out_h * s
    img = Image.new("RGBA", (W_, H_), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)

    R = H_ // 4
    cx, cy = W_ // 2, H_ // 2

    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=KR_RED + (255,))
    d.pieslice([cx - R, cy - R, cx + R, cy + R], 0, 180, fill=KR_BLUE + (255,))
    d.ellipse([cx - R, cy - R // 2, cx, cy + R // 2], fill=KR_RED + (255,))
    d.ellipse([cx, cy - R // 2, cx + R, cy + R // 2], fill=KR_BLUE + (255,))

    bar_l = int(H_ * 0.20)
    bar_t = int(H_ * 0.028)
    gap = int(bar_t * 1.6)
    half_gap = int(bar_l * 0.13)
    seg_l = (bar_l - 2 * half_gap) // 2

    def draw_trigram(center_x: int, center_y: int, pattern: list[str]) -> None:
        total_h = 3 * bar_t + 2 * gap
        top = center_y - total_h // 2
        for i, kind in enumerate(pattern):
            y0 = top + i * (bar_t + gap)
            y1 = y0 + bar_t
            if kind == "solid":
                d.rectangle(
                    [center_x - bar_l // 2, y0, center_x + bar_l // 2, y1],
                    fill=BLACK + (255,),
                )
            else:
                d.rectangle(
                    [center_x - bar_l // 2, y0,
                     center_x - bar_l // 2 + seg_l, y1],
                    fill=BLACK + (255,),
                )
                d.rectangle(
                    [center_x + bar_l // 2 - seg_l, y0,
                     center_x + bar_l // 2, y1],
                    fill=BLACK + (255,),
                )

    margin_x = int(W_ * 0.12)
    margin_y = int(H_ * 0.20)
    draw_trigram(margin_x, margin_y, ["solid", "solid", "solid"])
    draw_trigram(margin_x, H_ - margin_y, ["solid", "broken", "solid"])
    draw_trigram(W_ - margin_x, margin_y, ["broken", "solid", "broken"])
    draw_trigram(W_ - margin_x, H_ - margin_y, ["broken", "broken", "broken"])

    return img.resize((out_w, out_h), Image.LANCZOS)


def draw_japan_flag(out_w: int = 96, out_h: int = 64) -> Image.Image:
    """Procedural 일장기."""
    img = Image.new("RGBA", (out_w, out_h), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    r = int(out_h * 0.32)
    cx, cy = out_w // 2, out_h // 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=JP_RED + (255,))
    return img


def draw_czech_flag(out_w: int = 96, out_h: int = 64) -> Image.Image:
    """Procedural 체코기 — white top, red bottom, blue triangle from left
    reaching the horizontal mid-point."""
    W_, H_ = out_w * 4, out_h * 4
    img = Image.new("RGBA", (W_, H_), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    cz_red = (215, 20, 26)
    cz_blue = (17, 69, 126)
    # red lower half
    d.rectangle([0, H_ // 2, W_, H_], fill=cz_red + (255,))
    # blue triangle from left edge, apex at center
    d.polygon([(0, 0), (W_ // 2, H_ // 2), (0, H_)], fill=cz_blue + (255,))
    return img.resize((out_w, out_h), Image.LANCZOS)


def draw_mexico_flag(out_w: int = 96, out_h: int = 64) -> Image.Image:
    """Procedural 멕시코 국기 — 좌 녹색, 중앙 흰색, 우 빨강. 가운데 작은 갈색 동그라미
    (독수리 emblem 자리). 썸네일 코너 사이즈에서는 detail 살리지 않고 stylized."""
    W_, H_ = out_w * 4, out_h * 4
    img = Image.new("RGBA", (W_, H_), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    mx_green = (0, 104, 71)
    mx_red = (206, 17, 38)
    mx_brown = (139, 87, 42)
    # 좌측 녹색 1/3
    d.rectangle([0, 0, W_ // 3, H_], fill=mx_green + (255,))
    # 우측 빨강 1/3
    d.rectangle([2 * W_ // 3, 0, W_, H_], fill=mx_red + (255,))
    # 가운데 emblem (간이) — 갈색 동그라미
    cx, cy = W_ // 2, H_ // 2
    r = H_ // 6
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=mx_brown + (255,))
    return img.resize((out_w, out_h), Image.LANCZOS)


_TWEMOJI_DIR = Path(__file__).parent / "twemoji_flags"


def _twemoji_flag(country: str, w: int, h: int) -> Image.Image | None:
    """Load Twemoji PNG for the given country (KR/MX/CZ/JP/US/...) if available.

    Twemoji PNG is square 72x72 RGBA; we resize to (w, h) preserving aspect via pad.
    Returns None if the country code is not cached on disk.
    """
    code_map = {
        "KOREA": "KR", "한국": "KR", "KR": "KR",
        "JAPAN": "JP", "일본": "JP", "JP": "JP",
        "CZECH": "CZ", "CZECHIA": "CZ", "체코": "CZ", "CZ": "CZ",
        "MEXICO": "MX", "멕시코": "MX", "MX": "MX",
        "US": "US", "USA": "US", "미국": "US",
        "BR": "BR", "BRAZIL": "BR", "브라질": "BR",
        "DE": "DE", "GERMANY": "DE", "독일": "DE",
        "ES": "ES", "SPAIN": "ES", "스페인": "ES",
        "FR": "FR", "FRANCE": "FR", "프랑스": "FR",
        "GB": "GB", "UK": "GB", "ENGLAND": "GB", "영국": "GB",
    }
    code = code_map.get(country.upper())
    if not code:
        return None
    path = _TWEMOJI_DIR / f"{code}.png"
    if not path.exists():
        return None
    img = Image.open(path).convert("RGBA")
    # Fit (w, h) preserving aspect ratio of source (square) — pad if needed.
    src_w, src_h = img.size
    scale = min(w / src_w, h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    if (new_w, new_h) == (w, h):
        return img
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, ((w - new_w) // 2, (h - new_h) // 2), img)
    return out


def get_flag(country: str, w: int = 96, h: int = 64) -> Image.Image:
    # Prefer Twemoji PNG (real flag emoji) over procedural drawings.
    emoji_img = _twemoji_flag(country, w, h)
    if emoji_img is not None:
        return emoji_img
    if country.upper() in ("KR", "KOREA", "한국"):
        return draw_korean_flag(w, h)
    if country.upper() in ("JP", "JAPAN", "일본"):
        return draw_japan_flag(w, h)
    if country.upper() in ("CZ", "CZECH", "CZECHIA", "체코"):
        return draw_czech_flag(w, h)
    if country.upper() in ("MX", "MEXICO", "멕시코"):
        return draw_mexico_flag(w, h)
    raise ValueError(f"unsupported flag country: {country}")


def draw_corner_flags(bg, codes, position="bottom-right", fh=78, y_override=None):
    """Draw a row of flags (e.g. ['MX','KR']) with white borders. `position` picks
    a corner; `y_override` (px) lets you place them anywhere vertically — e.g. just
    below the sandwich top band. Used via spec `corner_flags`."""
    if not codes:
        return
    fw = int(fh * 1.5)
    flags = [get_flag(c, fw, fh).convert("RGBA") for c in codes]
    gap, m = 14, 30
    total_w = sum(f.width for f in flags) + gap * (len(flags) - 1)
    x = (bg.width - m - total_w) if "right" in position else m
    if y_override is not None:
        y = int(y_override)
    else:
        y = (bg.height - m - fh) if "bottom" in position else m
    d = ImageDraw.Draw(bg)
    for f in flags:
        d.rectangle([x - 3, y - 3, x + f.width + 3, y + fh + 3], outline=WHITE, width=3)
        bg.paste(f, (x, y), f)
        x += f.width + gap


# ============================================================================
# Stock clip → bg frame
# ============================================================================

import shutil as _shutil
_FFMPEG = _shutil.which("ffmpeg") or "/home/hjhj/.local/bin/ffmpeg"


def extract_frame(clip_path: Path, time_sec: float, out: Path,
                  container: str | None = None) -> bool:
    # Runs on the host (fish-speech docker no longer used). `container` kept for
    # signature compatibility but ignored.
    try:
        subprocess.run(
            [_FFMPEG, "-y",
             "-i", str(clip_path.resolve()),
             "-ss", str(time_sec), "-frames:v", "1",
             str(out.resolve())],
            check=True, capture_output=True,
        )
        return out.exists()
    except subprocess.CalledProcessError:
        return False


def pick_bg_from_run(segments_path: Path, container: str,
                     stock_path: str | None = None,
                     time_sec: float = 2.0,
                     out_name: str = ".thumbnail_bg.png") -> Path | None:
    run_dir = segments_path.parent
    if stock_path:
        clip = (run_dir / stock_path).resolve()
        if not clip.exists():
            return None
        out = run_dir / out_name
        if extract_frame(clip, time_sec, out, container):
            return out
        return None
    doc = json.loads(segments_path.read_text(encoding="utf-8"))
    for seg in doc["segments"]:
        sp = seg.get("stock_path")
        if not sp:
            continue
        clip = (run_dir / sp).resolve()
        if not clip.exists():
            continue
        out = run_dir / out_name
        if extract_frame(clip, time_sec, out, container):
            return out
    return None


# ============================================================================
# Backgrounds
# ============================================================================

def gradient_bg_legacy() -> Image.Image:
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        r = int(140 * (1 - t) + 8 * t)
        g = int(10 * (1 - t))
        b = int(20 * (1 - t))
        d.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def gradient_bg_from_hex(start_hex: str, end_hex: str,
                         direction: str = "horizontal") -> Image.Image:
    r1, g1, b1 = hex_to_rgb(start_hex)
    r2, g2, b2 = hex_to_rgb(end_hex)
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    if direction == "vertical":
        for y in range(H):
            t = y / (H - 1)
            r = int(r1 * (1 - t) + r2 * t)
            g = int(g1 * (1 - t) + g2 * t)
            b = int(b1 * (1 - t) + b2 * t)
            d.line([(0, y), (W, y)], fill=(r, g, b))
    else:
        for x in range(W):
            t = x / (W - 1)
            r = int(r1 * (1 - t) + r2 * t)
            g = int(g1 * (1 - t) + g2 * t)
            b = int(b1 * (1 - t) + b2 * t)
            d.line([(x, 0), (x, H)], fill=(r, g, b))
    return img


def solid_bg_from_hex(solid_hex: str) -> Image.Image:
    return Image.new("RGB", (W, H), hex_to_rgb(solid_hex))


def crop_fill(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_ratio = img.width / img.height
    tgt_ratio = target_w / target_h
    if src_ratio > tgt_ratio:
        new_h = target_h
        new_w = int(target_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    crop_x = (new_w - target_w) // 2
    crop_y = (new_h - target_h) // 2
    return img.crop((crop_x, crop_y, crop_x + target_w, crop_y + target_h))


def saturation_boost(img: Image.Image, factor: float = 1.15) -> Image.Image:
    return ImageEnhance.Color(img).enhance(factor)


def darken(img: Image.Image, amount: float) -> Image.Image:
    if amount <= 0:
        return img
    return ImageEnhance.Brightness(img).enhance(1 - amount)


def bottom_band_overlay(bg: Image.Image, alpha_max: int = 220,
                        start_frac: float = 0.40) -> Image.Image:
    """Dark gradient on the bottom (alpha 0 at start_frac → alpha_max at bottom)."""
    bg = bg.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    grad_start = int(H * start_frac)
    for y in range(grad_start, H):
        t = (y - grad_start) / max(1, H - grad_start)
        a = int(t * alpha_max)
        od.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    return Image.alpha_composite(bg, overlay)


def split_bg(left_img: Image.Image, right_img: Image.Image,
             divider_color: tuple = WHITE,
             divider_width: int = 10,
             slant: int = 60) -> Image.Image:
    """Two photos side by side with a slanted divider stripe."""
    half_w = W // 2
    left = crop_fill(left_img, half_w + slant, H)
    right = crop_fill(right_img, half_w + slant, H)
    canvas = Image.new("RGB", (W, H), BLACK)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (W - right.width, 0))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    poly = [
        (half_w - slant // 2 - divider_width // 2, 0),
        (half_w + slant // 2 - divider_width // 2, H),
        (half_w + slant // 2 + divider_width // 2, H),
        (half_w - slant // 2 + divider_width // 2, 0),
    ]
    od.polygon(poly, fill=divider_color + (255,))
    canvas = canvas.convert("RGBA")
    canvas = Image.alpha_composite(canvas, overlay)
    return canvas.convert("RGB")


# ============================================================================
# Text
# ============================================================================

def fit_font(text: str, font_path: str, max_w: int, max_h: int,
             start_size: int = 200, min_size: int = 36) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > min_size:
        font = ImageFont.truetype(font_path, size)
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            return font
        size -= 4
    return ImageFont.truetype(font_path, min_size)


def fit_font_multi(texts: list[str], font_path: str, max_w: int, max_h: int,
                   start_size: int = 200, min_size: int = 48) -> ImageFont.FreeTypeFont:
    """Find a font size where ALL strings fit in max_w x max_h."""
    size = start_size
    while size > min_size:
        font = ImageFont.truetype(font_path, size)
        ok = True
        for t in texts:
            bbox = font.getbbox(t)
            if (bbox[2] - bbox[0]) > max_w or (bbox[3] - bbox[1]) > max_h:
                ok = False
                break
        if ok:
            return font
        size -= 4
    return ImageFont.truetype(font_path, min_size)


def auto_split_lines(text: str) -> list[str]:
    """Split a one-liner into 2 balanced lines on a sensible boundary."""
    text = text.strip()
    if not text:
        return []
    if "\n" in text:
        parts = [t.strip() for t in text.split("\n") if t.strip()]
        return parts[:2] if len(parts) >= 2 else parts
    parts = text.split()
    if len(parts) == 1:
        return [text]
    target = len(text) / 2
    best_idx, best_diff = 1, 10**9
    cum = 0
    for i, p in enumerate(parts[:-1], start=1):
        cum += len(p) + 1
        diff = abs(cum - target)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    line1 = " ".join(parts[:best_idx])
    line2 = " ".join(parts[best_idx:])
    return [line1, line2]


def draw_text_with_accents(d: ImageDraw.ImageDraw, x: int, y: int,
                           text: str, font: ImageFont.FreeTypeFont,
                           accent_words: list[str], accent_fill: tuple,
                           base_fill: tuple,
                           stroke_width: int, stroke_fill: tuple) -> None:
    """Draw a line, recoloring tokens that match any accent_word.

    Matching is case-insensitive substring containment per whitespace token —
    e.g. accent_word "한국" hits token "한국行".
    """
    if not text:
        return
    pat = re.compile(r"(\s+)")
    tokens = pat.split(text)
    cursor_x = x
    for tok in tokens:
        if not tok:
            continue
        if tok.isspace():
            bbox = font.getbbox(tok)
            cursor_x += bbox[2] - bbox[0]
            continue
        fill = base_fill
        for w in accent_words or []:
            if w and w in tok:
                fill = accent_fill
                break
        d.text((cursor_x, y), tok, font=font, fill=fill,
               stroke_width=stroke_width, stroke_fill=stroke_fill)
        bbox = font.getbbox(tok)
        cursor_x += bbox[2] - bbox[0]


# ============================================================================
# Label badge (top-left)
# ============================================================================

def draw_label_badge(bg: Image.Image, text: str,
                     fill: tuple = LABEL_RED,
                     text_color: tuple = WHITE,
                     anchor: tuple[int, int] = (24, 24),
                     font_size: int = 36,
                     flag_country: str | None = None
                     ) -> tuple[int, int, int, int]:
    """Rounded rectangle with white text. Optional small flag on the left
    inside the badge (use for marking the source country of an authoring
    scholar or a citing publication). Returns (x0,y0,x1,y1) of the box.
    """
    font = ImageFont.truetype(FONT_BLACK, font_size)
    bb = font.getbbox(text)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    pad_x = 18
    pad_y = 10

    flag_img = None
    flag_w = flag_h = 0
    flag_gap = 0
    if flag_country:
        flag_h = max(28, int(th * 1.15))
        flag_w = int(flag_h * 1.5)
        flag_img = get_flag(flag_country, flag_w, flag_h)
        flag_gap = 12

    box_w = (flag_w + flag_gap) + tw + 2 * pad_x
    box_h = max(th, flag_h) + 2 * pad_y
    x0, y0 = anchor
    x1, y1 = x0 + box_w, y0 + box_h

    shadow_canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_canvas)
    sd.rounded_rectangle([x0 + 3, y0 + 4, x1 + 3, y1 + 4],
                         radius=10, fill=(0, 0, 0, 130))
    shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(3))
    bg.alpha_composite(shadow_canvas)

    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=fill + (255,))

    cursor_x = x0 + pad_x
    if flag_img is not None:
        flag_y = y0 + (box_h - flag_h) // 2
        bg.paste(flag_img, (cursor_x, flag_y), flag_img)
        bd = ImageDraw.Draw(bg)
        bd.rectangle([cursor_x - 1, flag_y - 1,
                      cursor_x + flag_w, flag_y + flag_h],
                     outline=WHITE, width=2)
        cursor_x += flag_w + flag_gap

    text_x = cursor_x - bb[0]
    text_y = y0 + (box_h - th) // 2 - bb[1]
    d.text((text_x, text_y), text, font=font, fill=text_color)
    return (x0, y0, x1, y1)


# ============================================================================
# Wordmark badge
# ============================================================================

def draw_wordmark_badge(bg: Image.Image, text: str = "파이널K",
                        position: str = "bottom-right",
                        font_size: int = 38) -> None:
    """Compact badge: dark bg + yellow text + thin white border."""
    font = ImageFont.truetype(FONT_BLACK, font_size)
    bb = font.getbbox(text)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    pad_x = 18
    pad_y = 10
    box_w = tw + 2 * pad_x
    box_h = th + 2 * pad_y
    if position == "top-right":
        x0 = W - box_w - 24
        y0 = 24
    elif position == "bottom-left":
        x0 = 24
        y0 = H - box_h - 24
    elif position == "top-left":
        x0 = 24
        y0 = 24
    else:  # bottom-right
        x0 = W - box_w - 24
        y0 = H - box_h - 24
    x1, y1 = x0 + box_w, y0 + box_h

    shadow_canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_canvas)
    sd.rounded_rectangle([x0 + 3, y0 + 4, x1 + 3, y1 + 4],
                         radius=12, fill=(0, 0, 0, 140))
    shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(4))
    bg.alpha_composite(shadow_canvas)

    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([x0, y0, x1, y1], radius=12,
                        fill=(20, 20, 24, 255), outline=WHITE + (255,), width=3)
    d.text((x0 + pad_x - bb[0], y0 + pad_y - bb[1]), text,
           font=font, fill=YELLOW)


# ============================================================================
# Face cutout (from stock clip frame)
# ============================================================================

def apply_rounded_mask(img: Image.Image, radius: int = 40,
                       border_w: int = 8,
                       border_color: tuple = WHITE,
                       feather: int = 4) -> Image.Image:
    """Round the corners, add a soft border."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, w - 1, h - 1], radius=radius, fill=255)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img.convert("RGB"), (0, 0), mask)
    if border_w > 0:
        d = ImageDraw.Draw(out)
        d.rounded_rectangle(
            [border_w // 2, border_w // 2, w - 1 - border_w // 2, h - 1 - border_w // 2],
            radius=radius, outline=border_color + (255,), width=border_w)
    return out


def paste_face_cutout(bg: Image.Image, face_img: Image.Image,
                      size: int, position: str = "right",
                      bottom_margin: int = 24) -> None:
    """Crop to square, round corners, paste."""
    fw, fh = face_img.size
    side = min(fw, fh)
    cx, cy = fw // 2, fh // 2
    sq = face_img.crop((cx - side // 2, cy - side // 2,
                         cx + side // 2, cy + side // 2))
    sq = sq.resize((size, size), Image.LANCZOS)
    rounded = apply_rounded_mask(sq, radius=int(size * 0.12), border_w=6)
    if position == "right":
        x = W - size - 36
    elif position == "left":
        x = 36
    else:
        x = (W - size) // 2
    y = H - size - bottom_margin
    bg.alpha_composite(rounded, (x, y))


# ============================================================================
# Punctuation accent
# ============================================================================

def draw_punctuation_accent(bg: Image.Image, text: str,
                            anchor: tuple[int, int],
                            font_size: int = 200,
                            color: tuple = YELLOW,
                            stroke_w: int = 14,
                            rotate: int = -8) -> None:
    font = ImageFont.truetype(FONT_BLACK, font_size)
    bb = font.getbbox(text)
    pad = max(stroke_w * 3, 30)
    tw = bb[2] - bb[0] + 2 * pad
    th = bb[3] - bb[1] + 2 * pad
    layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((pad - bb[0], pad - bb[1]), text, font=font, fill=color + (255,),
           stroke_width=stroke_w, stroke_fill=BLACK + (255,))
    if rotate:
        layer = layer.rotate(rotate, resample=Image.BICUBIC, expand=True)
    bg.alpha_composite(layer, anchor)


# ============================================================================
# Text band (dark backdrop behind a text line)
# ============================================================================

def draw_text_band(bg: Image.Image, bbox: tuple[int, int, int, int],
                   fill_rgb: tuple = BLACK, alpha: int = 170,
                   pad_x: int = 28, pad_y: int = 8, radius: int = 8) -> None:
    x0, y0, x1, y1 = bbox
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(
        [x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y],
        radius=radius, fill=fill_rgb + (alpha,))
    bg.alpha_composite(layer)


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--segments", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--spec", type=Path, default=None,
                   help="thumbnail_spec.json")
    p.add_argument("--bg", type=Path, default=None)
    p.add_argument("--bg-darken", type=float, default=None)
    p.add_argument("--docker-container", default="autotube-fish-speech")
    args = p.parse_args()

    run_dir = args.segments.parent
    doc = json.loads(args.segments.read_text(encoding="utf-8"))
    yt = doc.get("youtube", {})

    spec: dict = {}
    if args.spec:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        print(f"  spec: {args.spec}")

    # --- Layout mode -------------------------------------------------------
    # "sandwich" — 상단 텍스트 2줄 + 중간 imagery + 하단 텍스트 2줄 (바이스톰/쓸모왕)
    # "face-overlay" — 가운데 큰 헤드라인 + 우측 face cutout (기본, autotube v2-v4)
    layout = spec.get("layout", "face-overlay")

    # --- Text resolution ---------------------------------------------------
    if spec.get("text_lines"):
        text_lines = [s for s in spec["text_lines"] if s]
    elif "text" in spec:
        text_lines = auto_split_lines(spec.get("text", ""))
    else:
        raw = yt.get("thumbnail_copy") or yt.get("title") or "한국이 1위"
        sub = yt.get("thumbnail_subcopy") or ""
        text_lines = [raw, sub] if sub else auto_split_lines(raw)
    text_lines = [t for t in text_lines if t]

    # sandwich 모드는 별도의 top/bottom 라인을 받는다.
    top_lines = [s for s in (spec.get("top_text_lines") or []) if s]
    bottom_lines = [s for s in (spec.get("bottom_text_lines") or []) if s]

    accent_words = spec.get("accent_words", [])
    accent_fill = hex_to_rgb(spec.get("accent_color_hex", "#FFDC00"))
    base_fill = hex_to_rgb(spec.get("base_text_color_hex", "#FFFFFF"))
    stroke_fill = hex_to_rgb(spec.get("stroke_color_hex", "#000000"))
    stroke_w = int(spec.get("stroke_width", 12))

    text_band_conf = spec.get("text_band", True)
    if text_band_conf is True:
        text_band_conf = {"alpha": 170, "pad_x": 28, "pad_y": 8}
    elif text_band_conf is False:
        text_band_conf = None

    # sandwich 레이아웃은 코너 아이콘이 텍스트 띠와 충돌하므로 기본 false.
    _flag_default = layout != "sandwich"
    _wm_default = layout != "sandwich"
    show_flag = spec.get("show_flag", _flag_default)
    show_wordmark = spec.get("show_wordmark", _wm_default)
    wordmark_badge = spec.get("wordmark_badge", True)

    label_conf = spec.get("label")  # str or dict or None

    accent_punct_conf = spec.get("accent_punct")  # str or dict or None

    face_conf = spec.get("face")  # {clip|frame, size, position, t}

    print(f"thumbnail: lines={text_lines}, accents={accent_words}")

    # --- Background --------------------------------------------------------
    bg_conf = spec.get("background") or {}
    bg_type = bg_conf.get("type", "stock")
    bg_darken_v = (args.bg_darken if args.bg_darken is not None
                   else float(bg_conf.get("darken", 0.40)))

    if args.bg:
        bg = Image.open(args.bg).convert("RGB")
        print(f"  bg: {args.bg}")
    elif bg_type == "gradient":
        bg = gradient_bg_from_hex(
            bg_conf["start_hex"], bg_conf["end_hex"],
            bg_conf.get("direction", "horizontal"),
        )
        print(f"  bg: spec gradient {bg_conf['start_hex']} → {bg_conf['end_hex']}")
    elif bg_type == "solid":
        bg = solid_bg_from_hex(bg_conf["solid_hex"])
        print(f"  bg: spec solid {bg_conf['solid_hex']}")
    elif bg_type == "split":
        left_path = bg_conf.get("left_path")
        right_path = bg_conf.get("right_path")
        left_t = float(bg_conf.get("left_t", 2.0))
        right_t = float(bg_conf.get("right_t", 2.0))
        left = pick_bg_from_run(args.segments, args.docker_container,
                                stock_path=left_path, time_sec=left_t,
                                out_name=".thumbnail_bg_left.png")
        right = pick_bg_from_run(args.segments, args.docker_container,
                                 stock_path=right_path, time_sec=right_t,
                                 out_name=".thumbnail_bg_right.png")
        if not (left and right):
            print(f"  bg: split failed (left={left}, right={right}), fallback")
            bg = gradient_bg_legacy()
        else:
            li = Image.open(left).convert("RGB")
            ri = Image.open(right).convert("RGB")
            bg = split_bg(li, ri,
                          divider_color=WHITE,
                          divider_width=bg_conf.get("divider_width", 12),
                          slant=bg_conf.get("slant", 60))
            print(f"  bg: split — {left_path} | {right_path}")
    else:  # stock
        sp = bg_conf.get("stock_path")
        t_sec = float(bg_conf.get("t", 2.0))
        if sp:
            bg_path = pick_bg_from_run(args.segments, args.docker_container,
                                       stock_path=sp, time_sec=t_sec)
        else:
            bg_path = pick_bg_from_run(args.segments, args.docker_container)
        if bg_path:
            bg = Image.open(bg_path).convert("RGB")
            print(f"  bg: stock frame ({sp or 'auto'})")
        else:
            bg = gradient_bg_legacy()
            print(f"  bg: gradient fallback")

    bg = crop_fill(bg, W, H)
    bg = saturation_boost(bg, 1.12)
    bg = darken(bg, bg_darken_v)
    bg = bottom_band_overlay(bg, alpha_max=int(bg_conf.get("bottom_band_alpha", 220)),
                             start_frac=float(bg_conf.get("bottom_band_start", 0.42)))

    # Optional split labels — KR/JP flag watermarks behind each half
    if bg_type == "split":
        left_flag_c = bg_conf.get("left_flag")
        right_flag_c = bg_conf.get("right_flag")
        if left_flag_c:
            fl = get_flag(left_flag_c, 180, 120).convert("RGBA")
            fl.putalpha(Image.eval(fl.split()[3], lambda a: int(a * 0.55)))
            bg.alpha_composite(fl, (W // 4 - fl.width // 2, 36))
        if right_flag_c:
            fr = get_flag(right_flag_c, 180, 120).convert("RGBA")
            fr.putalpha(Image.eval(fr.split()[3], lambda a: int(a * 0.55)))
            bg.alpha_composite(fr, (3 * W // 4 - fr.width // 2, 36))
        if bg_conf.get("show_vs", True):
            draw_punctuation_accent(bg, "VS", anchor=(W // 2 - 110, H // 2 - 110),
                                    font_size=200, color=YELLOW, stroke_w=14, rotate=0)

    # --- Face cutout (optional) -------------------------------------------
    # sandwich 모드에선 face_conf 가 있어도 여기선 안 그림 — mid band 안으로 따로 그린다.
    if face_conf and layout != "sandwich":
        face_clip = face_conf.get("clip")
        face_t = float(face_conf.get("t", 2.0))
        face_size = int(face_conf.get("size", 360))
        face_pos = face_conf.get("position", "right")
        face_path = pick_bg_from_run(args.segments, args.docker_container,
                                     stock_path=face_clip, time_sec=face_t,
                                     out_name=".thumbnail_face.png")
        if face_path:
            face_img = Image.open(face_path).convert("RGB")
            paste_face_cutout(bg, face_img, face_size, face_pos)
            print(f"  face: {face_clip} @ {face_t}s, size={face_size}, pos={face_pos}")

    # --- Korean flag corner icon -------------------------------------------
    flag_box = None
    if show_flag:
        # Corner flag defaults to Korea (국뽕) but can be set per-spec, e.g. "MX"
        # for the 멕시코뽕 pipeline. Backward-compatible: omit → Korean flag.
        flag = get_flag(spec.get("flag_country", "KR"), 96, 64)
        bd = ImageDraw.Draw(bg)
        fx, fy = 24, H - flag.height - 24  # bottom-left by default
        flag_pos = spec.get("flag_position", "bottom-left")
        if flag_pos == "top-left":
            fx, fy = 24, 24
        elif flag_pos == "top-right":
            fx, fy = W - flag.width - 24, 24
        elif flag_pos == "bottom-right":
            fx, fy = W - flag.width - 24, H - flag.height - 24
        bd.rectangle(
            [fx - 3, fy - 3, fx + flag.width + 3, fy + flag.height + 3],
            outline=WHITE, width=3,
        )
        bg.paste(flag, (fx, fy), flag)
        flag_box = (fx, fy, fx + flag.width, fy + flag.height)

    # --- Authority label (top-left) ----------------------------------------
    # sandwich 에선 label 을 띠 아래(mid 영역)에 그려야 가려지지 않음 — 뒤에서 처리.
    if label_conf and layout != "sandwich":
        if isinstance(label_conf, str):
            label_text = label_conf
            label_fill = LABEL_RED
            label_text_c = WHITE
            label_flag = None
            label_font_size = 36
        else:
            label_text = label_conf["text"]
            label_fill = hex_to_rgb(label_conf.get("fill_hex", "#DC2626"))
            label_text_c = hex_to_rgb(label_conf.get("text_color_hex", "#FFFFFF"))
            label_flag = label_conf.get("flag")
            label_font_size = int(label_conf.get("font_size", 36))
        # If flag is at top-left, put label to its right
        label_anchor = (24, 24)
        if flag_box and flag_box[1] < 60:
            label_anchor = (flag_box[2] + 14, 24)
        draw_label_badge(bg, label_text,
                         fill=label_fill, text_color=label_text_c,
                         anchor=label_anchor, font_size=label_font_size,
                         flag_country=label_flag)

    # --- Sandwich layout (top text band + mid imagery + bottom text band) -
    if layout == "sandwich":
        # 양쪽 text band 가 H 의 32% 씩, 중간이 36%.
        top_h_frac = float(spec.get("top_band_frac", 0.38))
        bottom_h_frac = float(spec.get("bottom_band_frac", 0.38))
        top_h = int(H * top_h_frac)
        bottom_h = int(H * bottom_h_frac)
        mid_y0 = top_h
        mid_y1 = H - bottom_h

        # mid_images: { "left": path, "right": path, "size": optional int, "gap": optional int }
        # — 두 이미지를 중간 영역에 좌·우 나란히 배치. face_conf 보다 우선.
        mid_imgs = spec.get("mid_images")
        if mid_imgs and isinstance(mid_imgs, dict):
            mid_h = mid_y1 - mid_y0
            default_size = min(mid_h - 20, (W - 160) // 2)
            img_size = int(mid_imgs.get("size", default_size))
            mid_gap = int(mid_imgs.get("gap", 40))
            # 좌·우 배치: x = (W - (2*size + gap)) // 2 부터
            block_w = 2 * img_size + mid_gap
            base_x = (W - block_w) // 2
            fy = mid_y0 + (mid_h - img_size) // 2
            # optional vertical bias (negative = up, positive = down)
            fy += int(mid_imgs.get("y_offset", 0))
            run_dir = args.segments.parent.resolve() if args.segments else Path.cwd()
            for slot, key in [(0, "left"), (1, "right")]:
                img_rel = mid_imgs.get(key)
                if not img_rel:
                    continue
                img_path = Path(img_rel) if Path(img_rel).is_absolute() else (run_dir / img_rel).resolve()
                if not img_path.exists():
                    print(f"  mid_images.{key} missing: {img_path}", file=sys.stderr)
                    continue
                im = Image.open(img_path).convert("RGB")
                im = crop_fill(im, img_size, img_size)
                im = apply_rounded_mask(im, radius=24, feather=4)
                fx = base_x + slot * (img_size + mid_gap)
                bg.paste(im, (fx, fy), im)
                print(f"  mid_image[{key}]: {img_rel} @ {fx},{fy} size={img_size}")

        # mid band 안에 face cutout 배치 (face_conf 가 있을 때, mid_imgs 가 없을 때만).
        if face_conf and not mid_imgs:
            face_clip = face_conf.get("clip")
            face_t = float(face_conf.get("t", 2.0))
            face_size = int(face_conf.get("size", min(280, mid_y1 - mid_y0 - 20)))
            face_pos = face_conf.get("position", "right")
            face_path = pick_bg_from_run(args.segments, args.docker_container,
                                         stock_path=face_clip, time_sec=face_t,
                                         out_name=".thumbnail_face.png")
            if face_path:
                face_img = Image.open(face_path).convert("RGB")
                face_img = crop_fill(face_img, face_size, face_size)
                face_img = apply_rounded_mask(face_img, radius=24, feather=4)
                if face_pos == "left":
                    fx = 36
                elif face_pos == "center":
                    fx = (W - face_size) // 2
                else:
                    fx = W - face_size - 36
                # vertical-center inside the mid band
                fy = mid_y0 + (mid_y1 - mid_y0 - face_size) // 2
                bg.paste(face_img, (fx, fy), face_img)
                print(f"  face (mid): {face_clip} @ {face_t}s, size={face_size}")

        # 텍스트 띠 자체에 진한 검정 fill — 텍스트는 그 위에.
        band_alpha = int(spec.get("sandwich_band_alpha", 215))
        band_fill = hex_to_rgb(spec.get("sandwich_band_fill_hex", "#000000"))

        if bg.mode != "RGBA":
            bg = bg.convert("RGBA")

        def _draw_band(y0: int, y1: int):
            band = Image.new("RGBA", (W, y1 - y0), band_fill + (band_alpha,))
            bg.alpha_composite(band, (0, y0))

        _draw_band(0, top_h)
        _draw_band(H - bottom_h, H)

        # 권위 라벨은 띠 아래 (mid band 좌상단 모서리) 에 — 바이스톰/쓸모왕 "외신특보" 위치.
        if label_conf:
            if isinstance(label_conf, str):
                label_text = label_conf
                label_fill = LABEL_RED
                label_text_c = WHITE
                label_flag = None
                label_font_size = 30
            else:
                label_text = label_conf["text"]
                label_fill = hex_to_rgb(label_conf.get("fill_hex", "#DC2626"))
                label_text_c = hex_to_rgb(label_conf.get("text_color_hex", "#FFFFFF"))
                label_flag = label_conf.get("flag")
                label_font_size = int(label_conf.get("font_size", 30))
            draw_label_badge(bg, label_text,
                             fill=label_fill, text_color=label_text_c,
                             anchor=(24, top_h + 12),
                             font_size=label_font_size,
                             flag_country=label_flag)

        side_margin = 36
        max_text_w = W - 2 * side_margin

        # 상단 텍스트 — 호들갑 톤은 큰 글씨 (2026-05-28 사용자 피드백)
        if top_lines:
            tfont = fit_font_multi(top_lines, FONT_BLACK,
                                   max_text_w, top_h - 24,
                                   start_size=int(spec.get("text_start_size", 130)),
                                   min_size=int(spec.get("text_min_size", 64)))
            line_gap = 8
            lhs = [tfont.getbbox(t)[3] - tfont.getbbox(t)[1] for t in top_lines]
            block_h = sum(lhs) + line_gap * max(0, len(top_lines) - 1)
            cy = (top_h - block_h) // 2
            d = ImageDraw.Draw(bg)
            for i, line in enumerate(top_lines):
                b = tfont.getbbox(line)
                lw = b[2] - b[0]
                x = (W - lw) // 2 - b[0]
                y = cy - b[1]
                draw_text_with_accents(d, x, y, line, tfont,
                                       accent_words, accent_fill, base_fill,
                                       stroke_w, stroke_fill)
                cy += lhs[i] + line_gap

        # 하단 텍스트 — 호들갑 톤은 큰 글씨 (2026-05-28 사용자 피드백)
        if bottom_lines:
            bfont = fit_font_multi(bottom_lines, FONT_BLACK,
                                   max_text_w, bottom_h - 24,
                                   start_size=int(spec.get("text_start_size", 130)),
                                   min_size=int(spec.get("text_min_size", 64)))
            line_gap = 8
            lhs = [bfont.getbbox(t)[3] - bfont.getbbox(t)[1] for t in bottom_lines]
            block_h = sum(lhs) + line_gap * max(0, len(bottom_lines) - 1)
            cy = (H - bottom_h) + (bottom_h - block_h) // 2
            d = ImageDraw.Draw(bg)
            for i, line in enumerate(bottom_lines):
                b = bfont.getbbox(line)
                lw = b[2] - b[0]
                x = (W - lw) // 2 - b[0]
                y = cy - b[1]
                draw_text_with_accents(d, x, y, line, bfont,
                                       accent_words, accent_fill, base_fill,
                                       stroke_w, stroke_fill)
                cy += lhs[i] + line_gap

        # Kicker — 중간 band 하단에 작은 호들갑 한 줄 더 (멘트 풍성하게). stroke 로 가독성.
        kicker = spec.get("kicker")
        if kicker:
            kfont = fit_font_multi([kicker], FONT_BLACK, max_text_w - 60,
                                   max(40, int((mid_y1 - mid_y0) * 0.26)),
                                   start_size=int(spec.get("kicker_size", 58)),
                                   min_size=32)
            d = ImageDraw.Draw(bg)
            kb = kfont.getbbox(kicker)
            kw = kb[2] - kb[0]
            kx = (W - kw) // 2 - kb[0]
            ky = (H - bottom_h) - (kb[3] - kb[1]) - 18 - kb[1]
            draw_text_with_accents(d, kx, ky, kicker, kfont,
                                   accent_words, accent_fill, base_fill,
                                   stroke_w, stroke_fill)

        # ?! sticker 는 sandwich 에서 중간 band 우측 상단 모서리에 작게.
        if accent_punct_conf:
            if isinstance(accent_punct_conf, str):
                pt = accent_punct_conf; pc = YELLOW; pr = -8; psize = 130
            else:
                pt = accent_punct_conf["text"]
                pc = hex_to_rgb(accent_punct_conf.get("color_hex", "#FFDC00"))
                pr = int(accent_punct_conf.get("rotate", -8))
                psize = int(accent_punct_conf.get("size", 130))
            anchor_xy = (W - psize - 60, top_h + 12)
            draw_punctuation_accent(bg, pt, anchor=anchor_xy,
                                    font_size=psize, color=pc, rotate=pr)

        # Wordmark — sandwich 에선 기본 안 그림.
        if show_wordmark:
            if wordmark_badge:
                draw_wordmark_badge(bg, "파이널K",
                                    position=spec.get("wordmark_position", "bottom-right"))

        # V3 mode: bottom-left counter — black-stroked yellow text (NO box).
        # Recurring V3 thumbnail convention — replaces bottom band copy.
        # Single-line OR multi-line via `lines: [{text, font_size}, ...]`.
        counter_conf = spec.get("bottom_counter_label")
        if counter_conf:
            if isinstance(counter_conf, str):
                ct_lines = [{"text": counter_conf, "font_size": 78}]
                ct_fill = (255, 220, 0)
                ct_stroke = (0, 0, 0)
                ct_stroke_w = 6
            else:
                if "lines" in counter_conf:
                    ct_lines = list(counter_conf["lines"])
                else:
                    ct_lines = [{
                        "text": counter_conf["text"],
                        "font_size": int(counter_conf.get("font_size", 78)),
                    }]
                ct_fill = hex_to_rgb(counter_conf.get("text_color_hex", "#FFDC00"))
                ct_stroke = hex_to_rgb(counter_conf.get("stroke_color_hex", "#000000"))
                ct_stroke_w = int(counter_conf.get("stroke_width", 6))
            line_metrics = []
            for ln in ct_lines:
                lf = ImageFont.truetype(FONT_BLACK, int(ln.get("font_size", 78)))
                lbb = lf.getbbox(ln["text"])
                lh = lbb[3] - lbb[1]
                # optional flanking flags
                fl_left_img = None
                fl_right_img = None
                fl_gap = 14
                if ln.get("flag_left"):
                    fh = int(lh * 1.05)
                    fw = int(fh * 1.5)
                    fl_left_img = get_flag(ln["flag_left"], fw, fh)
                if ln.get("flag_right"):
                    fh = int(lh * 1.05)
                    fw = int(fh * 1.5)
                    fl_right_img = get_flag(ln["flag_right"], fw, fh)
                tw = lbb[2] - lbb[0]
                total_w = tw
                if fl_left_img is not None: total_w += fl_left_img.width + fl_gap
                if fl_right_img is not None: total_w += fl_right_img.width + fl_gap
                line_metrics.append({
                    "font": lf, "bb": lbb,
                    "w": total_w, "h": lh,
                    "tw": tw,
                    "text": ln["text"],
                    "flag_left": fl_left_img,
                    "flag_right": fl_right_img,
                    "flag_gap": fl_gap,
                })
            line_gap = 6
            total_h = sum(m["h"] for m in line_metrics) + line_gap * (len(line_metrics) - 1)
            margin = 24
            base_x = margin + ct_stroke_w
            cur_y = H - margin - total_h
            ct_draw = ImageDraw.Draw(bg)
            for m in line_metrics:
                cursor_x = base_x
                if m["flag_left"] is not None:
                    flag_y = cur_y + (m["h"] - m["flag_left"].height) // 2
                    bg.alpha_composite(m["flag_left"], (cursor_x, flag_y))
                    # tiny border for legibility
                    bd = ImageDraw.Draw(bg)
                    bd.rectangle([cursor_x - 1, flag_y - 1,
                                  cursor_x + m["flag_left"].width,
                                  flag_y + m["flag_left"].height],
                                 outline=(0, 0, 0, 255), width=2)
                    cursor_x += m["flag_left"].width + m["flag_gap"]
                text_x = cursor_x - m["bb"][0]
                text_y = cur_y - m["bb"][1]
                ct_draw.text((text_x, text_y), m["text"],
                             font=m["font"], fill=ct_fill,
                             stroke_width=ct_stroke_w, stroke_fill=ct_stroke)
                cursor_x += m["tw"]
                if m["flag_right"] is not None:
                    cursor_x += m["flag_gap"]
                    flag_y = cur_y + (m["h"] - m["flag_right"].height) // 2
                    bg.alpha_composite(m["flag_right"], (cursor_x, flag_y))
                    bd = ImageDraw.Draw(bg)
                    bd.rectangle([cursor_x - 1, flag_y - 1,
                                  cursor_x + m["flag_right"].width,
                                  flag_y + m["flag_right"].height],
                                 outline=(0, 0, 0, 255), width=2)
                cur_y += m["h"] + line_gap

        draw_corner_flags(bg, spec.get("corner_flags") or [], spec.get("corner_flags_position","bottom-right"), y_override=spec.get("corner_flags_y"))
        bg.convert("RGB").save(args.out, "PNG", optimize=True)
        print(f"saved: {args.out} ({args.out.stat().st_size // 1024} KB)")
        return 0

    # --- Main text (2-line) ------------------------------------------------
    d = ImageDraw.Draw(bg)
    # text occupies the lower-middle band; reserve top for label/flag
    side_margin = 60
    max_text_w = W - 2 * side_margin
    if face_conf and face_conf.get("position", "right") in ("right", "left"):
        # leave room for the face cutout
        max_text_w = W - 2 * side_margin - int(face_conf.get("size", 360)) - 24

    # find one font size that fits all lines
    big_font = fit_font_multi(text_lines, FONT_BLACK,
                              max_text_w, 160,
                              start_size=160, min_size=58)

    # vertical center of text block
    line_gap = 16
    line_heights = []
    for t in text_lines:
        b = big_font.getbbox(t)
        line_heights.append(b[3] - b[1])
    block_h = sum(line_heights) + line_gap * max(0, len(text_lines) - 1)
    # anchor block at vertical center, biased slightly down
    block_top = int(H * 0.50) - block_h // 2 + 20

    # Optional dark band behind each line
    if text_band_conf:
        tb_pad_x = int(text_band_conf.get("pad_x", 28))
        tb_pad_y = int(text_band_conf.get("pad_y", 8))
        tb_alpha = int(text_band_conf.get("alpha", 170))
        tb_fill = hex_to_rgb(text_band_conf.get("fill_hex", "#000000"))
        cy = block_top
        for i, line in enumerate(text_lines):
            b = big_font.getbbox(line)
            lw = b[2] - b[0]
            x_left = (W - lw) // 2
            x_right = x_left + lw
            y_top = cy
            y_bot = cy + line_heights[i] + b[1]
            draw_text_band(bg, (x_left, y_top, x_right, y_bot),
                           fill_rgb=tb_fill, alpha=tb_alpha,
                           pad_x=tb_pad_x, pad_y=tb_pad_y, radius=8)
            cy += line_heights[i] + line_gap

    # draw the lines (must refresh d after alpha composites)
    d = ImageDraw.Draw(bg)
    cy = block_top
    for i, line in enumerate(text_lines):
        b = big_font.getbbox(line)
        lw = b[2] - b[0]
        x = (W - lw) // 2 - b[0]
        y = cy - b[1]
        draw_text_with_accents(d, x, y, line, big_font,
                               accent_words, accent_fill, base_fill,
                               stroke_w, stroke_fill)
        cy += line_heights[i] + line_gap

    # --- Punctuation accent ("?!") -----------------------------------------
    if accent_punct_conf:
        if isinstance(accent_punct_conf, str):
            pt = accent_punct_conf
            pc = YELLOW
            pr = -8
            psize = 160
            pos_name = "right"
        else:
            pt = accent_punct_conf["text"]
            pc = hex_to_rgb(accent_punct_conf.get("color_hex", "#FFDC00"))
            pr = int(accent_punct_conf.get("rotate", -8))
            psize = int(accent_punct_conf.get("size", 160))
            pos_name = accent_punct_conf.get("position", "right")

        # layout-aware placement: avoid colliding with the text block or the
        # face cutout. "left" / "right" are hints; we pick the actual coords
        # from available negative space.
        face_pos = face_conf.get("position", "right") if face_conf else None
        face_size = int(face_conf.get("size", 360)) if face_conf else 0
        if pos_name == "right":
            if face_pos == "right":
                # Sticker centered above the face cutout (above the text band).
                fx = W - face_size - 36
                fy = H - face_size - 24
                anchor_xy = (fx + face_size // 2 - psize // 2,
                             max(40, fy - int(psize * 0.75)))
            else:
                anchor_xy = (W - psize - 80, max(60, block_top - psize - 30))
        elif pos_name == "left":
            if face_pos == "left":
                fx = 36 + face_size
                fy = H - face_size - 24
                anchor_xy = (fx - face_size // 2 - psize // 2,
                             max(40, fy - int(psize * 0.75)))
            else:
                anchor_xy = (260, 20) if label_conf else (40, 40)
        else:  # center
            anchor_xy = (W // 2 - psize // 2, max(60, block_top - psize - 30))
        draw_punctuation_accent(bg, pt, anchor=anchor_xy,
                                font_size=psize, color=pc, rotate=pr)

    # --- Wordmark ----------------------------------------------------------
    if show_wordmark:
        if wordmark_badge:
            draw_wordmark_badge(bg, "파이널K",
                                position=spec.get("wordmark_position", "bottom-right"))
        else:
            brand_font = ImageFont.truetype(FONT_BLACK, 44)
            brand = "파이널K"
            bb = brand_font.getbbox(brand)
            bw = bb[2] - bb[0]
            bh = bb[3] - bb[1]
            bx = W - bw - 32 - bb[0]
            by = H - bh - 30 - bb[1]
            d.text((bx, by), brand, font=brand_font, fill=YELLOW,
                   stroke_width=4, stroke_fill=BLACK)

    draw_corner_flags(bg, spec.get("corner_flags") or [], spec.get("corner_flags_position","bottom-right"), y_override=spec.get("corner_flags_y"))
    bg.convert("RGB").save(args.out, "PNG", optimize=True)
    print(f"saved: {args.out} ({args.out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
