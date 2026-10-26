"""Pillow translation of Manosaba's ink, aged paper and botanical UI.

All cached rasters are private, immutable inputs. Components composite on local
layers so ornaments never escape their assigned rectangle.
"""

from typing import Literal
from pathlib import Path
from functools import lru_cache
from contextvars import ContextVar
from dataclasses import dataclass

from PIL import Image
from PIL import ImageOps
from PIL import ImageDraw

from plugins.render.core import Rect
from plugins.render.core import Size
from plugins.render.core import Component
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.color import ColorLike
from plugins.render.color import normalize_color
from plugins.render.layout import Frame
from plugins.render.sizing import Fixed
from plugins.render.sizing import SizeValue
from plugins.render.sizing import as_size_value
from plugins.render.spacing import Insets
from plugins.render.spacing import InsetsLike
from plugins.render.spacing import as_insets
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste
from plugins.render.text_layout import ellipsis
from plugins.render.text_layout import text_width

from ..atoms import KitText
from ..atoms import fixed_or_bound

RESOURCES = Path(__file__).with_name("resources")
SERIF = RESOURCES / "SourceHanSerifSC.otf"
INK = (43, 34, 39, 255)
ROSE = (136, 43, 65, 255)
PINK = (255, 146, 174, 255)
PAPER = (232, 219, 214, 255)
SURFACE = (247, 237, 229, 255)
MUTED = (116, 95, 102, 255)
_panel_depth = ContextVar("manosaba_panel_depth", default=0)


@lru_cache(maxsize=24)
def asset(name: str) -> Image.Image:
    """Load only the curated, bundled assets; no game/runtime dependency."""
    with Image.open(RESOURCES / name) as image:
        return image.convert("RGBA")


@lru_cache(maxsize=48)
def resized(name: str, width: int, height: int) -> Image.Image:
    return asset(name).resize((max(1, width), max(1, height)), Image.Resampling.LANCZOS)


def ornament(
    canvas: Image.Image, name: str, box: tuple[int, int, int, int], opacity: float = 1
) -> None:
    x, y, width, height = box
    if width <= 0 or height <= 0:
        return
    image = resized(name, width, height)
    if opacity < 1:
        image = image.copy()
        image.putalpha(image.getchannel("A").point(lambda a: round(a * opacity)))
    alpha_composite_paste(canvas, image, (x, y))


@lru_cache(maxsize=24)
def paper_surface(width: int, height: int) -> Image.Image:
    # Cover preserves the original brush texture's aspect ratio on tall pages.
    texture = ImageOps.fit(
        asset("paper.png"), (width, height), method=Image.Resampling.LANCZOS
    )
    return Image.blend(texture, Image.new("RGBA", (width, height), PAPER), 0.76)


def book_paper(width: int, height: int, *, spine: float = 0.495) -> Image.Image:
    """Fit both complete leaves to a layout's binding position.

    The original binding is at 49.5% of the source. Resize each facing page
    independently, keeping its torn edges, stains, shadows and curved fold.
    No texture is discarded or painted back as an isolated separator.
    """
    if not 0 < spine < 1:
        raise ValueError("Book spine must lie strictly inside the page")
    width, height = max(2, width), max(1, height)
    source = asset("book.png")
    split = round(source.width * 0.495)
    target = max(1, min(width - 1, round(width * spine)))
    canvas = Image.new("RGBA", (width, height))
    for start, end, left, right in (
        (0, split, 0, target),
        (split, source.width, target, width),
    ):
        leaf = source.crop((start, 0, end, source.height))
        canvas.paste(
            leaf.resize((right - left, height), Image.Resampling.LANCZOS), (left, 0)
        )
    return canvas


