"""Original ornaments and surfaces for the Roselia render kit.

The module intentionally contains no copied Roselia logo or official artwork.
Its rose, pointed arches, glass shards, and botanical corners are simple
programmatic geometry inspired by the kit's design brief.
"""

import math
import random
from pathlib import Path
from functools import lru_cache
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
from plugins.render.types import ImageSource
from plugins.render.layout import Frame
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste

from ..atoms import KitText
from ..atoms import load_image
from ..atoms import resize_cover
from ..atoms import fixed_or_bound
from ..atoms import resize_contain
from ..atoms import vertical_gradient
from ..atoms import draw_panel_surface

KIT_DIR = Path(__file__).resolve().parent
FONTS_DIR = KIT_DIR / "resources" / "fonts"
BODY_FONT = FONTS_DIR / "SourceHanSerifSC-SemiBold.otf"
DISPLAY_FONT = FONTS_DIR / "CormorantSC-SemiBold.ttf"

BACKGROUND_TOP = rgba(12, 9, 22, 255)
BACKGROUND_BOTTOM = rgba(42, 23, 68, 255)
TEXT = rgba(33, 24, 47, 255)
MUTED = rgba(114, 101, 127, 255)
PANEL = rgba(247, 242, 250, 246)
PAPER = rgba(246, 244, 239, 255)
PRIMARY = rgba(116, 80, 168, 255)
ROSE = rgba(139, 45, 88, 255)
GOLD = rgba(184, 154, 98, 255)
GLASS = rgba(157, 213, 247, 255)
RULE = rgba(150, 169, 206, 255)

FRAME_CANVAS = 512
FRAME_AVATAR_DIAMETER = 416


def _with_alpha(color: ColorLike, alpha: int) -> Color:
    normalized = normalize_color(color)
    assert normalized is not None
    return (*normalized[:3], max(0, min(255, alpha)))


