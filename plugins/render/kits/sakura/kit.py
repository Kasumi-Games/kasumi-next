"""Soft pastel kit in cherry-blossom colors."""

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
from .components import SakuraPanel
from .components import SakuraBackground

SakuraFont = Literal["chinese", "display"]


class SakuraKit(BaseKit):
    """Pink-and-cream surfaces with generous rounding.

    The lightest of the kits: shadows are warm rather than grey, corners are
    rounder than elsewhere, and text is a soft plum instead of black so nothing
    on the page reads as harsh.
    """

    primary = rgba(240, 150, 180, 255)
    accent = rgba(196, 160, 216, 255)
    text_color = rgba(96, 66, 78, 255)
    muted_text_color = rgba(172, 142, 154, 255)
    panel_fill = rgba(255, 255, 255, 234)
    wash_top = rgba(255, 250, 251, 255)
    wash_bottom = rgba(252, 226, 236, 255)
    theme_signature_enabled = False

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        bottom: ColorLike | None = None,
        petal_density: float = 0.00005,
        petal_size: int = 18,
        random_seed: int = 0,
    ) -> Background:
        """Create the cream wash background with drifting petals.

        Args:
            fill: Optional top wash color override.
            bottom: Optional bottom wash color override.
            petal_density: Petals per logical pixel of page area.
            petal_size: Nominal petal size in logical pixels.
            random_seed: Seed making the petal scatter reproducible.

        Returns:
            Background renderer.
        """

        return SakuraBackground(
            top=fill or self.wash_top,
            bottom=bottom or self.wash_bottom,
            petal_density=petal_density,
            petal_size=petal_size,
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
        font: SakuraFont = "chinese",
    ) -> Component:
        """Create soft plum text."""

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
        shadow: bool = True,
    ) -> Component:
        """Create a rounded white card with a warm shadow.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.
            shadow: Whether to draw the drop shadow.

        Returns:
            Panel component.
        """

        return SakuraPanel(
            child,
            fill=fill or self.panel_fill,
            radius=44 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            shadow_blur=12 if shadow else 0,
            shadow_color=rgba(226, 158, 184, 92 if shadow else 0),
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a blossom-toned divider."""

        return KitSeparator(
            orientation, length, thickness, color or rgba(242, 208, 220, 255)
        )
