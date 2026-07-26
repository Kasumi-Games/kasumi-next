"""Signature visuals for the sakura kit."""

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
class SakuraBackground:
    """Warm cream wash with petals drifting across it."""

    top: Color = rgba(255, 250, 251, 255)
    bottom: Color = rgba(252, 226, 236, 255)
    petal_colors: tuple[Color, ...] = (
        rgba(247, 183, 205, 150),
        rgba(240, 158, 188, 130),
        rgba(255, 214, 227, 175),
    )
    petal_density: float = 0.00005
    petal_size: int = 18
    random_seed: int = 0

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = vertical_gradient(size, self.top, self.bottom).convert("RGBA")
        logical_area = ctx.unscale_px(size.width) * ctx.unscale_px(size.height)
        count = int(logical_area * self.petal_density)
        if count <= 0 or not self.petal_colors:
            return canvas

        rng = random.Random(self.random_seed)
        layer = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        base_size = max(2, ctx.scale_px(self.petal_size))
        for _ in range(count):
            scale = rng.uniform(0.6, 1.4)
            petal = _petal(
                max(2, round(base_size * scale)),
                rng.choice(self.petal_colors),
                rng.uniform(0, 360),
            )
            alpha_composite_paste(
                layer,
                petal,
                (
                    rng.randrange(-petal.width, size.width),
                    rng.randrange(-petal.height, size.height),
                ),
            )
        alpha_composite_paste(canvas, layer, (0, 0))
        return canvas


def _petal(size: int, color: Color, angle: float) -> Image.Image:
    """Draw one notched cherry petal, rotated by ``angle`` degrees."""

    # Supersample so the rotated edge stays smooth at small sizes.
    scale = 4
    box = size * scale
    petal = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(petal)
    draw.ellipse((box * 0.18, 0, box * 0.82, box), fill=color)
    # Notch the tip the way a real sakura petal is split.
    notch = box * 0.22
    draw.polygon(
        [
            (box / 2 - notch / 2, 0),
            (box / 2 + notch / 2, 0),
            (box / 2, notch * 0.9),
        ],
        fill=(0, 0, 0, 0),
    )
    petal = petal.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    target = max(1, round(petal.width / scale))
    return petal.resize((target, target), Image.Resampling.LANCZOS)


@dataclass(frozen=True)
class SakuraPanel:
    """Very round white card lifted by a warm pink shadow."""

    child: Component | None = None
    fill: ColorLike = rgba(255, 255, 255, 234)
    radius: int = 44
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    shadow_color: Color = rgba(226, 158, 184, 92)
    shadow_blur: int = 12
    shadow_offset: int = 6

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
            color=self.shadow_color,
            blur=ctx.scale_px(self.shadow_blur),
            offset=(0, ctx.scale_px(self.shadow_offset)),
        )
        draw_panel_surface(ctx, canvas, rect, fill=self.fill, radius=self.radius)
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)
