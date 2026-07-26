"""Dark, low-light kit for night reading."""

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
from .components import MidnightPanel
from .components import MidnightBackground

MidnightFont = Literal["chinese", "display"]


class MidnightKit(BaseKit):
    """Deep charcoal surfaces, light text, indigo glow.

    Built for dark-mode output: every surface sits above a night-sky gradient,
    and panels are separated from the background by an outer glow rather than by
    a hard border, so contrast stays comfortable at low brightness.
    """

    primary = rgba(108, 160, 255, 255)
    accent = rgba(126, 226, 214, 255)
    text_color = rgba(226, 232, 245, 255)
    muted_text_color = rgba(142, 152, 182, 255)
    panel_fill = rgba(30, 36, 56, 224)
    surface_top = rgba(11, 14, 23, 255)
    surface_bottom = rgba(26, 32, 56, 255)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        bottom: ColorLike | None = None,
        star_density: float = 0.00012,
        random_seed: int = 0,
    ) -> Background:
        """Create the night-sky gradient background.

        Args:
            fill: Optional top gradient color override.
            bottom: Optional bottom gradient color override.
            star_density: Stars per logical pixel of page area.
            random_seed: Seed making the star scatter reproducible.

        Returns:
            Background renderer.
        """

        return MidnightBackground(
            top=fill or self.surface_top,
            bottom=bottom or self.surface_bottom,
            star_density=star_density,
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
        font: MidnightFont = "chinese",
    ) -> Component:
        """Create light-on-dark text."""

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
        glow: bool = True,
    ) -> Component:
        """Create a dark panel with an indigo outer glow.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.
            glow: Whether to draw the outer glow.

        Returns:
            Panel component.
        """

        return MidnightPanel(
            child,
            fill=fill or self.panel_fill,
            radius=36 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            glow_blur=14 if glow else 0,
            glow_color=rgba(96, 132, 232, 90 if glow else 0),
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a muted divider."""

        return KitSeparator(
            orientation, length, thickness, color or rgba(70, 82, 115, 255)
        )
