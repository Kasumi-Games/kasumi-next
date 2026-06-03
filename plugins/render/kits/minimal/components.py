from typing import Literal
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
class MinimalBackground:
    fill: ColorLike = (255, 255, 255, 255)

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        return Image.new("RGBA", (size.width, size.height), normalize_color(self.fill))


@dataclass(frozen=True)
class MinimalText:
    text: str
    font_size: int = 40
    color: ColorLike = (80, 80, 80, 255)
    align: TextAlign = "left"
    wrap: bool = True
    max_lines: int | None = None
    overflow: Overflow = "ellipsis"
    line_height: int | None = None

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        lines, font_size = self._layout_text(constraints)
        font = load_font(font_size)
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
        font = load_font(max(1, ctx.scale_px(font_size)))
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
                font = load_font(font_size)
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
        font = load_font(font_size)
        line_height = self.line_height or round(font_size * 1.35)
        lines = _wrap_text(
            self.text, font, constraints.max_width if self.wrap else None
        )
        max_lines = _merge_line_limits(
            self.max_lines,
            None
            if constraints.max_height is None
            else _max_lines_for_height(constraints.max_height, line_height),
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
class MinimalImage:
    source: ImageSource
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    fit: ImageFit = "contain"
    opacity: float = 1.0
    radius: int = 0

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        image = _load_image(ctx, self.source)
        width_value = as_size_value(self.width)
        height_value = as_size_value(self.height)
        if isinstance(width_value, Fit) and isinstance(height_value, Fit):
            return constraints.clamp(_fit_intrinsic_image_size(image, constraints))

        width = _resolve_image_axis(
            width_value, constraints.max_width, image.width, "MinimalImage.width"
        )
        height = _resolve_image_axis(
            height_value, constraints.max_height, image.height, "MinimalImage.height"
        )
        if isinstance(width_value, Fit) and image.height:
            width = round(image.width * (height / image.height))
        if isinstance(height_value, Fit) and image.width:
            height = round(image.height * (width / image.width))
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        image = _load_image(ctx, self.source)
        if self.fit == "stretch":
            resized = image.resize((rect.width, rect.height), Image.Resampling.LANCZOS)
        elif self.fit == "cover":
            resized = _resize_cover(image, rect.width, rect.height)
        else:
            resized = _resize_contain(image, rect.width, rect.height)
        if self.opacity < 1:
            resized = _with_opacity(resized, self.opacity)
        if self.radius > 0:
            resized = _rounded_clip(resized, ctx.scale_px(self.radius))
        alpha_composite_paste(
            canvas,
            resized,
            (
                rect.x + max(0, (rect.width - resized.width) // 2),
                rect.y + max(0, (rect.height - resized.height) // 2),
            ),
        )


@dataclass(frozen=True)
class MinimalPanel:
    child: Component | None = None
    fill: ColorLike = (245, 245, 245, 255)
    radius: int = 20
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
class MinimalSeparator:
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    length: SizeValue | int | None = None
    thickness: int = 2
    color: ColorLike = (170, 170, 170, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        if self.orientation == "horizontal":
            return Size(
                _fixed_or_bound(
                    self.length, constraints.max_width, "MinimalSeparator.length"
                ),
                self.thickness,
            )
        return Size(
            self.thickness,
            _fixed_or_bound(
                self.length, constraints.max_height, "MinimalSeparator.length"
            ),
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        ImageDraw.Draw(canvas).rounded_rectangle(
            (rect.x, rect.y, rect.right, rect.bottom),
            radius=max(1, min(rect.width, rect.height) // 2),
            fill=normalize_color(self.color),
        )


def _load_image(ctx: RenderContext, source: ImageSource) -> Image.Image:
    if isinstance(source, Image.Image):
        return source.convert("RGBA").copy()
    return ctx.image_cache.load(source)


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


def _resize_contain(image: Image.Image, width: int, height: int) -> Image.Image:
    if width <= 0 or height <= 0:
        return Image.new("RGBA", (0, 0))
    ratio = min(width / image.width, height / image.height)
    return image.resize(
        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
        Image.Resampling.LANCZOS,
    )


def _resize_cover(image: Image.Image, width: int, height: int) -> Image.Image:
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


def _with_opacity(image: Image.Image, opacity: float) -> Image.Image:
    result = image.copy()
    result.putalpha(result.getchannel("A").point(lambda value: round(value * opacity)))
    return result


def _rounded_clip(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, image.width, image.height), radius=radius, fill=255
    )
    result = image.copy()
    result.putalpha(mask)
    return result


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
