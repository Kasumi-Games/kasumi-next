"""Windows 11 Fluent kit built on Mica surfaces."""

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
from .components import FluentPanel
from .components import FluentBackground

FluentFont = Literal["chinese", "display"]


class FluentKit(BaseKit):
    """Windows 11 Fluent design.

    Three things carry the look: Mica, which tints the page from a blurred
    desktop rather than a flat fill; the 8px corner radius Windows 11 uses on
    cards, far tighter than the other kits; and the layered card edge, a dark
    control stroke with a lit highlight along the top.

    Text uses the bundled CJK font rather than Segoe UI Variable, which is not
    redistributable and is absent off Windows.
    """

    primary = rgba(0, 120, 212, 255)
    accent = rgba(0, 95, 184, 255)
    text_color = rgba(26, 26, 26, 255)
    muted_text_color = rgba(94, 94, 94, 255)
    panel_fill = rgba(255, 255, 255, 178)
    mica_fill = rgba(243, 243, 243, 255)
    stroke_color = rgba(0, 0, 0, 15)
    divider_color = rgba(0, 0, 0, 20)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        noise_intensity: int = 10,
        random_seed: int = 0,
    ) -> Background:
        """Create the Mica background.

        Args:
            fill: Optional Mica base color override.
            noise_intensity: Acrylic grain strength from 0 to 255; ``0``
                disables the grain.
            random_seed: Seed making the grain reproducible.

        Returns:
            Background renderer.
        """

        return FluentBackground(
            fill=fill or self.mica_fill,
            noise_intensity=noise_intensity,
            random_seed=random_seed,
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
        font: FluentFont = "chinese",
    ) -> Component:
        """Create body text in the Fluent primary text color."""

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
        elevated: bool = True,
    ) -> Component:
        """Create a Fluent card.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional card fill color override.
            radius: Optional corner radius override; Windows 11 uses 8.
            elevated: Whether to draw the drop shadow.

        Returns:
            Panel component.
        """

        return FluentPanel(
            child,
            fill=fill or self.panel_fill,
            radius=8 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            stroke_color=self.stroke_color,
            shadow_blur=8 if elevated else 0,
            shadow_color=rgba(0, 0, 0, 28 if elevated else 0),
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 1,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a Fluent divider."""

        return KitSeparator(
            orientation, length, thickness, color or self.divider_color
        )
