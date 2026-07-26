from typing import Literal

from plugins.render.kit import BaseKit
from plugins.render.core import Component
from plugins.render.core import Background
from plugins.render.color import ColorLike
from plugins.render.types import ImageFit
from plugins.render.types import Overflow
from plugins.render.types import TextAlign
from plugins.render.types import ImageSource
from plugins.render.sizing import SizeValue
from plugins.render.spacing import InsetsLike

from ..atoms import KitText
from ..fonts import CHINESE_FONT
from .components import MinimalImage
from .components import MinimalPanel
from .components import MinimalSeparator
from .components import MinimalBackground


class MinimalKit(BaseKit):
    text_color = (80, 80, 80, 255)
    muted_text_color = (130, 130, 145, 255)
    panel_fill = (245, 245, 245, 255)

    def background(self, *, fill: ColorLike | None = None) -> Background:
        return MinimalBackground(fill or (255, 255, 255, 255))

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
    ) -> Component:
        # KitText with the shared CJK font rather than MinimalText: PIL's
        # default font has no CJK coverage, so Chinese rendered as tofu boxes.
        # This keeps minimal's last-resort property — the font path is only
        # touched at render time, and load_font falls back to the default font
        # instead of raising when the file is missing.
        return KitText(
            text,
            CHINESE_FONT,
            font_size=font_size,
            color=color or (80, 80, 80, 255),
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
        return MinimalImage(
            image,
            width=width,
            height=height,
            fit=fit,
            opacity=opacity,
            radius=radius,
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
        return MinimalPanel(
            child,
            fill=fill or (245, 245, 245, 255),
            radius=20 if radius is None else radius,
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
        return MinimalSeparator(
            orientation,
            length,
            thickness,
            color or (170, 170, 170, 255),
        )
