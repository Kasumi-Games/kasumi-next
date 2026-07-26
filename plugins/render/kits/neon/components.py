"""Signature visuals for the neon kit."""

from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter

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

from ..atoms import draw_soft_shadow
from ..atoms import draw_panel_surface


@dataclass(frozen=True)
class NeonBackground:
    """Arcade cabinet backdrop: horizon grid under CRT scanlines."""

    fill: Color = rgba(7, 6, 15, 255)
    grid_color: Color = rgba(255, 44, 160, 70)
    horizon_color: Color = rgba(34, 240, 255, 90)
    scanline_color: Color = rgba(0, 0, 0, 46)
    grid_spacing: int = 46
    scanline_spacing: int = 4
    horizon_ratio: float = 0.52

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new("RGBA", (size.width, size.height), self.fill)
        if size.width <= 0 or size.height <= 0:
            return canvas

        horizon = round(size.height * self.horizon_ratio)
        grid = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(grid)
        spacing = max(2, ctx.scale_px(self.grid_spacing))
        line_width = max(1, ctx.scale_px(1))

        # Floor lines: horizontal rules that bunch up toward the horizon.
        y = size.height
        step = spacing
        while y > horizon:
            draw.line((0, y, size.width, y), fill=self.grid_color, width=line_width)
            step = max(2, round(step * 0.78))
            y -= step

        # Floor lines: verticals fanning out from the vanishing point.
        center = size.width // 2
        for offset in range(0, size.width, spacing):
            for direction in (-1, 1):
                draw.line(
                    (center, horizon, center + direction * offset, size.height),
                    fill=self.grid_color,
                    width=line_width,
                )
        draw.line(
            (0, horizon, size.width, horizon),
            fill=self.horizon_color,
            width=max(1, ctx.scale_px(2)),
        )
        grid = grid.filter(ImageFilter.GaussianBlur(max(1, ctx.scale_px(1))))
        alpha_composite_paste(canvas, grid, (0, 0))

        scanlines = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        scan_draw = ImageDraw.Draw(scanlines)
        for y in range(0, size.height, max(2, ctx.scale_px(self.scanline_spacing))):
            scan_draw.line((0, y, size.width, y), fill=self.scanline_color, width=1)
        alpha_composite_paste(canvas, scanlines, (0, 0))
        return canvas


@dataclass(frozen=True)
class NeonPanel:
    """Dark slab ringed by a lit neon tube."""

    child: Component | None = None
    fill: ColorLike = rgba(14, 12, 28, 228)
    radius: int = 10
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    tube_color: ColorLike = rgba(255, 44, 160, 255)
    glow_color: Color = rgba(255, 44, 160, 120)
    glow_blur: int = 10
    tube_width: int = 2

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
        draw_soft_shadow(
            canvas,
            rect,
            radius=ctx.scale_px(self.radius),
            color=self.glow_color,
            blur=ctx.scale_px(self.glow_blur),
            spread=ctx.scale_px(3),
        )
        draw_panel_surface(
            ctx,
            canvas,
            rect,
            fill=self.fill,
            radius=self.radius,
            border_color=self.tube_color,
            border_width=self.tube_width,
        )
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)
