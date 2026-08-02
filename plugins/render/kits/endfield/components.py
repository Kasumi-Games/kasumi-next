"""Industrial information-system visuals for the Endfield kit.

The geometry and palette are derived from the live Endfield site rather than
from a screenshot alone.  The site repeatedly combines ``#191919`` ink,
``#fffa00`` signal yellow, cool neutral surfaces, 4--6 px diagonal hatching,
thin registration lines, and clipped rectangular information frames.  These
components translate those CSS primitives into deterministic Pillow drawing.
"""

from pathlib import Path
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw

from plugins.render.core import Rect
from plugins.render.core import Size
from plugins.render.core import Component
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.color import Color
from plugins.render.color import ColorLike
from plugins.render.color import rgba
from plugins.render.color import normalize_color
from plugins.render.layout import Frame
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste
from plugins.render.text_layout import text_width
from plugins.render.text_layout import draw_text_line

from ..atoms import fixed_or_bound
from ..atoms import draw_panel_surface
from ..fonts import CHINESE_FONT
from ..fonts import DISPLAY_FONT

INK = rgba(25, 25, 25, 255)
SIGNAL = rgba(255, 250, 0, 255)
PAPER = rgba(247, 247, 244, 255)
RULE = rgba(217, 217, 217, 255)


@dataclass(frozen=True)
class EndfieldBackground:
    """Pale technical field with grid, signal flag, and registration marks."""

    fill: Color = PAPER
    ink: Color = INK
    signal: Color = SIGNAL
    grid_spacing: int = 64
    hatch_spacing: int = 6

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new("RGBA", (size.width, size.height), self.fill)
        if size.width <= 0 or size.height <= 0:
            return canvas

        decoration = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(decoration, "RGBA")
        grid = max(24, ctx.scale_px(self.grid_spacing))
        thin = max(1, ctx.scale_px(1))

        # The live site lays faint vertical/horizontal construction lines over
        # both light and dark sections.  Keep them quiet enough to sit behind
        # arbitrary renderer content.
        for x in range(0, size.width + grid, grid):
            draw.line((x, 0, x, size.height), fill=(*self.ink[:3], 13), width=thin)
        for y in range(0, size.height + grid, grid):
            draw.line((0, y, size.width, y), fill=(*self.ink[:3], 10), width=thin)

        # Operator pages use a tall #fffa00 flag behind the hero illustration.
        # Its restrained card-sized translation anchors the upper-right field.
        flag_left = round(size.width * 0.69)
        flag_right = min(size.width, round(size.width * 0.83))
        flag_bottom = min(size.height, round(size.height * 0.31))
        if flag_right > flag_left and flag_bottom > 0:
            draw.rectangle(
                (flag_left, 0, flag_right, flag_bottom),
                fill=self.signal,
            )
            self._draw_hatch(
                draw,
                (flag_left, 0, flag_right, flag_bottom),
                ctx,
                color=(*self.ink[:3], 17),
            )

        # A shallow CSS hatch band appears behind the operator dossier copy.
        band_top = round(size.height * 0.72)
        self._draw_hatch(
            draw,
            (0, band_top, size.width, size.height),
            ctx,
            color=(*self.ink[:3], 15),
        )

        self._draw_registration_marks(draw, ctx, size)
        alpha_composite_paste(canvas, decoration, (0, 0))
        return canvas

    def _draw_hatch(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        ctx: RenderContext,
        *,
        color: Color,
    ) -> None:
        left, top, right, bottom = box
        spacing = max(4, ctx.scale_px(self.hatch_spacing))
        width = max(1, ctx.scale_px(1))
        height = max(0, bottom - top)
        for offset in range(-height, max(0, right - left) + height, spacing):
            x0 = left + offset
            draw.line(
                (x0, bottom, x0 + height, top),
                fill=color,
                width=width,
            )

    def _draw_registration_marks(
        self,
        draw: ImageDraw.ImageDraw,
        ctx: RenderContext,
        size: Size,
    ) -> None:
        stroke = max(1, ctx.scale_px(2))
        margin = max(10, ctx.scale_px(18))
        arm = max(8, ctx.scale_px(18))
        for x, y, sx, sy in (
            (margin, margin, 1, 1),
            (size.width - margin, margin, -1, 1),
            (margin, size.height - margin, 1, -1),
            (size.width - margin, size.height - margin, -1, -1),
        ):
            draw.line((x, y, x + sx * arm, y), fill=(*self.ink[:3], 75), width=stroke)
            draw.line((x, y, x, y + sy * arm), fill=(*self.ink[:3], 75), width=stroke)

        tick_y = max(margin, size.height - ctx.scale_px(34))
        tick = max(2, ctx.scale_px(4))
        gap = max(5, ctx.scale_px(8))
        start = max(margin * 2, round(size.width * 0.64))
        for x in range(start, size.width - margin, gap):
            draw.rectangle((x, tick_y, x + tick, tick_y + tick), fill=self.ink)


