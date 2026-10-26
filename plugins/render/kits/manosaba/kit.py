"""魔法少女的魔女审判 — an asset-backed, serif courtroom render kit."""

from math import ceil
from typing import Literal
from typing import Sequence
from pathlib import Path

from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import Spacer
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import Overlay
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.core import Background
from plugins.render.color import ColorLike
from plugins.render.types import ImageFit
from plugins.render.types import Overflow
from plugins.render.types import TextAlign
from plugins.render.types import ImageSource
from plugins.render.sizing import SizeValue
from plugins.render.sizing import as_size_value
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import load_font
from plugins.render.text_layout import text_width

from ..atoms import KitText
from ..atoms import KitImage
from .components import INK
from .components import PINK
from .components import ROSE
from .components import MUTED
from .components import PAPER
from .components import SERIF
from .components import SURFACE
from .components import RESOURCES
from .components import ChoicePanel
from .components import ManosabaPanel
from .components import ManosabaTitle
from .components import ManosabaSeparator
from .components import ManosabaBackground


class ManosabaKit(BaseKit):
    """Aged rose paper, ink ribbons, botanical corners and evidence dossiers.

    Runtime only needs Pillow and the bundled curated assets. UnityPy is used
    exclusively by scripts/extract_manosaba_assets.py to reproduce the bundle.
    """

    primary = ROSE
    accent = ROSE
    text_color = INK
    muted_text_color = MUTED
    panel_fill = SURFACE
    paper_fill = PAPER

    def background(self, *, fill: ColorLike | None = None) -> Background:
        return ManosabaBackground(fill=fill)

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
        return KitText(
            text,
            SERIF,
            font_size=font_size,
            color=self.text_color if color is None else color,
            align=align,
            wrap=wrap,
            max_lines=max_lines,
            overflow=overflow,
            line_height=line_height,
            center_glyphs_in_line=True,
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
    ) -> Component:
        return ManosabaPanel(
            child,
            width=width,
            height=height,
            padding=padding,
            fill=self.panel_fill if fill is None else fill,
            radius=radius,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        return ManosabaSeparator(
            orientation, length, thickness, self.primary if color is None else color
        )

    def page_title(self, text: str, *, font_size: int = 40) -> Component:
        return ManosabaTitle(text, font_size)

    def game_title(
        self, title: str, subtitle: str, *, width: int, height: int
    ) -> Component:
        return Frame(
            VStack(
                [
                    self.page_title(title, font_size=32),
                    self.text(subtitle, font_size=22, color=MUTED, wrap=False),
                ],
                gap=8,
                align="start",
            ),
            width=width,
            align_x="start",
            align_y="start",
        )

    def command_tile(
        self, label: str, *, width: int, height: int, detail: str = ""
    ) -> Component:
        if not detail:
            return ChoicePanel(
                self.text(
                    label, font_size=24, wrap=False, align="center", overflow="shrink"
                ),
                width=width,
                height=height,
            )
        return self.panel(
            VStack(
                [
                    self.text(label, font_size=24, wrap=False),
                    self.text(detail, font_size=20, color=MUTED, wrap=False),
                ],
                gap=4,
            ),
            width=width,
            height=height,
            padding=Insets.xy(20, 12),
        )

    def portrait(
        self, source: ImageSource, *, width: SizeValue | int, height: SizeValue | int
    ) -> Component:
        """Mount the game's side portraits as cropped photographs.

        Choice portraits end at a screen edge in the original game. Their
        hard edge belongs inside a picture mount, not on an open book page.
        Caller-provided standing illustrations retain their complete artwork.
        """
        side_portrait = isinstance(source, (str, Path)) and Path(source).resolve() in {
            RESOURCES / "portrait_ema.png",
            RESOURCES / "portrait_hiro.png",
        }
        inset_x = max(8, round(_pixels(width, 220) * 0.17))
        inset_y = max(8, round(_pixels(height, 260) * 0.18))
        return Frame(
            Overlay(
                [
                    self.image(
                        RESOURCES / "portrait_frame.png",
                        width=Fill(),
                        height=Fill(),
                        fit="stretch",
                    ),
                    Frame(
                        self.image(
                            source,
                            width=Fill(),
                            height=Fill(),
                            fit="cover" if side_portrait else "contain",
                        ),
                        padding=Insets.xy(inset_x, inset_y),
                        align_x="stretch",
                        align_y="stretch",
                    ),
                ]
            ),
            width=width,
            height=height,
            align_x="stretch",
            align_y="stretch",
        )

    def choice(
        self, text: str, *, width: SizeValue | int = 640, active: bool = False
    ) -> Component:
        """A game choice ribbon; active state uses the game's burgundy artwork."""
        return ChoicePanel(
            self.text(
                text,
                font_size=26,
                color=SURFACE if active else INK,
                align="center",
                wrap=False,
                max_lines=1,
            ),
            width=width,
            active=active,
        )

    def ornament(self, *, width: SizeValue | int = 320) -> Component:
        """Original diamond-and-thorn section divider, in its own layout slot."""
        return self.image(RESOURCES / "rule.png", width=width, height=32)

    def game_identity(
        self,
        identity: PlayerIdentity,
        *,
        width: SizeValue | int,
        detail: str | None = None,
    ) -> Component:
        total = _pixels(width, 720)
        avatar_size = 52
        gap = 12
        avatar = self._avatar(
            identity.avatar, identity.nickname, avatar_size, identity.avatar_frame
        )
        extras: list[Component] = []
        available = total - 28 - 64 - gap - 110  # Always reserve a legible nickname.
        if identity.level is not None and available >= 86:
            extras.append(self._chip(f"Lv.{identity.level}", width=86))
            available -= 98
        if detail and available >= 150:
            extras.append(
                Frame(
                    self.text(
                        detail,
                        font_size=22,
                        color=SURFACE,
                        align="right",
                        wrap=False,
                        max_lines=1,
                    ),
                    width=Fixed(min(available, 270)),
                )
            )
        return ManosabaPanel(
            HStack(
                [
                    avatar,
                    Frame(
                        self.text(
                            identity.nickname,
                            font_size=26,
                            color=SURFACE,
                            wrap=False,
                            max_lines=1,
                        ),
                        width=Fill(),
                        align_y="center",
                    ),
                    *extras,
                ],
                gap=gap,
                align="center",
            ),
            width=width,
            height=80,
            padding=Insets.only(left=14, right=14, top=8, bottom=8),
            fill=INK,
            border=ROSE,
            weight=2,
            ornate=False,
        )

    def player_card(
        self,
        *,
        avatar_image: ImageSource | None,
        frame_image: ImageSource | None,
        title1_image: ImageSource | None,
        title2_image: ImageSource | None,
        nickname: str,
        level: int,
        current_pt: int,
        description: str,
        width: SizeValue | int,
        height: SizeValue | int,
        standing_art: ImageSource | None = None,
    ) -> Component:
        total = _pixels(width, 784)
        compact = total < 460
        pad = 14 if compact else 26
        art_width = (
            min(230, total // 3) if standing_art is not None and total >= 620 else 0
        )
        content_width = total - pad * 2 - (art_width + 18 if art_width else 0)
        avatar_size = 58 if compact else 88
        heading = VStack(
            [
                self.text("人物档案", font_size=18, color=ROSE, wrap=False),
                self.text(
                    nickname, font_size=26 if compact else 36, wrap=False, max_lines=1
                ),
            ],
            gap=2,
            align="stretch",
        )
        identity = (
            HStack(
                [
                    self._avatar(avatar_image, nickname, avatar_size, frame_image),
                    Frame(heading, width=Fill(), align_x="stretch", align_y="center"),
                ],
                gap=14,
                align="center",
            )
            if not compact
            else heading
        )
        title_width = max(1, (content_width - 10) // 2)
        titles = Frame(
            HStack(
                [
                    Frame(
                        self.image(title1_image, width=Fill(), height=32)
                        if title1_image is not None
                        else self.separator(length=Fill()),
                        width=Fixed(title_width),
                        height=36,
                        align_y="center",
                    ),
                    Frame(
                        self.image(title2_image, width=Fill(), height=32)
                        if title2_image is not None
                        else self.separator(length=Fill()),
                        width=Fixed(title_width),
                        height=36,
                        align_y="center",
                    ),
                ],
                gap=10,
                align="center",
            ),
            height=36,
        )
        left = VStack(
            [
                identity,
                titles,
                Frame(
                    self.text(
                        description.strip() or "尚未留下证言。",
                        font_size=22,
                        color=INK if description.strip() else MUTED,
                        max_lines=3,
                        line_height=31,
                    ),
                    height=96,
                    align_x="stretch",
                    align_y="start",
                ),
                Spacer(height=Fill()),
                self.separator(length=Fill(), thickness=5),
                HStack(
                    [
                        Frame(
                            VStack(
                                [
                                    self.text(
                                        "赛季积分",
                                        font_size=18,
                                        color=MUTED,
                                        wrap=False,
                                        overflow="shrink",
                                    ),
                                    self.text(
                                        f"{current_pt:,} Pt",
                                        font_size=26,
                                        wrap=False,
                                        max_lines=1,
                                        overflow="shrink",
                                    ),
                                ],
                                gap=0,
                                align="start",
                            ),
                            width=Fill(),
                            align_x="stretch",
                        ),
                        Frame(
                            VStack(
                                [
                                    self.text("等级", font_size=18, color=MUTED),
                                    self.text(
                                        f"Lv.{level}",
                                        font_size=26,
                                        wrap=False,
                                        max_lines=1,
                                    ),
                                ],
                                gap=0,
                                align="start",
                            ),
                            width=Fill(),
                            align_x="stretch",
                        ),
                    ],
                    gap=10,
                    align="end",
                ),
            ],
            gap=10 if compact else 14,
            align="stretch",
        )
        content: Component = left
        if art_width:
            content = HStack(
                [
                    Frame(left, width=Fill(), align_x="stretch", align_y="stretch"),
                    Frame(
                        self.portrait(standing_art, width=art_width, height=300),
                        width=Fixed(art_width),
                        align_y="center",
                    ),
                ],
                gap=18,
                align="stretch",
            )
        return ManosabaPanel(
            content,
            width=width,
            height=height,
            padding=pad,
            fill=SURFACE,
            border=ROSE,
            weight=2,
            texture="book.png",
            book_spine=(total - pad - art_width - 9) / total
            if art_width
            else pad / 2 / total,
        )

    def pull_reveal(
        self, pulls: Sequence[PullRevealItem], *, width: SizeValue | int
    ) -> Component:
        total = _pixels(width, 784)
        if not pulls:
            return self.panel(
                self.text("尚无抽取记录", font_size=24, align="center"),
                width=width,
                padding=24,
            )
        if len(pulls) == 1 and total >= 560:
            return self._single_pull(pulls[0], width)
        if len(pulls) > 10:
            raise ValueError("Manosaba pull_reveal supports one to ten pulls")
        # Balance partial grids (six pulls become 3 + 3) and use a single
        # column at 200px. Art, status and compensation determine row height.
        gap = 12
        max_columns = min(5, max(1, (total + gap) // 164))
        columns = ceil(len(pulls) / ceil(len(pulls) / max_columns))
        tile_width = max(1, (total - gap * (columns - 1)) // columns)
        art_slot = any(p.image is not None for p in pulls)
        status_height = max(
            26 * (pull.is_new + pull.featured) + (24 if pull.note else 0)
            for pull in pulls
        )
        height = 162 + status_height
        if art_slot:
            height += 4 + min(200, max(128, round(tile_width * 0.7)))
        return Frame(
            Grid(
                [
                    self._pull_tile(pull, index, tile_width, height, art_slot)
                    for index, pull in enumerate(pulls, 1)
                ],
                columns=columns,
                column_track=Fixed(tile_width),
                row_track=Fixed(height),
                gap=gap,
            ),
            width=width,
            align_x="center",
            align_y="start",
        )

    def _single_pull(self, pull: PullRevealItem, width: SizeValue | int) -> Component:
        art = self.portrait(
            pull.image if pull.image is not None else RESOURCES / "diamond.png",
            width=220,
            height=260,
        )
        words = VStack(
            [
                self.text(
                    f"★{pull.rarity}  /  抽取结果", font_size=24, color=ROSE, wrap=False
                ),
                self.text(pull.name, font_size=32, max_lines=3),
                self.ornament(width=220),
                self.text(
                    " · ".join(
                        label
                        for flag, label in [
                            (pull.is_new, "初次获得"),
                            (pull.featured, "本期精选"),
                        ]
                        if flag
                    ),
                    font_size=24,
                    color=ROSE,
                    max_lines=2,
                ),
                self.text(pull.note, font_size=22, color=MUTED, max_lines=2),
            ],
            gap=12,
            align="stretch",
        )
        return ManosabaPanel(
            HStack(
                [
                    Frame(art, width=Fixed(220), height=Fixed(260)),
                    Frame(words, width=Fill(), align_x="stretch", align_y="center"),
                ],
                gap=24,
                align="center",
            ),
            width=width,
            height=352,
            padding=24,
            border=ROSE,
            weight=3 if pull.rarity >= 6 else 1,
            texture="book.png",
            book_spine=256 / _pixels(width, 784),
        )

    def _avatar(
        self,
        image: ImageSource | None,
        nickname: str,
        size: int,
        frame: ImageSource | None = None,
    ) -> Component:
        face = (
            self.image(
                image, width=Fill(), height=Fill(), fit="cover", radius=size // 2
            )
            if image is not None
            else Frame(
                self.text(
                    nickname[:1] or "?",
                    font_size=max(24, size // 2),
                    color=SURFACE,
                    align="center",
                    wrap=False,
                ),
                align_x="center",
                align_y="center",
            )
        )
        base = ManosabaPanel(
            face,
            width=size,
            height=size,
            padding=4,
            fill=INK,
            radius=size // 2,
            border=PINK,
            weight=2,
            ornate=False,
        )
        if frame is None:
            return base
        outer = round(size * 512 / 416)
        return Frame(
            Overlay(
                [
                    Frame(base, align_x="center", align_y="center"),
                    self.image(frame, width=outer, height=outer),
                ],
                align_x="center",
                align_y="center",
            ),
            width=outer,
            height=outer,
        )

    def _chip(self, label: str, *, width: int | None = None) -> Component:
        return ManosabaPanel(
            Frame(
                self.text(
                    label,
                    font_size=22,
                    color=PINK,
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
                align_x="center",
                align_y="center",
            ),
            width=width or text_width(label, load_font(22, SERIF)) + 22,
            height=36,
            fill=INK,
            border=ROSE,
            ornate=False,
        )

    def _pull_tile(
        self, pull: PullRevealItem, index: int, width: int, height: int, art_slot: bool
    ) -> Component:
        rare = pull.rarity >= 6
        # Numeric star count, a doubled frame, and a crest encode rarity even
        # in monochrome. NEW and UP are both preserved on separate lines.
        rows: list[Component] = [
            ManosabaPanel(
                HStack(
                    [
                        self.text(f"{index:02d}", font_size=22, color=PINK),
                        Spacer(width=Fill()),
                        self.text(
                            f"★{pull.rarity}", font_size=24, color=SURFACE, wrap=False
                        ),
                    ],
                    gap=4,
                    align="center",
                ),
                height=34,
                padding=Insets.xy(8, 3),
                fill=INK,
                border=ROSE,
                ornate=False,
            )
        ]
        if art_slot:
            art_height = min(200, max(128, round(width * 0.7)))
            rows.append(
                Frame(
                    self.portrait(
                        pull.image,
                        width=min(width - 16, round(art_height * 0.95)),
                        height=art_height,
                    )
                    if pull.image is not None
                    else self.image(
                        RESOURCES / "diamond.png", width=68, height=68, opacity=0.3
                    ),
                    height=art_height,
                    align_x="center",
                    align_y="center",
                )
            )
        rows.extend(
            [
                Frame(
                    self.text(
                        pull.name,
                        font_size=21,
                        align="center",
                        max_lines=2,
                        line_height=28,
                    ),
                    height=58,
                    align_y="center",
                    align_x="stretch",
                ),
                Spacer(height=Fill()),
                Frame(
                    self.text(
                        "初次获得" if pull.is_new else "",
                        font_size=20,
                        color=ROSE,
                        align="center",
                        wrap=False,
                    ),
                    height=26 if pull.is_new else 0,
                    align_x="stretch",
                ),
                Frame(
                    self.text(
                        "本期精选" if pull.featured else "",
                        font_size=20,
                        color=ROSE,
                        align="center",
                        wrap=False,
                    ),
                    height=26 if pull.featured else 0,
                    align_x="stretch",
                ),
                Frame(
                    self.text(
                        pull.note,
                        font_size=18,
                        color=MUTED,
                        align="center",
                        wrap=False,
                        max_lines=1,
                    ),
                    height=24 if pull.note else 0,
                    align_x="stretch",
                ),
                Frame(
                    self.image(RESOURCES / "crest.png", width=25, height=25)
                    if rare
                    else self.separator(length=Fill()),
                    height=22,
                    align_x="center",
                    align_y="center",
                ),
            ]
        )
        return ManosabaPanel(
            VStack(rows, gap=4, align="stretch"),
            width=width,
            height=height,
            padding=8,
            fill=SURFACE,
            border=ROSE if rare else MUTED,
            weight=3 if rare else 1,
            ornate=rare,
        )


def _pixels(value: SizeValue | int, fallback: int) -> int:
    token = as_size_value(value)
    return token.value if isinstance(token, Fixed) else fallback