@dataclass(frozen=True)
class RoseliaText(KitText):
    """Serif text that switches to ivory when rendered on the night sky.

    Shared page subtitles and footers sit directly on a kit background, while
    the same ``BaseKit.text`` atom is used inside light information panels.
    Sampling the already-painted pixel beneath the assigned text rectangle
    preserves the documented dark panel ink without forcing business
    renderers to know that Roselia has two surface tones.
    """

    light_color: ColorLike = rgba(238, 230, 242, 255)
    adaptive: bool = True

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if not self.adaptive or rect.width <= 0 or rect.height <= 0:
            super().render(ctx, canvas, rect)
            return
        sample = canvas.getpixel(
            (
                min(canvas.width - 1, max(0, rect.x + rect.width // 2)),
                min(canvas.height - 1, max(0, rect.y + rect.height // 2)),
            )
        )
        red, green, blue = sample[:3]
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        if luminance >= 105:
            super().render(ctx, canvas, rect)
            return
        KitText(
            self.text,
            self.font,
            font_size=self.font_size,
            color=self.light_color,
            align=self.align,
            wrap=self.wrap,
            max_lines=self.max_lines,
            overflow=self.overflow,
            line_height=self.line_height,
            letter_spacing=self.letter_spacing,
            center_glyphs_in_line=self.center_glyphs_in_line,
        ).render(ctx, canvas, rect)


@lru_cache(maxsize=96)
def rose_crest(size: int, color: Color = PRIMARY) -> Image.Image:
    """Return a cached, original five-petal rose crest.

    The construction is deliberately unlike the official Roselia wordmark:
    five almond petals surround a small polygonal centre, with a short curved
    stem and two leaves beneath it.
    """

    edge = max(4, int(size))
    scale = 4
    box = edge * scale
    centre = box / 2
    image = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    fill = normalize_color(color)
    assert fill is not None

    petal_length = box * 0.24
    petal_width = box * 0.13
    flower_y = box * 0.39
    for index in range(5):
        angle = -math.pi / 2 + index * math.tau / 5
        direction = (math.cos(angle), math.sin(angle))
        tangent = (-direction[1], direction[0])
        inner = (
            centre + direction[0] * box * 0.035,
            flower_y + direction[1] * box * 0.035,
        )
        outer = (
            centre + direction[0] * petal_length,
            flower_y + direction[1] * petal_length,
        )
        points = [
            inner,
            (
                centre + direction[0] * box * 0.13 + tangent[0] * petal_width,
                flower_y + direction[1] * box * 0.13 + tangent[1] * petal_width,
            ),
            outer,
            (
                centre + direction[0] * box * 0.13 - tangent[0] * petal_width,
                flower_y + direction[1] * box * 0.13 - tangent[1] * petal_width,
            ),
        ]
        draw.polygon(points, fill=fill)

    centre_radius = box * 0.065
    draw.regular_polygon(
        (centre, flower_y, centre_radius),
        n_sides=5,
        rotation=-18,
        fill=_with_alpha(GOLD, fill[3]),
    )
    stroke = max(2, round(box * 0.022))
    draw.arc(
        (centre - box * 0.05, flower_y, centre + box * 0.16, box * 0.89),
        93,
        250,
        fill=fill,
        width=stroke,
    )
    draw.polygon(
        (
            (centre - box * 0.01, box * 0.67),
            (centre - box * 0.22, box * 0.64),
            (centre - box * 0.10, box * 0.78),
        ),
        fill=fill,
    )
    draw.polygon(
        (
            (centre + box * 0.035, box * 0.73),
            (centre + box * 0.22, box * 0.69),
            (centre + box * 0.12, box * 0.82),
        ),
        fill=fill,
    )
    return image.resize((edge, edge), Image.Resampling.LANCZOS)


@dataclass(frozen=True)
class RoseCrest:
    """A layout component backed by :func:`rose_crest`'s image cache."""

    size: int = 32
    color: Color = PRIMARY

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(self.size, self.size))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        side = min(rect.width, rect.height)
        if side <= 0:
            return
        crest = rose_crest(side, self.color)
        alpha_composite_paste(
            canvas,
            crest,
            (rect.x + (rect.width - side) // 2, rect.y + (rect.height - side) // 2),
        )


@dataclass(frozen=True)
class LeafPair:
    """Small symmetrical leaf sprig used as the structural ★5 marker."""

    width: int = 30
    height: int = 20
    color: Color = GOLD

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(self.width, self.height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        cx = rect.width // 2
        cy = rect.height // 2
        stroke = max(1, ctx.scale_px(1))
        draw.line((cx, rect.height - 1, cx, cy), fill=self.color, width=stroke)
        draw.polygon(
            ((cx, cy + stroke), (ctx.scale_px(2), cy - ctx.scale_px(3)), (cx - ctx.scale_px(3), rect.height - ctx.scale_px(2))),
            fill=self.color,
        )
        draw.polygon(
            ((cx, cy + stroke), (rect.width - ctx.scale_px(2), cy - ctx.scale_px(3)), (cx + ctx.scale_px(3), rect.height - ctx.scale_px(2))),
            fill=self.color,
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class RoseliaBackground:
    """Deep violet hall with seeded glass light, petals, and pointed arches."""

    top: Color = BACKGROUND_TOP
    bottom: Color = BACKGROUND_BOTTOM
    petal_density: float = 0.000025
    shard_density: float = 0.000018
    random_seed: int = 617

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = vertical_gradient(size, self.top, self.bottom).convert("RGBA")
        if size.width <= 0 or size.height <= 0:
            return canvas

        ornament = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        self._draw_arches(ctx, ornament)
        self._draw_scatter(ctx, ornament)
        alpha_composite_paste(canvas, ornament, (0, 0))
        return canvas

    def _draw_arches(self, ctx: RenderContext, layer: Image.Image) -> None:
        draw = ImageDraw.Draw(layer)
        width, height = layer.size
        stroke = max(1, ctx.scale_px(1))
        arch_color = _with_alpha(GLASS, 28)

        def arch(cx: float, base_y: float, radius: float, direction: int) -> None:
            r = max(4, round(radius))
            rise = round(r * 1.45)
            x0 = round(cx - r)
            x1 = round(cx + r)
            apex = round(base_y - rise * direction)
            base = round(base_y)
            draw.line((x0, base, round(cx), apex, x1, base), fill=arch_color, width=stroke)
            inset = max(stroke * 6, round(r * 0.14))
            draw.line(
                (
                    x0 + inset,
                    base,
                    round(cx),
                    apex + inset,
                    x1 - inset,
                    base,
                ),
                fill=_with_alpha(PRIMARY, 28),
                width=stroke,
            )
            draw.line((round(cx), apex, round(cx), base), fill=arch_color, width=stroke)

        arch(width * 0.12, height * 0.34, min(width, height) * 0.28, 1)
        arch(width * 0.88, height * 0.72, min(width, height) * 0.30, -1)

    def _draw_scatter(self, ctx: RenderContext, layer: Image.Image) -> None:
        width, height = layer.size
        logical_area = ctx.unscale_px(width) * ctx.unscale_px(height)
        rng = random.Random(self.random_seed)
        draw = ImageDraw.Draw(layer)
        for _ in range(max(0, int(logical_area * self.shard_density))):
            x = rng.randrange(width)
            y = rng.randrange(height)
            edge = ctx.scale_px(rng.randint(6, 20))
            points = (
                (x, y - edge),
                (x + edge, y + edge // 2),
                (x - edge // 2, y + edge),
            )
            color = rng.choice((GLASS, RULE, PRIMARY))
            draw.polygon(points, fill=_with_alpha(color, rng.randint(16, 42)))
        _scatter_petals(
            layer,
            ctx,
            seed=self.random_seed ^ 0xB05E,
            density=self.petal_density,
            alpha_range=(20, 45),
        )


@dataclass(frozen=True)
class PetalScatter:
    """Transparent, deterministic layer of three small petal silhouettes."""

    seed: int
    density: float = 0.000025
    alpha_min: int = 20
    alpha_max: int = 45

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return Size(constraints.max_width or 0, constraints.max_height or 0)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        _scatter_petals(
            layer,
            ctx,
            seed=self.seed,
            density=self.density,
            alpha_range=(self.alpha_min, self.alpha_max),
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


def _scatter_petals(
    layer: Image.Image,
    ctx: RenderContext,
    *,
    seed: int,
    density: float,
    alpha_range: tuple[int, int],
) -> None:
    width, height = layer.size
    if width <= 0 or height <= 0:
        return
    logical_area = ctx.unscale_px(width) * ctx.unscale_px(height)
    rng = random.Random(seed)
    draw = ImageDraw.Draw(layer)
    for _ in range(max(0, int(logical_area * density))):
        x = rng.randrange(width)
        y = rng.randrange(height)
        size = ctx.scale_px(rng.randint(5, 13))
        style = rng.randrange(3)
        alpha = rng.randint(*alpha_range)
        color = _with_alpha(rng.choice((ROSE, PRIMARY, GLASS)), alpha)
        if style == 0:
            points = ((x, y - size), (x + size // 2, y), (x, y + size), (x - size // 3, y))
        elif style == 1:
            points = ((x - size, y), (x, y - size // 2), (x + size, y), (x, y + size // 3))
        else:
            points = ((x, y - size), (x + size, y + size), (x - size // 2, y + size // 2))
        draw.polygon(points, fill=color)


@dataclass(frozen=True)
class RoseliaPanel:
    """Ivory information surface with clipped double rules and corner leaves."""

    child: Component | None = None
    fill: ColorLike = PANEL
    radius: int = 20
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    outer_color: ColorLike = PRIMARY
    inner_color: ColorLike = RULE
    outer_width: int = 2
    inner_width: int = 1
    ornate: bool = True
    force_inner: bool = False

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
        draw_panel_surface(
            ctx,
            canvas,
            rect,
            fill=self.fill,
            radius=self.radius,
            border_color=self.outer_color if self.outer_width > 0 else None,
            border_width=self.outer_width,
        )
        logical_width = ctx.unscale_px(rect.width)
        logical_height = ctx.unscale_px(rect.height)
        show_inner = self.force_inner or (
            logical_width > 180 and logical_height > 48
        )
        if self.inner_width > 0 and show_inner:
            inset = ctx.scale_px(6)
            ImageDraw.Draw(canvas).rounded_rectangle(
                (rect.x + inset, rect.y + inset, rect.right - inset - 1, rect.bottom - inset - 1),
                radius=max(0, ctx.scale_px(max(0, self.radius - 6))),
                outline=normalize_color(self.inner_color),
                width=max(1, ctx.scale_px(self.inner_width)),
            )
        if self.ornate and ctx.unscale_px(rect.width) > 180 and ctx.unscale_px(rect.height) > 80:
            self._draw_corners(ctx, canvas, rect)
        Frame(
            self.child,
            padding=self.padding,
            align_x="stretch",
            align_y="stretch",
        ).render(ctx, canvas, rect)

    def _draw_corners(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        # Draw into a rect-sized layer: even aggressive future ornament edits
        # remain clipped to this component's allocation.
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        stroke = max(1, ctx.scale_px(1))
        reach = min(ctx.scale_px(34), rect.width // 4, rect.height // 3)
        color = _with_alpha(PRIMARY, 58)
        for flip_x, flip_y in ((False, False), (True, True)):
            ox = rect.width - 1 if flip_x else 0
            oy = rect.height - 1 if flip_y else 0
            sx = -1 if flip_x else 1
            sy = -1 if flip_y else 1
            points = [
                (ox + sx * ctx.scale_px(9), oy + sy * reach),
                (ox + sx * ctx.scale_px(10), oy + sy * ctx.scale_px(17)),
                (ox + sx * reach, oy + sy * ctx.scale_px(9)),
            ]
            draw.line(points, fill=color, width=stroke, joint="curve")
            leaf = ctx.scale_px(5)
            lx, ly = points[1]
            draw.polygon(
                ((lx, ly), (lx + sx * leaf * 2, ly + sy * leaf), (lx + sx * leaf, ly + sy * leaf * 2)),
                fill=_with_alpha(ROSE, 46),
            )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class RoseliaSeparator:
    """Fading horizontal rule with a fixed-height central diamond."""

    length: SizeValue | int | None = None
    thickness: int = 2
    color: ColorLike = RULE

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return Size(
            fixed_or_bound(self.length, constraints.max_width, "RoseliaSeparator.length"),
            9,
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        center_y = rect.height // 2
        centre_x = rect.width // 2
        stroke = max(1, min(rect.height, ctx.scale_px(self.thickness)))
        color = normalize_color(self.color)
        assert color is not None
        segments = max(1, min(36, rect.width // max(1, ctx.scale_px(10))))
        half_gap = ctx.scale_px(9)
        for side in (-1, 1):
            start = centre_x + side * half_gap
            end = rect.width - 1 if side > 0 else 0
            for index in range(segments):
                t0 = index / segments
                t1 = (index + 1) / segments
                x0 = round(start + (end - start) * t0)
                x1 = round(start + (end - start) * t1)
                alpha = round(color[3] * (1.0 - t0 * 0.82))
                draw.line((x0, center_y, x1, center_y), fill=(*color[:3], alpha), width=stroke)
        diamond = ctx.scale_px(4)
        draw.polygon(
            ((centre_x, center_y - diamond), (centre_x + diamond, center_y), (centre_x, center_y + diamond), (centre_x - diamond, center_y)),
            fill=_with_alpha(PRIMARY, color[3]),
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class RoseliaTitle:
    """Centred serif title lockup with rules and the original rose crest."""

    text: str
    font_size: int = 40
    subtitle: str | None = None
    text_color: ColorLike = rgba(238, 230, 242, 255)
    rule_color: ColorLike = RULE

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        width = constraints.max_width if constraints.max_width is not None else 520
        height = 104 if self.subtitle else 82
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        display = self.text.isascii()
        path = DISPLAY_FONT if display else BODY_FONT
        requested = ctx.scale_px(self.font_size)
        minimum = ctx.scale_px(24)
        max_width = max(1, rect.width - ctx.scale_px(64))
        font_size = requested
        while font_size > minimum:
            font = load_font(font_size, path)
            bbox = draw.textbbox((0, 0), self.text, font=font)
            if bbox[2] - bbox[0] <= max_width:
                break
            font_size -= ctx.scale_px(1)
        font = load_font(max(minimum, font_size), path)
        bbox = draw.textbbox((0, 0), self.text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        centre_x = rect.width // 2
        text_y = ctx.scale_px(25) - bbox[1]
        draw.text(
            (centre_x - text_width // 2, text_y),
            self.text,
            font=font,
            fill=normalize_color(self.text_color),
        )

        crest_size = ctx.scale_px(22)
        crest = rose_crest(crest_size, PRIMARY)
        alpha_composite_paste(layer, crest, (centre_x - crest_size // 2, 0))
        rule_y = ctx.scale_px(11)
        gap = ctx.scale_px(17)
        rule = normalize_color(self.rule_color)
        stroke = max(1, ctx.scale_px(1))
        draw.line((ctx.scale_px(10), rule_y, centre_x - gap, rule_y), fill=rule, width=stroke)
        draw.line((centre_x + gap, rule_y, rect.width - ctx.scale_px(10), rule_y), fill=rule, width=stroke)

        bottom_y = min(rect.height - ctx.scale_px(4), text_y + text_height + ctx.scale_px(10))
        draw.line(
            (centre_x - min(text_width // 2, ctx.scale_px(120)), bottom_y, centre_x + min(text_width // 2, ctx.scale_px(120)), bottom_y),
            fill=_with_alpha(RULE, 150),
            width=stroke,
        )
        if self.subtitle:
            sub_font = load_font(ctx.scale_px(18), DISPLAY_FONT if self.subtitle.isascii() else BODY_FONT)
            sub_bbox = draw.textbbox((0, 0), self.subtitle, font=sub_font)
            sub_width = sub_bbox[2] - sub_bbox[0]
            draw.text(
                (centre_x - sub_width // 2, bottom_y + ctx.scale_px(5) - sub_bbox[1]),
                self.subtitle,
                font=sub_font,
                fill=_with_alpha(self.text_color, 190),
            )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class RoseliaAvatarDisc:
    """Circular cool-grey avatar disc with an initial-letter fallback."""

    source: ImageSource | None
    initial: str
    size: int
    fill: ColorLike = rgba(226, 221, 235, 255)
    initial_color: ColorLike = TEXT

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(self.size, self.size))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        side = min(rect.width, rect.height)
        if side <= 0:
            return
        scale = 3
        box = side * scale
        layer = Image.new("RGBA", (box, box), (0, 0, 0, 0))
        mask = Image.new("L", (box, box), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, box - 1, box - 1), fill=255)
        if self.source is not None:
            art = resize_cover(load_image(ctx, self.source), box, box)
            layer.paste(art, (0, 0), mask)
        else:
            fill = normalize_color(self.fill)
            assert fill is not None
            base = Image.new("RGBA", (box, box), fill)
            layer.paste(base, (0, 0), mask)
            draw = ImageDraw.Draw(layer)
            glyph = (self.initial or "?")[:1]
            font = load_font(max(8, round(box * 0.46)), BODY_FONT)
            bbox = draw.textbbox((0, 0), glyph, font=font)
            draw.text(
                ((box - (bbox[2] - bbox[0])) // 2 - bbox[0], (box - (bbox[3] - bbox[1])) // 2 - bbox[1]),
                glyph,
                font=font,
                fill=normalize_color(self.initial_color),
            )
        rendered = layer.resize((side, side), Image.Resampling.LANCZOS)
        alpha_composite_paste(
            canvas,
            rendered,
            (rect.x + (rect.width - side) // 2, rect.y + (rect.height - side) // 2),
        )


def frame_overlay(avatar_size: int) -> Image.Image:
    """Create the unequipped double-ring, leaf, and bud avatar decoration."""

    canvas_size = max(4, round(avatar_size * FRAME_CANVAS / FRAME_AVATAR_DIAMETER))
    scale = 4
    box = canvas_size * scale
    image = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    centre = box / 2
    avatar_radius = box * FRAME_AVATAR_DIAMETER / FRAME_CANVAS / 2
    stroke = max(2, round(box * 0.018))
    draw.ellipse(
        (centre - avatar_radius - stroke, centre - avatar_radius - stroke, centre + avatar_radius + stroke, centre + avatar_radius + stroke),
        outline=PRIMARY,
        width=stroke,
    )
    outer = avatar_radius + stroke * 2.1
    draw.ellipse(
        (centre - outer, centre - outer, centre + outer, centre + outer),
        outline=_with_alpha(RULE, 220),
        width=max(1, stroke // 2),
    )
    leaf = box * 0.065
    draw.polygon(
        ((box * 0.18, box * 0.72), (box * 0.04, box * 0.69), (box * 0.12, box * 0.82)),
        fill=_with_alpha(PRIMARY, 225),
    )
    draw.polygon(
        ((box * 0.81, box * 0.28), (box * 0.94, box * 0.21), (box * 0.89, box * 0.36)),
        fill=_with_alpha(PRIMARY, 225),
    )
    bud_x, bud_y = box * 0.72, box * 0.045
    draw.ellipse((bud_x - leaf / 2, bud_y - leaf / 2, bud_x + leaf / 2, bud_y + leaf / 2), fill=ROSE)
    return image.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)


@dataclass(frozen=True)
class PointedArchImage:
    """Image or crest placeholder clipped into a narrow pointed arch."""

    source: ImageSource | None
    height: int
    placeholder_color: ColorLike = rgba(116, 80, 168, 72)
    fit: str = "cover"

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(constraints.max_width or self.height, self.height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        if self.source is not None:
            source = load_image(ctx, self.source)
            art = resize_cover(source, rect.width, rect.height) if self.fit == "cover" else resize_contain(source, rect.width, rect.height)
            layer.paste(art, ((rect.width - art.width) // 2, (rect.height - art.height) // 2))
        else:
            crest_size = max(ctx.scale_px(36), min(rect.width, rect.height) // 2)
            crest = rose_crest(crest_size, _with_alpha(self.placeholder_color, 110))
            alpha_composite_paste(layer, crest, ((rect.width - crest_size) // 2, (rect.height - crest_size) // 2))

        mask = Image.new("L", (rect.width, rect.height), 0)
        draw = ImageDraw.Draw(mask)
        shoulder = min(rect.height // 3, rect.width // 2)
        draw.polygon(
            ((rect.width // 2, 0), (rect.width - 1, shoulder), (rect.width - 1, rect.height - 1), (0, rect.height - 1), (0, shoulder)),
            fill=255,
        )
        layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", mask.size, 0), mask))
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


__all__ = [
    "BACKGROUND_BOTTOM",
    "BACKGROUND_TOP",
    "BODY_FONT",
    "DISPLAY_FONT",
    "FRAME_AVATAR_DIAMETER",
    "FRAME_CANVAS",
    "GLASS",
    "GOLD",
    "LeafPair",
    "MUTED",
    "PANEL",
    "PAPER",
    "PRIMARY",
    "PointedArchImage",
    "PetalScatter",
    "ROSE",
    "RULE",
    "RoseCrest",
    "RoseliaAvatarDisc",
    "RoseliaBackground",
    "RoseliaPanel",
    "RoseliaSeparator",
    "RoseliaText",
    "RoseliaTitle",
    "TEXT",
    "frame_overlay",
    "rose_crest",
]
