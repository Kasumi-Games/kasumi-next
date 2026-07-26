"""Signature visuals for the sailing kit."""

import math
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw
from PIL import ImageChops

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
from plugins.render.primitives import alpha_composite_paste

from ..atoms import vertical_gradient
from ..atoms import draw_panel_surface


@dataclass(frozen=True)
class SailingBackground:
    """Open-sky gradient closed off by layered wave bands along the bottom."""

    top: Color = rgba(226, 242, 251, 255)
    bottom: Color = rgba(150, 206, 235, 255)
    wave_colors: tuple[Color, ...] = (
        rgba(120, 186, 224, 150),
        rgba(64, 146, 196, 175),
        rgba(14, 76, 122, 205),
    )
    wave_height: int = 46
    wave_length: int = 260

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = vertical_gradient(size, self.top, self.bottom).convert("RGBA")
        if not self.wave_colors or size.width <= 0 or size.height <= 0:
            return canvas

        layer = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        amplitude = ctx.scale_px(self.wave_height) / 2
        wavelength = max(1, ctx.scale_px(self.wave_length))
        step = max(1, size.width // 96)

        for index, color in enumerate(self.wave_colors):
            # Later bands sit lower and are phase-shifted so crests never align.
            baseline = size.height - amplitude * (len(self.wave_colors) - index) * 1.15
            phase = index * math.pi / 2.4
            points = [
                (
                    x,
                    baseline
                    + amplitude * math.sin(2 * math.pi * x / wavelength + phase),
                )
                for x in range(0, size.width + step, step)
            ]
            points.append((size.width, size.height))
            points.append((0, size.height))
            draw.polygon(points, fill=color)

        alpha_composite_paste(canvas, layer, (0, 0))
        return canvas


@dataclass(frozen=True)
class SailingPanel:
    """Sail-cream surface topped by a deep-water accent bar."""

    child: Component | None = None
    fill: ColorLike = rgba(252, 252, 248, 232)
    radius: int = 30
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    accent_color: ColorLike = rgba(14, 76, 122, 255)
    accent_height: int = 6

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
        draw_panel_surface(ctx, canvas, rect, fill=self.fill, radius=self.radius)
        self._draw_accent(ctx, canvas, rect)
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)

    def _draw_accent(
        self, ctx: RenderContext, canvas: Image.Image, rect: Rect
    ) -> None:
        height = ctx.scale_px(self.accent_height)
        if height <= 0 or rect.width <= 0 or rect.height <= 0:
            return
        radius = min(
            ctx.scale_px(self.radius), rect.width // 2, rect.height // 2
        )
        # Clip the bar to the panel silhouette so it never overhangs the
        # rounded shoulders; on a pill-shaped panel it becomes a centered cap.
        mask = Image.new("L", (rect.width, rect.height), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, rect.width - 1, rect.height - 1), radius=radius, fill=255
        )
        bar = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        ImageDraw.Draw(bar).rectangle(
            (0, 0, rect.width, min(height, rect.height)),
            fill=normalize_color(self.accent_color),
        )
        bar.putalpha(ImageChops.multiply(bar.getchannel("A"), mask))
        alpha_composite_paste(canvas, bar, (rect.x, rect.y))
