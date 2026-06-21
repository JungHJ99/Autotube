#!/usr/bin/env python3
"""build_mx_cards.py — YouTube dark-mode UI card generator for the 멕시코뽕 (Mexico) pipeline.

Reads sources.json (mode=korean-reaction-for-mexico) and writes:
  video/video-card.png                 the source-video watch card (Korean title + thumbnail)
  comments/comment-NN.png              one card per Korean comment

The cards intentionally show the ORIGINAL KOREAN text — that is the proof, for the
Mexican viewer, that Koreans actually said these things. The Spanish translation rides
in the burned-in subtitle + the dubbed voice, not on the card.

1920x1080 canvas. YouTube dark palette:
  bg #0F0F0F, surface #212121, text #F1F1F1, secondary #AAAAAA, red #FF0000, blue #3EA6FF

Usage:
  python3 scripts/build_mx_cards.py output/<run>/
A downloaded video thumbnail at output/<run>/video_thumb.jpg (or .png) is used for the
video card if present; otherwise a red placeholder is drawn.
"""
import json
import re
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# When True, cards are emitted as floating RGBA panels (rounded corners + drop
# shadow + transparent margins) so build_video can composite them over a moving
# stock-video background — gives an "inserted card over footage" look instead of
# a full-screen static slideshow. Set MX_FLAT=1 to keep legacy full-screen cards.
import os as _os
PANEL = _os.environ.get("MX_FLAT") != "1"
PANEL_SCALE = float(_os.environ.get("MX_PANEL_SCALE", "0.82"))
PANEL_RADIUS = 40


def panelize(card):
    """Opaque full-frame card → floating rounded panel on transparent 1920x1080."""
    if not PANEL:
        return card.convert("RGB")
    pw, ph = int(W * PANEL_SCALE), int(H * PANEL_SCALE)
    small = card.convert("RGB").resize((pw, ph))
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=PANEL_RADIUS, fill=255)
    px, py = (W - pw) // 2, (H - ph) // 2
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # drop shadow
    shrect = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(shrect).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=PANEL_RADIUS, fill=190)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.paste((0, 0, 0, 190), (px, py + 14), shrect)
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    canvas = Image.alpha_composite(canvas, sh)
    # rounded card + thin light border
    ImageDraw.Draw(small).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=PANEL_RADIUS,
                                            outline=(255, 255, 255), width=3)
    crgba = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    crgba.paste(small, (0, 0), mask)
    canvas.alpha_composite(crgba, (px, py))
    return canvas

RUN = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
SRC = json.loads((RUN / "sources.json").read_text(encoding="utf-8"))

(RUN / "video").mkdir(exist_ok=True)
(RUN / "comments").mkdir(exist_ok=True)

W, H = 1920, 1080
BG = (15, 15, 15)
SURFACE = (33, 33, 33)
TEXT = (241, 241, 241)
SUB = (170, 170, 170)
RED = (255, 0, 0)
BLUE = (62, 166, 255)
BORDER = (60, 60, 60)

FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_MED = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
FONT_BLK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"

# Avatar accent palette (YouTube-ish saturated circles).
AVATAR_COLORS = [
    (255, 112, 67), (66, 165, 245), (102, 187, 106), (171, 71, 188),
    (255, 167, 38), (38, 198, 218), (236, 64, 122), (124, 179, 66),
]


def font(size, weight="reg"):
    path = {"reg": FONT_REG, "med": FONT_MED, "blk": FONT_BLK}[weight]
    return ImageFont.truetype(path, size)


def wrap_text(text, max_w, font_obj, draw):
    """Word-aware wrap handling CJK + Latin + explicit newlines."""
    if not text:
        return [""]
    out = []
    for para in text.split("\n"):
        if not para.strip():
            out.append("")
            continue
        tokens = re.findall(r"[A-Za-z0-9À-ɏ'\-.,!?:;()\[\]/&¿¡]+|[ \t]+|.", para)
        cur = ""
        for tok in tokens:
            trial = cur + tok
            if draw.textlength(trial, font=font_obj) > max_w and cur.strip():
                out.append(cur.rstrip())
                cur = tok.lstrip() if tok.isspace() else tok
            else:
                cur = trial
            if draw.textlength(cur, font=font_obj) > max_w and not tok.isspace():
                tmp = ""
                for ch in cur:
                    if draw.textlength(tmp + ch, font=font_obj) > max_w and tmp:
                        out.append(tmp)
                        tmp = ch
                    else:
                        tmp += ch
                cur = tmp
        if cur.strip():
            out.append(cur.rstrip())
    return out


