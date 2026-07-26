"""Signature visuals for the manga kit."""

import math
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
from plugins.render.layout import Frame
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import alpha_composite_paste

from ..atoms import draw_panel_surface


@dataclass(frozen=True)
class MangaBackground:
    """Printed-paper backdrop: halftone screentone plus corner speed lines."""

    fill: Color = rgba(246, 243, 236, 255)
    dot_color: Color = rgba(24, 24, 26, 58)
    speed_line_color: Color = rgba(24, 24, 26, 30)
    dot_spacing: int = 12
    dot_radius: float = 2.1
    speed_lines: int = 26
    speed_line_width: int = 3

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new("RGBA", (size.width, size.height), self.fill)
        if size.width <= 0 or size.height <= 0:
            return canvas

        self._draw_halftone(ctx, canvas, size)
        self._draw_speed_lines(ctx, canvas, size)
        return canvas

    def _draw_halftone(
        self, ctx: RenderContext, canvas: Image.Image, size: Size
    ) -> None:
        spacing = max(2, ctx.scale_px(self.dot_spacing))
        radius = max(1, round(ctx.scale_px(self.dot_radius)))
        layer = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        # Offset every other row so the tone reads as a diagonal screen, the way
        # real screentone is printed, rather than as a square grid.
        for row, y in enumerate(range(0, size.height + spacing, spacing)):
            offset = 0 if row % 2 == 0 else spacing // 2
            for x in range(-offset, size.width + spacing, spacing):
                draw.ellipse(
                    (x - radius, y - radius, x + radius, y + radius),
                    fill=self.dot_color,
                )
        alpha_composite_paste(canvas, layer, (0, 0))

    def _draw_speed_lines(
        self, ctx: RenderContext, canvas: Image.Image, size: Size
    ) -> None:
        if self.speed_lines <= 0:
            return
        layer = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        width = max(1, ctx.scale_px(self.speed_line_width))
        reach = math.hypot(size.width, size.height)
        # Fan out of the top-right corner across the upper-left quadrant.
        for index in range(self.speed_lines):
            angle = math.pi / 2 + (index / max(1, self.speed_lines - 1)) * (math.pi / 2)
            draw.line(
                (
                    size.width,
                    0,
                    size.width + reach * math.cos(angle),
                    reach * math.sin(angle),
                ),
                fill=self.speed_line_color,
                width=width,
            )
        alpha_composite_paste(canvas, layer, (0, 0))


@dataclass(frozen=True)
class MangaPanel:
    """Paper-white cell boxed in a heavy ink outline."""

    child: Component | None = None
    fill: ColorLike = rgba(255, 255, 255, 242)
    radius: int = 14
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    ink_color: ColorLike = rgba(18, 18, 20, 255)
    ink_width: int = 5

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
            border_color=self.ink_color,
            border_width=self.ink_width,
        )
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)
