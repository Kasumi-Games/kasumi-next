"""Monochrome manga kit drawn in ink and screentone."""

from typing import Literal

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

from ..atoms import KitText
from ..atoms import KitImage
from ..atoms import KitSeparator
from ..fonts import CHINESE_FONT
from ..fonts import DISPLAY_FONT
from .components import MangaPanel
from .components import MangaBackground

MangaFont = Literal["chinese", "display"]


class MangaKit(BaseKit):
    """Black ink on printed paper, with halftone screentone behind it.

    The only kit with no color: separation comes from ink weight and tone
    density instead of hue, so panels are outlined heavily and the page carries
    a printed screen. It survives grayscale and low-quality image compression
    better than the color kits.
    """

    primary = rgba(18, 18, 20, 255)
    accent = rgba(18, 18, 20, 255)
    text_color = rgba(18, 18, 20, 255)
    muted_text_color = rgba(112, 112, 118, 255)
    panel_fill = rgba(255, 255, 255, 242)
    paper_fill = rgba(246, 243, 236, 255)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        dot_spacing: int = 12,
        dot_radius: float = 2.1,
        speed_lines: int = 26,
    ) -> Background:
        """Create the screentone paper background.

        Args:
            fill: Optional paper color override.
            dot_spacing: Halftone dot pitch in logical pixels.
            dot_radius: Halftone dot radius in logical pixels.
            speed_lines: Number of corner speed lines; ``0`` disables them.

        Returns:
            Background renderer.
        """

        return MangaBackground(
            fill=fill or self.paper_fill,
            dot_spacing=dot_spacing,
            dot_radius=dot_radius,
            speed_lines=speed_lines,
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
        font: MangaFont = "chinese",
    ) -> Component:
        """Create ink-black text."""

        return KitText(
            text,
            CHINESE_FONT if font == "chinese" else DISPLAY_FONT,
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
        """Create an image wrapper."""

        return KitImage(
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
        ink_width: int = 5,
    ) -> Component:
        """Create a paper cell boxed in ink.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.
            ink_width: Outline weight in logical pixels.

        Returns:
            Panel component.
        """

        return MangaPanel(
            child,
            fill=fill or self.panel_fill,
            radius=14 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            ink_color=self.primary,
            ink_width=ink_width,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 3,
        color: ColorLike | None = None,
    ) -> Component:
        """Create an inked rule."""

        return KitSeparator(orientation, length, thickness, color or self.primary)
