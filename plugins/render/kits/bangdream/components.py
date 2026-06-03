from typing import Literal
from pathlib import Path
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw

from plugins.render.core import Rect
from plugins.render.core import Size
from plugins.render.core import Component
from plugins.render.core import Constraints
from plugins.render.core import LayoutError
from plugins.render.core import RenderContext
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
from plugins.render.primitives import draw_pill
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

from .backgrounds import load_image
from .backgrounds import resize_cover
from .backgrounds import rounded_clip
from .backgrounds import with_opacity
from .backgrounds import resize_contain


@dataclass(frozen=True)
class BanGDreamText:
    """Text renderer using the bundled BanG Dream! font and wrapping rules."""

    text: str
    font: str | Path
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
class BanGDreamImage:
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
            return constraints.clamp(_fit_intrinsic_image_size(image, constraints))

        width = _resolve_image_axis(
            width_value, constraints.max_width, image.width, "BanGDreamImage.width"
        )
        height = _resolve_image_axis(
            height_value, constraints.max_height, image.height, "BanGDreamImage.height"
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
class BanGDreamPanel:
    """Rounded translucent panel that stretches and renders an optional child."""

    child: Component | None = None
    fill: ColorLike = (255, 255, 255, 208)
    radius: int = 48
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None

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
        draw_rounded_rectangle(
            canvas,
            (rect.x, rect.y, rect.right, rect.bottom),
            ctx.scale_px(self.radius),
            self.fill,
        )
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)


@dataclass(frozen=True)
class BanGDreamSeparator:
    """Rounded divider line for horizontal or vertical separation."""

    orientation: Literal["horizontal", "vertical"] = "horizontal"
    length: SizeValue | int | None = None
    thickness: int = 2
    color: ColorLike = (170, 170, 170, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        if self.orientation == "horizontal":
            return Size(
                _fixed_or_bound(
                    self.length, constraints.max_width, "BanGDreamSeparator.length"
                ),
                self.thickness,
            )
        return Size(
            self.thickness,
            _fixed_or_bound(
                self.length, constraints.max_height, "BanGDreamSeparator.length"
            ),
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        ImageDraw.Draw(canvas).rounded_rectangle(
            (rect.x, rect.y, rect.right, rect.bottom),
            radius=max(1, min(rect.width, rect.height) // 2),
            fill=normalize_color(self.color),
        )


@dataclass(frozen=True)
class BanGDreamTitlePill:
    """Two-layer pill header with a colored title band and white subtitle band."""

    title: str
    subtitle: str
    title_font: str | Path
    subtitle_font: str | Path
    pill_width: int = 500
    pill_height: int = 57
    title_fill: ColorLike = (234, 78, 116, 255)
    subtitle_fill: ColorLike = (255, 255, 255, 255)
    title_text_color: ColorLike = (255, 255, 255, 255)
    subtitle_text_color: ColorLike = (80, 80, 80, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        subtitle_pill_height = self.pill_height * 85 // 62
        subtitle_pill_width = self.pill_width * 625 // 570
        overlap_height = self.pill_height * 9 // 62
        return constraints.clamp(
            Size(
                subtitle_pill_width,
                self.pill_height + subtitle_pill_height - overlap_height,
            )
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        measured = self.measure(ctx, Constraints())
        scaled_measured = ctx.scale_size(measured)
        layer = Image.new(
            "RGBA", (scaled_measured.width, scaled_measured.height), (0, 0, 0, 0)
        )
        pill_width = ctx.scale_px(self.pill_width)
        pill_height = ctx.scale_px(self.pill_height)
        subtitle_pill_width = ctx.scale_px(self.pill_width * 625 // 570)
        overlap_height = ctx.scale_px(self.pill_height * 9 // 62)
        subtitle_top = pill_height - overlap_height
        draw_pill(
            layer,
            (0, subtitle_top, subtitle_pill_width, scaled_measured.height),
            self.subtitle_fill,
        )
        draw_pill(layer, (0, 0, pill_width, pill_height), self.title_fill)
        draw = ImageDraw.Draw(layer)
        title_font = load_font(
            ctx.scale_px(self.pill_height * 33 // 61), self.title_font
        )
        subtitle_font = load_font(
            ctx.scale_px((self.pill_height * 85 // 62) * 36 // 75),
            self.subtitle_font,
        )
        _draw_left_aligned_text(
            draw,
            self.title,
            title_font,
            (0, 0, pill_width, pill_height),
            self.title_text_color,
            left_offset=ctx.scale_px(self.pill_height // 2),
        )
        _draw_left_aligned_text(
            draw,
            self.subtitle,
            subtitle_font,
            (0, subtitle_top, subtitle_pill_width, scaled_measured.height),
            self.subtitle_text_color,
            left_offset=ctx.scale_px((self.pill_height * 85 // 62) // 2),
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class BanGDreamPill:
    """Generic pill-shaped label."""

    text: str
    font: str | Path
    width: SizeValue | int
    height: SizeValue | int
    font_size: int = 30
    fill: ColorLike | None = None
    text_color: ColorLike | None = None
    align: TextAlign = "center"

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        font = load_font(self.font_size, self.font)
        width = _resolve_pill_axis(
            as_size_value(self.width),
            constraints.max_width,
            _text_width(self.text, font),
            "BanGDreamPill.width",
        )
        height = _resolve_pill_axis(
            as_size_value(self.height),
            constraints.max_height,
            self.font_size,
            "BanGDreamPill.height",
        )
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw_pill(
            layer,
            (0, 0, rect.width, rect.height),
            self.fill or (234, 78, 116, 255),
        )
        font = load_font(ctx.scale_px(self.font_size), self.font)
        _draw_aligned_text(
            ImageDraw.Draw(layer),
            self.text,
            font,
            (0, 0, rect.width, rect.height),
            self.text_color or (255, 255, 255, 255),
            align=self.align,
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


def _draw_left_aligned_text(
    draw: ImageDraw.ImageDraw, text: str, font, bbox, fill: ColorLike, left_offset: int
) -> None:
    _draw_aligned_text(
        draw,
        text,
        font,
        bbox,
        fill,
        align="left",
        left_offset=left_offset,
    )


def _draw_aligned_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    bbox,
    fill: ColorLike,
    *,
    align: TextAlign,
    left_offset: int = 0,
) -> None:
    left, top, _right, bottom = bbox
    text_bbox = draw.textbbox((0, 0), text, font=font)
    width = text_bbox[2] - text_bbox[0]
    height = text_bbox[3] - text_bbox[1]
    if align == "center":
        x = left + (_right - left - width) // 2 - text_bbox[0]
    elif align == "right":
        x = _right - width - text_bbox[0]
    else:
        x = left + left_offset - text_bbox[0]
    draw.text(
        (x, top + (bottom - top - height) // 2 - text_bbox[1]),
        text,
        font=font,
        fill=normalize_color(fill),
    )


def _fit_intrinsic_image_size(image: Image.Image, constraints: Constraints) -> Size:
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


def _fixed_or_bound(
    value: SizeValue | int | None, bound: int | None, owner: str
) -> int:
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


def _resolve_pill_axis(
    value: SizeValue,
    bound: int | None,
    intrinsic: int,
    owner: str,
) -> int:
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


def _resolve_image_axis(
    value: SizeValue, bound: int | None, intrinsic: int, owner: str
) -> int:
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
