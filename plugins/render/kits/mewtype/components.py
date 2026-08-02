"""Signature visuals for the Mewtype kit."""

import math
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

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
from plugins.render.layout import Frame
from plugins.render.sizing import Fill
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import load_font
from plugins.render.primitives import alpha_composite_paste


@dataclass(frozen=True)
class MewtypeTitle:
    """Thick gradient wordmark with the Yumemita subpage title ornaments.

    The website renders the same 110×130 plus-and-square artwork twice via the
    title's ``::before`` and ``::after`` pseudo-elements.  This component
    recreates that artwork with PIL and retains the site's 130-unit layout, so
    both copies stay anchored to the padded title box rather than to glyph
    bounds.
    """

    text: str
    font: str | Path | None = None
    font_size: int = 96
    gradient_top: Color = rgba(214, 128, 241, 255)
    gradient_bottom: Color = rgba(61, 189, 245, 255)
    outline_color: Color = rgba(255, 255, 255, 255)
    shadow_color: Color = rgba(70, 188, 248, 255)
    punch_outline_color: Color = rgba(174, 236, 246, 255)
    ornament_color: Color = rgba(201, 130, 232, 255)
    ornament_square_color: Color = rgba(255, 115, 213, 255)
    outline_width: int = 8
    face_weight: int = 1
    shadow_offset: int = 11
    horizontal_scale: float = 1.16
    min_font_size: int = 24

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        font_size = self._fit_font_size(constraints.max_width)
        height = self._logical_row_height(font_size)
        if constraints.max_width is not None:
            width = constraints.max_width
        else:
            width = self._logical_text_width(font_size) + self._ornament_reserve(
                font_size
            )
        return constraints.clamp(Size(width, height))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return

        logical_width = ctx.unscale_px(rect.width)
        font_size = self._fit_font_size(logical_width)
        font = load_font(max(1, ctx.scale_px(font_size)), self.font)
        display_text = self._display_text()
        face_weight = max(1, ctx.scale_px(self.face_weight))
        outline = max(1, ctx.scale_px(self.outline_width + self.face_weight))
        shadow_offset = max(1, ctx.scale_px(self.shadow_offset))

        bbox = font.getbbox(display_text, stroke_width=outline)
        natural_text_width = max(1, bbox[2] - bbox[0])
        text_width = max(1, round(natural_text_width * self.horizontal_scale))
        text_height = max(1, bbox[3] - bbox[1])
        # The source h1 is the title image plus 60/130 of the row height on
        # each side. Its ornaments are positioned against that padded box.
        row_height = min(
            rect.height,
            ctx.scale_px(self._logical_row_height(font_size)),
        )
        row_top = max(0, (rect.height - row_height) // 2)
        side_padding = round(row_height * 60 / 130)
        title_box_width = text_width + side_padding * 2
        title_box_left = (rect.width - title_box_width) // 2
        text_left = title_box_left + side_padding
        text_top = row_top + (row_height - text_height - shadow_offset) // 2

        # The CSS title has overflow:visible, so the burst can rise 40 units
        # above the 130-unit h1 without increasing layout height. Composite it
        # directly to the destination before drawing the local title layer.
        self._draw_punch(
            canvas,
            origin_x=rect.x,
            origin_y=rect.y,
            title_box_left=title_box_left,
            row_top=row_top,
            row_height=row_height,
        )
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))

        # The website keeps the word image and the +/square artwork separate.
        # Its word ledge repeats the face gradient, while only the ornament
        # asset uses a flat cyan extrusion. Render the text to a local asset so
        # it can also be widened without making the whole title row taller.
        text_layer = Image.new(
            "RGBA",
            (natural_text_width, text_height + shadow_offset),
            (0, 0, 0, 0),
        )
        local_x = -bbox[0]
        local_y = -bbox[1]

        extrusion_mask = Image.new("L", text_layer.size, 0)
        ImageDraw.Draw(extrusion_mask).text(
            (local_x, local_y + shadow_offset),
            display_text,
            font=font,
            fill=255,
            stroke_width=outline,
            stroke_fill=255,
        )
        extrusion = _vertical_color_ramp(
            text_layer.size,
            self.gradient_top,
            self.gradient_bottom,
            start_y=shadow_offset,
            end_y=text_height + shadow_offset - 1,
        )
        extrusion.putalpha(extrusion_mask)
        alpha_composite_paste(text_layer, extrusion, (0, 0))

        ImageDraw.Draw(text_layer).text(
            (local_x, local_y),
            display_text,
            font=font,
            fill=self.outline_color,
            stroke_width=outline,
            stroke_fill=self.outline_color,
        )
        face_mask = Image.new("L", text_layer.size, 0)
        ImageDraw.Draw(face_mask).text(
            (local_x, local_y),
            display_text,
            font=font,
            fill=255,
            stroke_width=face_weight,
            stroke_fill=255,
        )
        face = _vertical_color_ramp(
            text_layer.size,
            self.gradient_top,
            self.gradient_bottom,
            start_y=0,
            end_y=text_height - 1,
        )
        face.putalpha(face_mask)
        alpha_composite_paste(text_layer, face, (0, 0))

        if text_width != natural_text_width:
            text_layer = text_layer.resize(
                (text_width, text_layer.height),
                Image.Resampling.LANCZOS,
            )
        alpha_composite_paste(layer, text_layer, (text_left, text_top))

        self._draw_ornaments(
            layer,
            title_box_left=title_box_left,
            title_box_width=title_box_width,
            row_top=row_top,
            row_height=row_height,
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))

    def _fit_font_size(self, max_width: int | None) -> int:
        font_size = max(self.min_font_size, self.font_size)
        if max_width is None:
            return font_size
        while (
            font_size > self.min_font_size
            and self._logical_text_width(font_size)
            + self._ornament_reserve(font_size)
            > max_width
        ):
            font_size -= 1
        return font_size

    def _logical_text_width(self, font_size: int) -> int:
        font = load_font(font_size, self.font)
        bbox = font.getbbox(
            self._display_text(),
            stroke_width=self.outline_width + self.face_weight,
        )
        return max(1, round((bbox[2] - bbox[0]) * self.horizontal_scale))

    def _display_text(self) -> str:
        """Use the compact inter-word gap visible in the source title assets."""

        return self.text.replace(" ", "\u2009")

    def _ornament_reserve(self, font_size: int) -> int:
        row_height = self._logical_row_height(font_size)
        return round(row_height * 120 / 130)

    def _logical_row_height(self, font_size: int) -> int:
        font = load_font(font_size, self.font)
        bbox = font.getbbox(
            self._display_text(),
            stroke_width=self.outline_width + self.face_weight,
        )
        # Eight logical pixels produced the same visible-alpha ratio as the
        # site's 198 px wordmark inside its 260 px source canvas. Keep that
        # sizing reference stable even when the cyan extrusion is deepened.
        alpha_height = max(1, bbox[3] - bbox[1]) + 8
        # The reference wordmark's visible alpha is 198 px high inside its
        # 260 px source canvas. Preserve that vertical breathing-room ratio.
        return max(
            max(1, bbox[3] - bbox[1]) + self.shadow_offset,
            round(alpha_height * 260 / 198),
        )

    def _draw_punch(
        self,
        canvas: Image.Image,
        *,
        origin_x: int,
        origin_y: int,
        title_box_left: int,
        row_top: int,
        row_height: int,
    ) -> None:
        punch_width = max(1, round(row_height * 386 / 130))
        punch_height = max(1, round(row_height * 149 / 130))
        left = round(row_height * 2 / 130)
        bottom = round(row_height * 21 / 130)
        punch = _title_punch(
            self.outline_color,
            self.punch_outline_color,
        ).resize(
            (punch_width, punch_height),
            Image.Resampling.LANCZOS,
        )
        alpha_composite_paste(
            canvas,
            punch,
            (
                origin_x + title_box_left + left,
                origin_y + row_top + row_height - bottom - punch_height,
            ),
        )

    def _draw_ornaments(
        self,
        layer: Image.Image,
        *,
        title_box_left: int,
        title_box_width: int,
        row_top: int,
        row_height: int,
    ) -> None:
        ornament_height = max(1, round(row_height * 64 / 130))
        ornament_width = max(1, round(row_height * 55 / 130))
        ornament = _title_ornament(
            self.ornament_color,
            self.ornament_square_color,
            self.shadow_color,
            self.outline_color,
        ).resize(
            (ornament_width, ornament_height),
            Image.Resampling.LANCZOS,
        )

        # CSS final state:
        # ::before { top: 0; right: 8/130 * row-height }
        # ::after  { bottom: 17/130 * row-height; left: 2/130 * row-height }
        right = round(row_height * 8 / 130)
        left = round(row_height * 2 / 130)
        bottom = round(row_height * 17 / 130)
        alpha_composite_paste(
            layer,
            ornament,
            (
                title_box_left + left,
                row_top + row_height - bottom - ornament_height,
            ),
        )
        alpha_composite_paste(
            layer,
            ornament,
            (
                title_box_left + title_box_width - right - ornament_width,
                row_top,
            ),
        )


