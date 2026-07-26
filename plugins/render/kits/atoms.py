"""Mechanical atoms shared by kits.

These are the parts of a kit that carry no visual identity: text wrapping and
shrink-to-fit math, image fitting, panel child framing, and divider sizing. They
take every color, font, and radius as an argument, so a kit decides how it looks
and reuses this module only for the arithmetic.

Signature visuals -- backgrounds, glow, screentone, accent bars -- stay in each
kit's own ``components.py``. This module deliberately holds nothing that would
make two kits look alike.
"""

from typing import Literal
from pathlib import Path
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter

from plugins.render.core import Rect
from plugins.render.core import Size
from plugins.render.core import Component
from plugins.render.core import Constraints
from plugins.render.core import LayoutError
from plugins.render.core import RenderContext
from plugins.render.color import Color
from plugins.render.color import ColorLike
from plugins.render.color import normalize_color
from plugins.render.types import ImageFit
from plugins.render.types import Overflow
from plugins.render.types import TextAlign
from plugins.render.types import ImageSource
from plugins.render.layout import Frame
from plugins.render.sizing import Fit
from plugins.render.sizing import Fill
from plugins.render.sizing import Fixed
from plugins.render.sizing import Fraction
from plugins.render.sizing import SizeValue
from plugins.render.sizing import as_size_value
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste
from plugins.render.primitives import draw_rounded_rectangle
from plugins.render.text_layout import ellipsis as _ellipsis
from plugins.render.text_layout import wrap_text as _wrap_text
from plugins.render.text_layout import text_width as _text_width
from plugins.render.text_layout import draw_text_line as _draw_text_line
from plugins.render.text_layout import merge_line_limits as _merge_line_limits
from plugins.render.text_layout import display_text_width as _display_text_width
from plugins.render.text_layout import max_lines_for_height as _max_lines_for_height