def fmt_count(n):
    if n is None:
        return "0"
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if n >= 10000:
        return f"{n/10000:.1f}만".replace(".0만", "만")
    if n >= 1000:
        return f"{n/1000:.1f}천".replace(".0천", "천")
    return str(n)


def find_thumb(video=None):
    # Per-video thumb (video_thumb_01.jpg ...) preferred; fall back to the
    # single-video name (video_thumb.jpg) for mx-v1 runs.
    names = []
    if video is not None:
        tf = video.get("thumb_file")
        if tf:
            names.append(tf)
        vn = video.get("video_n")
        if vn is not None:
            names.append(f"video_thumb_{int(vn):02d}")
    names.append("video_thumb")
    for stem in names:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = RUN / (stem if stem.endswith(ext) else stem + ext)
            if p.exists():
                return p
    return None


def normalize_videos(src):
    """Return a list of video dicts (each with a 'comments' list). Supports both
    mx-v2 (videos:[...]) and mx-v1 (top-level video + comments)."""
    if isinstance(src.get("videos"), list) and src["videos"]:
        vids = []
        for i, v in enumerate(src["videos"], start=1):
            v = dict(v)
            v.setdefault("video_n", i)
            vids.append(v)
        return vids
    v = dict(src.get("video", {}))
    v.setdefault("video_n", 1)
    v["comments"] = src.get("comments", [])
    return [v]


def draw_play_button(d, cx, cy, r=56):
    """Red rounded YouTube play button centered at (cx, cy)."""
    d.rounded_rectangle((cx - r, cy - r*0.7, cx + r, cy + r*0.7), radius=18, fill=RED)
    tri = [(cx - r*0.28, cy - r*0.38), (cx - r*0.28, cy + r*0.38), (cx + r*0.42, cy)]
    d.polygon(tri, fill=(255, 255, 255))


