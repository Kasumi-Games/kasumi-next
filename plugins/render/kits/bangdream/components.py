import random
from typing import Literal
from pathlib import Path
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw

from plugins.render.core import Rect
from plugins.render.core import Size
from plugins.render.core import Component
from plugins.render.core import Constraints
from plugins.render.core import LayoutError
from plugins.render.core import RenderContext
from plugins.render.color import ColorLike
from plugins.render.color import rgba
from plugins.render.color import normalize_color
from plugins.render.types import ImageFit
from plugins.render.types import Overflow
from plugins.render.types import TextAlign
from plugins.render.types import ImageSource
from plugins.render.layout import Frame
from plugins.render.sizing import Fit
from plugins.render.sizing import Fill
from plugins.render.sizing import Fixed
from plugins.render.sizing import Fraction
from plugins.render.sizing import SizeValue
from plugins.render.sizing import as_size_value
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import draw_pill
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste
from plugins.render.primitives import draw_rounded_rectangle
from plugins.render.text_layout import ellipsis as _ellipsis
from plugins.render.text_layout import wrap_text as _wrap_text
from plugins.render.text_layout import text_width as _text_width
from plugins.render.text_layout import draw_text_line as _draw_text_line
from plugins.render.text_layout import merge_line_limits as _merge_line_limits
from plugins.render.text_layout import display_text_width as _display_text_width
from plugins.render.text_layout import max_lines_for_height as _max_lines_for_height

from .backgrounds import BG_DIR
from .backgrounds import load_image
from .backgrounds import resize_cover
from .backgrounds import rounded_clip
from .backgrounds import with_opacity
from .backgrounds import resize_contain


