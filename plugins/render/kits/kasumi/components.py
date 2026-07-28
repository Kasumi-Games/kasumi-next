"""Signature visuals for the Kasumi kit.

The art direction, in one line: the starry sky Kasumi looks up at, carried into
a bright lilac dawn — drifting nebula colour and four-point glints instead of
literal yellow stars. キラキラドキドキ comes from coral, champagne gold, and
violet sparkling across a warm, airy sky.
"""

import math
import random
from pathlib import Path
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
from plugins.render.color import normalize_color
from plugins.render.types import ImageSource
from plugins.render.layout import Frame
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste

from ..atoms import mix_color
from ..atoms import load_image
from ..atoms import resize_cover
from ..atoms import draw_soft_shadow
from ..atoms import vertical_gradient
from ..atoms import draw_panel_surface
from ..fonts import CHINESE_FONT

KIT_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = KIT_DIR / "resources"
STANDING_DIR = RESOURCES_DIR / "standing"
ITEM_FRAMES_DIR = (
    Path(__file__).resolve().parents[3]
    / "inventory"
    / "resources"
    / "items"
    / "avatar_frames"
)

#: The Look Up at the Starry Sky trim art (Bestdori card 425, trained).
STANDING_ART = STANDING_DIR / "kasumi_starry_after_training.png"
STANDING_ART_NORMAL = STANDING_DIR / "kasumi_starry_normal.png"

#: The former kit-owned frame is now the art of an inventory item. Kept as a
#: public constant for asset-contract checks; the kit no longer equips it by
#: default.
AVATAR_FRAME = ITEM_FRAMES_DIR / "frame_kasumi_starbeat.png"

#: Frame asset contract: 512 canvas, avatar circle Ø 416 centered.
FRAME_CANVAS = 512
FRAME_AVATAR_DIAMETER = 416

#: Sparkle palette for a pale sky. White glints disappeared on the old light
#: component surfaces, so the dawn treatment uses coral, gold, violet, and
#: cyan marks with enough chroma to remain visible after chat downscaling.
SPARKLE_COLORS: tuple[tuple[Color, int], ...] = (
    (rgba(224, 81, 111, 255), 4),
    (rgba(220, 157, 43, 255), 4),
    (rgba(112, 91, 170, 255), 3),
    (rgba(67, 146, 181, 255), 1),
)


def sparkle(size: int, color: Color, *, ratio: float = 0.2) -> Image.Image:
    """Draw a concave four-point glint (✦), supersampled.

    This is the kit's replacement for a literal five-point star: the shape a
    camera makes of a point of light.

    Args:
        size: Output edge length in pixels.
        color: Glint color, alpha included.
        ratio: Waist thickness as a fraction of the radius.

    Returns:
        Glint image.
    """

    scale = 4
    box = max(4, size * scale)
    half = box / 2
    inner = max(1.0, half * ratio)
    points = []
    for index in range(8):
        angle = math.pi / 4 * index - math.pi / 2
        radius = half if index % 2 == 0 else inner
        points.append((half + radius * math.cos(angle), half + radius * math.sin(angle)))
    # Draw and resize alpha separately, then apply it to a solid-colour image.
    # Resizing straight RGBA with transparent-black surrounding pixels creates
    # grey/black fringes around the glint when Pillow interpolates the RGB
    # channels. A colour-backed alpha mask keeps every feathered pixel luminous.
    mask = Image.new("L", (box, box), 0)
    ImageDraw.Draw(mask).polygon(points, fill=color[3])
    edge = max(1, size)
    mask = mask.resize((edge, edge), Image.Resampling.LANCZOS)
    image = Image.new("RGBA", (edge, edge), (*color[:3], 0))
    image.putalpha(mask)
    return image


