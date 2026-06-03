from typing import Literal
from pathlib import Path

from plugins.render.kit import BaseKit
from plugins.render.core import Component
from plugins.render.core import Background
from plugins.render.color import ColorLike
from plugins.render.color import rgba
from plugins.render.types import ImageFit
from plugins.render.types import Overflow
from plugins.render.types import TextAlign
from plugins.render.types import ImageSource
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike

from .components import BanGDreamPill
from .components import BanGDreamText
from .components import BanGDreamImage
from .components import BanGDreamPanel
from .components import BanGDreamSeparator
from .components import BanGDreamTitlePill
from .backgrounds import BanGDreamImageBackground
from .backgrounds import BanGDreamPatternBackground

KIT_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = KIT_DIR / "resources"
FONTS_DIR = RESOURCES_DIR / "Fonts"
BG_DIR = RESOURCES_DIR / "BG"
CHINESE_FONT = FONTS_DIR / "old.ttf"
DISPLAY_FONT = FONTS_DIR / "Orbitron Black.ttf"
BanGDreamFont = Literal["chinese", "display"]


class BanGDreamKit(BaseKit):
    """BanG Dream!-styled rendering kit.

    The kit implements the neutral ``BaseKit`` atom contract and also exposes
    theme-specific helpers such as badges, board frames, and title pills. Those
    helpers are concrete BanG Dream! conveniences rather than shared base-kit
    promises.
    """

    primary = rgba(234, 78, 116, 255)
    text_color = rgba(80, 80, 80, 255)
    muted_text_color = rgba(130, 130, 145, 255)
    panel_fill = rgba(255, 255, 255, 208)

    def background(self, *, source: ImageSource | None = None, **props) -> Background:
        """Create a BanG Dream! background.

        When ``source`` is omitted, this returns the simple repeating-pattern
        background. When ``source`` is provided, it builds the richer image
        treatment with blur, triangle facets, scattered stars, and repeated
        watermark text. Extra keyword props configure that image treatment.
        """

        if source is None:
            return self.background_simple()
        return BanGDreamImageBackground(
            source,
            fill=props.get("fill", rgba(252, 243, 240, 255)),
            text=props.get("text", "BanG Dream!"),
            blur_radius=props.get("blur_radius", 25),
            triangle_size=props.get("triangle_size", 200),
            brightness_add=props.get("brightness_add", 20),
            brightness_difference=props.get("brightness_difference", 0.04),
            opacity=props.get("opacity", 1.0),
            star_density=props.get("star_density", 0.00001),
            star_angle_range=props.get("star_angle_range", 72),
            star_size_range=props.get("star_size_range", (25, 75)),
            text_opacity=props.get("text_opacity", 0.5),
            random_seed=props.get("random_seed", 0),
        )

    def background_simple(
        self, *, fill: ColorLike = rgba(252, 243, 240, 255)
    ) -> Background:
        """Create the simple tiled BanG Dream! background."""

        return BanGDreamPatternBackground(
            fill=fill, pattern=BG_DIR / "bg_object_big.png"
        )

    def text(
        self,
        text: str,
        *,
        font_size: int = 40,
        color: ColorLike | None = None,
        align: TextAlign = "left",
        wrap: bool = True,
        max_lines: int | None = None,
        overflow: Overflow = "ellipsis",
        line_height: int | None = None,
        font: BanGDreamFont = "chinese",
    ) -> Component:
        """Create themed text using the bundled BanG Dream! font."""

        return BanGDreamText(
            text,
            _resolve_font(font),
            font_size=font_size,
            color=color or self.text_color,
            align=align,
            wrap=wrap,
            max_lines=max_lines,
            overflow=overflow,
            line_height=line_height,
        )

    def image(
        self,
        image: ImageSource,
        *,
        width: SizeValue | int | None = None,
        height: SizeValue | int | None = None,
        fit: ImageFit = "contain",
        opacity: float = 1.0,
        radius: int = 0,
    ) -> Component:
        """Create a themed image component with optional opacity and rounding."""

        return BanGDreamImage(
            image, width=width, height=height, fit=fit, opacity=opacity, radius=radius
        )

    def panel(
        self,
        child: Component | None = None,
        *,
        width: SizeValue | int | None = None,
        height: SizeValue | int | None = None,
        padding: InsetsLike = 0,
        fill: ColorLike | None = None,
        radius: int | None = None,
    ) -> Component:
        """Create a translucent rounded panel for grouping content."""

        return BanGDreamPanel(
            child,
            fill=fill or self.panel_fill,
            radius=48 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a rounded horizontal or vertical separator."""

        return BanGDreamSeparator(
            orientation, length, thickness, color or (170, 170, 170, 255)
        )

    def title_pill(
        self,
        title: str,
        subtitle: str,
        *,
        pill_width: int = 500,
        pill_height: int = 57,
        title_fill: ColorLike | None = None,
        subtitle_fill: ColorLike | None = None,
        title_text_color: ColorLike | None = None,
        subtitle_text_color: ColorLike | None = None,
        title_font: BanGDreamFont = "chinese",
        subtitle_font: BanGDreamFont = "chinese",
    ) -> Component:
        """Create the two-layer BanG Dream! title pill header."""

        return BanGDreamTitlePill(
            title,
            subtitle,
            _resolve_font(title_font),
            _resolve_font(subtitle_font),
            pill_width=pill_width,
            pill_height=pill_height,
            title_fill=title_fill or self.primary,
            subtitle_fill=subtitle_fill or (255, 255, 255, 255),
            title_text_color=title_text_color or (255, 255, 255, 255),
            subtitle_text_color=subtitle_text_color or (80, 80, 80, 255),
        )

    def pill(
        self,
        text: str,
        *,
        width: SizeValue | int,
        height: SizeValue | int,
        font_size: int = 30,
        fill: ColorLike | None = None,
        text_color: ColorLike | None = None,
        align: TextAlign = "center",
        font: BanGDreamFont = "chinese",
    ) -> Component:
        """Create a generic pill-shaped label."""

        return BanGDreamPill(
            text,
            _resolve_font(font),
            width=width,
            height=height,
            font_size=font_size,
            fill=fill or (230, 230, 230, 255),
            text_color=text_color or (255, 255, 255, 255),
            align=align,
        )


def _resolve_font(font: BanGDreamFont) -> Path:
    if font == "chinese":
        return CHINESE_FONT
    if font == "display":
        return DISPLAY_FONT
    raise ValueError(f"unknown BanG Dream! font: {font!r}")