@dataclass(frozen=True)
class ManosabaBackground:
    fill: ColorLike | None = None

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        if size.width <= 0 or size.height <= 0:
            return Image.new("RGBA", (size.width, size.height))
        if self.fill is not None:
            return Image.new(
                "RGBA", (size.width, size.height), normalize_color(self.fill)
            )
        canvas = paper_surface(size.width, size.height).copy()
        edge = min(ctx.scale_px(56), max(8, size.height // 6))
        ornament(canvas, "thorns_top.png", (0, 0, size.width, edge), 0.75)
        ornament(
            canvas, "thorns_bottom.png", (0, size.height - edge, size.width, edge), 0.8
        )
        draw = ImageDraw.Draw(canvas)
        margin = min(ctx.scale_px(18), size.width // 5, size.height // 5)
        if size.width > 2 * margin and size.height > 2 * margin:
            draw.rectangle(
                (margin, margin, size.width - margin - 1, size.height - margin - 1),
                outline=(*ROSE[:3], 255),
                width=max(1, ctx.scale_px(1)),
            )
        return canvas


@dataclass(frozen=True)
class ManosabaPanel:
    child: Component | None = None
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    padding: InsetsLike = 0
    fill: ColorLike = SURFACE
    radius: int | None = None
    ornate: bool = True
    border: ColorLike = (128, 105, 108, 255)
    weight: int = 1
    texture: str | None = None
    book_spine: float = 0.495

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
        layer = Image.new("RGBA", (rect.width, rect.height))
        draw = ImageDraw.Draw(layer)
        stroke = max(1, ctx.scale_px(self.weight))
        bounds = (0, 0, rect.width - 1, rect.height - 1)
        draw.rounded_rectangle(
            bounds,
            radius=ctx.scale_px(self.radius or 0),
            fill=normalize_color(self.fill),
            outline=normalize_color(self.border),
            width=stroke,
        )
        if self.texture is not None and self.radius is None:
            paper = (
                book_paper(rect.width, rect.height, spine=self.book_spine)
                if self.texture == "book.png"
                else resized(self.texture, rect.width, rect.height)
            )
            layer = Image.blend(layer, paper, 0.16)
            draw = ImageDraw.Draw(layer)
        padding = as_insets(self.padding)
        # Small list rows must not put flourishes behind their badge or star
        # count. Nested cards use a single rule rather than repeating frames.
        corner = min(24, max(0, min(padding.left, padding.right) - 6))
        if (
            self.ornate
            and self.radius is None
            and _panel_depth.get() == 0
            and corner >= 12
            and min(rect.width, rect.height) >= ctx.scale_px(54)
        ):
            inset = ctx.scale_px(5)
            draw.rectangle(
                (inset, inset, rect.width - inset - 1, rect.height - inset - 1),
                outline=normalize_color(self.border),
                width=max(1, ctx.scale_px(1)),
            )
            corner = min(ctx.scale_px(corner), rect.height // 3, rect.width // 5)
            ornament(
                layer,
                "flourish_left.png",
                (0, rect.height - corner, corner, corner),
                0.48,
            )
            ornament(
                layer,
                "flourish_right.png",
                (rect.width - corner, 0, corner, corner),
                0.48,
            )
        # The child renders on the same bounded layer; transparent custom fills
        # retain their alpha when composited onto the parent.
        token = _panel_depth.set(_panel_depth.get() + 1)
        try:
            Frame(
                self.child, padding=self.padding, align_x="stretch", align_y="stretch"
            ).render(ctx, layer, Rect(0, 0, rect.width, rect.height))
        finally:
            _panel_depth.reset(token)
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class ManosabaTitle:
    text: str
    font_size: int = 40

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        face = KitText(
            self.text, SERIF, font_size=self.font_size, wrap=False, max_lines=1
        )
        natural = face.measure(ctx, Constraints()).width + 88
        return constraints.clamp(Size(natural, round(self.font_size * 1.45) + 32))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height))
        # Actual distressed button art, with the lettering authored by the kit.
        ornament(layer, "tab.png", (0, 0, rect.width, rect.height))
        pad = min(ctx.scale_px(44), rect.width // 4)
        minimum_face = load_font(ctx.scale_px(22), SERIF)
        if text_width(self.text, minimum_face) + pad * 2 > rect.width:
            pad = min(
                pad,
                max(
                    ctx.scale_px(16),
                    (rect.width - text_width(self.text, minimum_face)) // 2,
                ),
            )
        available = max(1, rect.width - pad * 2)
        size = ctx.scale_px(self.font_size)
        face = load_font(size, SERIF)
        while size > ctx.scale_px(22) and text_width(self.text, face) > available:
            size -= 1
            face = load_font(size, SERIF)
        label = ellipsis(self.text, face, available)
        bbox = face.getbbox(label)
        y = (rect.height - (bbox[3] - bbox[1])) // 2 - bbox[1] - ctx.scale_px(4)
        draw = ImageDraw.Draw(layer)
        draw.text((pad, y), label, font=face, fill=SURFACE)
        if label:
            draw.text((pad, y), label[0], font=face, fill=PINK)
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class ManosabaSeparator:
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    length: SizeValue | int | None = None
    thickness: int = 2
    color: ColorLike = ROSE

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        bound = (
            constraints.max_width
            if self.orientation == "horizontal"
            else constraints.max_height
        )
        length = fixed_or_bound(self.length, bound, "ManosabaSeparator.length")
        return (
            Size(length, self.thickness)
            if self.orientation == "horizontal"
            else Size(self.thickness, length)
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height))
        draw = ImageDraw.Draw(layer)
        color = normalize_color(self.color)
        if self.orientation == "horizontal":
            middle = rect.width // 2
            cy = rect.height // 2
            r = min(rect.height // 2, ctx.scale_px(7))
            draw.line(
                (0, cy, rect.width - 1, cy), fill=color, width=max(1, ctx.scale_px(1))
            )
            draw.polygon(
                (
                    (middle - r, cy),
                    (middle, cy - r),
                    (middle + r, cy),
                    (middle, cy + r),
                ),
                fill=color,
            )
        else:
            draw.line(
                (rect.width // 2, 0, rect.width // 2, rect.height - 1),
                fill=color,
                width=max(1, ctx.scale_px(self.thickness)),
            )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class ChoicePanel:
    """Original ornamented choice ribbon, keeping its end caps undistorted."""

    child: Component
    width: SizeValue | int | None = None
    height: SizeValue | int = 68
    active: bool = False

    @staticmethod
    def _padding(height: int) -> Insets:
        # Reserve the actual ornamental end cap, including on 240px command
        # tiles; a constant 30px inset lets long labels paint over its curls.
        return Insets.xy(round(150 * height / 220) + 6, 12)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        height = as_size_value(self.height)
        return Frame(
            self.child,
            width=self.width,
            height=self.height,
            padding=self._padding(height.value if isinstance(height, Fixed) else 68),
            align_x="stretch",
            align_y="center",
        ).measure(ctx, constraints)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        width = as_size_value(self.width)
        if isinstance(width, Fixed):
            rect = Rect(
                rect.x, rect.y, min(rect.width, ctx.scale_px(width.value)), rect.height
            )
        source = asset("choice_active.png" if self.active else "choice.png")
        layer = Image.new("RGBA", (rect.width, rect.height))
        cap = min(round(150 * rect.height / source.height), rect.width // 2)
        # Horizontal 3-slice: original flourishes keep their proportions.
        for box, target in [
            ((0, 0, 150, source.height), (0, 0, cap, rect.height)),
            (
                (150, 0, source.width - 150, source.height),
                (cap, 0, rect.width - 2 * cap, rect.height),
            ),
            (
                (source.width - 150, 0, source.width, source.height),
                (rect.width - cap, 0, cap, rect.height),
            ),
        ]:
            x, y, w, h = target
            if w > 0:
                alpha_composite_paste(
                    layer,
                    source.crop(box).resize((w, h), Image.Resampling.LANCZOS),
                    (x, y),
                )
        Frame(
            self.child,
            padding=self._padding(ctx.unscale_px(rect.height)),
            align_x="stretch",
            align_y="center",
        ).render(ctx, layer, Rect(0, 0, rect.width, rect.height))
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))
