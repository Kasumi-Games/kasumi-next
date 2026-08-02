"""Generate the 星屑玻璃 avatar frame sold by 流星堂."""

import math
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "plugins/inventory/resources/items/avatar_frames"
CANVAS = 512
SS = 4
CENTER = CANVAS * SS // 2
AVATAR_RADIUS = 208 * SS


def _canvas() -> Image.Image:
    return Image.new("RGBA", (CANVAS * SS, CANVAS * SS), (0, 0, 0, 0))


def _ring(draw: ImageDraw.ImageDraw, color, *, width: int, inset: int = 0) -> None:
    radius = AVATAR_RADIUS + inset * SS
    draw.ellipse(
        (CENTER - radius, CENTER - radius, CENTER + radius, CENTER + radius),
        outline=color,
        width=width * SS,
    )


def _save(image: Image.Image, name: str) -> None:
    result = image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result.save(OUTPUT / f"{name}.png")


def stardust() -> None:
    image = _canvas()
    glow = _canvas()
    glow_draw = ImageDraw.Draw(glow)
    _ring(glow_draw, (116, 174, 255, 150), width=22, inset=13)
    glow = glow.filter(ImageFilter.GaussianBlur(12 * SS))
    image.alpha_composite(glow)
    draw = ImageDraw.Draw(image)
    _ring(draw, (216, 235, 255, 255), width=8, inset=7)
    _ring(draw, (102, 150, 226, 255), width=12, inset=18)
    for angle, size in ((205, 15), (226, 8), (34, 11), (58, 7)):
        rad = math.radians(angle)
        radius = AVATAR_RADIUS + 24 * SS
        x = CENTER + math.cos(rad) * radius
        y = CENTER + math.sin(rad) * radius
        points = [
            (x, y - size * SS),
            (x + size * SS * 0.22, y - size * SS * 0.22),
            (x + size * SS, y),
            (x + size * SS * 0.22, y + size * SS * 0.22),
            (x, y + size * SS),
            (x - size * SS * 0.22, y + size * SS * 0.22),
            (x - size * SS, y),
            (x - size * SS * 0.22, y - size * SS * 0.22),
        ]
        draw.polygon(points, fill=(255, 255, 255, 245))
    _save(image, "frame_shop_stardust")


def main() -> None:
    stardust()


if __name__ == "__main__":
    main()
