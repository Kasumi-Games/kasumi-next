import math
import random
from pathlib import Path
from dataclasses import dataclass

import numpy as np
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter
from PIL import ImageEnhance

from plugins.render.core import Size
from plugins.render.core import RenderContext
from plugins.render.color import ColorLike
from plugins.render.color import normalize_color
from plugins.render.types import ImageSource
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste

KIT_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = KIT_DIR / "resources"
BG_DIR = RESOURCES_DIR / "BG"
FONTS_DIR = RESOURCES_DIR / "Fonts"
ORBITRON_FONT = FONTS_DIR / "Orbitron Black.ttf"


@dataclass(frozen=True)
class BanGDreamPatternBackground:
    """Simple filled background tiled with the BanG Dream! object pattern."""

    fill: ColorLike
    pattern: ImageSource

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new(
            "RGBA", (size.width, size.height), normalize_color(self.fill)
        )
        pattern = load_image(ctx, self.pattern)
        if ctx.render_ratio > 1:
            pattern = pattern.resize(
                (
                    max(1, pattern.width * ctx.render_ratio),
                    max(1, pattern.height * ctx.render_ratio),
                ),
                Image.Resampling.LANCZOS,
            )
        for x in range(0, size.width, pattern.width):
            for y in range(0, size.height, pattern.height):
                alpha_composite_paste(canvas, pattern, (x, y))
        return canvas


@dataclass(frozen=True)
class BanGDreamImageBackground:
    """Source-derived BanG Dream! background with blur, facets, stars, and text."""

    source: ImageSource
    fill: ColorLike = (252, 243, 240, 255)
    text: str = "BanG Dream!"
    blur_radius: int = 25
    triangle_size: int = 200
    brightness_add: int = 20
    brightness_difference: float = 0.04
    opacity: float = 1.0
    star_density: float = 0.00001
    star_angle_range: float = 72
    star_size_range: tuple[float, float] = (25, 75)
    text_opacity: float = 0.5
    random_seed: int | None = 0

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new(
            "RGBA", (size.width, size.height), normalize_color(self.fill)
        )
        image = spread(
            load_image(ctx, self.source), size.width, size.height, self.brightness_add
        )
        image = create_blurred_triangle_pattern(
            image,
            blur_radius=ctx.scale_px(self.blur_radius),
            triangle_size=ctx.scale_px(self.triangle_size),
            brightness_difference=self.brightness_difference,
        )
        rng = (
            random.Random(self.random_seed) if self.random_seed is not None else random
        )
        for star_name in ("star1.png", "star2.png"):
            star_path = BG_DIR / star_name
            if star_path.exists():
                scatter_images(
                    image,
                    star_path,
                    density=self.star_density / (ctx.render_ratio * ctx.render_ratio),
                    angle_range=self.star_angle_range,
                    size_range=(
                        self.star_size_range[0] * ctx.render_ratio,
                        self.star_size_range[1] * ctx.render_ratio,
                    ),
                    rng=rng,
                )
        draw_repeated_text(
            image,
            self.text,
            font_size=ctx.scale_px(150),
            angle=15,
            line_spacing=ctx.scale_px(50),
            letter_spacing=ctx.scale_px(100),
            stroke_width=ctx.scale_px(3),
            skew_angle=-12,
            opacity=self.text_opacity,
            scale_x=0.8,
        )
        if self.opacity < 1:
            image = with_opacity(image, self.opacity)
        alpha_composite_paste(canvas, image, (0, 0))
        return canvas


def load_image(ctx: RenderContext, source: ImageSource) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGBA").copy()
    return ctx.image_cache.load(source)


def resize_contain(image: Image.Image, width: int, height: int) -> Image.Image:
    if width <= 0 or height <= 0:
        return Image.new("RGBA", (0, 0))
    ratio = min(width / image.width, height / image.height)
    return image.resize(
        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
        Image.Resampling.LANCZOS,
    )