def _vertical_color_ramp(
    size: tuple[int, int],
    top: Color,
    bottom: Color,
    *,
    start_y: int = 0,
    end_y: int | None = None,
) -> Image.Image:
    """Build a full-size vertical RGBA gradient for the title face."""

    width, height = size
    end_y = max(start_y + 1, height - 1 if end_y is None else end_y)
    ramp = Image.new("RGBA", (1, max(1, height)), top)
    pixels = ramp.load()
    for y in range(max(1, height)):
        ratio = min(1.0, max(0.0, (y - start_y) / max(1, end_y - start_y)))
        pixels[0, y] = tuple(
            round(top[channel] + (bottom[channel] - top[channel]) * ratio)
            for channel in range(4)
        )
    return ramp.resize((max(1, width), max(1, height)), Image.Resampling.BILINEAR)


@lru_cache(maxsize=8)
def _title_ornament(
    plus: Color,
    square: Color,
    extrusion: Color,
    outline: Color,
) -> Image.Image:
    """Rebuild the site's 110×130 ornament as layered vector-like PIL shapes."""

    # Draw four times larger and downsample so the compact curved corners
    # retain the same smooth, asset-like edge treatment at normal output size.
    scale = 4
    image = Image.new("RGBA", (110 * scale, 130 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def rounded_box(
        box: tuple[int, int, int, int],
        radius: int,
        fill: Color,
        *,
        y_offset: int = 0,
    ) -> None:
        x0, y0, x1, y1 = box
        draw.rounded_rectangle(
            (
                x0 * scale,
                (y0 + y_offset) * scale,
                x1 * scale,
                (y1 + y_offset) * scale,
            ),
            radius=radius * scale,
            fill=fill,
        )

    # The colored lower layer is a 12-unit drop of the complete white
    # silhouette, matching the cyan extrusion visible in the source WebP.
    for fill, y_offset in ((extrusion, 12), (outline, 0)):
        rounded_box((21, 0, 65, 84), 12, fill, y_offset=y_offset)
        rounded_box((1, 20, 85, 64), 12, fill, y_offset=y_offset)
        rounded_box((65, 74, 109, 118), 12, fill, y_offset=y_offset)

    # Purple plus and pink block faces.
    rounded_box((33, 12, 53, 72), 2, plus)
    rounded_box((13, 32, 73, 52), 2, plus)
    rounded_box((77, 86, 97, 106), 2, square)

    return image.resize((110, 130), Image.Resampling.LANCZOS)


@lru_cache(maxsize=8)
def _title_punch(fill: Color, outline: Color) -> Image.Image:
    """Recreate the white left-hand burst used behind every subpage title."""

    # Points are the simplified opaque contour of deco_kit-punch.webp in its
    # native 549×222 coordinate system.
    points = (
        (1, 71),
        (34, 103),
        (6, 139),
        (51, 140),
        (52, 185),
        (88, 157),
        (117, 191),
        (125, 148),
        (130, 147),
        (546, 221),
        (150, 71),
        (161, 29),
        (118, 44),
        (102, 1),
        (78, 40),
        (39, 17),
        (46, 62),
    )
    scale = 4
    image = Image.new("RGBA", (549 * scale, 222 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scaled = [(x * scale, y * scale) for x, y in points]
    # The reference has a very light cyan hairline beneath the white face.
    dropped = [(x, y + 3 * scale) for x, y in scaled]
    draw.polygon(dropped, fill=outline)
    draw.polygon(scaled, fill=fill)
    draw.line(
        scaled + [scaled[0]],
        fill=outline,
        width=scale,
        joint="curve",
    )
    return image.resize((549, 222), Image.Resampling.LANCZOS)


@dataclass(frozen=True)
class MewtypeBackground:
    """Exact white grid with the subpages' faint repeating confetti layer."""

    fill: Color = rgba(252, 241, 255, 255)
    grid_color: Color = rgba(255, 255, 255, 255)
    cyan: Color = rgba(29, 211, 243, 255)
    pink: Color = rgba(255, 115, 213, 255)
    mint: Color = rgba(78, 232, 183, 255)
    yellow: Color = rgba(255, 219, 82, 255)
    purple: Color = rgba(155, 115, 231, 255)
    grid_spacing: int = 40
    grid_width: int = 2
    decoration_density: float = 0.000063
    random_seed: int = 0

    def render(self, ctx: RenderContext, size: Size) -> Image.Image:
        canvas = Image.new(
            "RGBA", (max(0, size.width), max(0, size.height)), self.fill
        )
        if size.width <= 0 or size.height <= 0:
            return canvas

        self._draw_grid(ctx, canvas, size)
        self._draw_decorations(ctx, canvas, size)
        return canvas

    def _draw_grid(
        self, ctx: RenderContext, canvas: Image.Image, size: Size
    ) -> None:
        spacing = max(8, ctx.scale_px(self.grid_spacing))
        width = max(1, ctx.scale_px(self.grid_width))
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for x in range(0, size.width + spacing, spacing):
            draw.line((x, 0, x, size.height), fill=self.grid_color, width=width)
        for y in range(0, size.height + spacing, spacing):
            draw.line((0, y, size.width, y), fill=self.grid_color, width=width)
        alpha_composite_paste(canvas, layer, (0, 0))

    def _draw_decorations(
        self, ctx: RenderContext, canvas: Image.Image, size: Size
    ) -> None:
        if self.decoration_density <= 0:
            return

        # bg_ptn-obj.webp is a 2000 px source displayed as a repeating
        # 1000×1000 CSS-pixel tile at 50% opacity.
        tile_size = max(1, ctx.scale_px(1000))
        tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
        tile_draw = ImageDraw.Draw(tile)
        rng = random.Random(self.random_seed)
        tile_count = max(1, round(1_000_000 * self.decoration_density))
        # Dominant colors sampled from bg_ptn-obj.webp. The source pixels have
        # alpha ≈109 and the CSS layer is itself at 50% opacity, producing an
        # effective peak alpha of about 55.
        colors = (
            rgba(246, 137, 183, 255),
            rgba(198, 143, 214, 255),
            rgba(255, 202, 181, 255),
            rgba(178, 187, 255, 255),
            rgba(246, 137, 183, 255),
            rgba(255, 221, 132, 255),
            rgba(191, 248, 190, 255),
            rgba(237, 110, 180, 255),
            rgba(178, 187, 255, 255),
            rgba(246, 137, 183, 255),
        )
        for index in range(tile_count):
            x = rng.randrange(0, tile_size)
            y = rng.randrange(0, tile_size)
            nominal = round(rng.triangular(10, 54, 27))
            scale = max(3, ctx.scale_px(nominal))
            color = colors[index % len(colors)]
            subtle_kind = index % 7
            if subtle_kind == 0:
                self._draw_ring(tile_draw, x, y, scale, color, ctx)
            elif subtle_kind == 1:
                self._draw_diamond(tile_draw, x, y, scale, color)
            elif subtle_kind == 2:
                self._draw_triangle(tile_draw, x, y, scale, color)
            elif subtle_kind == 3:
                self._draw_confetti(tile_draw, x, y, scale, color)
            elif subtle_kind == 4:
                self._draw_dot(tile_draw, x, y, scale, color)
            elif subtle_kind == 5:
                self._draw_hollow_triangle(
                    tile_draw,
                    x,
                    y,
                    scale,
                    color,
                    ctx,
                )
            else:
                self._draw_short_dash(
                    tile_draw,
                    x,
                    y,
                    scale,
                    color,
                    ctx,
                )

        for tile_y in range(0, size.height, tile_size):
            for tile_x in range(0, size.width, tile_size):
                alpha_composite_paste(canvas, tile, (tile_x, tile_y))

        # bg_head-sub.webp adds the handful of saturated stationery marks only
        # in the 295 px subpage header, rather than repeating them down-page.
        header_height = min(size.height, ctx.scale_px(295))
        if header_height <= 0:
            return
        header = Image.new(
            "RGBA",
            (size.width, header_height),
            (0, 0, 0, 0),
        )
        self._draw_header_art(ctx, header, size.width)
        alpha_composite_paste(canvas, header, (0, 0))

    def _draw_header_art(
        self,
        ctx: RenderContext,
        header: Image.Image,
        width: int,
    ) -> None:
        """Rebuild the fixed 1920×295 bg_head-sub.webp composition."""

        draw = ImageDraw.Draw(header)
        reference_width = ctx.scale_px(1920)
        offset_x = (width - reference_width) // 2
        mint = rgba(140, 255, 230, 255)
        pale_mint = rgba(230, 255, 199, 255)
        yellow = rgba(255, 234, 125, 255)
        pink = rgba(255, 154, 226, 255)
        cyan = rgba(133, 234, 255, 255)

        # Coordinates are the ten connected objects from the source WebP after
        # its native 2880×443 canvas is scaled to the CSS 1920×295 size.
        objects = (
            ("zigzag", 494, 0, 60, 35, mint),
            ("capsule", 1194, 44, 68, 41, pink),
            ("hash", 1527, 52, 55, 57, self.cyan),
            ("capsule", 655, 65, 57, 39, cyan),
            ("plus", 1655, 127, 32, 35, self.cyan),
            ("zigzag", 1771, 149, 59, 59, yellow),
            ("hash", 221, 151, 64, 65, self.cyan),
            ("zigzag", 1360, 158, 75, 62, mint),
            ("zigzag", 456, 167, 85, 53, yellow),
            ("zigzag", 0, 174, 79, 61, pale_mint),
        )
        for kind, x, y, object_width, object_height, color in objects:
            box = (
                offset_x + ctx.scale_px(x),
                ctx.scale_px(y),
                ctx.scale_px(object_width),
                ctx.scale_px(object_height),
            )
            if kind == "zigzag":
                self._draw_header_zigzag(draw, box, color, ctx)
            elif kind == "capsule":
                self._draw_header_capsule(draw, box, color, ctx)
            else:
                self._draw_header_symbol(
                    draw,
                    box,
                    color,
                    ctx,
                    is_hash=kind == "hash",
                )

    def _draw_header_zigzag(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        color: Color,
        ctx: RenderContext,
    ) -> None:
        x, y, width, height = box
        points = (
            (x, y + round(height * 0.82)),
            (x + round(width * 0.20), y + round(height * 0.25)),
            (x + round(width * 0.42), y + round(height * 0.47)),
            (x + round(width * 0.62), y),
            (x + round(width * 0.82), y + round(height * 0.20)),
            (x + width, y + round(height * 0.14)),
        )
        self._draw_header_stroked_path(draw, points, color, ctx)

    def _draw_header_capsule(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        color: Color,
        ctx: RenderContext,
    ) -> None:
        x, y, width, height = box
        gap = round(height * 0.25)
        inset = round(width * 0.14)
        paths = (
            (
                (x, y + height - gap),
                (x + width - inset, y),
            ),
            (
                (x + inset, y + height),
                (x + width, y + gap),
            ),
        )
        for path in paths:
            self._draw_header_stroked_path(draw, path, color, ctx)

    def _draw_header_stroked_path(
        self,
        draw: ImageDraw.ImageDraw,
        points: tuple[tuple[int, int], ...],
        color: Color,
        ctx: RenderContext,
    ) -> None:
        shadow_offset = max(1, ctx.scale_px(3))
        outer_width = max(3, ctx.scale_px(12))
        face_width = max(2, ctx.scale_px(7))
        shadow = rgba(168, 166, 181, 100)
        draw.line(
            [(x + shadow_offset, y + shadow_offset) for x, y in points],
            fill=shadow,
            width=outer_width,
            joint="curve",
        )
        draw.line(
            points,
            fill=rgba(255, 255, 255, 230),
            width=outer_width,
            joint="curve",
        )
        draw.line(
            points,
            fill=color,
            width=face_width,
            joint="curve",
        )

    def _draw_header_symbol(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        color: Color,
        ctx: RenderContext,
        *,
        is_hash: bool,
    ) -> None:
        x, y, width, height = box
        verticals = (0.36, 0.64) if is_hash else (0.5,)
        horizontals = (0.36, 0.64) if is_hash else (0.5,)
        paths: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for ratio in verticals:
            px = x + round(width * ratio)
            paths.append(((px, y), (px, y + height)))
        for ratio in horizontals:
            py = y + round(height * ratio)
            paths.append(((x, py), (x + width, py)))
        for path in paths:
            self._draw_header_stroked_path(draw, path, color, ctx)

    @staticmethod
    def _soft(color: Color, alpha: int = 155) -> Color:
        return rgba(color[0], color[1], color[2], min(alpha, color[3]))

    def _draw_ring(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        size: int,
        color: Color,
        ctx: RenderContext,
    ) -> None:
        radius = max(4, size // 2)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            outline=self._soft(color, 55),
            width=max(1, ctx.scale_px(2)),
        )

    def _draw_diamond(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        size: int,
        color: Color,
    ) -> None:
        radius = max(3, size // 2)
        draw.polygon(
            ((x, y - radius), (x + radius, y), (x, y + radius), (x - radius, y)),
            fill=self._soft(color, 55),
        )

    def _draw_triangle(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        size: int,
        color: Color,
    ) -> None:
        radius = max(3, size // 2)
        draw.polygon(
            ((x, y + radius), (x - radius, y - radius), (x + radius, y - radius)),
            fill=self._soft(color, 55),
        )

    def _draw_confetti(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        size: int,
        color: Color,
    ) -> None:
        radius = max(2, size // 5)
        angle = math.pi / 4
        dx = round(radius * math.cos(angle))
        dy = round(radius * math.sin(angle))
        draw.polygon(
            (
                (x - dx * 2, y),
                (x, y - dy * 2),
                (x + dx * 2, y),
                (x, y + dy * 2),
            ),
            fill=self._soft(color, 55),
        )

    def _draw_dot(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        size: int,
        color: Color,
    ) -> None:
        radius = max(2, size // 4)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=self._soft(color, 55),
        )

    def _draw_hollow_triangle(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        size: int,
        color: Color,
        ctx: RenderContext,
    ) -> None:
        radius = max(4, size // 2)
        points = (
            (x, y - radius),
            (x + radius, y + radius),
            (x - radius, y + radius),
            (x, y - radius),
        )
        draw.line(
            points,
            fill=self._soft(color, 55),
            width=max(1, ctx.scale_px(2)),
            joint="curve",
        )

    def _draw_short_dash(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        size: int,
        color: Color,
        ctx: RenderContext,
    ) -> None:
        half = max(3, size // 3)
        draw.line(
            (x - half, y + half, x + half, y - half),
            fill=self._soft(color, 55),
            width=max(1, ctx.scale_px(3)),
        )


@dataclass(frozen=True)
class MewtypeArticleHeader:
    """Exact cyan article heading without the panel's offset frame."""

    child: Component
    width: SizeValue | int
    height: SizeValue | int
    padding: InsetsLike = 0
    fill: ColorLike = rgba(29, 211, 243, 255)
    radius: int = 6

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
        radius = min(
            max(0, ctx.scale_px(self.radius)),
            rect.width // 2,
            rect.height // 2,
        )
        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(
            (0, 0, rect.width - 1, rect.height - 1),
            radius=radius,
            fill=normalize_color(self.fill),
        )
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))
        Frame(
            self.child,
            width=self.width,
            height=self.height,
            padding=self.padding,
            align_x="stretch",
            align_y="stretch",
        ).render(ctx, canvas, rect)


@dataclass(frozen=True)
class MewtypeStreamHeading:
    """Panel-local heading from ON AIR's ``p-onair-article__stream-head``.

    The source uses a 22px extra-bold line with 1.6 line-height and a 16px
    two-tone pixel cross at the left.  It has no rule or filled title band;
    those belong to the page-level ``c-article-head`` one tier above it.
    """

    child: Component
    width: SizeValue | int
    height: SizeValue | int = 36
    marker_size: int = 16
    content_left: int = 30
    marker_outer: ColorLike = rgba(29, 211, 243, 255)
    marker_inner: ColorLike = rgba(144, 238, 255, 255)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return Frame(
            self.child,
            width=self.width,
            height=self.height,
            align_x="stretch",
            align_y="center",
        ).measure(ctx, constraints)

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return

        size = min(ctx.scale_px(self.marker_size), rect.width, rect.height)
        left = min(ctx.scale_px(2), max(0, rect.width - size))
        top = max(0, (rect.height - size) // 2)
        step = size / 5

        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        def band(x0: float, y0: float, x1: float, y1: float, fill: ColorLike) -> None:
            draw.rectangle(
                (
                    round(left + x0 * step),
                    round(top + y0 * step),
                    round(left + x1 * step) - 1,
                    round(top + y1 * step) - 1,
                ),
                fill=normalize_color(fill),
            )

        # Exact five-step silhouette of the official 15x15 inline SVG.
        band(2, 0, 3, 5, self.marker_outer)
        band(1, 1, 4, 4, self.marker_outer)
        band(0, 2, 5, 3, self.marker_outer)
        band(2, 1, 3, 4, self.marker_inner)
        band(1, 2, 4, 3, self.marker_inner)
        alpha_composite_paste(canvas, layer, (rect.x, rect.y))

        content_left = min(ctx.scale_px(self.content_left), rect.width)
        child_rect = Rect(
            rect.x + content_left,
            rect.y,
            max(0, rect.width - content_left),
            rect.height,
        )
        Frame(
            self.child,
            width=Fill(),
            height=Fill(),
            align_x="start",
            align_y="center",
        ).render(ctx, canvas, child_rect)


@dataclass(frozen=True)
class MewtypePanel:
    """White content block with a cyan offset edge and pixel-punched corners."""

    child: Component | None = None
    fill: ColorLike = rgba(255, 255, 255, 255)
    radius: int | None = None
    padding: InsetsLike = 0
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    frame_color: ColorLike = rgba(29, 211, 243, 255)
    notch: int = 11
    frame_offset: int = 4
    border_width: int = 0

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

        layer = Image.new("RGBA", (rect.width, rect.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        fill = normalize_color(self.fill)
        frame = normalize_color(self.frame_color)
        offset = min(
            max(1, ctx.scale_px(self.frame_offset)),
            max(1, min(rect.width, rect.height) // 5),
        )

        if self.radius is not None:
            radius = min(
                max(0, ctx.scale_px(self.radius)),
                rect.width // 2,
                rect.height // 2,
            )
            border_width = max(0, ctx.scale_px(self.border_width))
            if border_width:
                draw.rounded_rectangle(
                    (0, 0, rect.width - 1, rect.height - 1),
                    radius=radius,
                    fill=frame,
                )
                draw.rounded_rectangle(
                    (
                        border_width,
                        border_width,
                        max(border_width, rect.width - border_width - 1),
                        max(border_width, rect.height - border_width - 1),
                    ),
                    radius=max(0, radius - border_width),
                    fill=fill,
                )
            else:
                draw.rounded_rectangle(
                    (offset, offset, rect.width - 1, rect.height - 1),
                    radius=radius,
                    fill=frame,
                )
                draw.rounded_rectangle(
                    (
                        0,
                        0,
                        max(0, rect.width - offset - 1),
                        max(0, rect.height - offset - 1),
                    ),
                    radius=radius,
                    fill=fill,
                )
        else:
            notch = min(
                max(2, ctx.scale_px(self.notch)),
                max(2, min(rect.width, rect.height) // 4),
            )
            frame_shape = _pixel_panel_polygon(
                offset,
                offset,
                rect.width - 1,
                rect.height - 1,
                notch,
            )
            body_shape = _pixel_panel_polygon(
                0,
                0,
                max(0, rect.width - offset - 1),
                max(0, rect.height - offset - 1),
                notch,
            )
            draw.polygon(frame_shape, fill=frame)
            draw.polygon(body_shape, fill=fill)

        alpha_composite_paste(canvas, layer, (rect.x, rect.y))
        content_rect = rect
        if self.radius is None or not self.border_width:
            content_rect = Rect(
                rect.x,
                rect.y,
                max(0, rect.width - offset),
                max(0, rect.height - offset),
            )
        Frame(
            self.child, padding=self.padding, align_x="stretch", align_y="stretch"
        ).render(ctx, canvas, content_rect)


def _pixel_panel_polygon(
    left: int, top: int, right: int, bottom: int, notch: int
) -> tuple[tuple[int, int], ...]:
    """Return a rectangle with small stepped cut-outs at opposing corners."""

    if right <= left or bottom <= top:
        return ((left, top), (right, top), (right, bottom), (left, bottom))
    notch = min(
        notch,
        max(1, (right - left) // 5),
        max(1, (bottom - top) // 5),
    )
    step = notch
    cut = notch * 2
    return (
        (left + cut, top),
        (right - cut, top),
        (right - cut, top + step),
        (right - step, top + step),
        (right - step, top + cut),
        (right, top + cut),
        (right, bottom - cut),
        (right - step, bottom - cut),
        (right - step, bottom - step),
        (right - cut, bottom - step),
        (right - cut, bottom),
        (left + cut, bottom),
        (left + cut, bottom - step),
        (left + step, bottom - step),
        (left + step, bottom - cut),
        (left, bottom - cut),
        (left, top + cut),
        (left + step, top + cut),
        (left + step, top + step),
        (left + cut, top + step),
    )
