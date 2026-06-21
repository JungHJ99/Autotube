#!/usr/bin/env python3
"""
Generate chibi character PNGs for build_video.py overlay.

Output: characters/male_closed.png, male_open.png, female_closed.png, female_open.png
All 400x400, transparent background. Centered chibi style.
"""
from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path("/home/hjhj/autotube/characters")
OUT.mkdir(exist_ok=True)
SIZE = 400

# Palette
SKIN = (255, 224, 196)
BLUSH = (255, 158, 158)
EYE_WHITE = (255, 255, 255)
EYE_BLACK = (30, 30, 35)
HIGHLIGHT = (255, 255, 255)
MOUTH_PINK = (220, 80, 90)
OUTLINE = (40, 30, 30)

M_HAIR = (45, 35, 50)
M_SHIRT = (60, 110, 200)
M_SHIRT_SHADE = (40, 80, 160)

F_HAIR = (130, 70, 45)
F_HAIR_SHADE = (100, 50, 30)
F_SHIRT = (255, 110, 160)
F_SHIRT_SHADE = (220, 75, 130)
F_BOW = (255, 80, 130)

CX = SIZE // 2  # 200
FACE_CY = 160   # face center vertical
FACE_R = 110    # face radius


def draw_neck_and_body(d, shirt, shirt_shade):
    # Neck
    d.rectangle([CX - 16, FACE_CY + FACE_R - 10, CX + 16, FACE_CY + FACE_R + 18],
                fill=SKIN, outline=OUTLINE, width=3)
    # Shoulders/torso — wider trapezoid-like ellipse
    d.ellipse([CX - 130, FACE_CY + FACE_R + 5, CX + 130, FACE_CY + FACE_R + 130],
              fill=shirt_shade, outline=OUTLINE, width=3)
    d.ellipse([CX - 115, FACE_CY + FACE_R + 5, CX + 115, FACE_CY + FACE_R + 115],
              fill=shirt, outline=OUTLINE, width=3)


def draw_face(d):
    d.ellipse([CX - FACE_R, FACE_CY - FACE_R, CX + FACE_R, FACE_CY + FACE_R],
              fill=SKIN, outline=OUTLINE, width=4)


def draw_eyes(d):
    for ex in [CX - 38, CX + 38]:
        # eye white
        d.ellipse([ex - 22, FACE_CY - 8, ex + 22, FACE_CY + 30],
                  fill=EYE_WHITE, outline=OUTLINE, width=3)
        # large pupil
        d.ellipse([ex - 17, FACE_CY - 3, ex + 17, FACE_CY + 28],
                  fill=EYE_BLACK)
        # double highlight (sparkle)
        d.ellipse([ex - 12, FACE_CY + 0, ex - 2, FACE_CY + 11],
                  fill=HIGHLIGHT)
        d.ellipse([ex + 4, FACE_CY + 14, ex + 11, FACE_CY + 21],
                  fill=HIGHLIGHT)


def draw_blush(d):
    for ex in [CX - 62, CX + 62]:
        d.ellipse([ex - 20, FACE_CY + 30, ex + 20, FACE_CY + 50],
                  fill=BLUSH)


def draw_mouth(d, mouth_state: str):
    my = FACE_CY + 52
    if mouth_state == "closed":
        d.arc([CX - 14, my, CX + 14, my + 18],
              start=200, end=340, fill=OUTLINE, width=4)
    else:
        # open round
        d.ellipse([CX - 11, my, CX + 11, my + 22],
                  fill=MOUTH_PINK, outline=OUTLINE, width=3)
        d.ellipse([CX - 6, my + 11, CX + 6, my + 20],
                  fill=(255, 130, 140))


def draw_male_hair(d):
    # Top hair cap — wider than face on top
    # main scalp: chord arc covering top half of head
    d.chord([CX - FACE_R - 10, FACE_CY - FACE_R - 15,
             CX + FACE_R + 10, FACE_CY + 30],
            start=180, end=0, fill=M_HAIR, outline=OUTLINE, width=3)
    # side bangs — just a tiny fringe at forehead, NOT covering eyes
    # bangs sit between y = FACE_CY - FACE_R + 5 and FACE_CY - 25 (above eyes)
    fringe_y = FACE_CY - 30
    fringe_top = FACE_CY - FACE_R + 5
    # 3 small spike tufts on forehead
    spikes = [
        [(CX - 70, fringe_y), (CX - 50, fringe_top + 5), (CX - 30, fringe_y - 5)],
        [(CX - 25, fringe_y), (CX - 5, fringe_top), (CX + 20, fringe_y - 8)],
        [(CX + 25, fringe_y), (CX + 50, fringe_top + 5), (CX + 75, fringe_y)],
    ]
    for tri in spikes:
        d.polygon(tri, fill=M_HAIR, outline=OUTLINE)


def draw_female_hair(d):
    # Top hair cap — sits ON TOP of head, going below face slightly on the sides
    # (a half-ellipse that crowns the head, not engulfing it)
    d.chord([CX - FACE_R - 8, FACE_CY - FACE_R - 18,
             CX + FACE_R + 8, FACE_CY - 20],
            start=180, end=0, fill=F_HAIR, outline=OUTLINE, width=3)
    # Two pigtails — small round tufts on each side
    # left pigtail
    d.ellipse([CX - FACE_R - 28, FACE_CY - 30,
               CX - FACE_R + 8, FACE_CY + 30],
              fill=F_HAIR, outline=OUTLINE, width=3)
    # right pigtail
    d.ellipse([CX + FACE_R - 8, FACE_CY - 30,
               CX + FACE_R + 28, FACE_CY + 30],
              fill=F_HAIR, outline=OUTLINE, width=3)
    # Small bangs — short side-swept on left side only (clean)
    bangs_y = FACE_CY - 38
    # left swept bang — a slim curved chord
    d.chord([CX - 80, FACE_CY - FACE_R - 5,
             CX + 30, FACE_CY - 20],
            start=200, end=350, fill=F_HAIR, outline=OUTLINE, width=2)
    # Bow on right side of head
    bx, by = CX + FACE_R - 15, FACE_CY - FACE_R + 10
    d.polygon([(bx, by), (bx - 24, by - 14), (bx - 24, by + 14)],
              fill=F_BOW, outline=OUTLINE)
    d.polygon([(bx, by), (bx + 24, by - 14), (bx + 24, by + 14)],
              fill=F_BOW, outline=OUTLINE)
    d.ellipse([bx - 8, by - 8, bx + 8, by + 8], fill=F_BOW, outline=OUTLINE)


def render(kind: str, mouth: str):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if kind == "male":
        draw_neck_and_body(d, M_SHIRT, M_SHIRT_SHADE)
    else:
        draw_neck_and_body(d, F_SHIRT, F_SHIRT_SHADE)

    draw_face(d)

    if kind == "male":
        draw_male_hair(d)
    else:
        draw_female_hair(d)

    draw_eyes(d)
    draw_blush(d)
    draw_mouth(d, mouth)

    return img


for kind in ["male", "female"]:
    for mouth in ["closed", "open"]:
        img = render(kind, mouth)
        out = OUT / f"{kind}_{mouth}.png"
        img.save(out, "PNG")
        print(f"  saved {out.relative_to(OUT.parent)} ({out.stat().st_size // 1024}KB)")