def render_video_card(v, out_path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title = v.get("title_ko", SRC.get("topic", ""))
    channel = v.get("channel", "")
    views = v.get("view_count")
    published = v.get("published_human") or v.get("published_at", "")[:10]

    # --- thumbnail region (16:9, centered top) ---
    thumb_w = 1200
    thumb_h = int(thumb_w * 9 / 16)  # 675
    thumb_x = (W - thumb_w) // 2
    thumb_y = 70
    box = (thumb_x, thumb_y, thumb_x + thumb_w, thumb_y + thumb_h)
    tp = find_thumb(v)
    if tp:
        th = Image.open(tp).convert("RGB")
        # cover-fit into the 16:9 box
        scale = max(thumb_w / th.width, thumb_h / th.height)
        th = th.resize((int(th.width*scale)+1, int(th.height*scale)+1))
        left = (th.width - thumb_w) // 2
        top = (th.height - thumb_h) // 2
        th = th.crop((left, top, left + thumb_w, top + thumb_h))
        img.paste(th, (thumb_x, thumb_y))
    else:
        d.rectangle(box, fill=SURFACE)
    # subtle border + play button
    d.rectangle(box, outline=(0, 0, 0), width=2)
    draw_play_button(d, W // 2, thumb_y + thumb_h // 2)

    # --- title (below thumbnail) ---
    f_title = font(56, "blk")
    ty = thumb_y + thumb_h + 44
    for ln in wrap_text(title, thumb_w, f_title, d)[:2]:
        d.text((thumb_x, ty), ln, font=f_title, fill=TEXT)
        ty += 74

    # --- channel + meta row ---
    ty += 14
    f_ch = font(38, "med")
    # channel avatar dot
    av_r = 26
    d.ellipse((thumb_x, ty, thumb_x + av_r*2, ty + av_r*2), fill=AVATAR_COLORS[0])
    if channel:
        d.text((thumb_x + av_r, ty + av_r - 22), channel[:1], font=font(32, "blk"),
               fill=(255, 255, 255), anchor="ma")
    d.text((thumb_x + av_r*2 + 24, ty + 6), channel, font=f_ch, fill=TEXT)
    meta = []
    if views is not None:
        meta.append(f"조회수 {fmt_count(views)}회")
    if published:
        meta.append(str(published))
    if meta:
        d.text((thumb_x + av_r*2 + 24, ty + 56), "  ·  ".join(meta),
               font=font(32), fill=SUB)

    # --- red YouTube badge top-left ---
    draw_play_button(d, thumb_x + 40, 40, r=30)
    d.text((thumb_x + 86, 18), "YouTube", font=font(34, "blk"), fill=TEXT)

    panelize(img).save(out_path)


def render_comment_card(comment, video_title, out_path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    text_ko = comment.get("original_text", "")
    likes = comment.get("like_count", 0)
    author = comment.get("author", "익명")
    rank = comment.get("rank", comment.get("n", 1))

    pad = 90
    # --- context strip: which video ---
    strip = (pad, 56, W - pad, 188)
    d.rounded_rectangle(strip, radius=16, fill=(28, 28, 28))
    draw_play_button(d, strip[0] + 52, (strip[1] + strip[3]) // 2, r=26)
    d.text((strip[0] + 96, strip[1] + 26), "유튜브 인기 댓글", font=font(28, "med"), fill=RED)
    vt = video_title if len(video_title) < 64 else video_title[:62] + "…"
    d.text((strip[0] + 96, strip[1] + 66), vt, font=font(30, "med"), fill=SUB)

    # --- comment body card ---
    card = (pad, 226, W - pad, H - 60)
    d.rounded_rectangle(card, radius=22, fill=SURFACE)
    inner_x = card[0] + 56
    inner_y = card[1] + 46

    # avatar
    av_r = 40
    color = AVATAR_COLORS[(sum(ord(c) for c in author)) % len(AVATAR_COLORS)]
    d.ellipse((inner_x, inner_y, inner_x + av_r*2, inner_y + av_r*2), fill=color)
    d.text((inner_x + av_r, inner_y + av_r - 26), author[:1], font=font(44, "blk"),
           fill=(255, 255, 255), anchor="ma")

    # author + rank
    name_x = inner_x + av_r*2 + 28
    d.text((name_x, inner_y + 2), f"@{author}", font=font(36, "med"), fill=TEXT)
    d.text((name_x, inner_y + 50), f"인기 댓글 {rank}위", font=font(30), fill=SUB)

    # comment text (large)
    f_body = font(54)
    by = inner_y + av_r*2 + 36
    line_h = 76
    body_max_y = card[3] - 130
    for ln in wrap_text(text_ko, card[2] - card[0] - 112, f_body, d):
        if by + line_h > body_max_y:
            break
        d.text((inner_x, by), ln, font=f_body, fill=TEXT)
        by += line_h

    # footer: like thumb + count + reply
    foot_y = card[3] - 96
    # thumbs-up glyph (simple)
    tx = inner_x
    d.rounded_rectangle((tx, foot_y + 14, tx + 18, foot_y + 44), radius=3, fill=SUB)
    d.polygon([(tx + 18, foot_y + 14), (tx + 40, foot_y + 4), (tx + 40, foot_y + 24),
               (tx + 18, foot_y + 24)], fill=SUB)
    d.text((tx + 56, foot_y + 8), f"{fmt_count(likes)}", font=font(34, "med"), fill=SUB)
    d.text((tx + 220, foot_y + 8), "답글", font=font(34, "med"), fill=SUB)

    panelize(img).save(out_path)


def main():
    videos = normalize_videos(SRC)
    single = len(videos) == 1 and not isinstance(SRC.get("videos"), list)
    for v in videos:
        vn = int(v.get("video_n", 1))
        video_title = v.get("title_ko", SRC.get("topic", ""))
        # mx-v1 single video keeps the legacy flat filenames; mx-v2 uses -NN.
        vcard = "video-card.png" if single else f"video-card-{vn:02d}.png"
        render_video_card(v, RUN / "video" / vcard)
        print(f"  wrote video/{vcard}")
        comments = v.get("comments", [])
        for c in comments:
            cn = c["n"]
            cname = (f"comment-{cn:02d}.png" if single
                     else f"v{vn:02d}-comment-{cn:02d}.png")
            render_comment_card(c, video_title, RUN / "comments" / cname)
        print(f"  wrote {len(comments)} comment cards for video {vn}")


if __name__ == "__main__":
    main()
