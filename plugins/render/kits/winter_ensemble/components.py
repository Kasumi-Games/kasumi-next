"""Deterministic snow and flat stationery; no seasonal clock or artwork."""

import math
from pathlib import Path
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw

from plugins.render.core import Rect
from plugins.render.core import Size
from plugins.render.core import Component
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.color import ColorLike
from plugins.render.color import normalize_color
from plugins.render.layout import Frame
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike
from plugins.render.spacing import as_insets
from plugins.render.kits.atoms import KitText
from plugins.render.kits.atoms import KitImage
from plugins.render.kits.atoms import KitSeparator
from plugins.render.kits.atoms import load_image
from plugins.render.kits.atoms import resize_contain
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste
from plugins.render.raster_cache import cached_background
from plugins.render.kits.mewtype.fonts import CHINESE_BODY_FONT
from plugins.render.kits.mewtype.fonts import CHINESE_HEADING_FONT

SNOW = (229, 237, 242, 255)
PAPER = (255, 248, 236, 255)
INK = (36, 59, 83, 255)
MUTED = (92, 111, 126, 255)
LINE = (205, 210, 207, 255)
STAMP = (168, 75, 80, 255)
AMBER = (213, 138, 69, 255)
NUMBER_FONT = (
    Path(__file__).parents[1] / "roselia/resources/fonts/CormorantSC-SemiBold.ttf"
)
GILT = (181, 158, 119, 255)
FROST = (143, 171, 188, 255)


def snowflake(draw, x, y, radius, color, width):
    """Six cut-crystal arms; coordinates are already in render pixels."""
    for i in range(6):
        angle = math.pi * i / 3 - math.pi / 2
        u, v = math.cos(angle), math.sin(angle)
        draw.line((x, y, x + u * radius, y + v * radius), fill=color, width=width)
        for side in (-1, 1):
            draw.line(
                (
                    x + u * radius * 0.55,
                    y + v * radius * 0.55,
                    x + u * radius * 0.76 - v * side * radius * 0.23,
                    y + v * radius * 0.76 + u * side * radius * 0.23,
                ),
                fill=color,
                width=width,
            )


def sprig(draw, x, y, scale, color, *, mirror=1):
    """An engraved pine sprig confined to the surrounding margin."""
    points = [
        (x + mirror * t * scale, y + (t * 0.48 + t * t * 0.004) * scale)
        for t in range(0, 73, 3)
    ]
    draw.line(points, fill=color, width=max(1, round(scale)), joint="curve")
    for t in (14, 27, 40, 53, 66):
        px, py = x + mirror * t * scale, y + (t * 0.48 + t * t * 0.004) * scale
        for side in (-1, 1):
            ex, ey = px - mirror * (9 + side * 4) * scale, py + side * 11 * scale
            mx, my = (px + ex) / 2, (py + ey) / 2
            draw.polygon(
                [
                    (px, py),
                    (mx + 2 * scale, my + mirror * 2 * scale),
                    (ex, ey),
                    (mx - 2 * scale, my - mirror * 2 * scale),
                ],
                fill=color,
            )


@dataclass(frozen=True)
class WinterRule(KitSeparator):
    """A hairline and central engraved lozenge, with measured breathing room."""

    def measure(self, ctx, constraints):
        size = super().measure(ctx, constraints)
        return constraints.clamp(Size(size.width, 12))

    def render(self, ctx, canvas, rect):
        if min(rect.width, rect.height) <= 0:
            return
        draw = ImageDraw.Draw(canvas)
        x, y = rect.x + rect.width // 2, rect.y + rect.height // 2
        gap = ctx.scale_px(10)
        weight = max(1, ctx.scale_px(1))
        draw.line((rect.x, y, x - gap, y), fill=LINE, width=weight)
        draw.line((x + gap, y, rect.right - 1, y), fill=LINE, width=weight)
        r = ctx.scale_px(3)
        draw.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=GILT)