@dataclass(frozen=True)
class KitText:
    """Text renderer parameterized by font file and color."""

    text: str
    font: str | Path | None = None
    font_size: int = 40
    color: ColorLike = (80, 80, 80, 255)
    align: TextAlign = "left"
    wrap: bool = True
    max_lines: int | None = None
    overflow: Overflow = "ellipsis"
    line_height: int | None = None

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        lines, font_size = self._layout_text(constraints)
        font = load_font(font_size, self.font)
        line_height = self.line_height or round(font_size * 1.35)
        width = max((_text_width(line, font) for line in lines), default=0)
        if ctx.pixel_ratio > 1:
            # TrueType metrics are not linear in size: a line measured at the
            # logical size can be narrower than 1/ratio of the same line at
            # draw size (e.g. "+1665 Pt" is 108px at 26 but 222px at 52), and
            # render() draws on a rect-sized layer at ``pixel_ratio`` scale,
            # clipping the last glyph. Measure at draw size too and keep the
            # safer width.
            draw_font = load_font(font_size * ctx.pixel_ratio, self.font)
            draw_width = max(
                (_text_width(line, draw_font) for line in lines), default=0
            )
            width = max(width, -(-draw_width // ctx.pixel_ratio))
        if self.wrap and constraints.max_width is not None:
            width = min(width, constraints.max_width)
        return constraints.clamp(Size(width, line_height * max(1, len(lines))))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        constraints = ctx.unscale_constraints(
            Constraints(max_width=rect.width, max_height=rect.height)
        )
        lines, font_size = self._layout_text(constraints)
        font = load_font(max(1, ctx.scale_px(font_size)), self.font)
        line_height = ctx.scale_px(self.line_height or round(font_size * 1.35))
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        y = 0
        for line in lines:
            if y >= rect.height:
                break
            line_width = _display_text_width(line, font, rect.width)
            if self.align == "center":
                x = max(0, (rect.width - line_width) // 2)
            elif self.align == "right":
                x = max(0, rect.width - line_width)
            else:
                x = 0
            _draw_text_line(
                draw,
                (x, y),
                line,
                font,
                normalize_color(self.color),
                max_width=line_width,
            )
            y += line_height
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))

    def _layout_text(self, constraints: Constraints) -> tuple[list[str], int]:
        font_size = self.font_size
        if self.overflow == "shrink" and (
            constraints.max_width is not None or constraints.max_height is not None
        ):
            while font_size > 8:
                font = load_font(font_size, self.font)
                line_height = self.line_height or round(font_size * 1.35)
                lines = _wrap_text(
                    self.text, font, constraints.max_width if self.wrap else None
                )
                width_fits = (
                    constraints.max_width is None
                    or self.wrap
                    or _text_width(self.text, font) <= constraints.max_width
                )
                height_fits = constraints.max_height is None or len(
                    lines
                ) <= _max_lines_for_height(constraints.max_height, line_height)
                if width_fits and height_fits:
                    break
                font_size -= 1
        font = load_font(font_size, self.font)
        line_height = self.line_height or round(font_size * 1.35)
        lines = _wrap_text(
            self.text, font, constraints.max_width if self.wrap else None
        )
        max_lines = _merge_line_limits(
            self.max_lines,
            (
                None
                if constraints.max_height is None
                else _max_lines_for_height(constraints.max_height, line_height)
            ),
        )
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            if self.overflow == "ellipsis":
                lines[-1] = _ellipsis(
                    lines[-1], font, constraints.max_width, force=True
                )
        elif (
            self.overflow == "ellipsis"
            and not self.wrap
            and constraints.max_width is not None
        ):
            lines = [_ellipsis(line, font, constraints.max_width) for line in lines]
        return lines or [""], font_size


@dataclass(frozen=True)
class KitImage:
    """Image renderer with contain, cover, stretch, opacity, and rounded clipping."""

    source: ImageSource
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    fit: ImageFit = "contain"
    opacity: float = 1.0
    radius: int = 0

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        image = load_image(ctx, self.source)
        width_value = as_size_value(self.width)
        height_value = as_size_value(self.height)
        if isinstance(width_value, Fit) and isinstance(height_value, Fit):
            return constraints.clamp(fit_intrinsic_image_size(image, constraints))

        width = resolve_axis(
            width_value, constraints.max_width, image.width, "KitImage.width"
        )
        height = resolve_axis(
            height_value, constraints.max_height, image.height, "KitImage.height"
        )
        if isinstance(width_value, Fit) and image.height:
            width = round(image.width * (height / image.height))
        if isinstance(height_value, Fit) and image.width:
            height = round(image.height * (width / image.width))
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        image = load_image(ctx, self.source)
        if self.fit == "stretch":
            resized = image.resize((rect.width, rect.height), Image.Resampling.LANCZOS)
        elif self.fit == "cover":
            resized = resize_cover(image, rect.width, rect.height)
        else:
            resized = resize_contain(image, rect.width, rect.height)
        if self.opacity < 1:
            resized = with_opacity(resized, self.opacity)
        if self.radius > 0:
            resized = rounded_clip(resized, ctx.scale_px(self.radius))
        alpha_composite_paste(
            canvas,
            resized,
            (
                rect.x + max(0, (rect.width - resized.width) // 2),
                rect.y + max(0, (rect.height - resized.height) // 2),
            ),
        )


@dataclass(frozen=True)
class KitPanel:
    """Rounded panel with an optional outline, stretching an optional child."""

    child: Component | None = None
    fill: ColorLike = (255, 255, 255, 230)
    radius: int = 32
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    border_color: ColorLike | None = None
    border_width: int = 0

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return Frame(
            self.child,
            width=self.width,
            height=self.height,
            padding=self.padding,
            align_x="stretch",
            align_y="stretch",
        ).measure(ctx, constraints)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        draw_panel_surface(
            ctx,
            canvas,
            rect,
            fill=self.fill,
            radius=self.radius,
            border_color=self.border_color,
            border_width=self.border_width,
        )
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)


@dataclass(frozen=True)
class KitSeparator:
    """Rounded divider line for horizontal or vertical separation."""

    orientation: Literal["horizontal", "vertical"] = "horizontal"
    length: SizeValue | int | None = None
    thickness: int = 2
    color: ColorLike = (170, 170, 170, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        if self.orientation == "horizontal":
            return Size(
                fixed_or_bound(
                    self.length, constraints.max_width, "KitSeparator.length"
                ),
                self.thickness,
            )
        return Size(
            self.thickness,
            fixed_or_bound(
                self.length, constraints.max_height, "KitSeparator.length"
            ),
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        ImageDraw.Draw(canvas).rounded_rectangle(
            (rect.x, rect.y, rect.right, rect.bottom),
            radius=max(1, min(rect.width, rect.height) // 2),
            fill=normalize_color(self.color),
        )


def draw_panel_surface(
    ctx: RenderContext,
    canvas: Image.Image,
    rect: Rect,
    *,
    fill: ColorLike,
    radius: int,
    border_color: ColorLike | None = None,
    border_width: int = 0,
) -> None:
    """Paint a rounded panel surface with an optional inset outline.

    Args:
        ctx: Shared render context.
        canvas: Destination image.
        rect: Panel rectangle in render pixels.
        fill: Panel fill color.
        radius: Corner radius in logical pixels.
        border_color: Optional outline color.
        border_width: Outline width in logical pixels.
    """

    scaled_radius = ctx.scale_px(radius)
    draw_rounded_rectangle(
        canvas,
        (rect.x, rect.y, rect.right, rect.bottom),
        scaled_radius,
        fill,
    )
    if border_color is None or border_width <= 0:
        return
    stroke = max(1, ctx.scale_px(border_width))
    draw_rounded_rectangle(
        canvas,
        (rect.x, rect.y, rect.right, rect.bottom),
        scaled_radius,
        None,
        outline=border_color,
        width=stroke,
    )


def draw_soft_shadow(
    canvas: Image.Image,
    rect: Rect,
    *,
    radius: int,
    color: Color,
    blur: int,
    offset: tuple[int, int] = (0, 0),
    spread: int = 0,
) -> None:
    """Composite a blurred rounded silhouette behind a panel.

    Used for both drop shadows and outer glow; the difference is only the color
    and offset a kit passes in.

    Args:
        canvas: Destination image.
        rect: Panel rectangle in render pixels.
        radius: Corner radius in render pixels.
        color: Shadow color including alpha.
        blur: Gaussian blur radius in render pixels.
        offset: Shadow offset in render pixels.
        spread: Pixels the silhouette grows beyond the panel.
    """

    if rect.width <= 0 or rect.height <= 0:
        return
    pad = max(1, blur * 3 + spread)
    layer_width = rect.width + spread * 2 + pad * 2
    layer_height = rect.height + spread * 2 + pad * 2
    layer = Image.new("RGBA", (layer_width, layer_height), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        (pad, pad, layer_width - pad - 1, layer_height - pad - 1),
        radius=max(0, radius + spread),
        fill=color,
    )
    if blur > 0:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    alpha_composite_paste(
        canvas,
        layer,
        (rect.x - spread - pad + offset[0], rect.y - spread - pad + offset[1]),
    )


def vertical_gradient(size: Size, top: Color, bottom: Color) -> Image.Image:
    """Build a top-to-bottom linear gradient image.

    Args:
        size: Output size in pixels.
        top: Color at the top edge.
        bottom: Color at the bottom edge.

    Returns:
        Gradient image in RGBA mode. A zero-sized request yields a zero-sized
        image, matching a plain ``Image.new`` background.
    """

    if size.width <= 0 or size.height <= 0:
        return Image.new("RGBA", (max(0, size.width), max(0, size.height)), (0, 0, 0, 0))

    column = Image.new("RGBA", (1, size.height))
    pixels = column.load()
    for y in range(size.height):
        ratio = y / max(1, size.height - 1)
        pixels[0, y] = mix_color(top, bottom, ratio)
    return column.resize((size.width, size.height), Image.Resampling.BILINEAR)


def mix_color(start: Color, end: Color, ratio: float) -> Color:
    """Linearly interpolate between two colors.

    Args:
        start: Color at ``ratio`` 0.
        end: Color at ``ratio`` 1.
        ratio: Interpolation position, clamped to ``[0, 1]``.

    Returns:
        Interpolated color.
    """

    ratio = min(1.0, max(0.0, ratio))
    return (
        round(start[0] + (end[0] - start[0]) * ratio),
        round(start[1] + (end[1] - start[1]) * ratio),
        round(start[2] + (end[2] - start[2]) * ratio),
        round(start[3] + (end[3] - start[3]) * ratio),
    )


def load_image(ctx: RenderContext, source: ImageSource) -> Image.Image:
    """Load an image source through the render cache."""

    if isinstance(source, Image.Image):
        return source.convert("RGBA").copy()
    return ctx.image_cache.load(source)


def fit_intrinsic_image_size(image: Image.Image, constraints: Constraints) -> Size:
    """Scale an image's intrinsic size down into the given constraints."""

    width = image.width
    height = image.height
    if width <= 0 or height <= 0:
        return Size(0, 0)

    ratio = 1.0
    if constraints.max_width is not None:
        ratio = min(ratio, constraints.max_width / width)
    if constraints.max_height is not None:
        ratio = min(ratio, constraints.max_height / height)
    ratio = max(0, ratio)
    return Size(max(1, round(width * ratio)), max(1, round(height * ratio)))


def resize_contain(image: Image.Image, width: int, height: int) -> Image.Image:
    """Resize an image to fit entirely inside a box."""

    if width <= 0 or height <= 0:
        return Image.new("RGBA", (0, 0))
    ratio = min(width / image.width, height / image.height)
    return image.resize(
        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
        Image.Resampling.LANCZOS,
    )


def resize_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    """Resize and center-crop an image to fill a box."""

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


def with_opacity(image: Image.Image, opacity: float) -> Image.Image:
    """Return a copy of an image with its alpha channel scaled."""

    result = image.copy()
    result.putalpha(result.getchannel("A").point(lambda value: round(value * opacity)))
    return result


def rounded_clip(image: Image.Image, radius: int) -> Image.Image:
    """Return a copy of an image clipped to a rounded rectangle."""

    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, image.width, image.height), radius=radius, fill=255
    )
    result = image.copy()
    result.putalpha(mask)
    return result


def resolve_axis(
    value: SizeValue, bound: int | None, intrinsic: int, owner: str
) -> int:
    """Resolve a sizing token against a parent bound and an intrinsic size."""

    if isinstance(value, Fit):
        return intrinsic
    if isinstance(value, Fixed):
        return value.value
    if isinstance(value, Fill):
        if bound is None:
            raise LayoutError(f"{owner} uses Fill(), but parent axis is unbounded")
        return bound
    if isinstance(value, Fraction):
        if bound is None:
            raise LayoutError(f"{owner} uses Fraction(), but parent axis is unbounded")
        return round(bound * value.value)
    return intrinsic


def fixed_or_bound(
    value: SizeValue | int | None, bound: int | None, owner: str
) -> int:
    """Resolve a sizing token that has no intrinsic size, such as a divider."""

    size_value = as_size_value(value)
    if isinstance(size_value, Fit):
        return 0
    if isinstance(size_value, Fixed):
        return size_value.value
    if isinstance(size_value, (Fill, Fraction)):
        if bound is None:
            raise LayoutError(f"{owner} requires bounded parent axis")
        return (
            bound if isinstance(size_value, Fill) else round(bound * size_value.value)
        )
    return 0


def draw_aligned_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    bbox: tuple[int, int, int, int],
    fill: ColorLike,
    *,
    align: TextAlign = "center",
    left_offset: int = 0,
) -> None:
    """Draw a single vertically centered text line inside a box."""

    left, top, right, bottom = bbox
    text_bbox = draw.textbbox((0, 0), text, font=font)
    width = text_bbox[2] - text_bbox[0]
    height = text_bbox[3] - text_bbox[1]
    if align == "center":
        x = left + (right - left - width) // 2 - text_bbox[0]
    elif align == "right":
        x = right - width - text_bbox[0]
    else:
        x = left + left_offset - text_bbox[0]
    draw.text(
        (x, top + (bottom - top - height) // 2 - text_bbox[1]),
        text,
        font=font,
        fill=normalize_color(fill),
    )
