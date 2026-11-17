"""Draw winter frames with layered rails, snow crests and woven ribbons.

Shares the Manosaba frames' silhouette hierarchy, with original winter motifs.
All five 512px assets retain a transparent face window and rebuild offline.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from PIL import ImageDraw

SIZE, SS = 512, 4
OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "plugins/inventory/resources/items/avatar_frames"
)
INK = "#243b53"
DEEP = "#152b40"
IVORY = "#fff8ec"
ICE = "#b3cfdd"
SILVER = "#e2edf1"
RED = "#a84b50"
WINE = "#703745"
PINE = "#47665b"
GOLD = "#d4b37d"
PALE_GOLD = "#f4dfb5"


def pt(x, y):
    return round(x * SS), round(y * SS)


def line(d, points, color, width=3):
    d.line([pt(*p) for p in points], fill=color, width=round(width * SS), joint="curve")


def poly(d, points, color, edge=INK, width=3):
    d.polygon([pt(*p) for p in points], fill=color)
    if edge:
        line(d, [*points, points[0]], edge, width)


def ellipse(d, x, y, rx, ry=None, fill=None, edge=None, width=3):
    ry = rx if ry is None else ry
    d.ellipse(
        (*pt(x - rx, y - ry), *pt(x + rx, y + ry)),
        fill=fill,
        outline=edge,
        width=round(width * SS),
    )


def curve(d, controls, color, width):
    a, b, c, e = controls
    points = []
    for i in range(61):
        t = i / 60
        points.append(
            tuple(
                (1 - t) ** 3 * a[j]
                + 3 * (1 - t) ** 2 * t * b[j]
                + 3 * (1 - t) * t * t * c[j]
                + t**3 * e[j]
                for j in (0, 1)
            )
        )
    line(d, points, color, width)


def crystal(d, x, y, r=27, color=SILVER, edge=INK):
    # Broad six-fold arms with a dark underdrawing stay readable at 64px.
    for stroke, width in ((edge, 9), (color, 4)):
        for i in range(6):
            a = math.radians(i * 60 - 90)
            u, v = math.cos(a), math.sin(a)
            line(d, [(x, y), (x + u * r, y + v * r)], stroke, width)
            for sign in (-1, 1):
                line(
                    d,
                    [
                        (x + u * r * 0.58, y + v * r * 0.58),
                        (
                            x + u * r * 0.78 - v * sign * r * 0.23,
                            y + v * r * 0.78 + u * sign * r * 0.23,
                        ),
                    ],
                    stroke,
                    width,
                )
    ellipse(d, x, y, 5, fill=color, edge=edge, width=1)


def jewel(d, x, y, r=15, color=ICE):
    poly(d, [(x, y - r), (x + r * 0.7, y), (x, y + r), (x - r * 0.7, y)], color, INK, 3)
    line(d, [(x, y - r + 4), (x, y + r - 4)], IVORY, 2)
    line(d, [(x - r * 0.5, y), (x + r * 0.5, y)], IVORY, 2)


def sprig(d, side, *, gold=False, dense=False):
    flip = lambda x: x if side < 0 else 512 - x
    controls = [(flip(188), 476), (flip(72), 475), (flip(20), 414), (flip(32), 330)]
    curve(d, controls, INK, 12)
    curve(d, controls, GOLD if gold else PINE, 6)
    for x, y, a in [(135, 463, -24), (96, 441, -38), (65, 409, -58), (43, 371, -78)]:
        for sign in (-1, 1):
            angle = math.radians(a + sign * 34)
            ux, uy = math.cos(angle), math.sin(angle)
            end = (x - ux * 32, y + uy * 32)
            points = [
                (flip(x), y),
                (flip((x + end[0]) / 2 - uy * 7), (y + end[1]) / 2 - ux * 7),
                (flip(end[0]), end[1]),
                (flip((x + end[0]) / 2 + uy * 7), (y + end[1]) / 2 + ux * 7),
            ]
            poly(d, points, GOLD if gold else PINE, INK, 2)
            line(
                d,
                [(flip(x), y), (flip(end[0]), end[1])],
                PALE_GOLD if gold else ICE,
                1.5,
            )
    if dense:
        for x, y in [(87, 437), (108, 453), (65, 415)]:
            ellipse(d, flip(x), y, 8, fill=RED, edge=INK, width=2)
            ellipse(d, flip(x) - 2, y - 2, 2, fill=IVORY)


def bow(d, *, paired=False, gold=False):
    for side in (-1, 1):
        x = lambda n: 256 + side * n
        color = IVORY if paired and side < 0 else RED
        edge = GOLD if gold else INK
        poly(
            d,
            [(x(9), 34), (x(72), 8), (x(112), 43), (x(63), 69), (x(8), 51)],
            color,
            edge,
            4,
        )
        poly(
            d,
            [
                (x(51), 53),
                (x(94), 75),
                (x(119), 135),
                (x(95), 124),
                (x(84), 145),
                (x(69), 95),
            ],
            color,
            edge,
            4,
        )
        line(
            d,
            [(x(24), 41), (x(68), 25), (x(89), 42)],
            ICE if color == IVORY else "#d7a1a1",
            5,
        )
        # A pair of fine woven stripes belongs on the tails.
        line(d, [(x(79), 99), (x(96), 131)], GOLD if gold else IVORY, 3)
    ellipse(d, 256, 43, 25, fill=INK, edge=GOLD if gold else IVORY, width=3)
    crystal(d, 256, 43, 18, PALE_GOLD if gold else SILVER, INK)


def medal(d, x=256, y=467, *, gold=False, triple=False):
    for side in (-1, 1):
        poly(
            d,
            [
                (x + side * 5, y + 9),
                (x + side * 25, y + 4),
                (x + side * 39, 508),
                (x + side * 19, 496),
                (x + side * 8, 505),
            ],
            RED,
            INK,
            3,
        )
        line(
            d,
            [(x + side * 18, y + 20), (x + side * 27, 493)],
            GOLD if gold else IVORY,
            3,
        )
    for i in range(12):
        a = i * math.pi / 6
        ellipse(
            d,
            x + math.cos(a) * 24,
            y + math.sin(a) * 24,
            9,
            fill=GOLD if gold else SILVER,
            edge=INK,
            width=2,
        )
    ellipse(d, x, y, 29, fill=INK, edge=PALE_GOLD if gold else IVORY, width=3)
    if triple:
        for dx in (-13, 0, 13):
            jewel(d, x + dx, y, 10, PALE_GOLD)
    else:
        crystal(d, x, y, 20, PALE_GOLD if gold else SILVER, INK)


def pendant(d, side=1):
    x = 479 if side > 0 else 33
    for i in range(4):
        ellipse(d, x, 205 + i * 25, 7, 16, edge=INK, width=7)
        ellipse(d, x, 205 + i * 25, 7, 16, edge=SILVER, width=3)
    jewel(d, x, 312, 17)


def crown(d):
    poly(
        d,
        [(182, 50), (171, 15), (220, 34), (256, 4), (292, 34), (341, 15), (330, 50)],
        GOLD,
        INK,
        4,
    )
    line(d, [(187, 53), (325, 53)], IVORY, 4)
    for x, y in [(180, 14), (256, 6), (332, 14)]:
        ellipse(d, x, y, 6, fill=PALE_GOLD, edge=INK, width=2)
    jewel(d, 256, 34, 10, RED)


def build_frame(kind):
    im = Image.new("RGBA", (SIZE * SS, SIZE * SS))
    d = ImageDraw.Draw(im)
    accent = GOLD if kind == "champion" else SILVER
    # Strong dark rail, a narrow metallic lip and a coloured inner band.
    ellipse(d, 256, 256, 235, edge=DEEP, width=20)
    ellipse(d, 256, 256, 235, edge=accent, width=5)
    ellipse(
        d, 256, 256, 223, edge=RED if kind in ("character", "podium") else INK, width=14
    )
    ellipse(d, 256, 256, 212, edge=IVORY, width=5)
    ellipse(d, 256, 256, 207, fill=(0, 0, 0, 0))
    if kind == "character":
        bow(d, paired=True)
        sprig(d, -1, dense=True)
        pendant(d)
        crystal(d, 220, 469, 25)
        jewel(d, 269, 475, 22, RED)
        crystal(d, 309, 454, 19)
    elif kind == "champion":
        sprig(d, -1, gold=True, dense=True)
        sprig(d, 1, gold=True, dense=True)
        crown(d)
        medal(d, gold=True)
        for side in (-1, 1):
            crystal(d, 256 + side * 211, 168, 24, PALE_GOLD)
    elif kind == "podium":
        sprig(d, -1, dense=True)
        sprig(d, 1, dense=True)
        for x, y, r in [(208, 43, 16), (256, 28, 23), (304, 43, 16)]:
            jewel(d, x, y, r, RED)
        medal(d, triple=True)
    elif kind == "top10":
        sprig(d, -1, dense=True)
        sprig(d, 1)
        crystal(d, 256, 32, 29)
        medal(d)
    elif kind == "top50":
        sprig(d, -1)
        crystal(d, 405, 91, 23)
        medal(d, 151, 453)
        jewel(d, 316, 476, 15)
    else:
        raise ValueError(kind)
    # Same transparent safety window as the existing Manosaba frames.
    d.rectangle((*pt(208, 240), *pt(304, 352)), fill=(0, 0, 0, 0))
    return im.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for kind in ("character", "champion", "podium", "top10", "top50"):
        build_frame(kind).save(OUTPUT / f"frame_winter_{kind}.png", optimize=True)


if __name__ == "__main__":
    main()