@dataclass(frozen=True)
class BanGDreamText:
    """Text renderer using the bundled BanG Dream! font and wrapping rules."""

    text: str
    font: str | Path
    font_size: int = 40
    color: ColorLike = (80, 80, 80, 255)
    align: TextAlign = "left"
    wrap: bool = True
    max_lines: int | None = None
    overflow: Overflow = "ellipsis"
    line_height: int | None = None

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        lines, font_size = self._layout_text(constraints)
        font = load_font(font_size, self.font)
        line_height = self.line_height or round(font_size * 1.35)
        width = max((_text_width(line, font) for line in lines), default=0)
        if ctx.pixel_ratio > 1:
            # Same guard as ``KitText.measure``: TrueType metrics are not
            # linear in size, and render() draws at ``pixel_ratio`` scale on
            # a rect-sized layer, so a logical-size measurement can clip the
            # last glyph. Measure at draw size too and keep the safer width.
            draw_font = load_font(font_size * ctx.pixel_ratio, self.font)
            draw_width = max(
                (_text_width(line, draw_font) for line in lines), default=0
            )
            width = max(width, -(-draw_width // ctx.pixel_ratio))
        if self.wrap and constraints.max_width is not None:
            width = min(width, constraints.max_width)
        return constraints.clamp(Size(width, line_height * max(1, len(lines))))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        constraints = ctx.unscale_constraints(
            Constraints(max_width=rect.width, max_height=rect.height)
        )
        lines, font_size = self._layout_text(constraints)
        font = load_font(max(1, ctx.scale_px(font_size)), self.font)
        line_height = ctx.scale_px(self.line_height or round(font_size * 1.35))
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        y = 0
        for line in lines:
            if y >= rect.height:
                break
            line_width = _display_text_width(line, font, rect.width)
            if self.align == "center":
                x = max(0, (rect.width - line_width) // 2)
            elif self.align == "right":
                x = max(0, rect.width - line_width)
            else:
                x = 0
            _draw_text_line(
                draw,
                (x, y),
                line,
                font,
                normalize_color(self.color),
                max_width=line_width,
            )
            y += line_height
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))

    def _layout_text(self, constraints: Constraints) -> tuple[list[str], int]:
        font_size = self.font_size
        if self.overflow == "shrink" and (
            constraints.max_width is not None or constraints.max_height is not None
        ):
            while font_size > 8:
                font = load_font(font_size, self.font)
                line_height = self.line_height or round(font_size * 1.35)
                lines = _wrap_text(
                    self.text, font, constraints.max_width if self.wrap else None
                )
                width_fits = (
                    constraints.max_width is None
                    or self.wrap
                    or _text_width(self.text, font) <= constraints.max_width
                )
                height_fits = constraints.max_height is None or len(
                    lines
                ) <= _max_lines_for_height(constraints.max_height, line_height)
                if width_fits and height_fits:
                    break
                font_size -= 1
        font = load_font(font_size, self.font)
        line_height = self.line_height or round(font_size * 1.35)
        lines = _wrap_text(
            self.text, font, constraints.max_width if self.wrap else None
        )
        max_lines = _merge_line_limits(
            self.max_lines,
            (
                None
                if constraints.max_height is None
                else _max_lines_for_height(constraints.max_height, line_height)
            ),
        )
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            if self.overflow == "ellipsis":
                lines[-1] = _ellipsis(
                    lines[-1], font, constraints.max_width, force=True
                )
        elif (
            self.overflow == "ellipsis"
            and not self.wrap
            and constraints.max_width is not None
        ):
            lines = [_ellipsis(line, font, constraints.max_width) for line in lines]
        return lines or [""], font_size


@dataclass(frozen=True)
class BanGDreamImage:
    """Image renderer with contain, cover, stretch, opacity, and rounded clipping."""

    source: ImageSource
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    fit: ImageFit = "contain"
    opacity: float = 1.0
    radius: int = 0

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        image = load_image(ctx, self.source)
        width_value = as_size_value(self.width)
        height_value = as_size_value(self.height)
        if isinstance(width_value, Fit) and isinstance(height_value, Fit):
            return constraints.clamp(_fit_intrinsic_image_size(image, constraints))

        width = _resolve_image_axis(
            width_value, constraints.max_width, image.width, "BanGDreamImage.width"
        )
        height = _resolve_image_axis(
            height_value, constraints.max_height, image.height, "BanGDreamImage.height"
        )
        if isinstance(width_value, Fit) and image.height:
            width = round(image.width * (height / image.height))
        if isinstance(height_value, Fit) and image.width:
            height = round(image.height * (width / image.width))
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        image = load_image(ctx, self.source)
        if self.fit == "stretch":
            resized = image.resize((rect.width, rect.height), Image.Resampling.LANCZOS)
        elif self.fit == "cover":
            resized = resize_cover(image, rect.width, rect.height)
        else:
            resized = resize_contain(image, rect.width, rect.height)
        if self.opacity < 1:
            resized = with_opacity(resized, self.opacity)
        if self.radius > 0:
            resized = rounded_clip(resized, ctx.scale_px(self.radius))
        alpha_composite_paste(
            canvas,
            resized,
            (
                rect.x + max(0, (rect.width - resized.width) // 2),
                rect.y + max(0, (rect.height - resized.height) // 2),
            ),
        )


@dataclass(frozen=True)
class BanGDreamPanel:
    """Rounded translucent panel that stretches and renders an optional child."""

    child: Component | None = None
    fill: ColorLike = (255, 255, 255, 208)
    radius: int = 48
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None

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
        draw_rounded_rectangle(
            canvas,
            (rect.x, rect.y, rect.right, rect.bottom),
            ctx.scale_px(self.radius),
            self.fill,
        )
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, rect)


@dataclass(frozen=True)
class BanGDreamTitledPanel:
    """Panel with a top tab title and a square upper-left main corner."""

    title: str
    child: Component | None
    title_font: str | Path
    title_width: SizeValue | int
    title_height: SizeValue | int
    main_width: SizeValue | int
    main_height: SizeValue | int
    title_font_size: int = 40
    stroke_width: int = 6
    title_radius: int | None = None
    main_radius: int | None = None
    title_fill: ColorLike = rgba(234, 78, 116, 255)
    main_fill: ColorLike = rgba(255, 255, 255, 255)

    @property
    def width(self) -> SizeValue:
        return _combine_titled_panel_width(self.title_width, self.main_width)

    @property
    def height(self) -> SizeValue:
        return _combine_titled_panel_height(self.title_height, self.main_height)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(_resolve_titled_panel_layout(self, constraints).size)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        constraints = ctx.unscale_constraints(
            Constraints(max_width=rect.width, max_height=rect.height)
        )
        layout = _resolve_titled_panel_layout(self, constraints)
        scaled = ctx.scale_size(layout.size)
        layer = Image.new("RGBA", (scaled.width, scaled.height), (0, 0, 0, 0))

        title_w = ctx.scale_px(layout.title_width)
        title_h = ctx.scale_px(layout.title_height)
        main_w = ctx.scale_px(layout.main_width)
        main_h = ctx.scale_px(layout.main_height)
        stroke = max(0, ctx.scale_px(self.stroke_width))
        title_radius = (
            max(0, title_h // 2)
            if self.title_radius is None
            else max(0, ctx.scale_px(self.title_radius))
        )
        main_radius = (
            max(0, title_h // 2)
            if self.main_radius is None
            else max(0, ctx.scale_px(self.main_radius))
        )

        _draw_upper_left_square_rounded_rect(
            layer,
            (0, title_h, main_w, title_h + main_h),
            main_radius,
            self.main_fill,
        )
        _draw_top_rounded_rect(
            layer,
            (0, 0, title_w, title_h),
            title_radius,
            self.main_fill,
        )
        if title_w > stroke * 2 and title_h > stroke:
            _draw_top_rounded_rect(
                layer,
                (stroke, stroke, title_w - stroke, title_h),
                max(0, title_radius - stroke),
                self.title_fill,
            )

        draw = ImageDraw.Draw(layer)
        font = load_font(ctx.scale_px(self.title_font_size), self.title_font)
        _draw_aligned_text(
            draw,
            self.title,
            font,
            (stroke, stroke, max(stroke, title_w - stroke), title_h),
            (255, 255, 255, 255),
            align="center",
        )

        if self.child is not None:
            self.child.render(
                ctx,
                layer,
                Rect(0, title_h, main_w, main_h),
            )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class BanGDreamSeparator:
    """Rounded divider line for horizontal or vertical separation."""

    orientation: Literal["horizontal", "vertical"] = "horizontal"
    length: SizeValue | int | None = None
    thickness: int = 2
    color: ColorLike = (170, 170, 170, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        if self.orientation == "horizontal":
            return Size(
                _fixed_or_bound(
                    self.length, constraints.max_width, "BanGDreamSeparator.length"
                ),
                self.thickness,
            )
        return Size(
            self.thickness,
            _fixed_or_bound(
                self.length, constraints.max_height, "BanGDreamSeparator.length"
            ),
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        ImageDraw.Draw(canvas).rounded_rectangle(
            (rect.x, rect.y, rect.right, rect.bottom),
            radius=max(1, min(rect.width, rect.height) // 2),
            fill=normalize_color(self.color),
        )


@dataclass(frozen=True)
class BanGDreamTitlePill:
    """Two-layer pill header with a colored title band and white subtitle band."""

    title: str
    subtitle: str
    title_font: str | Path
    subtitle_font: str | Path
    pill_width: int = 500
    pill_height: int = 57
    title_fill: ColorLike = (234, 78, 116, 255)
    subtitle_fill: ColorLike = (255, 255, 255, 255)
    title_text_color: ColorLike = (255, 255, 255, 255)
    subtitle_text_color: ColorLike = (80, 80, 80, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        subtitle_pill_height = self.pill_height * 85 // 62
        subtitle_pill_width = self.pill_width * 625 // 570
        overlap_height = self.pill_height * 9 // 62
        return constraints.clamp(
            Size(
                subtitle_pill_width,
                self.pill_height + subtitle_pill_height - overlap_height,
            )
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        measured = self.measure(ctx, Constraints())
        scaled_measured = ctx.scale_size(measured)
        layer = Image.new(
            "RGBA", (scaled_measured.width, scaled_measured.height), (0, 0, 0, 0)
        )
        pill_width = ctx.scale_px(self.pill_width)
        pill_height = ctx.scale_px(self.pill_height)
        subtitle_pill_width = ctx.scale_px(self.pill_width * 625 // 570)
        overlap_height = ctx.scale_px(self.pill_height * 9 // 62)
        subtitle_top = pill_height - overlap_height
        draw_pill(
            layer,
            (0, subtitle_top, subtitle_pill_width, scaled_measured.height),
            self.subtitle_fill,
        )
        draw_pill(layer, (0, 0, pill_width, pill_height), self.title_fill)
        draw = ImageDraw.Draw(layer)
        title_font = load_font(
            ctx.scale_px(self.pill_height * 33 // 61), self.title_font
        )
        subtitle_font = load_font(
            ctx.scale_px((self.pill_height * 85 // 62) * 36 // 75),
            self.subtitle_font,
        )
        _draw_left_aligned_text(
            draw,
            self.title,
            title_font,
            (0, 0, pill_width, pill_height),
            self.title_text_color,
            left_offset=ctx.scale_px(self.pill_height // 2),
        )
        _draw_left_aligned_text(
            draw,
            self.subtitle,
            subtitle_font,
            (0, subtitle_top, subtitle_pill_width, scaled_measured.height),
            self.subtitle_text_color,
            left_offset=ctx.scale_px((self.pill_height * 85 // 62) // 2),
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class BanGDreamPill:
    """Generic pill-shaped label."""

    text: str
    font: str | Path
    width: SizeValue | int
    height: SizeValue | int
    font_size: int = 30
    fill: ColorLike | None = None
    text_color: ColorLike | None = None
    align: TextAlign = "center"

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        font = load_font(self.font_size, self.font)
        width = _resolve_pill_axis(
            as_size_value(self.width),
            constraints.max_width,
            _text_width(self.text, font),
            "BanGDreamPill.width",
        )
        height = _resolve_pill_axis(
            as_size_value(self.height),
            constraints.max_height,
            self.font_size,
            "BanGDreamPill.height",
        )
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw_pill(
            layer,
            (0, 0, rect.width, rect.height),
            self.fill or (234, 78, 116, 255),
        )
        font = load_font(ctx.scale_px(self.font_size), self.font)
        _draw_aligned_text(
            ImageDraw.Draw(layer),
            self.text,
            font,
            (0, 0, rect.width, rect.height),
            self.text_color or (255, 255, 255, 255),
            align=self.align,
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class BanGDreamRingedAvatar:
    """Circular avatar in a BanG Dream! primary ring, with an initial fallback.

    When ``source`` is ``None`` the inner disc is filled with a soft brand tint
    and carries the player's initial instead of leaving a hole. ``ring_width=0``
    disables the theme ring when an equipped cosmetic frame replaces it.
    Rendering is supersampled so the circle edge stays clean after the
    page-level downscale.

    Attributes:
        source: Optional avatar image.
        initial: Fallback glyph drawn when no avatar exists; first char is used.
        size: Logical diameter of the whole component including the ring.
        ring_color: Ring stroke color.
        ring_width: Logical ring stroke width.
        ring_gap: Logical gap between the ring and the inner disc.
        fallback_fill: Inner disc fill used for the initial fallback.
        initial_color: Initial glyph color.
        initial_font: Font used for the initial glyph.
    """

    source: ImageSource | None
    initial: str
    size: int
    ring_color: ColorLike = rgba(234, 78, 116, 255)
    ring_width: int = 3
    ring_gap: int = 2
    fallback_fill: ColorLike = rgba(250, 228, 234, 255)
    initial_color: ColorLike = rgba(80, 80, 80, 255)
    initial_font: str | Path | None = None

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

        ring_width = max(0, ctx.scale_px(self.ring_width)) * supersample
        ring_gap = (
            max(0, ctx.scale_px(self.ring_gap)) * supersample
            if ring_width > 0
            else 0
        )
        inner = max(1, big - 2 * (ring_width + ring_gap))
        inner_xy = (big - inner) // 2

        if self.source is not None:
            art = resize_cover(load_image(ctx, self.source), inner, inner)
            mask = Image.new("L", (inner, inner), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, inner - 1, inner - 1), fill=255)
            layer.paste(art, (inner_xy, inner_xy), mask)
        else:
            draw.ellipse(
                (inner_xy, inner_xy, inner_xy + inner - 1, inner_xy + inner - 1),
                fill=normalize_color(self.fallback_fill),
            )
            glyph = (self.initial or "?")[:1]
            font = load_font(max(8, round(inner * 0.46)), self.initial_font)
            bbox = draw.textbbox((0, 0), glyph, font=font)
            draw.text(
                (
                    inner_xy + (inner - (bbox[2] - bbox[0])) // 2 - bbox[0],
                    inner_xy + (inner - (bbox[3] - bbox[1])) // 2 - bbox[1],
                ),
                glyph,
                font=font,
                fill=normalize_color(self.initial_color),
            )

        if ring_width > 0:
            half_stroke = ring_width // 2
            draw.ellipse(
                (
                    half_stroke,
                    half_stroke,
                    big - half_stroke - 1,
                    big - half_stroke - 1,
                ),
                outline=normalize_color(self.ring_color),
                width=ring_width,
            )
        resized = layer.resize((side, side), Image.Resampling.LANCZOS)
        alpha_composite_paste(
            canvas,
            resized,
            (
                rect.x + max(0, (rect.width - side) // 2),
                rect.y + max(0, (rect.height - side) // 2),
            ),
        )


@dataclass(frozen=True)
class BanGDreamTileFrame:
    """Rounded outline drawn over a tile, used as the top-rarity border.

    Stretches to whatever rectangle it is given; pair it with a fixed-size
    ``Frame`` inside an ``Overlay`` so it traces the tile underneath.

    Attributes:
        radius: Logical corner radius matching the tile panel.
        color: Stroke color.
        thickness: Logical stroke width.
    """

    radius: int = 24
    color: ColorLike = rgba(234, 78, 116, 255)
    thickness: int = 4

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(
            Size(constraints.max_width or 0, constraints.max_height or 0)
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        supersample = 2
        thickness = max(1, ctx.scale_px(self.thickness)) * supersample
        radius = max(0, ctx.scale_px(self.radius)) * supersample
        temp = Image.new(
            "RGBA", (rect.width * supersample, rect.height * supersample), (0, 0, 0, 0)
        )
        inset = thickness // 2
        ImageDraw.Draw(temp).rounded_rectangle(
            (
                inset,
                inset,
                rect.width * supersample - 1 - inset,
                rect.height * supersample - 1 - inset,
            ),
            radius=radius,
            outline=normalize_color(self.color),
            width=thickness,
        )
        layer = temp.resize((rect.width, rect.height), Image.Resampling.LANCZOS)
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class BanGDreamStarScatter:
    """Deterministic sprinkle of the kit's star sprites around a tile edge.

    Positions avoid the central content box so scattered stars celebrate the
    tile without sitting under its text. The scatter is seeded, so the same
    pull always renders the same image.

    Attributes:
        seed: Random seed; pass the pull index so tiles differ.
        count: Number of stars.
        size_range: Logical star size range in pixels.
        opacity: Star alpha multiplier.
        tint: Optional solid color replacing the sprite's own colors; the
            sprite then only contributes its alpha shape.
    """

    seed: int = 0
    count: int = 6
    size_range: tuple[int, int] = (12, 26)
    opacity: float = 0.85
    tint: ColorLike | None = None

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(
            Size(constraints.max_width or 0, constraints.max_height or 0)
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        sources = [
            path
            for path in (BG_DIR / "star1.png", BG_DIR / "star2.png")
            if path.exists()
        ]
        if not sources:
            return
        rng = random.Random(self.seed)
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        keep_out = (
            rect.width * 0.24,
            rect.height * 0.26,
            rect.width * 0.76,
            rect.height * 0.82,
        )
        for _ in range(self.count):
            star = load_image(ctx, sources[rng.randrange(len(sources))])
            size = max(
                2, ctx.scale_px(round(rng.uniform(self.size_range[0], self.size_range[1])))
            )
            sprite = star.resize((size, size), Image.Resampling.BILINEAR)
            if self.tint is not None:
                red, green, blue, _alpha = normalize_color(self.tint)
                tinted = Image.new("RGBA", sprite.size, (red, green, blue, 0))
                tinted.putalpha(sprite.getchannel("A"))
                sprite = tinted
            sprite = sprite.rotate(
                rng.uniform(0, 72), expand=True, resample=Image.Resampling.BICUBIC
            )
            x = y = 0.0
            for _attempt in range(16):
                x = rng.uniform(0, rect.width)
                y = rng.uniform(0, rect.height)
                inside_keep_out = (
                    keep_out[0] < x < keep_out[2] and keep_out[1] < y < keep_out[3]
                )
                if not inside_keep_out:
                    break
            alpha_composite_paste(
                layer,
                sprite,
                (round(x - sprite.width / 2), round(y - sprite.height / 2)),
            )
        if self.opacity < 1:
            layer = with_opacity(layer, self.opacity)
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class BanGDreamBannerChip:
    """Miniature two-layer pill in the title-pill silhouette, with a ring.

    A white under-band peeks out to the lower right of a filled band, echoing
    ``BanGDreamTitlePill`` at chip scale; the optional ring traces the band in
    the kit primary. The band fill is intended to be a dark emphasis color —
    never the primary — so the label stays readable.

    Attributes:
        text: Chip label.
        font: Label font path.
        width: Logical total width including the under-band offset.
        height: Logical total height including the under-band offset.
        font_size: Label font size.
        band_fill: Fill of the top band that carries the text.
        band_text_color: Label color on the band.
        under_fill: Fill of the offset under-band.
        ring_color: Optional ring stroke color around the band.
        ring_width: Logical ring stroke width.
    """

    text: str
    font: str | Path
    width: int
    height: int
    font_size: int = 22
    band_fill: ColorLike = rgba(80, 80, 80, 255)
    band_text_color: ColorLike = rgba(255, 255, 255, 255)
    under_fill: ColorLike = rgba(255, 255, 255, 255)
    ring_color: ColorLike | None = rgba(234, 78, 116, 255)
    ring_width: int = 3

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(self.width, self.height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        offset_x = max(2, rect.width // 9)
        offset_y = max(2, rect.height // 5)
        band_w = rect.width - offset_x
        band_h = rect.height - offset_y
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw_pill(
            layer, (offset_x, offset_y, rect.width, rect.height), self.under_fill
        )
        draw_pill(layer, (0, 0, band_w, band_h), self.band_fill)
        if self.ring_color is not None and self.ring_width > 0:
            stroke = max(1, ctx.scale_px(self.ring_width))
            inset = stroke // 2
            ImageDraw.Draw(layer).rounded_rectangle(
                (inset, inset, band_w - 1 - inset, band_h - 1 - inset),
                radius=max(0, (band_h - stroke) // 2),
                outline=normalize_color(self.ring_color),
                width=stroke,
            )
        font = load_font(max(1, ctx.scale_px(self.font_size)), self.font)
        _draw_aligned_text(
            ImageDraw.Draw(layer),
            self.text,
            font,
            (0, 0, band_w, band_h),
            self.band_text_color,
            align="center",
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))


@dataclass(frozen=True)
class _TitledPanelLayout:
    title_width: int
    title_height: int
    main_width: int
    main_height: int

    @property
    def size(self) -> Size:
        return Size(
            max(self.title_width, self.main_width),
            self.title_height + self.main_height,
        )


def _combine_titled_panel_width(
    title_width: SizeValue | int,
    main_width: SizeValue | int,
) -> SizeValue:
    title = as_size_value(title_width)
    main = as_size_value(main_width)
    if isinstance(title, Fill) or isinstance(main, Fill):
        return Fill()
    if isinstance(title, Fixed) and isinstance(main, Fixed):
        return Fixed(max(title.value, main.value))
    return Fit()


def _combine_titled_panel_height(
    title_height: SizeValue | int,
    main_height: SizeValue | int,
) -> SizeValue:
    title = as_size_value(title_height)
    main = as_size_value(main_height)
    if isinstance(title, Fill) or isinstance(main, Fill):
        return Fill()
    if isinstance(title, Fixed) and isinstance(main, Fixed):
        return Fixed(title.value + main.value)
    return Fit()


def _resolve_titled_panel_layout(
    panel: BanGDreamTitledPanel,
    constraints: Constraints,
) -> _TitledPanelLayout:
    title_width = _resolve_titled_panel_width(
        as_size_value(panel.title_width),
        constraints.max_width,
        "BanGDreamTitledPanel.title_width",
    )
    main_width = _resolve_titled_panel_width(
        as_size_value(panel.main_width),
        constraints.max_width,
        "BanGDreamTitledPanel.main_width",
    )
    title_height, main_height = _resolve_titled_panel_heights(
        as_size_value(panel.title_height),
        as_size_value(panel.main_height),
        constraints.max_height,
    )
    return _TitledPanelLayout(
        title_width=title_width,
        title_height=title_height,
        main_width=main_width,
        main_height=main_height,
    )


def _resolve_titled_panel_width(
    value: SizeValue,
    bound: int | None,
    owner: str,
) -> int:
    if isinstance(value, Fit):
        return 0
    if isinstance(value, Fixed):
        return value.value
    if isinstance(value, Fill):
        if bound is None:
            raise LayoutError(f"{owner} uses Fill(), but parent axis is unbounded")
        return bound
    if isinstance(value, Fraction):
        if bound is None:
            raise LayoutError(f"{owner} uses Fraction(), but parent axis is unbounded")
        return round(bound * value.value)
    return 0


def _resolve_titled_panel_heights(
    title_height: SizeValue,
    main_height: SizeValue,
    bound: int | None,
) -> tuple[int, int]:
    title_fixed = _resolve_titled_panel_non_fill_height(
        title_height,
        bound,
        "BanGDreamTitledPanel.title_height",
    )
    main_fixed = _resolve_titled_panel_non_fill_height(
        main_height,
        bound,
        "BanGDreamTitledPanel.main_height",
    )
    fill_count = int(isinstance(title_height, Fill)) + int(
        isinstance(main_height, Fill)
    )
    if fill_count == 0:
        return title_fixed, main_fixed
    if bound is None:
        raise LayoutError(
            "BanGDreamTitledPanel.height uses Fill(), but parent axis is unbounded"
        )
    fill_height = max(0, (bound - title_fixed - main_fixed) // fill_count)
    return (
        fill_height if isinstance(title_height, Fill) else title_fixed,
        fill_height if isinstance(main_height, Fill) else main_fixed,
    )


def _resolve_titled_panel_non_fill_height(
    value: SizeValue,
    bound: int | None,
    owner: str,
) -> int:
    if isinstance(value, Fit):
        return 0
    if isinstance(value, Fixed):
        return value.value
    if isinstance(value, Fill):
        return 0
    if isinstance(value, Fraction):
        if bound is None:
            raise LayoutError(f"{owner} uses Fraction(), but parent axis is unbounded")
        return round(bound * value.value)
    return 0


def _draw_top_rounded_rect(
    target: Image.Image,
    bbox: tuple[int, int, int, int],
    radius: int,
    fill: ColorLike,
) -> None:
    left, top, right, bottom = bbox
    width = max(0, right - left)
    height = max(0, bottom - top)
    if width == 0 or height == 0:
        return
    radius = min(max(0, radius), width // 2, height)
    color = normalize_color(fill)
    draw = ImageDraw.Draw(target)
    if radius == 0:
        draw.rectangle((left, top, right, bottom), fill=color)
        return
    draw.rectangle((left, top + radius, right, bottom), fill=color)
    draw.rectangle((left + radius, top, right - radius, bottom), fill=color)
    draw.pieslice(
        (left, top, left + radius * 2, top + radius * 2),
        180,
        270,
        fill=color,
    )
    draw.pieslice(
        (right - radius * 2, top, right, top + radius * 2), 270, 360, fill=color
    )


def _draw_upper_left_square_rounded_rect(
    target: Image.Image,
    bbox: tuple[int, int, int, int],
    radius: int,
    fill: ColorLike,
) -> None:
    left, top, right, bottom = bbox
    draw_rounded_rectangle(target, bbox, radius, fill)
    radius = max(0, min(radius, (right - left) // 2, (bottom - top) // 2))
    if radius > 0:
        ImageDraw.Draw(target).rectangle(
            (left, top, left + radius, top + radius),
            fill=normalize_color(fill),
        )


def _draw_left_aligned_text(
    draw: ImageDraw.ImageDraw, text: str, font, bbox, fill: ColorLike, left_offset: int
) -> None:
    _draw_aligned_text(
        draw,
        text,
        font,
        bbox,
        fill,
        align="left",
        left_offset=left_offset,
    )


def _draw_aligned_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    bbox,
    fill: ColorLike,
    *,
    align: TextAlign,
    left_offset: int = 0,
) -> None:
    left, top, _right, bottom = bbox
    text_bbox = draw.textbbox((0, 0), text, font=font)
    width = text_bbox[2] - text_bbox[0]
    height = text_bbox[3] - text_bbox[1]
    if align == "center":
        x = left + (_right - left - width) // 2 - text_bbox[0]
    elif align == "right":
        x = _right - width - text_bbox[0]
    else:
        x = left + left_offset - text_bbox[0]
    draw.text(
        (x, top + (bottom - top - height) // 2 - text_bbox[1]),
        text,
        font=font,
        fill=normalize_color(fill),
    )


def _fit_intrinsic_image_size(image: Image.Image, constraints: Constraints) -> Size:
    width = image.width
    height = image.height
    if width <= 0 or height <= 0:
        return Size(0, 0)

    ratio = 1.0
    if constraints.max_width is not None:
        ratio = min(ratio, constraints.max_width / width)
    if constraints.max_height is not None:
        ratio = min(ratio, constraints.max_height / height)
    ratio = max(0, ratio)
    return Size(max(1, round(width * ratio)), max(1, round(height * ratio)))


def _fixed_or_bound(
    value: SizeValue | int | None, bound: int | None, owner: str
) -> int:
    size_value = as_size_value(value)
    if isinstance(size_value, Fit):
        return 0
    if isinstance(size_value, Fixed):
        return size_value.value
    if isinstance(size_value, (Fill, Fraction)):
        if bound is None:
            raise LayoutError(f"{owner} requires bounded parent axis")
        return (
            bound if isinstance(size_value, Fill) else round(bound * size_value.value)
        )
    return 0


def _resolve_pill_axis(
    value: SizeValue,
    bound: int | None,
    intrinsic: int,
    owner: str,
) -> int:
    if isinstance(value, Fit):
        return intrinsic
    if isinstance(value, Fixed):
        return value.value
    if isinstance(value, Fill):
        if bound is None:
            raise LayoutError(f"{owner} uses Fill(), but parent axis is unbounded")
        return bound
    if isinstance(value, Fraction):
        if bound is None:
            raise LayoutError(f"{owner} uses Fraction(), but parent axis is unbounded")
        return round(bound * value.value)
    return intrinsic


def _resolve_image_axis(
    value: SizeValue, bound: int | None, intrinsic: int, owner: str
) -> int:
    if isinstance(value, Fit):
        return intrinsic
    if isinstance(value, Fixed):
        return value.value
    if isinstance(value, Fill):
        if bound is None:
            raise LayoutError(f"{owner} uses Fill(), but parent axis is unbounded")
        return bound
    if isinstance(value, Fraction):
        if bound is None:
            raise LayoutError(f"{owner} uses Fraction(), but parent axis is unbounded")
        return round(bound * value.value)
    return intrinsic
