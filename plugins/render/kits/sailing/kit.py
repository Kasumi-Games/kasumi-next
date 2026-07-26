"""Ocean-voyage kit for the sailing theme."""

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
from .components import SailingPanel
from .components import SailingBackground

SailingFont = Literal["chinese", "display"]


class SailingKit(BaseKit):
    """Sea blues under sail-cream surfaces.

    This is the visual counterpart to the ``theme_s1_sailing`` cosmetic item.
    (The 「Kasumi，扬帆起航」 season it was authored for was scrapped before
    launch; the theme item currently has no grant path and is held for reuse.)
    Content sits on cream panels so the deep-water palette stays in the
    background and never fights the text.
    """

    primary = rgba(14, 76, 122, 255)
    accent = rgba(64, 166, 208, 255)
    text_color = rgba(28, 58, 84, 255)
    muted_text_color = rgba(104, 134, 158, 255)
    panel_fill = rgba(252, 252, 248, 232)
    sky_top = rgba(226, 242, 251, 255)
    sky_bottom = rgba(150, 206, 235, 255)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        bottom: ColorLike | None = None,
        wave_height: int = 46,
        wave_length: int = 260,
    ) -> Background:
        """Create the sky-and-waves background.

        Args:
            fill: Optional sky color at the top edge.
            bottom: Optional sky color at the horizon.
            wave_height: Peak-to-trough wave height in logical pixels.
            wave_length: Distance between wave crests in logical pixels.

        Returns:
            Background renderer.
        """

        return SailingBackground(
            top=fill or self.sky_top,
            bottom=bottom or self.sky_bottom,
            wave_height=wave_height,
            wave_length=wave_length,
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
        font: SailingFont = "chinese",
    ) -> Component:
        """Create deep-water text."""

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
        accent: bool = True,
    ) -> Component:
        """Create a cream panel with a deep-water accent bar.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.
            accent: Whether to draw the top accent bar.

        Returns:
            Panel component.
        """

        return SailingPanel(
            child,
            fill=fill or self.panel_fill,
            radius=30 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            accent_color=self.primary,
            accent_height=6 if accent else 0,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a foam-toned divider."""

        return KitSeparator(
            orientation, length, thickness, color or rgba(168, 200, 220, 255)
        )