def scatter_sparkles(
    layer: Image.Image,
    ctx: RenderContext,
    *,
    seed: int,
    glint_density: float,
    dot_density: float,
    max_glint: int = 26,
) -> None:
    """Scatter glints and bokeh dots over a layer, deterministically.

    Args:
        layer: RGBA layer mutated in place.
        ctx: Render context, for logical-to-render scaling.
        seed: Random seed; equal seeds give equal skies.
        glint_density: Glints per logical pixel of area.
        dot_density: Bokeh dots per logical pixel of area.
        max_glint: Largest glint size in logical pixels.
    """

    width, height = layer.size
    if width <= 0 or height <= 0:
        return
    logical_area = ctx.unscale_px(width) * ctx.unscale_px(height)
    rng = random.Random(seed)
    colors = [color for color, weight in SPARKLE_COLORS for _ in range(weight)]

    draw = ImageDraw.Draw(layer)
    for _ in range(int(logical_area * dot_density)):
        x = rng.randrange(width)
        y = rng.randrange(height)
        radius = max(1, ctx.scale_px(rng.choice((1, 1, 1, 2))))
        color = rng.choice(colors)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(*color[:3], rng.randint(30, 110)),
        )

    for _ in range(int(logical_area * glint_density)):
        size = ctx.scale_px(rng.randint(7, max_glint))
        color = rng.choice(colors)
        alpha = rng.randint(110, 225)
        glint = sparkle(size, (*color[:3], alpha), ratio=rng.uniform(0.14, 0.24))
        x = rng.randrange(-size, width)
        y = rng.randrange(-size, height)
        if size >= ctx.scale_px(18):
            # Large glints get a soft halo so they read as light, not markers.
            halo_alpha = glint.getchannel("A").resize(
                (size * 2, size * 2), Image.Resampling.BILINEAR
            )
            halo_alpha = halo_alpha.filter(
                ImageFilter.GaussianBlur(max(1, size // 3))
            )
            halo_alpha = halo_alpha.point(lambda value: round(value * 0.55))
            halo = Image.new("RGBA", (size * 2, size * 2), (*color[:3], 0))
            halo.putalpha(halo_alpha)
            alpha_composite_paste(layer, halo, (x - size // 2, y - size // 2))
        alpha_composite_paste(layer, glint, (x, y))


@dataclass(frozen=True)
class KasumiBackground:
    """A lilac dawn: warm gradient, faint colour drift, four-point glints."""

    top: Color = rgba(242, 238, 255, 255)
    bottom: Color = rgba(255, 232, 226, 255)
    glint_density: float = 0.00006
    dot_density: float = 0.00010
    random_seed: int = 425  # the card that started this theme

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = vertical_gradient(size, self.top, self.bottom).convert("RGBA")
        if size.width <= 0 or size.height <= 0:
            return canvas

        nebula = self._nebula(size)
        if nebula is not None:
            alpha_composite_paste(canvas, nebula, (0, 0))

        layer = Image.new("RGBA", (size.width, size.height), (0, 0, 0, 0))
        scatter_sparkles(
            layer,
            ctx,
            seed=self.random_seed,
            glint_density=self.glint_density,
            dot_density=self.dot_density,
        )
        alpha_composite_paste(canvas, layer, (0, 0))
        return canvas

    def _nebula(self, size: Size) -> Image.Image | None:
        """Very low alpha colour drift, computed small and upscaled."""

        edge = 48
        # The wash is deliberately restrained: the shared components bring
        # plenty of colour, and the background only needs to keep the sky from
        # reading as a flat white sheet.
        blooms = (
            (0.18, 0.18, rgba(168, 142, 232, 255), 0.55, 0.18),
            (0.82, 0.30, rgba(255, 151, 163, 255), 0.48, 0.16),
            (0.48, 0.88, rgba(255, 195, 113, 255), 0.58, 0.13),
        )
        base = (0, 0, 0, 0)
        small = Image.new("RGBA", (edge, edge), base)
        pixels = small.load()
        for py in range(edge):
            for px in range(edge):
                color = base
                for bx, by, bloom_color, radius, strength in blooms:
                    dx = (px + 0.5) / edge - bx
                    dy = (py + 0.5) / edge - by
                    distance = (dx * dx + dy * dy) ** 0.5
                    if distance >= radius:
                        continue
                    falloff = (1.0 - distance / radius) ** 2
                    tinted = (*bloom_color[:3], round(255 * strength))
                    color = mix_color(color, tinted, falloff * strength)
                pixels[px, py] = color
        return small.resize((size.width, size.height), Image.Resampling.BICUBIC)


@dataclass(frozen=True)
class KasumiPanel:
    """Translucent warm-white surface with a coral hairline and soft shadow."""

    child: Component | None = None
    fill: ColorLike = rgba(255, 251, 252, 238)
    radius: int = 28
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    border_color: ColorLike = rgba(222, 103, 124, 78)
    border_width: int = 1
    glow_color: Color = rgba(91, 67, 125, 30)
    glow_blur: int = 12

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
        if self.glow_blur > 0 and self.glow_color[3] > 0:
            draw_soft_shadow(
                canvas,
                rect,
                radius=ctx.scale_px(self.radius),
                color=self.glow_color,
                blur=ctx.scale_px(self.glow_blur),
                spread=ctx.scale_px(1),
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


@dataclass(frozen=True)
class SparkleScatter:
    """A transparent layer of glints, for overlaying on Tier A surfaces."""

    seed: int = 0
    glint_density: float = 0.00018
    dot_density: float = 0.0
    opacity: float = 1.0

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return Size(constraints.max_width or 0, constraints.max_height or 0)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        scatter_sparkles(
            layer,
            ctx,
            seed=self.seed,
            glint_density=self.glint_density,
            dot_density=self.dot_density,
            max_glint=18,
        )
        if self.opacity < 1.0:
            opacity = max(0.0, self.opacity)
            alpha = layer.getchannel("A").point(
                lambda value: round(value * opacity)
            )
            layer.putalpha(alpha)
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class KasumiAvatarDisc:
    """Circular avatar disc with an initial-glyph fallback.

    The ring around it belongs to the avatar frame (:func:`frame_overlay` or a
    hand-drawn asset), so this component draws only the disc. Supersampled so
    the circle edge survives the page downscale.

    Attributes:
        source: Optional avatar image.
        initial: Fallback glyph; first character is used.
        size: Logical diameter.
        fill: Disc fill behind the initial fallback.
        initial_color: Initial glyph color.
    """

    source: ImageSource | None
    initial: str
    size: int
    fill: ColorLike = rgba(232, 222, 246, 255)
    initial_color: ColorLike = rgba(62, 48, 89, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(self.size, self.size))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        side = min(rect.width, rect.height)
        if side <= 0:
            return
        supersample = 3
        big = side * supersample
        layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        if self.source is not None:
            art = resize_cover(load_image(ctx, self.source), big, big)
            mask = Image.new("L", (big, big), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
            layer.paste(art, (0, 0), mask)
        else:
            draw.ellipse((0, 0, big - 1, big - 1), fill=normalize_color(self.fill))
            glyph = (self.initial or "?")[:1]
            font = load_font(max(8, round(big * 0.46)), CHINESE_FONT)
            bbox = draw.textbbox((0, 0), glyph, font=font)
            draw.text(
                (
                    (big - (bbox[2] - bbox[0])) // 2 - bbox[0],
                    (big - (bbox[3] - bbox[1])) // 2 - bbox[1],
                ),
                glyph,
                font=font,
                fill=normalize_color(self.initial_color),
            )

        resized = layer.resize((side, side), Image.Resampling.LANCZOS)
        alpha_composite_paste(
            canvas,
            resized,
            (
                rect.x + (rect.width - side) // 2,
                rect.y + (rect.height - side) // 2,
            ),
        )


def frame_overlay(avatar_size: int) -> Image.Image:
    """The kit's unequipped avatar decoration at ``avatar_size`` pixels.

    Args:
        avatar_size: Rendered avatar diameter in pixels.

    Returns:
        Frame image sized ``round(avatar_size * 512 / 416)`` square.
    """

    canvas_size = max(4, round(avatar_size * FRAME_CANVAS / FRAME_AVATAR_DIAMETER))
    scale = 4
    box = canvas_size * scale
    image = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    center = box / 2
    avatar_radius = box * FRAME_AVATAR_DIAMETER / FRAME_CANVAS / 2
    ring_width = box * 0.035
    draw.ellipse(
        (
            center - avatar_radius - ring_width,
            center - avatar_radius - ring_width,
            center + avatar_radius + ring_width,
            center + avatar_radius + ring_width,
        ),
        outline=rgba(255, 118, 98, 255),
        width=max(1, round(ring_width)),
    )
    outer = avatar_radius + ring_width * 1.9
    draw.ellipse(
        (center - outer, center - outer, center + outer, center + outer),
        outline=rgba(255, 205, 160, 200),
        width=max(1, round(ring_width * 0.35)),
    )
    result = image.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)
    glint = sparkle(max(4, canvas_size // 5), rgba(255, 214, 150, 235))
    alpha_composite_paste(result, glint, (round(canvas_size * 0.66), 0))
    small = sparkle(max(3, canvas_size // 8), rgba(255, 214, 150, 220))
    alpha_composite_paste(
        result, small, (round(canvas_size * 0.04), round(canvas_size * 0.62))
    )
    return result
