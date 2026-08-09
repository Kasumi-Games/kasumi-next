"""Dreamy grid-paper kit inspired by the common Yumemita subpage style."""

from typing import Literal
from typing import Sequence

from plugins.render.kit import BaseKit
from plugins.render.kit import PlayerIdentity
from plugins.render.kit import PullRevealItem
from plugins.render.core import Component
from plugins.render.core import Background
from plugins.render.color import ColorLike
from plugins.render.color import rgba
from plugins.render.types import ImageFit
from plugins.render.types import Overflow
from plugins.render.types import TextAlign
from plugins.render.types import ImageSource
from plugins.render.layout import Grid
from plugins.render.layout import Frame
from plugins.render.layout import HStack
from plugins.render.layout import Spacer
from plugins.render.layout import VStack
from plugins.render.layout import Overlay
from plugins.render.sizing import Fill
from plugins.render.sizing import Fixed
from plugins.render.sizing import SizeValue
from plugins.render.sizing import as_size_value
from plugins.render.spacing import Insets
from plugins.render.spacing import InsetsLike
from plugins.render.primitives import load_font
from plugins.render.text_layout import text_width

from ..atoms import KitText
from ..atoms import KitImage
from ..atoms import KitSeparator
from .components import MewtypePanel
from .components import MewtypeTitle
from .components import MewtypeBackground
from .components import MewtypeArticleHeader
from .components import MewtypeStreamHeading
from .fonts import CHINESE_BODY_FONT
from .fonts import CHINESE_HEADING_FONT
from .fonts import LATIN_DISPLAY_FONT
from .fonts import LATIN_TITLE_FONT

MewtypeFont = Literal["chinese", "display", "heading"]

_ENGLISH_PAGE_TITLES = {
    "ON AIR": "ONAIR",
    "资料": "PROFILE",
    "签到": "CHECK IN",
    "排行榜": "RANKING",
    "赛季排行": "RANKING",
    "帮助": "HELP",
    "抽卡记录": "GACHA",
    "邮箱": "MAILBOX",
    "邮件": "MAIL",
    "红包": "RED ENVELOPE",
    "黑香澄": "BLACKKASUMI",
    "探险": "EXPLORATION",
    "探险统计": "EXPLORATION",
    "一笔画": "ONE STROKE",
    "猜卡面": "CARD QUIZ",
    "猜谱面": "CHART QUIZ",
}


