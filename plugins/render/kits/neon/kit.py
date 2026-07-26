"""Retro arcade kit with neon tubing on a dark cabinet."""

from typing import Literal

from plugins.render.kit import BaseKit
from plugins.render.core import Component
from plugins.render.core import Background
from plugins.render.color import ColorLike
from plugins.render.color import rgba
from plugins.render.color import normalize_color
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
from .components import NeonPanel
from .components import NeonBackground

NeonFont = Literal["chinese", "display"]


class NeonKit(BaseKit):
    """Magenta and cyan neon over a near-black cabinet.

    Corners are deliberately tight and borders are lit rather than soft, which
    is what separates this from the midnight kit: midnight recedes, neon glares.
    Numerals read best through ``font="display"``.
    """

    primary = rgba(255, 44, 160, 255)
    accent = rgba(34, 240, 255, 255)
    text_color = rgba(232, 236, 255, 255)
    muted_text_color = rgba(150, 140, 190, 255)
    panel_fill = rgba(14, 12, 28, 228)
    cabinet_fill = rgba(7, 6, 15, 255)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        grid_spacing: int = 46,
        scanline_spacing: int = 4,
        horizon_ratio: float = 0.52,
    ) -> Background:
        """Create the horizon-grid background with scanlines.

        Args:
            fill: Optional cabinet color override.
            grid_spacing: Grid line spacing in logical pixels.
            scanline_spacing: Scanline spacing in logical pixels.
            horizon_ratio: Horizon position as a fraction of page height.

        Returns:
            Background renderer.
        """

        return NeonBackground(
            fill=fill or self.cabinet_fill,
            grid_color=rgba(*self.primary[:3], 70),
            horizon_color=rgba(*self.accent[:3], 90),
            grid_spacing=grid_spacing,
            scanline_spacing=scanline_spacing,
            horizon_ratio=horizon_ratio,
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
        font: NeonFont = "chinese",
    ) -> Component:
        """Create bright text for a dark cabinet."""

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
        tube_color: ColorLike | None = None,
    ) -> Component:
        """Create a dark panel ringed by a lit neon tube.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.
            tube_color: Optional tube color override; pass ``accent`` for cyan.

        Returns:
            Panel component.
        """

        tube = normalize_color(tube_color) or self.primary
        return NeonPanel(
            child,
            fill=fill or self.panel_fill,
            radius=10 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            tube_color=tube,
            glow_color=rgba(*tube[:3], 120),
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a lit divider."""

        return KitSeparator(
            orientation, length, thickness, color or rgba(*self.primary[:3], 190)
        )
