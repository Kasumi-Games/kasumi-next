"""Generate the four YUMEMITA season-ranking avatar frames.

The frames translate the Mewtype kit into small game UI assets: cyan framing,
pink annotations, indigo structure lines, white sticker outlines, pixel-cut
corners, and sparse candy-coloured stationery marks.  The four ranks share a
silhouette but gain layers and ornaments with rarity.

The character frame is intentionally not generated here.  It is an AI-assisted
illustration based on Nakamachi Arale's stage headphones.

Usage:
    uv run python scripts/draw_yumemita_frames.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw
from PIL import ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "plugins/inventory/resources/items/avatar_frames"

CANVAS = 512
SS = 4
BIG = CANVAS * SS
CENTER = BIG // 2
AVATAR_RADIUS = 208 * SS

# MewtypeKit palette plus the title-gradient lavender.
CYAN = (29, 211, 243, 255)
CYAN_LIGHT = (174, 236, 246, 255)
PINK = (255, 115, 213, 255)
PINK_LIGHT = (255, 196, 235, 255)
INDIGO = (32, 47, 109, 255)
LAVENDER = (201, 130, 232, 255)
PAPER = (252, 241, 255, 255)
WHITE = (255, 255, 255, 255)
LEMON = (255, 225, 111, 255)
MINT = (123, 241, 204, 255)


def _canvas() -> Image.Image:
    return Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))


def _arc(
    draw: ImageDraw.ImageDraw,
    radius: float,
    start: float,
    end: float,
    color: tuple[int, int, int, int],
    width: float,
) -> None:
    r = radius * SS
    draw.arc(
        (CENTER - r, CENTER - r, CENTER + r, CENTER + r),
        start=start,
        end=end,
        fill=color,
        width=max(1, round(width * SS)),
    )


def _ring(
    draw: ImageDraw.ImageDraw,
    radius: float,
    color: tuple[int, int, int, int],
    width: float,
) -> None:
    _arc(draw, radius, 0, 360, color, width)


def _polygon(draw: ImageDraw.ImageDraw, points, *, fill) -> None:
    draw.polygon([(round(x * SS), round(y * SS)) for x, y in points], fill=fill)


def _rotate_point(cx: float, cy: float, x: float, y: float, angle: float):
    rad = math.radians(angle)
    return (
        cx + x * math.cos(rad) - y * math.sin(rad),
        cy + x * math.sin(rad) + y * math.cos(rad),
    )


def _diamond(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    color,
    *,
    angle: float = 0,
) -> None:
    points = [
        _rotate_point(cx, cy, 0, -size, angle),
        _rotate_point(cx, cy, size, 0, angle),
        _rotate_point(cx, cy, 0, size, angle),
        _rotate_point(cx, cy, -size, 0, angle),
    ]
    _polygon(draw, points, fill=color)


def _plus(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    size: float,
    color,
    *,
    outline=WHITE,
) -> None:
    arm = size * 0.34
    points = [
        (cx - arm, cy - size),
        (cx + arm, cy - size),
        (cx + arm, cy - arm),
        (cx + size, cy - arm),
        (cx + size, cy + arm),
        (cx + arm, cy + arm),
        (cx + arm, cy + size),
        (cx - arm, cy + size),
        (cx - arm, cy + arm),
        (cx - size, cy + arm),
        (cx - size, cy - arm),
        (cx - arm, cy - arm),
    ]
    if outline is not None:
        expanded = [
            (cx + (x - cx) * 1.25, cy + (y - cy) * 1.25) for x, y in points
        ]
        _polygon(draw, expanded, fill=outline)
    _polygon(draw, points, fill=color)


def _slash_pair(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    *,
    color,
    angle: float,
) -> None:
    for offset in (-8, 8):
        points = [
            _rotate_point(cx, cy, -23 + offset, -5, angle),
            _rotate_point(cx, cy, 23 + offset, -5, angle),
            _rotate_point(cx, cy, 23 + offset, 5, angle),
            _rotate_point(cx, cy, -23 + offset, 5, angle),
        ]
        _polygon(draw, points, fill=WHITE)
        inset = [
            _rotate_point(cx, cy, -20 + offset, -3, angle),
            _rotate_point(cx, cy, 20 + offset, -3, angle),
            _rotate_point(cx, cy, 20 + offset, 3, angle),
            _rotate_point(cx, cy, -20 + offset, 3, angle),
        ]
        _polygon(draw, inset, fill=color)


def _burst(draw: ImageDraw.ImageDraw, cx: float, cy: float, radii, *, fill) -> None:
    outer, inner, count = radii
    points = []
    for index in range(count * 2):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / count
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    _polygon(draw, points, fill=fill)


def _punch_avatar_window(image: Image.Image) -> None:
    mask = Image.new("L", image.size, 255)
    ImageDraw.Draw(mask).ellipse(
        (
            CENTER - AVATAR_RADIUS,
            CENTER - AVATAR_RADIUS,
            CENTER + AVATAR_RADIUS,
            CENTER + AVATAR_RADIUS,
        ),
        fill=0,
    )
    image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))


def _save(image: Image.Image, name: str) -> None:
    result = image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result.save(OUTPUT / f"{name}.png")
    print(f"wrote {OUTPUT / f'{name}.png'}")


def top50() -> None:
    """Rarity 3: one clean cyan rail with restrained stationery marks."""

    image = _canvas()
    draw = ImageDraw.Draw(image)

    _ring(draw, 222, INDIGO, 17)
    _ring(draw, 218, CYAN, 12)
    _ring(draw, 211, WHITE, 3)

    # Pixel-cut joint blocks echo the corners of Mewtype panels.
    for angle, colors in ((222, (CYAN, PINK)), (42, (PINK, CYAN))):
        rad = math.radians(angle)
        cx = 256 + math.cos(rad) * 220
        cy = 256 + math.sin(rad) * 220
        _diamond(draw, cx, cy, 14, WHITE, angle=45)
        _diamond(draw, cx, cy, 10, colors[0], angle=45)
        dx = math.cos(rad + math.pi / 2) * 19
        dy = math.sin(rad + math.pi / 2) * 19
        _diamond(draw, cx + dx, cy + dy, 6, colors[1], angle=45)

    _punch_avatar_window(image)
    _save(image, "frame_yumemita_top50")


def top10() -> None:
    """Rarity 4: cyan/pink double track with rhythmic segmented beats."""

    image = _canvas()
    draw = ImageDraw.Draw(image)

    _ring(draw, 226, INDIGO, 18)
    _ring(draw, 222, CYAN, 12)
    _ring(draw, 213, PINK, 7)
    _ring(draw, 208.5, WHITE, 3)

    # Alternating paper-colour beats ride the outer track.
    for start, end, color in (
        (204, 225, PINK),
        (237, 252, LAVENDER),
        (292, 310, PINK_LIGHT),
        (24, 43, LEMON),
        (70, 86, MINT),
        (125, 143, LAVENDER),
    ):
        _arc(draw, 222, start, end, WHITE, 17)
        _arc(draw, 222, start + 1, end - 1, color, 10)

    _slash_pair(draw, 102, 99, color=CYAN, angle=-35)
    _slash_pair(draw, 410, 413, color=PINK, angle=-35)

    _punch_avatar_window(image)
    _save(image, "frame_yumemita_top10")


def podium() -> None:
    """Rarity 5: a tri-colour medal rail and paired sticker ornaments."""

    image = _canvas()

    # A soft cyan extrusion gives the sticker ring the kit title's ledge.
    extrusion = _canvas()
    extrusion_draw = ImageDraw.Draw(extrusion)
    _ring(extrusion_draw, 226, (29, 211, 243, 185), 20)
    image.alpha_composite(extrusion, (0, 7 * SS))

    draw = ImageDraw.Draw(image)
    _ring(draw, 226, WHITE, 25)
    _ring(draw, 226, INDIGO, 19)
    for start, end, color in (
        (0, 118, CYAN),
        (120, 238, PINK),
        (240, 358, LAVENDER),
    ):
        _arc(draw, 226, start, end, color, 13)
    _ring(draw, 213, WHITE, 4)

    # Three paper tabs make the podium tier readable even at 64 px.
    for angle, color in ((270, LEMON), (282, PINK), (258, CYAN)):
        rad = math.radians(angle)
        cx = 256 + math.cos(rad) * 238
        cy = 256 + math.sin(rad) * 238
        points = [
            _rotate_point(cx, cy, -13, -24, angle + 90),
            _rotate_point(cx, cy, 13, -24, angle + 90),
            _rotate_point(cx, cy, 10, 22, angle + 90),
            (cx, cy),
            _rotate_point(cx, cy, -10, 22, angle + 90),
        ]
        outline = [(256 + (x - 256) * 1.015, 256 + (y - 256) * 1.015) for x, y in points]
        _polygon(draw, outline, fill=WHITE)
        _polygon(draw, points, fill=color)

    _plus(draw, 92, 113, 18, LAVENDER)
    _diamond(draw, 126, 91, 9, PINK, angle=45)
    _plus(draw, 420, 399, 15, CYAN)
    _diamond(draw, 390, 427, 8, PINK, angle=45)

    _punch_avatar_window(image)
    _save(image, "frame_yumemita_podium")


def _gradient_ring(image: Image.Image, *, radius: float, width: float) -> None:
    mask = Image.new("L", image.size, 0)
    _ring(ImageDraw.Draw(mask), radius, 255, width)
    gradient = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = gradient.load()
    for y in range(BIG):
        t = y / max(1, BIG - 1)
        color = tuple(round(LAVENDER[i] * (1 - t) + CYAN[i] * t) for i in range(4))
        for x in range(BIG):
            pixels[x, y] = color
    gradient.putalpha(mask)
    image.alpha_composite(gradient)


def _infinity(draw: ImageDraw.ImageDraw, cx: float, cy: float, *, color) -> None:
    points = []
    for index in range(161):
        t = 2 * math.pi * index / 160
        denominator = 1 + math.sin(t) ** 2
        x = 34 * math.cos(t) / denominator
        y = 23 * math.sin(t) * math.cos(t) / denominator
        points.append((round((cx + x) * SS), round((cy + y) * SS)))
    draw.line(points, fill=WHITE, width=12 * SS, joint="curve")
    draw.line(points, fill=color, width=7 * SS, joint="curve")


def champion() -> None:
    """Rarity 6: title-gradient ring, paper burst crown, and infinity seal."""

    image = _canvas()
    glow = _canvas()
    _ring(ImageDraw.Draw(glow), 226, (29, 211, 243, 145), 28)
    glow = glow.filter(ImageFilter.GaussianBlur(10 * SS))
    image.alpha_composite(glow)

    draw = ImageDraw.Draw(image)

    # The white/cyan burst mirrors the Mewtype page-title punch ornament.
    _burst(draw, 256, 39, (74, 55, 12), fill=CYAN_LIGHT)
    _burst(draw, 256, 34, (68, 51, 12), fill=WHITE)

    _ring(draw, 228, WHITE, 31)
    _ring(draw, 228, INDIGO, 24)
    _gradient_ring(image, radius=228, width=16)
    draw = ImageDraw.Draw(image)
    _ring(draw, 214, WHITE, 5)
    _ring(draw, 211, CYAN_LIGHT, 2)

    # Four chunky shine gates suggest stage lights without literal stars.
    for angle, color in ((205, PINK), (235, LEMON), (25, MINT), (55, PINK)):
        rad = math.radians(angle)
        cx = 256 + math.cos(rad) * 229
        cy = 256 + math.sin(rad) * 229
        _diamond(draw, cx, cy, 15, WHITE, angle=45)
        _diamond(draw, cx, cy, 10, color, angle=45)

    _plus(draw, 92, 93, 21, LAVENDER)
    _diamond(draw, 126, 66, 10, PINK, angle=45)
    _plus(draw, 420, 418, 18, CYAN)
    _diamond(draw, 386, 446, 9, PINK, angle=45)

    # The season's ∞ identity doubles as a compact champion medallion.
    _infinity(draw, 256, 477, color=PINK)

    _punch_avatar_window(image)
    _save(image, "frame_yumemita_champion")


def main() -> None:
    top50()
    top10()
    podium()
    champion()


if __name__ == "__main__":
    main()