@dataclass(frozen=True)
class WinterBackground:
    fill: ColorLike = SNOW

    @cached_background
    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new(
            "RGBA", (size.width, size.height), normalize_color(self.fill)
        )
        if min(size.width, size.height) == 0:
            return canvas
        if normalize_color(self.fill) == SNOW:
            wash = Image.new("RGBA", (1, 2))
            wash.putpixel((0, 0), (220, 232, 240, 255))
            wash.putpixel((0, 1), (237, 242, 244, 255))
            canvas = wash.resize((size.width, size.height), Image.Resampling.BILINEAR)
        draw = ImageDraw.Draw(canvas)
        step = max(1, ctx.scale_px(113))
        for row, y in enumerate(range(step // 2, size.height, step)):
            for col, x in enumerate(range(step // 3, size.width, step)):
                x += ctx.scale_px((row * 29 + col * 17) % 47 - 23)
                y0 = y + ctx.scale_px((col * 19) % 37 - 18)
                r = max(1, ctx.scale_px(1))
                draw.ellipse((x - r, y0 - r, x + r, y0 + r), fill=(249, 252, 253, 255))
        # A low, quiet street silhouette belongs to the edge, never the content.
        if normalize_color(self.fill) == SNOW:
            # Pale, engraved branches remain in the outside gutter.
            sprig(
                draw,
                size.width - ctx.scale_px(12),
                ctx.scale_px(130),
                ctx.scale_px(1),
                (184, 202, 211, 255),
                mirror=-1,
            )
            sprig(
                draw,
                ctx.scale_px(12),
                size.height - ctx.scale_px(170),
                ctx.scale_px(1),
                (184, 202, 211, 255),
            )
            for x, y, r in [
                (size.width - ctx.scale_px(26), ctx.scale_px(45), 10),
                (ctx.scale_px(24), size.height - ctx.scale_px(220), 7),
            ]:
                snowflake(
                    draw,
                    x,
                    y,
                    ctx.scale_px(r),
                    (169, 191, 204, 255),
                    max(1, ctx.scale_px(1)),
                )
            base = size.height - ctx.scale_px(4)
            for i, x in enumerate(range(0, size.width, ctx.scale_px(82))):
                h = ctx.scale_px(9 + i * 7 % 15)
                w = ctx.scale_px(54 + i * 11 % 23)
                draw.rectangle((x, base - h, x + w, base), fill=(192, 208, 218, 255))
                draw.polygon(
                    [
                        (x, base - h),
                        (x + w // 2, base - h - ctx.scale_px(7)),
                        (x + w, base - h),
                    ],
                    fill=(192, 208, 218, 255),
                )
                draw.rectangle(
                    (
                        x + w // 2,
                        base - h + ctx.scale_px(5),
                        x + w // 2 + ctx.scale_px(4),
                        base - h + ctx.scale_px(10),
                    ),
                    fill=(235, 216, 185, 255),
                )
                if i % 2 == 0:
                    for wx in range(
                        x + ctx.scale_px(9), x + w - ctx.scale_px(5), ctx.scale_px(12)
                    ):
                        draw.rectangle(
                            (
                                wx,
                                base - ctx.scale_px(7),
                                wx + ctx.scale_px(3),
                                base - ctx.scale_px(3),
                            ),
                            fill=(235, 216, 185, 255),
                        )
                # Snow caps keep the skyline light; alternating window heights
                # suggest a street without adding another illustration panel.
                draw.line(
                    (
                        x,
                        base - h,
                        x + w // 2,
                        base - h - ctx.scale_px(7),
                        x + w,
                        base - h,
                    ),
                    fill=(247, 250, 250, 255),
                    width=max(1, ctx.scale_px(2)),
                )
        return canvas


@dataclass(frozen=True)
class WinterPaper:
    child: Component | None = None
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    padding: InsetsLike = 0
    fill: ColorLike = PAPER
    radius: int = 4
    border: ColorLike = LINE
    weight: int = 1
    tape: bool = False
    index: bool = False
    perforation: int | None = None

    def _frame(self):
        return Frame(
            self.child,
            width=self.width,
            height=self.height,
            padding=self.padding,
            align_x="stretch",
            align_y="stretch",
        )

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return self._frame().measure(ctx, constraints)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if min(rect.width, rect.height) <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height))
        d = ImageDraw.Draw(layer)
        inset = ctx.scale_px(4) if self.tape else 0
        if self.tape:
            d.rectangle(
                (ctx.scale_px(3), inset, rect.width - 1, rect.height - 1),
                fill=(192, 204, 209, 255),
            )
        bounds = (0, 0, rect.width - 1 - inset, rect.height - 1 - inset)
        d.rounded_rectangle(
            bounds,
            ctx.scale_px(self.radius),
            fill=normalize_color(self.fill),
            outline=normalize_color(self.border),
            width=max(1, ctx.scale_px(self.weight)),
        )
        if self.index:
            d.rectangle((0, 0, ctx.scale_px(3), rect.height - 1), fill=STAMP)
        if self.perforation is not None:
            y = ctx.scale_px(self.perforation)
            for x in range(
                ctx.scale_px(10), rect.width - ctx.scale_px(10), ctx.scale_px(12)
            ):
                d.line(
                    (x, y, x + ctx.scale_px(5), y),
                    fill=LINE,
                    width=max(1, ctx.scale_px(1)),
                )
            r = ctx.scale_px(5)
            for x in (0, rect.width - 1):
                d.ellipse((x - r, y - r, x + r, y + r), fill=(0, 0, 0, 0))
            if self.weight >= 3:
                edge = ctx.scale_px(7)
                d.rectangle(
                    (edge, edge, rect.width - edge - 1, rect.height - edge - 1),
                    outline=(217, 191, 150, 255),
                    width=max(1, ctx.scale_px(1)),
                )
        if self.tape and normalize_color(self.fill) == PAPER:
            # Faint paper fibres and a short translucent plaid binding strip.
            for y in range(ctx.scale_px(11), rect.height - inset, ctx.scale_px(23)):
                d.line(
                    (ctx.scale_px(2), y, rect.width - inset - 2, y),
                    fill=(248, 241, 230, 255),
                )
            x, w, h = ctx.scale_px(32), ctx.scale_px(86), ctx.scale_px(13)
            d.rectangle((x, 0, x + w, h), fill=(220, 183, 174, 255))
            for px in range(x, x + w, ctx.scale_px(8)):
                d.line(
                    (px, 0, px, h),
                    fill=(193, 140, 135, 255),
                    width=max(1, ctx.scale_px(2)),
                )
            d.line(
                (x, h // 2, x + w, h // 2),
                fill=(241, 214, 201, 255),
                width=max(1, ctx.scale_px(2)),
            )
        padding = as_insets(self.padding)
        ornate = (
            normalize_color(self.fill) == PAPER
            and self.radius <= 8
            and min(padding.left, padding.right, padding.top, padding.bottom) >= 24
            and rect.width >= ctx.scale_px(160)
            and rect.height >= ctx.scale_px(140)
        )
        if ornate:
            # All engraving is within the reserved padding, never behind text.
            edge = ctx.scale_px(10)
            right, bottom = (
                rect.width - 1 - inset - edge,
                rect.height - 1 - inset - edge,
            )
            d.rectangle(
                (edge, edge, right, bottom),
                outline=(215, 201, 176, 255),
                width=max(1, ctx.scale_px(1)),
            )
            e2 = edge + ctx.scale_px(4)
            d.line(
                (e2, ctx.scale_px(36), e2, bottom - ctx.scale_px(26)),
                fill=(231, 222, 204, 255),
                width=max(1, ctx.scale_px(1)),
            )
            d.line(
                (
                    right - ctx.scale_px(4),
                    ctx.scale_px(36),
                    right - ctx.scale_px(4),
                    bottom - ctx.scale_px(26),
                ),
                fill=(231, 222, 204, 255),
                width=max(1, ctx.scale_px(1)),
            )
            for x, y in [(edge, edge), (right, edge), (edge, bottom), (right, bottom)]:
                r = ctx.scale_px(4)
                d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=GILT)
            # Small corner crystal stamps give the paper an engraved finish.
            for x, y in [
                (ctx.scale_px(24), ctx.scale_px(24)),
                (right - ctx.scale_px(14), bottom - ctx.scale_px(14)),
            ]:
                snowflake(
                    d,
                    x,
                    y,
                    ctx.scale_px(7),
                    (183, 165, 137, 255),
                    max(1, ctx.scale_px(1)),
                )
        self._frame().render(ctx, layer, Rect(0, 0, rect.width, rect.height))
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class WinterHeading:
    text: str
    font_size: int = 52

    def _text(self):
        return KitText(
            self.text, CHINESE_HEADING_FONT, font_size=self.font_size, color=INK
        )

    def measure(self, ctx, constraints):
        size = ctx.measure(self._text(), constraints.shrink(height=28))
        return constraints.clamp(Size(size.width, size.height + 28))

    def render(self, ctx, canvas, rect):
        d = ImageDraw.Draw(canvas)
        d.line(
            (rect.x, rect.y, rect.right - 1, rect.y),
            fill=INK,
            width=max(1, ctx.scale_px(2)),
        )
        d.line(
            (
                rect.x,
                rect.y + ctx.scale_px(5),
                rect.right - 1,
                rect.y + ctx.scale_px(5),
            ),
            fill=(179, 163, 134, 255),
            width=max(1, ctx.scale_px(1)),
        )
        dy = ctx.scale_px(25)
        text_width = rect.width
        if rect.width >= ctx.scale_px(600):
            # Only use spare header space; a long business title gets it back.
            measured = ctx.measure(
                self._text(), Constraints(max_width=ctx.unscale_px(rect.width))
            )
            if (
                measured.width <= ctx.unscale_px(rect.width) - 150
                and measured.height < self.font_size * 2
            ):
                x, y = rect.right - ctx.scale_px(35), rect.y + dy + ctx.scale_px(28)
                r = ctx.scale_px(23)
                d.ellipse(
                    (x - r, y - r, x + r, y + r),
                    outline=FROST,
                    width=max(1, ctx.scale_px(1)),
                )
                snowflake(d, x, y, ctx.scale_px(15), FROST, max(1, ctx.scale_px(1)))
                sprig(
                    d,
                    x - ctx.scale_px(82),
                    y - ctx.scale_px(13),
                    ctx.scale_px(0.6),
                    FROST,
                )
                text_width -= ctx.scale_px(140)
        self._text().render(
            ctx, canvas, Rect(rect.x, rect.y + dy, text_width, max(0, rect.height - dy))
        )


@dataclass(frozen=True)
class WinterArt(KitImage):
    """Fit the visible art, retaining all nontransparent pixels and the source."""

    def render(self, ctx, canvas, rect):
        if rect.width <= 0 or rect.height <= 0:
            return
        source = load_image(ctx, self.source)
        bounds = source.getchannel("A").getbbox()
        if bounds is None:
            return
        fitted = resize_contain(source.crop(bounds), rect.width, rect.height)
        alpha_composite_paste(
            canvas,
            fitted,
            (
                rect.x + (rect.width - fitted.width) // 2,
                rect.y + (rect.height - fitted.height) // 2,
            ),
        )


@dataclass(frozen=True)
class WinterSeal:
    text: str

    def measure(self, ctx, constraints):
        return constraints.clamp(Size(148, 56))

    def render(self, ctx, canvas, rect):
        layer = Image.new("RGBA", (rect.width, rect.height))
        d = ImageDraw.Draw(layer)
        pad = ctx.scale_px(7)
        d.rectangle(
            (pad, pad, rect.width - pad - 1, rect.height - pad - 1),
            outline=STAMP,
            width=max(1, ctx.scale_px(2)),
        )
        inside = pad + ctx.scale_px(3)
        d.rectangle(
            (inside, inside, rect.width - inside - 1, rect.height - inside - 1),
            outline=(187, 113, 111, 255),
            width=max(1, ctx.scale_px(1)),
        )
        font = load_font(ctx.scale_px(22), CHINESE_HEADING_FONT)
        d.text(
            (rect.width // 2, rect.height // 2),
            self.text,
            font=font,
            anchor="mm",
            fill=STAMP,
        )
        alpha_composite_paste(
            canvas, layer.rotate(5, Image.Resampling.BICUBIC), (rect.x, rect.y)
        )


@dataclass(frozen=True)
class WinterMark:
    day: int
    done: bool = False
    gift: bool = False

    def measure(self, ctx, constraints):
        return constraints.clamp(Size(80, 100))

    def render(self, ctx, canvas, rect):
        d = ImageDraw.Draw(canvas)
        cx, cy, r = (
            rect.x + rect.width // 2,
            rect.y + ctx.scale_px(32),
            ctx.scale_px(28),
        )
        box = (cx - r, cy - r, cx + r, cy + r)
        if self.done:
            d.ellipse(box, outline=STAMP, width=max(1, ctx.scale_px(2)))
            r2 = r - ctx.scale_px(5)
            d.ellipse(
                (cx - r2, cy - r2, cx + r2, cy + r2),
                outline=STAMP,
                width=max(1, ctx.scale_px(1)),
            )
            points = []
            for i in range(10):
                angle = i * math.pi / 5 - math.pi / 2 + (self.day % 3 - 1) * 0.12
                length = ctx.scale_px(16 if i % 2 == 0 else 7)
                points.append(
                    (cx + math.cos(angle) * length, cy + math.sin(angle) * length)
                )
            d.polygon(points, fill=STAMP)
        else:
            for angle in range(0, 360, 24):
                d.arc(box, angle, angle + 13, fill=LINE, width=max(1, ctx.scale_px(1)))
            if self.gift:
                a = ctx.scale_px(11)
                d.rectangle(
                    (cx - a, cy - a // 2, cx + a, cy + a),
                    outline=STAMP,
                    width=max(1, ctx.scale_px(2)),
                )
                d.line(
                    (cx, cy - a, cx, cy + a), fill=STAMP, width=max(1, ctx.scale_px(2))
                )
                d.arc(
                    (cx - a, cy - a, cx, cy),
                    180,
                    360,
                    fill=STAMP,
                    width=max(1, ctx.scale_px(2)),
                )
                d.arc(
                    (cx, cy - a, cx + a, cy),
                    180,
                    360,
                    fill=STAMP,
                    width=max(1, ctx.scale_px(2)),
                )
            else:
                d.text(
                    (cx, cy),
                    str(self.day),
                    font=load_font(ctx.scale_px(24), NUMBER_FONT),
                    fill=INK,
                    anchor="mm",
                )
        d.text(
            (cx, rect.y + ctx.scale_px(84)),
            f"{self.day:02d}",
            font=load_font(ctx.scale_px(22), CHINESE_BODY_FONT),
            fill=INK,
            anchor="mm",
        )
