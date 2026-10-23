"""Draw S4's five original, reproducible Manosaba avatar-frame assets.

Ink and ivory rails, rose-wax seals, chains, judgment scales and twin ribbons
form one family. The central face stays transparent. The shared character
frame represents Ema and Hiro together; rank frames use separate silhouettes.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from PIL import ImageDraw

SIZE, SS = 512, 4
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "plugins/inventory/resources/items/avatar_frames"
INK = "#2b2227"
ROSE = "#882b41"
WINE = "#581e31"
PAPER = "#f7ede5"
PINK = "#d9a0ad"
SILVER = "#cbc8d3"
GOLD = "#e1c28e"
SHADOW = "#74646b"


def pt(x, y):
    return round(x * SS), round(y * SS)


def line(draw, points, color, width):
    draw.line(
        [pt(*p) for p in points], fill=color, width=round(width * SS), joint="curve"
    )


def poly(draw, points, color, outline=None, width=3):
    draw.polygon([pt(*p) for p in points], fill=color)
    if outline:
        line(draw, [*points, points[0]], outline, width)


def ellipse(draw, x, y, rx, ry, color=None, outline=None, width=3):
    draw.ellipse(
        (*pt(x - rx, y - ry), *pt(x + rx, y + ry)),
        fill=color,
        outline=outline,
        width=round(width * SS),
    )


def diamond(draw, x, y, r, color=ROSE, edge=PAPER):
    poly(
        draw,
        [(x, y - r), (x + r * 0.72, y), (x, y + r), (x - r * 0.72, y)],
        color,
        edge,
        3,
    )


def curve(draw, points, color, width):
    a, b, c, d = points
    samples = []
    for i in range(41):
        t = i / 40
        samples.append(
            tuple(
                (1 - t) ** 3 * a[j]
                + 3 * (1 - t) ** 2 * t * b[j]
                + 3 * (1 - t) * t * t * c[j]
                + t**3 * d[j]
                for j in (0, 1)
            )
        )
    line(draw, samples, color, width)


def leaf(draw, x, y, angle, color, length=39):
    angle = math.radians(angle)
    ux, uy = math.cos(angle), math.sin(angle)
    vx, vy = -uy, ux
    points = [
        (x + ux * a + vx * b, y + uy * a + vy * b)
        for a, b in [
            (-length / 2, 0),
            (-length / 5, 11),
            (length / 3, 8),
            (length / 2, 0),
            (length / 3, -8),
            (-length / 5, -11),
        ]
    ]
    poly(draw, points, color, INK, 3)
    line(
        draw,
        [
            (x - ux * length * 0.3, y - uy * length * 0.3),
            (x + ux * length * 0.32, y + uy * length * 0.32),
        ],
        PAPER,
        3,
    )


def rose(draw, x, y, radius, color=ROSE, edge=PAPER):
    # Five broad petals remain readable at the 64px in-game frame size.
    for i in range(5):
        a = math.radians(i * 72 - 90)
        ellipse(
            draw,
            x + math.cos(a) * radius * 0.45,
            y + math.sin(a) * radius * 0.45,
            radius * 0.59,
            radius * 0.59,
            color,
            INK,
            3,
        )
    for i in range(3):
        a = math.radians(i * 120 - 55)
        ellipse(
            draw,
            x + math.cos(a) * radius * 0.19,
            y + math.sin(a) * radius * 0.19,
            radius * 0.39,
            radius * 0.35,
            None,
            edge,
            3,
        )
    diamond(draw, x, y, 6, edge, edge)


def chain(draw, side, *, gold=False):
    color = GOLD if gold else SILVER
    for i in range(5):
        x = 30 + i * 3 if side < 0 else 482 - i * 3
        y = 190 + i * 29
        ellipse(draw, x, y, 12 if i % 2 == 0 else 7, 22, None, INK, 9)
        ellipse(draw, x, y, 12 if i % 2 == 0 else 7, 22, None, color, 4)


def vine(draw, side, *, gold=False, dense=False):
    x = lambda n: n if side < 0 else 512 - n
    points = [(x(160), 463), (x(18), 444), (x(9), 335), (x(54), 253)]
    curve(draw, points, INK, 12)
    curve(draw, points, GOLD if gold else SILVER, 6)
    for px, py, angle in [(57, 372, -125), (80, 415, -48), (122, 447, -22)]:
        leaf(
            draw,
            x(px),
            py,
            angle if side < 0 else 180 - angle,
            GOLD if gold else SILVER,
        )
    if dense:
        leaf(draw, x(46), 326, -70 if side < 0 else 250, PINK, 36)
        rose(draw, x(82), 425, 27, ROSE, GOLD if gold else PAPER)


def scales(draw):
    line(draw, [(256, 6), (256, 50)], INK, 14)
    line(draw, [(256, 6), (256, 50)], GOLD, 7)
    line(draw, [(184, 17), (328, 17)], INK, 14)
    line(draw, [(184, 17), (328, 17)], GOLD, 7)
    for x in (192, 320):
        line(draw, [(x, 17), (x - 22, 45), (x + 22, 45), (x, 17)], INK, 7)
        line(draw, [(x, 19), (x - 20, 43), (x + 20, 43), (x, 19)], GOLD, 3)
        poly(
            draw, [(x - 26, 43), (x + 26, 43), (x + 17, 58), (x - 17, 58)], GOLD, INK, 3
        )
    diamond(draw, 256, 14, 12, ROSE, GOLD)


def seal(draw, x=256, y=465, *, tier=0):
    poly(
        draw,
        [(x - 27, y + 12), (x - 38, 507), (x - 8, 494), (x, 507), (x + 10, y + 18)],
        WINE,
        INK,
        3,
    )
    poly(
        draw,
        [(x + 7, y + 10), (x + 16, 508), (x + 35, 492), (x + 48, 503), (x + 29, y + 4)],
        ROSE,
        INK,
        3,
    )
    for i in range(12):
        a = math.radians(i * 30)
        ellipse(draw, x + math.cos(a) * 25, y + math.sin(a) * 25, 12, 12, ROSE, INK, 2)
    ellipse(draw, x, y, 29, 29, WINE, GOLD if tier == 1 else PAPER, 4)
    if tier == 1:
        poly(
            draw,
            [
                (x - 17, y - 10),
                (x - 10, y + 9),
                (x + 10, y + 9),
                (x + 17, y - 10),
                (x + 5, y - 2),
                (x, y - 16),
                (x - 6, y - 2),
            ],
            GOLD,
        )
    elif tier == 2:
        for dx in (-12, 0, 12):
            diamond(draw, x + dx, y, 8, PAPER, PAPER)
    else:
        diamond(draw, x, y, 16, PAPER, ROSE)


def base(accent=SILVER, *, heavy=False):
    image = Image.new("RGBA", (SIZE * SS, SIZE * SS))
    draw = ImageDraw.Draw(image)
    ellipse(draw, 256, 256, 233, 233, None, INK, 19 if heavy else 14)
    ellipse(draw, 256, 256, 235, 235, None, accent, 6)
    ellipse(
        draw, 256, 256, 220, 220, None, ROSE if heavy else SHADOW, 16 if heavy else 10
    )
    ellipse(draw, 256, 256, 211, 211, None, PAPER, 5)
    # An open avatar disc, before the edge ornaments are applied.
    ellipse(draw, 256, 256, 208, 208, (0, 0, 0, 0))
    return image, draw


def build_frame(kind):
    image, draw = base(
        GOLD if kind == "champion" else SILVER,
        heavy=kind in ("champion", "podium", "character"),
    )
    if kind == "champion":
        chain(draw, -1, gold=True)
        chain(draw, 1, gold=True)
        vine(draw, -1, gold=True, dense=True)
        vine(draw, 1, gold=True, dense=True)
        scales(draw)
        seal(draw, tier=1)
    elif kind == "podium":
        chain(draw, -1)
        chain(draw, 1)
        vine(draw, -1, dense=True)
        vine(draw, 1, dense=True)
        for x, y, r in [(213, 37, 16), (256, 27, 23), (299, 37, 16)]:
            diamond(draw, x, y, r, ROSE, SILVER)
        seal(draw, tier=2)
    elif kind == "top10":
        vine(draw, -1)
        vine(draw, 1)
        rose(draw, 256, 34, 29, ROSE, PAPER)
        seal(draw)
    elif kind == "top50":
        chain(draw, 1)
        for angle in (205, 335):
            a = math.radians(angle)
            diamond(draw, 256 + math.cos(a) * 226, 256 + math.sin(a) * 226, 19)
        seal(draw, 151, 453)
    elif kind == "character":
        # The ivory and ink bow halves are a paired-character silhouette.
        for side, color in [(-1, PAPER), (1, INK)]:
            x = lambda n: 256 + side * n
            poly(
                draw,
                [(x(8), 36), (x(71), 3), (x(116), 37), (x(64), 66), (x(9), 52)],
                color,
                ROSE,
                5,
            )
            poly(
                draw,
                [
                    (x(51), 47),
                    (x(113), 82),
                    (x(133), 155),
                    (x(112), 141),
                    (x(97), 161),
                    (x(80), 94),
                ],
                color,
                ROSE,
                5,
            )
            line(draw, [(x(13), 43), (x(67), 26), (x(88), 35)], PINK, 6)
        rose(draw, 256, 41, 29, ROSE, PAPER)
        vine(draw, -1)
        chain(draw, 1)
        rose(draw, 216, 461, 30, PAPER, ROSE)
        rose(draw, 269, 472, 31, ROSE, PAPER)
        diamond(draw, 311, 451, 21, INK, PAPER)
    else:
        raise ValueError(kind)
    # Mandatory face window even if a new ornament is added later.
    draw.rectangle((*pt(208, 240), *pt(304, 352)), fill=(0, 0, 0, 0))
    return image.resize((512, 512), Image.Resampling.LANCZOS)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for kind in ("champion", "podium", "top10", "top50", "character"):
        path = OUTPUT / f"frame_manosaba_{kind}.png"
        build_frame(kind).save(path, optimize=True)
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
