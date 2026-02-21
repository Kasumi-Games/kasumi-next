from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
FONTS_DIR = RESOURCES_DIR / "Fonts"


def _resolve_image(target: Union[Image.Image, ImageDraw.ImageDraw]) -> Image.Image:
    if isinstance(target, Image.Image):
        return target
    if hasattr(target, "_image"):
        return target._image
    raise TypeError("target must be PIL.Image.Image or ImageDraw.ImageDraw")


def load_font(
    size: int,
    font_name: str = "old.ttf",
    fonts_dir: Optional[Path] = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Load a font from render_service resources with fallback.

    Args:
        size: target font size.
        font_name: font filename under fonts_dir.
        fonts_dir: optional custom fonts directory.
    """
    base_dir = fonts_dir or FONTS_DIR
    font_path = base_dir / font_name
    try:
        return ImageFont.truetype(str(font_path), size)
    except OSError:
        return ImageFont.load_default()


def alpha_composite_paste(
    dest: Image.Image, source: Image.Image, pos: tuple[int, int]
) -> None:
    """Paste source onto dest with alpha compositing and boundary clipping."""
    x, y = pos
    w, h = source.size
    dest_w, dest_h = dest.size

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(dest_w, x + w)
    y2 = min(dest_h, y + h)

    if x1 >= x2 or y1 >= y2:
        return

    sx1 = x1 - x
    sy1 = y1 - y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    source_crop = source.crop((sx1, sy1, sx2, sy2))
    dest_crop = dest.crop((x1, y1, x2, y2))

    if dest_crop.mode != "RGBA":
        dest_crop = dest_crop.convert("RGBA")
    if source_crop.mode != "RGBA":
        source_crop = source_crop.convert("RGBA")

    comp = Image.alpha_composite(dest_crop, source_crop)
    dest.paste(comp, (x1, y1))


def draw_rounded_rectangle(
    target: Union[Image.Image, ImageDraw.ImageDraw],
    bbox: Tuple[int, int, int, int],
    corner_radius: int = 10,
    fill: Optional[Tuple[int, int, int, int]] = None,
    outline: Optional[Tuple[int, int, int, int]] = None,
    width: int = 1,
    scale: int = 4,
) -> Image.Image:
    """Draw rounded rectangle with anti-aliased edges."""
    image = _resolve_image(target)
    left, top, right, bottom = bbox
    w, h = right - left, bottom - top

    max_radius = min(w // 2, h // 2)
    corner_radius = min(corner_radius, max_radius)

    if corner_radius <= 0:
        draw = ImageDraw.Draw(image)
        draw.rectangle(bbox, fill=fill, outline=outline, width=width)
        return image

    scaled_w, scaled_h = w * scale, h * scale
    scaled_radius = corner_radius * scale
    scaled_width = width * scale

    bg_color = (0, 0, 0, 0)
    if fill:
        bg_color = (fill[0], fill[1], fill[2], 0)
    temp_img = Image.new("RGBA", (scaled_w, scaled_h), bg_color)
    temp_draw = ImageDraw.Draw(temp_img)

    if fill:
        temp_draw.rectangle(
            [scaled_radius, 0, scaled_w - scaled_radius, scaled_h], fill=fill
        )
        temp_draw.rectangle(
            [0, scaled_radius, scaled_w, scaled_h - scaled_radius], fill=fill
        )
        temp_draw.pieslice(
            [0, 0, scaled_radius * 2, scaled_radius * 2], 180, 270, fill=fill
        )
        temp_draw.pieslice(
            [scaled_w - scaled_radius * 2, 0, scaled_w, scaled_radius * 2],
            270,
            360,
            fill=fill,
        )
        temp_draw.pieslice(
            [0, scaled_h - scaled_radius * 2, scaled_radius * 2, scaled_h],
            90,
            180,
            fill=fill,
        )
        temp_draw.pieslice(
            [
                scaled_w - scaled_radius * 2,
                scaled_h - scaled_radius * 2,
                scaled_w,
                scaled_h,
            ],
            0,
            90,
            fill=fill,
        )

    if outline and width > 0:
        for i in range(scaled_width):
            temp_draw.line(
                [scaled_radius, i, scaled_w - scaled_radius, i], fill=outline
            )
            temp_draw.line(
                [
                    scaled_radius,
                    scaled_h - i - 1,
                    scaled_w - scaled_radius,
                    scaled_h - i - 1,
                ],
                fill=outline,
            )
            temp_draw.line(
                [i, scaled_radius, i, scaled_h - scaled_radius], fill=outline
            )
            temp_draw.line(
                [
                    scaled_w - i - 1,
                    scaled_radius,
                    scaled_w - i - 1,
                    scaled_h - scaled_radius,
                ],
                fill=outline,
            )
            temp_draw.arc(
                [i, i, scaled_radius * 2 - i, scaled_radius * 2 - i],
                180,
                270,
                fill=outline,
            )
            temp_draw.arc(
                [
                    scaled_w - scaled_radius * 2 + i,
                    i,
                    scaled_w - i,
                    scaled_radius * 2 - i,
                ],
                270,
                360,
                fill=outline,
            )
            temp_draw.arc(
                [
                    i,
                    scaled_h - scaled_radius * 2 + i,
                    scaled_radius * 2 - i,
                    scaled_h - i,
                ],
                90,
                180,
                fill=outline,
            )
            temp_draw.arc(
                [
                    scaled_w - scaled_radius * 2 + i,
                    scaled_h - scaled_radius * 2 + i,
                    scaled_w - i,
                    scaled_h - i,
                ],
                0,
                90,
                fill=outline,
            )

    temp_img = temp_img.resize((w, h), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer.paste(temp_img, (left, top))
    result = Image.alpha_composite(image, layer)
    if result is not image:
        image.paste(result)
    return image


def draw_pill(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    fill: Tuple[int, int, int, int],
    scale: int = 4,
) -> Image.Image:
    """Draw a pill shape with anti-aliased edges."""
    left, top, right, bottom = bbox
    w, h = right - left, bottom - top

    radius = h // 2
    scaled_w, scaled_h = w * scale, h * scale
    scaled_radius = radius * scale

    bg_color = (fill[0], fill[1], fill[2], 0)
    temp_img = Image.new("RGBA", (scaled_w, scaled_h), bg_color)
    temp_draw = ImageDraw.Draw(temp_img)

    temp_draw.rectangle(
        [scaled_radius, 0, scaled_w - scaled_radius, scaled_h], fill=fill
    )
    temp_draw.pieslice([0, 0, scaled_radius * 2, scaled_h], 90, 270, fill=fill)
    temp_draw.pieslice(
        [scaled_w - scaled_radius * 2, 0, scaled_w, scaled_h], 270, 90, fill=fill
    )

    temp_img = temp_img.resize((w, h), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer.paste(temp_img, (left, top))
    result = Image.alpha_composite(image, layer)
    if result is not image:
        image.paste(result)
    return image


def generate_simple_background(width: int, height: int) -> Image.Image:
    """Generate a simple background image."""
    layer = Image.new("RGBA", (width, height), (252, 243, 240, 0))
    background = Image.new("RGBA", (width, height), (252, 243, 240, 255))
    pattern = Image.open(RESOURCES_DIR / "BG" / "bg_object_big.png").convert("RGBA")

    for x in range(0, width, pattern.width):
        for y in range(0, height, pattern.height):
            layer.paste(pattern, (x, y), pattern.split()[3])

    result = Image.alpha_composite(background, layer)
    return result
