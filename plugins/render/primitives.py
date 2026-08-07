from pathlib import Path
from threading import local
from collections import OrderedDict

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from .color import ColorLike
from .color import rgba
from .color import normalize_color

ImageTarget = Image.Image | ImageDraw.ImageDraw

_FONT_CACHE_MAX_ITEMS = 64
_FONT_CACHE_LOCAL = local()


def resolve_image(target: ImageTarget) -> Image.Image:
    """Resolve a PIL image from an image or draw target.

    Args:
        target: PIL image or ``ImageDraw`` instance.

    Returns:
        Underlying PIL image.
    """

    if isinstance(target, Image.Image):
        return target
    if hasattr(target, "_image"):
        return target._image
    raise TypeError("target must be PIL.Image.Image or ImageDraw.ImageDraw")


def load_font(
    size: int,
    font: str | Path | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font with a default-font fallback.

    Args:
        size: Font size in pixels.
        font: Optional font file path.

    Returns:
        Loaded PIL font.
    """

    cache: OrderedDict[
        tuple[str | None, int], ImageFont.FreeTypeFont | ImageFont.ImageFont
    ] = getattr(_FONT_CACHE_LOCAL, "items", None)
    if cache is None:
        cache = OrderedDict()
        _FONT_CACHE_LOCAL.items = cache

    key = (None if font is None else str(font), size)
    cached = cache.get(key)
    if cached is not None:
        cache.move_to_end(key)
        return cached

    if font is None:
        loaded = ImageFont.load_default(size)
    else:
        try:
            loaded = ImageFont.truetype(str(font), size)
        except OSError:
            loaded = ImageFont.load_default()
    cache[key] = loaded
    while len(cache) > _FONT_CACHE_MAX_ITEMS:
        cache.popitem(last=False)
    return loaded


def alpha_composite_paste(
    dest: Image.Image, source: Image.Image, pos: tuple[int, int]
) -> None:
    """Alpha-composite a source image onto a destination with clipping.

    Args:
        dest: Destination image mutated in place.
        source: Source image.
        pos: Top-left paste position on ``dest``.
    """

    x, y = pos
    if source.mode != "RGBA":
        source = source.convert("RGBA")

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(dest.width, x + source.width)
    y2 = min(dest.height, y + source.height)
    if x1 >= x2 or y1 >= y2:
        return

    source_box = (x1 - x, y1 - y, x2 - x, y2 - y)
    if dest.mode == "RGBA":
        dest.alpha_composite(source, dest=(x1, y1), source=source_box)
        return

    crop = source.crop(source_box)
    base = dest.crop((x1, y1, x2, y2)).convert("RGBA")
    dest.paste(Image.alpha_composite(base, crop), (x1, y1))


def draw_rounded_rectangle(
    target: ImageTarget,
    bbox: tuple[int, int, int, int],
    corner_radius: int = 10,
    fill: ColorLike | None = None,
    outline: ColorLike | None = None,
    width: int = 1,
    scale: int = 1,
) -> Image.Image:
    """Draw a rounded rectangle.

    Args:
        target: PIL image or ``ImageDraw`` instance to draw on.
        bbox: Rectangle bounds as ``(left, top, right, bottom)``.
        corner_radius: Radius for rounded corners.
        fill: Optional fill color.
        outline: Optional outline color.
        width: Outline width in pixels.
        scale: Deprecated compatibility argument; drawing is no longer locally supersampled.

    Returns:
        Mutated target image.
    """

    image = resolve_image(target)
    left, top, right, bottom = bbox
    shape_w = max(0, right - left)
    shape_h = max(0, bottom - top)
    if shape_w == 0 or shape_h == 0:
        return image

    fill_color = normalize_color(fill)
    outline_color = normalize_color(outline)
    corner_radius = min(max(0, corner_radius), shape_w // 2, shape_h // 2)
    temp = Image.new("RGBA", (shape_w, shape_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp)
    if corner_radius == 0:
        draw.rectangle(
            (0, 0, shape_w, shape_h),
            fill=fill_color,
            outline=outline_color,
            width=width,
        )
    else:
        draw.rounded_rectangle(
            (0, 0, shape_w, shape_h),
            radius=corner_radius,
            fill=fill_color,
            outline=outline_color,
            width=max(1, width),
        )
    alpha_composite_paste(image, temp, (left, top))
    return image


def draw_pill(
    target: ImageTarget,
    bbox: tuple[int, int, int, int],
    fill: ColorLike,
    scale: int = 1,
) -> Image.Image:
    """Draw a pill shape.

    Args:
        target: PIL image or ``ImageDraw`` instance to draw on.
        bbox: Pill bounds as ``(left, top, right, bottom)``.
        fill: Fill color.
        scale: Deprecated compatibility argument; drawing is no longer locally supersampled.

    Returns:
        Mutated target image.
    """

    left, top, right, bottom = bbox
    return draw_rounded_rectangle(
        target,
        bbox,
        corner_radius=max(0, (bottom - top) // 2),
        fill=fill,
        outline=None,
        width=0,
        scale=scale,
    )


def transparent(size: tuple[int, int]) -> Image.Image:
    """Create a transparent RGBA image.

    Args:
        size: Image size as ``(width, height)``.

    Returns:
        Transparent image.
    """

    return Image.new("RGBA", size, (0, 0, 0, 0))


def solid(size: tuple[int, int], color: ColorLike = rgba(255, 255, 255)) -> Image.Image:
    """Create a solid RGBA image.

    Args:
        size: Image size as ``(width, height)``.
        color: Fill color.

    Returns:
        Solid image.
    """

    return Image.new("RGBA", size, normalize_color(color) or rgba(255, 255, 255))