class MewtypeKit(BaseKit):
    """Pastel stationery, pixel-cut cards, and bright cyan/pink accents.

    This follows the visual language shared by the Yumemita story,
    staff/cast, character, and other interior pages: a pale lavender graph-paper
    field, playful candy-colored marks, dark indigo copy, pink annotations, and
    cyan framing. The redesigned site homepage intentionally is not the
    reference for this kit.
    """

    primary = rgba(29, 211, 243, 255)
    accent = rgba(255, 115, 213, 255)
    text_color = rgba(32, 47, 109, 255)
    muted_text_color = rgba(32, 47, 109, 190)
    panel_fill = rgba(255, 255, 255, 255)
    paper_fill = rgba(252, 241, 255, 255)
    grid_color = rgba(255, 255, 255, 255)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        grid_spacing: int = 40,
        decoration_density: float = 0.000063,
        random_seed: int = 0,
    ) -> Background:
        """Create the exact grid, repeating confetti, and subpage-header marks."""

        return MewtypeBackground(
            fill=fill or self.paper_fill,
            grid_color=self.grid_color,
            cyan=self.primary,
            pink=self.accent,
            grid_spacing=grid_spacing,
            decoration_density=decoration_density,
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
        font: MewtypeFont = "chinese",
    ) -> Component:
        """Create rounded indigo body text or geometric display text."""

        selected_font = {
            "chinese": CHINESE_BODY_FONT,
            "display": LATIN_DISPLAY_FONT,
            "heading": CHINESE_HEADING_FONT,
        }[font]
        return KitText(
            text,
            selected_font,
            font_size=font_size,
            color=color or self.text_color,
            align=align,
            wrap=wrap,
            max_lines=max_lines,
            overflow=overflow,
            line_height=line_height,
            letter_spacing=max(1, round(font_size * 0.06)),
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
        """Create an image wrapper."""

        return KitImage(
            image, width=width, height=height, fit=fit, opacity=opacity, radius=radius
        )

    def page_title(self, text: str, *, font_size: int = 96) -> Component:
        """Create an English outlined wordmark like the site's subpage assets."""

        return MewtypeTitle(
            self.display_title(text),
            font=LATIN_TITLE_FONT,
            font_size=font_size,
            gradient_top=rgba(214, 128, 241, 255),
            gradient_bottom=rgba(61, 189, 245, 255),
            outline_color=rgba(255, 255, 255, 255),
            shadow_color=rgba(70, 188, 248, 255),
            punch_outline_color=rgba(174, 236, 246, 255),
            ornament_color=rgba(201, 130, 232, 255),
            ornament_square_color=self.accent,
            outline_width=8,
            face_weight=1,
            horizontal_scale=1.16,
        )

    def display_title(self, text: str) -> str:
        """Return the concise English label used by this theme's title system."""

        label = " ".join(text.strip().split())
        translated = _ENGLISH_PAGE_TITLES.get(label)
        if translated is not None:
            return translated
        if "卡池" in label or "招募" in label:
            return "GACHA"
        if "赛季" in label:
            return "SEASON"
        if label.isascii():
            return label.upper()
        return "CONTENTS"

    def article_header(
        self,
        text: str,
        *,
        width: SizeValue | int,
        height: int = 67,
        font_size: int = 28,
        detail: str | None = None,
    ) -> Component:
        """Create the cyan ``c-article-head`` bar used below site wordmarks."""

        children: list[Component] = [
            Frame(
                self.text(
                    text,
                    font_size=font_size,
                    color=rgba(255, 255, 255, 255),
                    wrap=False,
                    max_lines=1,
                    font="heading",
                ),
                width=Fill(),
                align_x="start",
                align_y="center",
            )
        ]
        if detail:
            children.append(
                self.text(
                    detail,
                    font_size=max(20, font_size - 5),
                    color=rgba(255, 255, 255, 255),
                    align="right",
                    wrap=False,
                    max_lines=1,
                    font="heading",
                )
            )
        vertical_padding = min(
            10,
            max(4, (height - round(font_size * 1.35)) // 2),
        )
        return MewtypeArticleHeader(
            Frame(
                HStack(children, gap=16, align="center"),
                align_x="start",
                align_y="center",
            ),
            width=_fixed(width),
            height=Fixed(height),
            padding=Insets.only(
                left=22,
                top=vertical_padding,
                right=22,
                bottom=vertical_padding,
            ),
            fill=self.primary,
            radius=6,
        )

    def compact_header(
        self,
        title: str,
        subtitle: str | None,
        *,
        width: SizeValue | int,
    ) -> Component:
        """Create a secondary-only header for dense, in-progress surfaces."""

        return self.article_header(title, width=width, detail=subtitle)

    def panel_heading(
        self,
        text: str,
        *,
        width: SizeValue | int,
        font_size: int = 26,
    ) -> Component:
        """Create ON AIR's unboxed heading for content inside a panel."""

        return MewtypeStreamHeading(
            self.text(
                text,
                font_size=font_size,
                color=self.text_color,
                wrap=False,
                max_lines=1,
                line_height=round(font_size * 1.6),
                font="heading",
            ),
            width=_fixed(width),
            height=Fixed(round(font_size * 1.6)),
            marker_size=round(font_size * 16 / 22),
            content_left=round(font_size * 30 / 22),
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
        frame_color: ColorLike | None = None,
    ) -> Component:
        """Create a white card with the subpages' cyan pixel-offset frame.

        An explicit ``radius`` switches the surface to a rounded treatment for
        small badges and meters. Ordinary panels keep their clipped, stepped
        corners.
        """

        return MewtypePanel(
            child,
            fill=fill or self.panel_fill,
            radius=radius,
            padding=padding,
            width=width,
            height=height,
            frame_color=frame_color or self.primary,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a cyan rule matching the section-header bars."""

        return KitSeparator(orientation, length, thickness, color or self.primary)

    # ------------------------------------------------------------------
    # Tier A surfaces.
    # ------------------------------------------------------------------

    def game_identity(
        self,
        identity: PlayerIdentity,
        *,
        width: SizeValue | int,
        detail: str | None = None,
    ) -> Component:
        """Create a compact punched-card identity strip for game boards."""

        strip_width = _pixels(width, fallback=720)
        gap = 14
        avatar_cell = round(54 * 512 / 416)
        minimum_name_width = 96
        budget = strip_width - 16 - 20 - avatar_cell - gap

        level_chip: Component | None = None
        level_width = 0
        if identity.level is not None:
            level_label = f"Lv.{identity.level}"
            level_width = _text_px(level_label, 22) + 28
            level_chip = self._label_chip(level_label, width=level_width)

        detail_component: Component | None = None
        detail_width = 0
        if detail:
            detail_width = _text_px(detail, 22)
            detail_component = self.text(
                detail,
                font_size=22,
                align="right",
                wrap=False,
                max_lines=1,
            )

        def _fits() -> bool:
            reserved = 0
            if level_chip is not None:
                reserved += level_width + gap
            if detail_component is not None:
                reserved += detail_width + gap
            return budget - reserved >= minimum_name_width

        if not _fits() and level_chip is not None:
            level_chip = None
        if not _fits() and detail_component is not None:
            detail_component = None

        cells: list[Component] = [
            self._avatar(
                identity.avatar,
                identity.nickname,
                54,
                frame=identity.avatar_frame,
            ),
            Frame(
                self.text(
                    identity.nickname,
                    font_size=27,
                    wrap=False,
                    max_lines=1,
                    overflow="shrink",
                ),
                width=Fill(),
                align_x="start",
                align_y="center",
            ),
        ]
        if level_chip is not None:
            cells.append(level_chip)
        if detail_component is not None:
            cells.append(detail_component)

        return MewtypePanel(
            HStack(cells, gap=gap, align="center"),
            width=_fixed(width),
            height=Fixed(82),
            padding=Insets.only(left=14, top=10, right=22, bottom=10),
            frame_color=self.primary,
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
        """Create the Mewtype profile block used by inventory and rankings."""

        title_images = [
            image for image in (title1_image, title2_image) if image is not None
        ]
        title_slot: Component | None = None
        if title_images:
            title_slot = Frame(
                HStack(
                    [self.image(image, height=Fixed(36)) for image in title_images],
                    gap=10,
                    align="center",
                ),
                height=Fixed(40),
                align_x="start",
                align_y="center",
            )

        name_block: list[Component] = [
            HStack(
                [
                    Frame(
                        self.text(
                            nickname,
                            font_size=34,
                            wrap=False,
                            max_lines=1,
                            overflow="shrink",
                        ),
                        width=Fill(),
                        align_x="start",
                        align_y="center",
                    ),
                    self._label_chip(f"Lv.{level}"),
                ],
                gap=12,
                align="center",
            )
        ]
        if title_slot is not None:
            name_block.append(title_slot)

        identity_row = HStack(
            [
                self._avatar(avatar_image, nickname, 112, frame=frame_image),
                Frame(
                    VStack(name_block, gap=10, align="stretch"),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
            ],
            gap=24,
            align="center",
        )

        profile_text = description.strip()
        profile = self.text(
            profile_text or "这个人还没有写简介。",
            font_size=22,
            color=self.text_color,
            max_lines=3,
            overflow="ellipsis",
            line_height=30,
        )
        stats = HStack(
            [
                self._stat_block("SEASON PT", f"{current_pt:,}"),
                self.separator(
                    orientation="vertical",
                    length=Fixed(54),
                    thickness=3,
                    color=self.primary,
                ),
                self._stat_block("LEVEL", f"Lv.{level}"),
                Spacer(width=Fill()),
            ],
            gap=22,
            align="center",
        )

        left: Component = VStack(
            [
                identity_row,
                self.separator(length=Fill(), color=self.primary),
                Frame(profile, height=Fixed(90), align_x="stretch", align_y="start"),
                Spacer(height=Fill()),
                stats,
            ],
            gap=16,
            align="stretch",
        )
        content: Component = left
        if standing_art is not None:
            content = HStack(
                [
                    Frame(left, width=Fill(), align_x="stretch", align_y="stretch"),
                    Frame(
                        self.image(standing_art, height=Fill(), fit="contain"),
                        width=Fixed(240),
                        align_x="end",
                        align_y="end",
                    ),
                ],
                gap=18,
                align="stretch",
            )

        return MewtypePanel(
            content,
            width=_fixed(width),
            height=_fixed(height),
            padding=Insets.only(left=30, top=28, right=26, bottom=26),
            fill=self.panel_fill,
            frame_color=self.primary,
        )

    def pull_reveal(
        self,
        pulls: Sequence[PullRevealItem],
        *,
        width: SizeValue | int,
    ) -> Component:
        """Create uniform cyan/pink ticket tiles for one-to-ten pulls."""

        total_width = _pixels(width, fallback=720)
        count = max(1, len(pulls))
        columns = (
            10
            if len(pulls) > 5 and total_width >= 1200
            else 5
            if len(pulls) > 5
            else count
        )
        gap = 12
        tile_width = (total_width - gap * (columns - 1)) // columns
        art_slot = any(pull.image is not None for pull in pulls)
        tile_height = 204 + (104 if art_slot else 0)
        tiles = [
            self._pull_tile(
                pull,
                tile_width,
                tile_height,
                art_slot=art_slot,
            )
            for pull in pulls
        ]
        return Frame(
            Grid(
                children=tiles,
                columns=columns,
                column_track=Fixed(tile_width),
                row_track=Fixed(tile_height),
                gap=gap,
            ),
            width=Fixed(total_width),
            align_x="center",
            align_y="start",
        )

    def _avatar(
        self,
        source: ImageSource | None,
        nickname: str,
        size: int,
        *,
        frame: ImageSource | None = None,
    ) -> Component:
        if source is None:
            face: Component = Frame(
                self.text(
                    nickname[:1] or "?",
                    font_size=max(24, size // 2),
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
                align_x="center",
                align_y="center",
            )
        else:
            face = self.image(
                source,
                width=Fill(),
                height=Fill(),
                fit="cover",
                radius=max(1, size // 2 - 5),
            )

        disc: Component = MewtypePanel(
            face,
            width=Fixed(size),
            height=Fixed(size),
            padding=5,
            fill=self.paper_fill,
            radius=size // 2,
            frame_color=self.accent,
            frame_offset=4,
        )
        if frame is None:
            return disc
        frame_size = round(size * 512 / 416)
        return Frame(
            Overlay(
                [
                    Frame(disc, align_x="center", align_y="center"),
                    self.image(
                        frame,
                        width=Fixed(frame_size),
                        height=Fixed(frame_size),
                    ),
                ],
                align_x="center",
                align_y="center",
            ),
            width=Fixed(frame_size),
            height=Fixed(frame_size),
            align_x="center",
            align_y="center",
        )

    def _label_chip(self, label: str, *, width: int | None = None) -> Component:
        chip_width = width or _text_px(label, 22) + 28
        return MewtypePanel(
            Frame(
                self.text(
                    label,
                    font_size=22,
                    color=self.text_color,
                    align="center",
                    wrap=False,
                    max_lines=1,
                    font="display" if label.isascii() else "chinese",
                ),
                align_x="center",
                align_y="center",
            ),
            width=Fixed(chip_width),
            height=Fixed(36),
            fill=rgba(255, 255, 255, 255),
            radius=6,
            frame_color=self.accent,
            border_width=2,
        )

    def _stat_block(self, label: str, value: str) -> Component:
        return VStack(
            [
                self.text(
                    label,
                    font_size=18,
                    color=self.accent,
                    wrap=False,
                    max_lines=1,
                    font="display",
                ),
                self.text(
                    value,
                    font_size=32,
                    wrap=False,
                    max_lines=1,
                    font="display" if value.isascii() else "chinese",
                ),
            ],
            gap=4,
            align="start",
        )

    def _pull_tile(
        self,
        pull: PullRevealItem,
        width: int,
        height: int,
        *,
        art_slot: bool,
    ) -> Component:
        top_rarity = pull.rarity >= 6
        if top_rarity:
            rarity: Component = self._label_chip(f"★{pull.rarity}", width=64)
        else:
            rarity = self.text(
                f"★{pull.rarity}",
                font_size=22,
                align="center",
                wrap=False,
                max_lines=1,
            )

        rows: list[Component] = [
            Frame(rarity, height=Fixed(36), align_x="center", align_y="center")
        ]
        if art_slot:
            rows.append(
                Frame(
                    self.image(
                        pull.image,
                        width=Fill(),
                        height=Fixed(96),
                        fit="contain",
                        radius=10,
                    )
                    if pull.image is not None
                    else None,
                    height=Fixed(96),
                    align_x="center",
                    align_y="center",
                )
            )

        rows.append(
            Frame(
                self.text(
                    pull.name,
                    font_size=20,
                    align="center",
                    max_lines=2,
                    overflow="ellipsis",
                ),
                height=Fixed(56),
                align_x="center",
                align_y="center",
            )
        )

        markers = [
            label
            for enabled, label in (
                (pull.is_new, "NEW"),
                (pull.featured, "PICK UP"),
            )
            if enabled
        ]
        marker_text = " · ".join(markers)
        if markers and _text_px(marker_text, 18) > width - 16:
            marker_text = markers[0]
        rows.append(
            Frame(
                self.text(
                    marker_text,
                    font_size=18,
                    color=self.accent,
                    align="center",
                    wrap=False,
                    max_lines=1,
                )
                if markers
                else None,
                height=Fixed(24),
                align_x="center",
                align_y="center",
            )
        )
        rows.append(
            Frame(
                self.text(
                    pull.note,
                    font_size=18,
                    color=self.muted_text_color,
                    align="center",
                    wrap=False,
                    max_lines=1,
                    overflow="ellipsis",
                )
                if pull.note
                else None,
                height=Fixed(24),
                align_x="center",
                align_y="center",
            )
        )

        return MewtypePanel(
            VStack(rows, gap=6, align="stretch"),
            width=Fixed(width),
            height=Fixed(height),
            padding=Insets.only(left=8, top=12, right=8, bottom=10),
            fill=rgba(255, 250, 255, 250) if top_rarity else self.panel_fill,
            frame_color=self.accent if top_rarity else self.primary,
        )


def _pixels(value: SizeValue | int, *, fallback: int) -> int:
    token = as_size_value(value)
    return token.value if isinstance(token, Fixed) else fallback


def _fixed(value: SizeValue | int) -> SizeValue:
    return as_size_value(value)


def _text_px(text: str, font_size: int) -> int:
    return text_width(text, load_font(font_size, CHINESE_BODY_FONT)) + max(
        0, len(text) - 1
    ) * max(1, round(font_size * 0.06))