def resize_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    if width <= 0 or height <= 0:
        return Image.new("RGBA", (0, 0))
    ratio = max(width / image.width, height / image.height)
    resized = image.resize(
        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def spread(
    image: Image.Image, width: int, height: int, brightness_add: int
) -> Image.Image:
    if width <= 0 or height <= 0:
        return Image.new("RGBA", (0, 0))
    image = image.convert("RGBA")
    if brightness_add:
        r, g, b, a = image.split()
        r = r.point(lambda value: min(255, max(0, value + brightness_add)))
        g = g.point(lambda value: min(255, max(0, value + brightness_add)))
        b = b.point(lambda value: min(255, max(0, value + brightness_add)))
        image = Image.merge("RGBA", (r, g, b, a))

    image_ratio = image.width / image.height
    canvas_ratio = width / height
    if image_ratio > canvas_ratio:
        scaled_width = width
        scaled_height = max(1, round(image.height * (width / image.width)))
    else:
        scaled_height = height
        scaled_width = max(1, round(image.width * (height / image.height)))

    tile = image.resize((scaled_width, scaled_height), Image.Resampling.BICUBIC)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for y in range(0, height, tile.height):
        for x in range(0, width, tile.width):
            alpha_composite_paste(canvas, tile, (x, y))
    return canvas


def create_blurred_triangle_pattern(
    image: Image.Image,
    blur_radius: float,
    triangle_size: float,
    brightness_difference: float,
) -> Image.Image:
    blurred = image.filter(ImageFilter.GaussianBlur(blur_radius))
    if triangle_size <= 0 or brightness_difference == 0:
        return blurred

    mask = Image.new("L", blurred.size, 0)
    draw = ImageDraw.Draw(mask)
    tri_h = triangle_size * math.sqrt(3) / 2
    rows = math.ceil(blurred.height / tri_h)
    cols = math.ceil(blurred.width / triangle_size)

    for row in range(rows + 1):
        offset_y = row * tri_h
        offset_row = row % 2 == 1
        for col in range(-1, cols + 1):
            offset_x = col * triangle_size
            if offset_row:
                offset_x += triangle_size / 2
            draw.polygon(
                [
                    (offset_x + triangle_size / 2, offset_y),
                    (offset_x, offset_y + tri_h),
                    (offset_x + triangle_size, offset_y + tri_h),
                ],
                fill=255,
            )

    if np is None:
        brightened = ImageEnhance.Brightness(blurred).enhance(1 + brightness_difference)
        return Image.composite(brightened, blurred, mask)

    image_array = np.array(blurred).astype(float)
    mask_array = np.array(mask).astype(float) / 255.0
    factor = 1 + brightness_difference * mask_array
    if len(image_array.shape) == 3:
        factor = np.stack([factor] * image_array.shape[2], axis=-1)
    output = np.clip(image_array * factor, 0, 255).astype(np.uint8)
    return Image.fromarray(output).convert(blurred.mode)


def scatter_images(
    canvas: Image.Image,
    source: ImageSource,
    *,
    density: float,
    angle_range: float,
    size_range: tuple[float, float],
    rng: random.Random | random.Random,
) -> None:
    star = load_image(RenderContext(), source)
    count = int(canvas.width * canvas.height * density)
    for _ in range(count):
        size = max(1, round(rng.uniform(size_range[0], size_range[1])))
        angle = rng.uniform(0, angle_range)
        image = star.resize((size, size), Image.Resampling.BILINEAR)
        image = image.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        x = round(rng.uniform(0, canvas.width) - image.width / 2)
        y = round(rng.uniform(0, canvas.height) - image.height / 2)
        alpha_composite_paste(canvas, image, (x, y))


def draw_repeated_text(
    canvas: Image.Image,
    text: str,
    *,
    font_size: int,
    angle: float,
    line_spacing: int,
    letter_spacing: int,
    stroke_width: int,
    skew_angle: float,
    opacity: float,
    scale_x: float,
) -> None:
    if not text:
        return
    font = load_font(font_size, ORBITRON_FONT)
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_image = Image.new(
        "RGBA",
        (
            round(text_width + stroke_width * 2 + 50),
            round(text_height + stroke_width * 2 + 50),
        ),
        (0, 0, 0, 0),
    )
    ImageDraw.Draw(text_image).text(
        (stroke_width + 10, stroke_width + 10),
        text,
        font=font,
        fill=None,
        stroke_width=stroke_width,
        stroke_fill=(255, 255, 255, 255),
    )

    cropped_bbox = text_image.getbbox()
    if cropped_bbox is not None:
        text_image = text_image.crop(cropped_bbox)

    width, height = text_image.size
    text_image = text_image.resize(
        (max(1, round(width * scale_x)), height), Image.Resampling.BILINEAR
    )
    skew_radians = math.radians(skew_angle)
    tan_skew = math.tan(skew_radians)
    skew_offset = abs(text_image.height * tan_skew)
    skewed_width = round(text_image.width + skew_offset)
    x_shift = skew_offset if tan_skew < 0 else 0
    skewed = text_image.transform(
        (skewed_width, text_image.height),
        Image.Transform.AFFINE,
        (1, -tan_skew, -x_shift if tan_skew < 0 else 0, 0, 1, 0),
        resample=Image.Resampling.BILINEAR,
    )
    rotated = skewed.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    step_x = rotated.width + letter_spacing
    step_y = rotated.height + line_spacing
    cols = int(canvas.width / step_x) + 4
    rows = int(canvas.height / step_y) + 4
    for row in range(-2, rows):
        y = row * step_y
        row_offset = step_x / 2 if row % 2 else 0
        for col in range(-2, cols):
            x = col * step_x + row_offset
            alpha_composite_paste(layer, rotated, (round(x), round(y)))

    if opacity < 1:
        layer.putalpha(
            layer.getchannel("A").point(lambda value: round(value * opacity))
        )
    alpha_composite_paste(canvas, layer, (0, 0))


def with_opacity(image: Image.Image, opacity: float) -> Image.Image:
    result = image.copy()
    result.putalpha(result.getchannel("A").point(lambda value: round(value * opacity)))
    return result


def rounded_clip(image: Image.Image, radius: int) -> Image.Image:
    from PIL import ImageDraw

    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, image.width, image.height), radius=radius, fill=255
    )
    result = image.copy()
    result.putalpha(mask)
    return result
