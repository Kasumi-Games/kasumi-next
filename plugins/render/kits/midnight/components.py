"""Signature visuals for the midnight kit."""

import random
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

from ..atoms import draw_soft_shadow
from ..atoms import vertical_gradient
from ..atoms import draw_panel_surface


@dataclass(frozen=True)
class MidnightBackground:
    """Night-sky gradient dusted with deterministic stars."""

    top: Color = rgba(11, 14, 23, 255)
    bottom: Color = rgba(26, 32, 56, 255)
    star_color: Color = rgba(198, 214, 255, 255)
    star_density: float = 0.00012
    random_seed: int = 0

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = vertical_gradient(size, self.top, self.bottom).convert("RGBA")
        logical_area = ctx.unscale_px(size.width) * ctx.unscale_px(size.height)
        count = int(logical_area * self.star_density)
        if count <= 0:
            return canvas

        layer = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        rng = random.Random(self.random_seed)
        for _ in range(count):
            x = rng.randrange(size.width)
            y = rng.randrange(size.height)
            radius = max(1, ctx.scale_px(rng.choice((1, 1, 2, 3))))
            alpha = rng.randint(40, 190)
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(*self.star_color[:3], alpha),
            )
        alpha_composite_paste(canvas, layer, (0, 0))
        return canvas


@dataclass(frozen=True)
class MidnightPanel:
    """Raised dark surface lit by an indigo outer glow and a hairline edge."""

    child: Component | None = None
    fill: ColorLike = rgba(30, 36, 56, 224)
    radius: int = 36
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    glow_color: Color = rgba(96, 132, 232, 90)
    glow_blur: int = 14
    border_color: ColorLike = rgba(126, 148, 208, 70)
    border_width: int = 2

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
            spread=ctx.scale_px(2),
        )
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
