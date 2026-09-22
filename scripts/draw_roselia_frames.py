"""Draw the four Roselia season-ranking avatar-frame assets.

The visual grammar is deliberately Roselia-specific: black-violet enamel,
antique-gold tracery, thorn vines, layered roses, round rose medallions, and
black lace.  Avoid segmented candy rails, paper tabs, cyan blocks, and sticker
geometry; those belong to the Mewtype family of frames.

The character frame is intentionally not generated here.  Like the earlier
Kasumi character frame, it is an AI-assisted flat cartoon wig asset tied to the
featured character's hair and accessory silhouette.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter

SIZE = 512
SS = 4
CENTER = (SIZE // 2, SIZE // 2)
AVATAR_RADIUS = 181
OUTPUT_DIR = Path("plugins/inventory/resources/items/avatar_frames")

INK = (13, 9, 20, 255)
BLACK_VIOLET = (25, 16, 38, 255)
ENAMEL = (48, 29, 70, 255)
PURPLE = (82, 47, 122, 255)
AMETHYST = (126, 78, 164, 255)
LAVENDER = (181, 151, 202, 255)
BURGUNDY = (91, 22, 52, 255)
ROSE = (145, 43, 81, 255)
ANTIQUE_GOLD = (163, 127, 67, 255)
PALE_GOLD = (226, 204, 146, 255)
SILVER = (177, 168, 190, 255)


def _canvas() -> Image.Image:
    return Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))


def _xy(point: tuple[float, float]) -> tuple[int, int]:
    return round(point[0] * SS), round(point[1] * SS)


def _box(
    center: tuple[float, float], radius_x: float, radius_y: float | None = None
) -> tuple[int, int, int, int]:
    if radius_y is None:
        radius_y = radius_x
    x, y = center
    return (
        round((x - radius_x) * SS),
        round((y - radius_y) * SS),
        round((x + radius_x) * SS),
        round((y + radius_y) * SS),
    )


def _arc(
    draw: ImageDraw.ImageDraw,
    radius: float,
    start: float,
    end: float,
    fill: tuple[int, int, int, int],
    width: float,
) -> None:
    draw.arc(
        _box(CENTER, radius),
        start=start,
        end=end,
        fill=fill,
        width=round(width * SS),
    )


def _ring(
    draw: ImageDraw.ImageDraw,
    radius: float,
    fill: tuple[int, int, int, int],
    width: float,
) -> None:
    draw.ellipse(_box(CENTER, radius), outline=fill, width=round(width * SS))


def _radial_point(
    radius: float, angle_degrees: float, center: tuple[float, float] = CENTER
) -> tuple[float, float]:
    angle = math.radians(angle_degrees)
    return center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)


def _polygon(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] | None = None,
    width: float = 1,
) -> None:
    scaled = [_xy(point) for point in points]
    draw.polygon(scaled, fill=fill)
    if outline is not None:
        draw.line(
            [*scaled, scaled[0]],
            fill=outline,
            width=round(width * SS),
            joint="curve",
        )


def _punch_avatar_window(image: Image.Image) -> None:
    alpha = image.getchannel("A")
    mask = ImageDraw.Draw(alpha)
    mask.ellipse(_box(CENTER, AVATAR_RADIUS), fill=0)
    image.putalpha(alpha)


def _base_ring(
    rail: tuple[int, int, int, int] = ENAMEL,
    *,
    gold: bool = False,
    glow: bool = False,
    outer_radius: float = 224,
    band_width: float = 12,
    inner_ring: bool = True,
    inner_radius: float = 194,
    accent_color: tuple[int, int, int, int] | None = None,
    glow_color: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    image = _canvas()
    accent = accent_color or (PALE_GOLD if gold else SILVER)

    if glow:
        glow_layer = _canvas()
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_rgb = glow_color or (PALE_GOLD if gold else rail)
        _ring(
            glow_draw,
            outer_radius,
            (*glow_rgb[:3], 200),
            band_width + 9,
        )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(6 * SS))
        image.alpha_composite(glow_layer)

    draw = ImageDraw.Draw(image)
    _ring(draw, outer_radius, INK, band_width + 6)
    _ring(draw, outer_radius + 4, accent, 2.5)
    _ring(draw, outer_radius - band_width * 0.48, rail, band_width)
    _ring(draw, outer_radius - band_width, AMETHYST, 2)
    if inner_ring:
        _ring(draw, inner_radius, BLACK_VIOLET, max(8, band_width * 0.72))
        _ring(draw, inner_radius - band_width * 0.45, accent, 2.2)

    _punch_avatar_window(image)
    return image


def _almond(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    length: float,
    width: float,
    angle_degrees: float,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] = ANTIQUE_GOLD,
    outline_width: float = 1.2,
) -> None:
    angle = math.radians(angle_degrees)
    forward = (math.cos(angle), math.sin(angle))
    side = (-forward[1], forward[0])
    points: list[tuple[float, float]] = []
    for along, across in (
        (-0.50, 0.00),
        (-0.28, 0.42),
        (0.00, 0.50),
        (0.28, 0.36),
        (0.50, 0.00),
        (0.28, -0.36),
        (0.00, -0.50),
        (-0.28, -0.42),
    ):
        points.append(
            (
                center[0] + forward[0] * length * along + side[0] * width * across,
                center[1] + forward[1] * length * along + side[1] * width * across,
            )
        )
    _polygon(draw, points, fill, outline, outline_width)


def _rose(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    radius: float,
    *,
    outer: tuple[int, int, int, int] = BURGUNDY,
    inner: tuple[int, int, int, int] = ROSE,
    edge: tuple[int, int, int, int] = ANTIQUE_GOLD,
) -> None:
    for index in range(7):
        angle = -90 + index * (360 / 7)
        direction = math.radians(angle)
        petal_center = (
            center[0] + math.cos(direction) * radius * 0.30,
            center[1] + math.sin(direction) * radius * 0.30,
        )
        _almond(
            draw,
            petal_center,
            radius * 1.08,
            radius * 0.72,
            angle,
            outer,
            edge,
            0.8,
        )
    for index in range(5):
        angle = -72 + index * 72
        direction = math.radians(angle)
        petal_center = (
            center[0] + math.cos(direction) * radius * 0.14,
            center[1] + math.sin(direction) * radius * 0.14,
        )
        _almond(
            draw,
            petal_center,
            radius * 0.70,
            radius * 0.48,
            angle + 12,
            inner,
            edge,
            0.7,
        )
    draw.ellipse(
        _box(center, radius * 0.13), fill=PALE_GOLD, outline=edge, width=2 * SS
    )


def _thorn_vine(
    draw: ImageDraw.ImageDraw,
    start: float,
    end: float,
    *,
    radius: float = 231,
    color: tuple[int, int, int, int] = ANTIQUE_GOLD,
) -> None:
    _arc(draw, radius, start, end, color, 2.2)
    steps = max(2, round(abs(end - start) / 24))
    for index in range(steps + 1):
        angle = start + (end - start) * index / steps
        base = _radial_point(radius, angle)
        tangent = math.radians(angle + (70 if index % 2 else -70))
        tip = (
            base[0] + math.cos(tangent) * 10,
            base[1] + math.sin(tangent) * 10,
        )
        left = _radial_point(radius - 3, angle - 1.8)
        right = _radial_point(radius + 3, angle + 1.8)
        _polygon(draw, [left, right, tip], color)


def _filigree_curl(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    *,
    flip: bool = False,
    color: tuple[int, int, int, int] = ANTIQUE_GOLD,
) -> None:
    x, y = center
    if flip:
        draw.arc(_box((x, y), 34, 22), 190, 350, fill=color, width=round(2 * SS))
        draw.arc(
            _box((x - 19, y + 3), 15, 13), 10, 185, fill=color, width=round(2 * SS)
        )
        tip = [(x + 32, y - 3), (x + 43, y - 8), (x + 35, y + 3)]
    else:
        draw.arc(_box((x, y), 34, 22), 190, 350, fill=color, width=round(2 * SS))
        draw.arc(
            _box((x + 19, y + 3), 15, 13), 190, 355, fill=color, width=round(2 * SS)
        )
        tip = [(x - 32, y - 3), (x - 43, y - 8), (x - 35, y + 3)]
    _polygon(draw, tip, color)


def _champion_medallion(draw: ImageDraw.ImageDraw) -> None:
    """One bold round crest, avoiding a crown or pointed-triangle silhouette."""

    _arc(draw, 226, 226, 254, PALE_GOLD, 4)
    _arc(draw, 226, 286, 314, PALE_GOLD, 4)
    center = (256, 48)
    draw.ellipse(
        _box(center, 42),
        fill=BLACK_VIOLET,
        outline=PALE_GOLD,
        width=round(3.5 * SS),
    )
    draw.ellipse(
        _box(center, 34),
        outline=ANTIQUE_GOLD,
        width=round(1.8 * SS),
    )
    _rose(draw, center, 28, outer=ENAMEL, inner=AMETHYST, edge=PALE_GOLD)


def _save(image: Image.Image, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    resized = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    resized.save(OUTPUT_DIR / filename, optimize=True)


def draw_top50() -> None:
    image = _base_ring(
        BLACK_VIOLET,
        outer_radius=211,
        band_width=7,
        inner_ring=False,
        accent_color=SILVER,
    )
    _save(image, "frame_roselia_top50.png")


def draw_top10() -> None:
    image = _base_ring(
        PURPLE,
        outer_radius=219,
        band_width=12,
        inner_radius=198,
        accent_color=LAVENDER,
    )
    draw = ImageDraw.Draw(image)
    _thorn_vine(draw, 128, 220, radius=225, color=LAVENDER)
    _thorn_vine(draw, 320, 412, radius=225, color=LAVENDER)
    _rose(
        draw,
        (256, 43),
        25,
        outer=ENAMEL,
        inner=AMETHYST,
        edge=SILVER,
    )
    _save(image, "frame_roselia_top10.png")


def draw_podium() -> None:
    image = _base_ring(
        BLACK_VIOLET,
        gold=True,
        outer_radius=226,
        band_width=16,
        inner_radius=196,
    )
    draw = ImageDraw.Draw(image)
    _thorn_vine(draw, 104, 229, radius=234, color=ANTIQUE_GOLD)
    _thorn_vine(draw, 311, 436, radius=234, color=ANTIQUE_GOLD)
    _filigree_curl(draw, (164, 83))
    _filigree_curl(draw, (348, 83), flip=True)
    _rose(draw, (218, 48), 25)
    _rose(draw, (256, 31), 30, outer=ENAMEL, inner=AMETHYST, edge=PALE_GOLD)
    _rose(draw, (294, 48), 25)
    _save(image, "frame_roselia_podium.png")


def draw_champion() -> None:
    image = _base_ring(
        ENAMEL,
        gold=True,
        glow=True,
        outer_radius=232,
        band_width=18,
        inner_radius=194,
    )
    draw = ImageDraw.Draw(image)
    _champion_medallion(draw)
    _save(image, "frame_roselia_champion.png")


def main() -> None:
    draw_top50()
    draw_top10()
    draw_podium()
    draw_champion()


if __name__ == "__main__":
    main()
