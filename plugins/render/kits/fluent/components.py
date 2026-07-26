"""Signature visuals for the fluent kit."""

import random
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

from ..atoms import mix_color
from ..atoms import draw_soft_shadow
from ..atoms import draw_panel_surface

#: Edge length of the generated noise tile, in pixels.
NOISE_TILE = 128

#: Resolution the radial bloom is computed at before being scaled up. Mica
#: blurs the desktop heavily, so a low-resolution source upscales cleanly.
BLOOM_RESOLUTION = 64


@dataclass(frozen=True)
class Bloom:
    """One radial color pool in the simulated desktop wallpaper.

    Attributes:
        x: Horizontal center as a fraction of page width.
        y: Vertical center as a fraction of page height.
        color: Bloom color.
        radius: Bloom radius as a fraction of the page diagonal.
        strength: Peak opacity from 0.0 to 1.0.
    """

    x: float
    y: float
    color: Color
    radius: float
    strength: float


@dataclass(frozen=True)
class FluentBackground:
    """Mica material: a desaturated desktop bloom under fine acrylic noise.

    Mica tints a window from the wallpaper behind it rather than painting a
    flat color, so this renders a soft multi-bloom wash over the Mica base
    instead of a plain fill.
    """

    fill: Color = rgba(243, 243, 243, 255)
    blooms: tuple[Bloom, ...] = (
        Bloom(0.30, 0.28, rgba(120, 168, 226, 255), 0.62, 0.42),
        Bloom(0.74, 0.40, rgba(168, 148, 216, 255), 0.58, 0.34),
        Bloom(0.52, 0.88, rgba(132, 198, 210, 255), 0.54, 0.26),
    )
    noise_intensity: int = 10
    random_seed: int = 0

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new("RGBA", (max(0, size.width), max(0, size.height)), self.fill)
        if size.width <= 0 or size.height <= 0:
            return canvas

        if self.blooms:
            bloom = _render_blooms(self.blooms, self.fill).resize(
                (size.width, size.height), Image.Resampling.BICUBIC
            )
            alpha_composite_paste(canvas, bloom, (0, 0))
        if self.noise_intensity > 0:
            _apply_noise(canvas, size, self.noise_intensity, self.random_seed)
        return canvas


def _render_blooms(blooms: tuple[Bloom, ...], base: Color) -> Image.Image:
    """Compose the radial blooms at low resolution over the Mica base."""

    edge = BLOOM_RESOLUTION
    image = Image.new("RGBA", (edge, edge), base)
    pixels = image.load()
    for py in range(edge):
        for px in range(edge):
            color = base
            for bloom in blooms:
                dx = (px + 0.5) / edge - bloom.x
                dy = (py + 0.5) / edge - bloom.y
                distance = (dx * dx + dy * dy) ** 0.5
                if distance >= bloom.radius:
                    continue
                # Squared falloff keeps the center soft instead of ring-edged.
                falloff = (1.0 - distance / bloom.radius) ** 2
                color = mix_color(color, bloom.color, falloff * bloom.strength)
            pixels[px, py] = color
    return image


def _apply_noise(
    canvas: Image.Image, size: Size, intensity: int, seed: int
) -> None:
    """Composite a tiled, seeded grain over the canvas.

    A repeated tile is used rather than full-page noise because per-pixel
    generation costs far more than the grain is worth at this opacity.
    """

    rng = random.Random(seed)
    alpha = Image.frombytes(
        "L", (NOISE_TILE, NOISE_TILE), rng.randbytes(NOISE_TILE * NOISE_TILE)
    ).point(lambda value: value * intensity // 255)
    tile = Image.new("RGBA", (NOISE_TILE, NOISE_TILE), (255, 255, 255, 0))
    tile.putalpha(alpha)
    for x in range(0, size.width, NOISE_TILE):
        for y in range(0, size.height, NOISE_TILE):
            alpha_composite_paste(canvas, tile, (x, y))


@dataclass(frozen=True)
class FluentPanel:
    """Fluent card: translucent layer, control stroke, and a lit top edge.

    The top highlight is what makes a Fluent surface read as raised. It fades
    out over the upper part of the card so only the edge catches the light.
    """

    child: Component | None = None
    fill: ColorLike = rgba(255, 255, 255, 178)
    radius: int = 8
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    stroke_color: ColorLike = rgba(0, 0, 0, 15)
    stroke_width: int = 1
    highlight_color: ColorLike = rgba(255, 255, 255, 200)
    shadow_color: Color = rgba(0, 0, 0, 28)
    shadow_blur: int = 8
    shadow_offset: int = 2

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
        draw_panel_surface(
            ctx,
            canvas,
            rect,
            fill=self.fill,
            radius=self.radius,
            border_color=self.stroke_color,
            border_width=self.stroke_width,
        )
        self._draw_top_highlight(ctx, canvas, rect)
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)

    def _draw_top_highlight(
        self, ctx: RenderContext, canvas: Image.Image, rect: Rect
    ) -> None:
        stroke = max(1, ctx.scale_px(self.stroke_width))
        if rect.width <= 0 or rect.height <= 0:
            return
        radius = min(
            ctx.scale_px(self.radius), rect.width // 2, rect.height // 2
        )
        highlight = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        ImageDraw.Draw(highlight).rounded_rectangle(
            (0, 0, rect.width - 1, rect.height - 1),
            radius=radius,
            outline=normalize_color(self.highlight_color),
            width=stroke,
        )
        highlight.putalpha(
            ImageChops.multiply(
                highlight.getchannel("A"), _top_fade_mask(rect.width, rect.height)
            )
        )
        alpha_composite_paste(canvas, highlight, (rect.x, rect.y))


def _top_fade_mask(width: int, height: int) -> Image.Image:
    """Build a mask that is opaque at the top edge and clear below it."""

    fade = max(1, round(height * 0.45))
    column = Image.new("L", (1, height), 0)
    pixels = column.load()
    for y in range(min(fade, height)):
        pixels[0, y] = round(255 * (1.0 - y / fade))
    return column.resize((width, height), Image.Resampling.BILINEAR)
