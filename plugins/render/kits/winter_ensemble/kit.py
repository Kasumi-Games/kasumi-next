"""Winter ensemble: warm paper, snow blue, ink and red registration marks."""

from typing import Sequence

from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Spacer
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import Overlay
from plugins.render.kit import PlayerIdentity
from plugins.render.kit import PullRevealItem
from plugins.render.types import ImageSource
from plugins.render.sizing import as_size_value
from plugins.render.kits.atoms import KitText
from plugins.render.kits.atoms import KitImage
from plugins.render.kits.atoms import KitSeparator
from plugins.render.kits.mewtype.fonts import CHINESE_BODY_FONT
from plugins.render.kits.mewtype.fonts import CHINESE_HEADING_FONT

from .components import INK
from .components import LINE
from .components import SNOW
from .components import AMBER
from .components import MUTED
from .components import PAPER
from .components import STAMP
from .components import NUMBER_FONT
from .components import WinterArt
from .components import WinterRule
from .components import WinterPaper
from .components import WinterHeading
from .components import WinterBackground


def pixels(value, fallback=784):
    token = as_size_value(value)
    return token.value if isinstance(token, Fixed) else fallback


class WinterEnsembleKit(BaseKit):
    primary = STAMP
    accent = AMBER
    text_color = INK
    muted_text_color = MUTED
    panel_fill = PAPER

    def background(self, *, fill=None):
        return WinterBackground(SNOW if fill is None else fill)

    def text(
        self,
        text,
        *,
        font_size=40,
        color=None,
        align="left",
        wrap=True,
        max_lines=None,
        overflow="ellipsis",
        line_height=None,
    ):
        return KitText(
            text,
            CHINESE_BODY_FONT,
            font_size=font_size,
            color=INK if color is None else color,
            align=align,
            wrap=wrap,
            max_lines=max_lines,
            overflow=overflow,
            line_height=line_height,
            center_glyphs_in_line=True,
        )

    def page_title(self, text, *, font_size=52):
        return WinterHeading(text, font_size)

    def number(self, text, *, font_size=64, color=INK):
        return KitText(
            text,
            NUMBER_FONT,
            font_size=font_size,
            color=color,
            wrap=False,
            max_lines=1,
            line_height=round(font_size * 1.08),
            center_glyphs_in_line=True,
        )

    def art(self, source, *, width, height):
        return WinterArt(source, width=width, height=height)

    def image(
        self, image, *, width=None, height=None, fit="contain", opacity=1.0, radius=0
    ):
        return KitImage(
            image, width=width, height=height, fit=fit, opacity=opacity, radius=radius
        )

    def panel(
        self, child=None, *, width=None, height=None, padding=0, fill=None, radius=None
    ):
        return WinterPaper(
            child,
            width,
            height,
            padding,
            PAPER if fill is None else fill,
            4 if radius is None else radius,
        )

    def separator(
        self, *, orientation="horizontal", length=None, thickness=1, color=None
    ):
        if orientation == "horizontal" and thickness == 1 and color is None:
            return WinterRule(orientation, length, thickness, LINE)
        return KitSeparator(
            orientation, length, thickness, LINE if color is None else color
        )

    def avatar(self, source, nickname, size, frame=None):
        face = (
            self.image(
                source,
                width=Fixed(size),
                height=Fixed(size),
                fit="cover",
                radius=size // 2,
            )
            if source
            else self.panel(
                Frame(
                    self.text(
                        nickname[:1] or "?",
                        font_size=max(24, size // 2),
                        align="center",
                    ),
                    align_x="center",
                    align_y="center",
                ),
                width=size,
                height=size,
                radius=size // 2,
            )
        )
        extent = round(size * 512 / 416) if frame is not None else size
        layers = [
            Frame(face, width=extent, height=extent, align_x="center", align_y="center")
        ]
        if frame is not None:
            layers.append(self.image(frame, width=extent, height=extent))
        return Frame(Overlay(layers), width=extent, height=extent)

    def game_identity(self, identity: PlayerIdentity, *, width, detail=None):
        w = pixels(width)
        children = [
            self.avatar(identity.avatar, identity.nickname, 48, identity.avatar_frame),
            Frame(
                self.text(identity.nickname, font_size=26, wrap=False, max_lines=1),
                width=Fill(),
                align_x="stretch",
                align_y="center",
            ),
        ]
        if w >= 360 and identity.level is not None:
            children.append(self.text(f"Lv.{identity.level}", font_size=22, wrap=False))
        if w >= 560 and detail:
            children.append(
                Frame(
                    self.text(detail, font_size=22, wrap=False, max_lines=1),
                    width=Fixed(min(260, w // 3)),
                    align_y="center",
                )
            )
        return self.panel(
            HStack(children, gap=14, align="center"), width=width, height=80, padding=12
        )

    def player_card(
        self,
        *,
        avatar_image,
        frame_image,
        title1_image,
        title2_image,
        nickname,
        level,
        current_pt,
        description,
        width,
        height,
        standing_art: ImageSource | None = None,
    ):
        titles = [
            self.image(t, height=36)
            for t in (title1_image, title2_image)
            if t is not None
        ]
        identity = HStack(
            [
                self.avatar(avatar_image, nickname, 96, frame_image),
                Frame(
                    VStack(
                        [
                            self.text(nickname, font_size=34, wrap=False, max_lines=1),
                            self.text(f"Lv.{level}", font_size=24),
                            Frame(HStack(titles, gap=12), height=40),
                        ],
                        gap=8,
                    ),
                    width=Fill(),
                    align_x="stretch",
                ),
            ],
            gap=24,
            align="center",
        )
        left = VStack(
            [
                identity,
                self.separator(length=Fill()),
                self.text(
                    description.strip() or "这个人还没有写简介。",
                    font_size=24,
                    max_lines=4,
                ),
                Spacer(height=Fill()),
                self.text(f"赛季 Pt  {current_pt:,}", font_size=30),
            ],
            gap=18,
        )
        body = (
            left
            if standing_art is None
            else HStack(
                [
                    Frame(left, width=Fill()),
                    self.image(standing_art, width=240, height=Fill()),
                ],
                gap=24,
            )
        )
        return WinterPaper(body, width=width, height=height, padding=32, tape=True)

    def pull_reveal(self, pulls: Sequence[PullRevealItem], *, width):
        w = pixels(width)
        if not pulls:
            return self.panel(
                self.text("暂无抽取结果", font_size=26), width=width, padding=32
            )
        if len(pulls) == 1 and w >= 540:
            p = pulls[0]
            art = (
                self.art(p.image, width=Fixed(w * 3 // 5), height=Fixed(420))
                if p.image
                else self.text("暂无立绘", font_size=26)
            )
            return WinterPaper(
                HStack(
                    [art, Frame(self._pull_info(p), width=Fill(), align_y="center")],
                    gap=24,
                ),
                width=width,
                padding=24,
                tape=True,
            )
        cols = max(1, min(5, w // 210, len(pulls)))
        tw = (w - 16 * (cols - 1)) // cols
        tiles = []
        for p in pulls:
            art = (
                self.art(p.image, width=Fill(), height=Fixed(220))
                if p.image
                else self.text("暂无立绘", font_size=22, align="center")
            )
            content = VStack(
                [
                    Frame(art, height=220, align_y="center"),
                    Spacer(height=4),
                    self._pull_info(p),
                ],
                gap=12,
            )
            tiles.append(
                WinterPaper(
                    content,
                    tw,
                    500,
                    18,
                    PAPER,
                    4,
                    AMBER if p.rarity >= 6 else LINE,
                    3 if p.rarity >= 6 else 1,
                    perforation=250,
                )
            )
        return Grid(
            tiles, columns=cols, column_track=Fixed(tw), row_track=Fixed(500), gap=16
        )

    def _pull_info(self, p):
        status = " · ".join(
            s for yes, s in [(p.is_new, "新获得"), (p.featured, "精选")] if yes
        )
        return VStack(
            [
                self.text(f"★{p.rarity}", font_size=30 if p.rarity >= 6 else 24),
                Frame(self.text(p.name, font_size=24, max_lines=2), height=66),
                Frame(
                    self.text(status, font_size=22, color=STAMP, max_lines=2), height=48
                ),
                Frame(self.text(p.note, font_size=22, max_lines=2), height=40),
            ],
            gap=6,
        )