@dataclass(frozen=True)
class EndfieldPanel:
    """Clipped dossier panel with a signal rail and offset technical shadow."""

    child: Component | None = None
    fill: ColorLike = rgba(255, 255, 255, 244)
    radius: int | None = None
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    ink_color: ColorLike = INK
    signal_color: ColorLike = SIGNAL
    border_width: int = 2
    cut: int = 16
    rail: bool = True

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
        if rect.width <= 0 or rect.height <= 0:
            return
        if self.radius is not None:
            draw_panel_surface(
                ctx,
                canvas,
                rect,
                fill=self.fill,
                radius=self.radius,
                border_color=self.ink_color,
                border_width=self.border_width,
            )
        else:
            self._draw_clipped_surface(ctx, canvas, rect)
        Frame(
            self.child,
            padding=self.padding,
            align_x="stretch",
            align_y="stretch",
        ).render(ctx, canvas, rect)

    def _draw_clipped_surface(
        self,
        ctx: RenderContext,
        canvas: Image.Image,
        rect: Rect,
    ) -> None:
        cut = min(ctx.scale_px(self.cut), rect.width // 4, rect.height // 4)
        stroke = max(1, ctx.scale_px(self.border_width))
        points = (
            (rect.x + cut, rect.y),
            (rect.right - 1, rect.y),
            (rect.right - 1, rect.bottom - cut - 1),
            (rect.right - cut - 1, rect.bottom - 1),
            (rect.x, rect.bottom - 1),
            (rect.x, rect.y + cut),
        )
        shadow_offset = max(2, ctx.scale_px(5))
        shadow_points = tuple((x + shadow_offset, y + shadow_offset) for x, y in points)
        draw = ImageDraw.Draw(canvas)
        draw.polygon(shadow_points, fill=rgba(25, 25, 25, 34))
        draw.polygon(points, fill=normalize_color(self.fill))
        draw.line(
            (*points, points[0]),
            fill=normalize_color(self.ink_color),
            width=stroke,
            joint="curve",
        )

        if not self.rail:
            return
        signal = normalize_color(self.signal_color)
        rail_height = max(3, ctx.scale_px(5))
        rail_left = rect.x + cut + stroke
        rail_right = min(
            rect.right - stroke - 1,
            rail_left + max(ctx.scale_px(44), round(rect.width * 0.23)),
        )
        draw.rectangle(
            (rail_left, rect.y + stroke, rail_right, rect.y + rail_height),
            fill=signal,
        )
        block = max(4, ctx.scale_px(7))
        draw.rectangle(
            (
                rect.right - cut - block,
                rect.bottom - block - stroke,
                rect.right - cut,
                rect.bottom - stroke,
            ),
            fill=normalize_color(self.ink_color),
        )


@dataclass(frozen=True)
class EndfieldTitle:
    """Bracketed dossier heading with REC metadata and a yellow baseline."""

    text: str
    font: str | Path | None = CHINESE_FONT
    display_font: str | Path | None = DISPLAY_FONT
    font_size: int = 54
    color: ColorLike = INK
    signal_color: ColorLike = SIGNAL
    min_font_size: int = 18

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        font_size = self._fit_font_size(constraints.max_width)
        face = load_font(font_size, self.font)
        desired_width = text_width(self.text, face) + font_size * 2
        width = (
            min(desired_width, constraints.max_width)
            if constraints.max_width is not None
            else desired_width
        )
        return constraints.clamp(Size(width, round(font_size * 1.72)))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        logical_width = ctx.unscale_px(rect.width)
        font_size = self._fit_font_size(logical_width)
        font = load_font(max(1, ctx.scale_px(font_size)), self.font)
        micro_font = load_font(max(1, ctx.scale_px(max(9, font_size // 5))), self.display_font)
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        ink = normalize_color(self.color)
        signal = normalize_color(self.signal_color)

        micro = "REC  //  ENDFIELD"
        draw.text((0, 0), micro, font=micro_font, fill=ink)
        face_y = max(ctx.scale_px(14), round(rect.height * 0.20))
        bracket_width = max(2, ctx.scale_px(3))
        bracket_height = min(rect.height - face_y - ctx.scale_px(8), ctx.scale_px(font_size))
        bracket_arm = max(5, ctx.scale_px(10))
        draw.line(
            (0, face_y, 0, face_y + bracket_height),
            fill=ink,
            width=bracket_width,
        )
        draw.line((0, face_y, bracket_arm, face_y), fill=ink, width=bracket_width)
        draw.line(
            (0, face_y + bracket_height, bracket_arm, face_y + bracket_height),
            fill=ink,
            width=bracket_width,
        )

        x = bracket_arm + ctx.scale_px(10)
        draw_text_line(
            draw,
            (x, face_y - ctx.scale_px(5)),
            self.text,
            font,
            ink,
            max_width=max(1, rect.width - x - bracket_arm - ctx.scale_px(10)),
        )
        right = rect.width - 1
        draw.line(
            (right, face_y, right, face_y + bracket_height),
            fill=ink,
            width=bracket_width,
        )
        draw.line((right - bracket_arm, face_y, right, face_y), fill=ink, width=bracket_width)
        draw.line(
            (
                right - bracket_arm,
                face_y + bracket_height,
                right,
                face_y + bracket_height,
            ),
            fill=ink,
            width=bracket_width,
        )
        baseline_y = min(rect.height - 1, face_y + bracket_height + ctx.scale_px(5))
        draw.rectangle(
            (x, baseline_y, min(right, x + round(rect.width * 0.42)), baseline_y + max(2, ctx.scale_px(3))),
            fill=signal,
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))

    def _fit_font_size(self, max_width: int | None) -> int:
        font_size = max(self.min_font_size, self.font_size)
        if max_width is None:
            return font_size
        reserve = font_size * 2
        while font_size > self.min_font_size:
            font = load_font(font_size, self.font)
            if text_width(self.text, font) + reserve <= max_width:
                break
            font_size -= 1
            reserve = font_size * 2
        return font_size


@dataclass(frozen=True)
class EndfieldSeparator:
    """Segmented technical rule with a yellow signal lead."""

    orientation: str = "horizontal"
    length: SizeValue | int | None = None
    thickness: int = 3
    color: ColorLike = INK
    signal_color: ColorLike = SIGNAL

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        if self.orientation == "horizontal":
            return Size(
                fixed_or_bound(
                    self.length,
                    constraints.max_width,
                    "EndfieldSeparator.length",
                ),
                self.thickness,
            )
        return Size(
            self.thickness,
            fixed_or_bound(
                self.length,
                constraints.max_height,
                "EndfieldSeparator.length",
            ),
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        draw = ImageDraw.Draw(canvas)
        ink = normalize_color(self.color)
        signal = normalize_color(self.signal_color)
        if self.orientation == "horizontal":
            lead = max(ctx.scale_px(22), round(rect.width * 0.18))
            gap = max(2, ctx.scale_px(4))
            draw.rectangle((rect.x, rect.y, min(rect.right, rect.x + lead), rect.bottom), fill=signal)
            draw.rectangle(
                (min(rect.right, rect.x + lead + gap), rect.y, rect.right, rect.bottom),
                fill=ink,
            )
        else:
            lead = max(ctx.scale_px(22), round(rect.height * 0.18))
            gap = max(2, ctx.scale_px(4))
            draw.rectangle((rect.x, rect.y, rect.right, min(rect.bottom, rect.y + lead)), fill=signal)
            draw.rectangle(
                (rect.x, min(rect.bottom, rect.y + lead + gap), rect.right, rect.bottom),
                fill=ink,
            )
