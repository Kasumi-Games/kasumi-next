"""Endfield-inspired industrial dossier render kit."""

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
from ..fonts import CHINESE_FONT
from ..fonts import DISPLAY_FONT
from .components import EndfieldPanel
from .components import EndfieldTitle
from .components import EndfieldSeparator
from .components import EndfieldBackground

EndfieldFont = Literal["chinese", "display"]


class EndfieldKit(BaseKit):
    """High-contrast industrial UI based on the live Endfield website.

    The kit uses the site's actual recurring palette and CSS grammar: #191919
    ink, #fffa00 signal yellow, white/faint-gray information surfaces,
    diagonal hatching, one-pixel rules, wide display type, and clipped dossier
    frames.  No website illustration assets are embedded; the identity comes
    from reusable geometry so every bot renderer can carry it consistently.
    """

    primary = rgba(25, 25, 25, 255)
    accent = rgba(255, 250, 0, 255)
    text_color = rgba(25, 25, 25, 255)
    muted_text_color = rgba(102, 102, 102, 255)
    panel_fill = rgba(255, 255, 255, 244)
    paper_fill = rgba(247, 247, 244, 255)
    rule_color = rgba(217, 217, 217, 255)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        grid_spacing: int = 64,
        hatch_spacing: int = 6,
    ) -> Background:
        """Create the site's pale construction-grid field."""

        return EndfieldBackground(
            fill=fill or self.paper_fill,
            ink=self.primary,
            signal=self.accent,
            grid_spacing=grid_spacing,
            hatch_spacing=hatch_spacing,
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
        font: EndfieldFont = "chinese",
    ) -> Component:
        """Create compact dossier copy or wide technical display type."""

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
            image,
            width=width,
            height=height,
            fit=fit,
            opacity=opacity,
            radius=radius,
        )

    def page_title(self, text: str, *, font_size: int = 54) -> Component:
        """Create a bracketed REC dossier heading."""

        return EndfieldTitle(
            text,
            font=CHINESE_FONT,
            display_font=DISPLAY_FONT,
            font_size=font_size,
            color=self.primary,
            signal_color=self.accent,
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
        ink_color: ColorLike | None = None,
        signal_color: ColorLike | None = None,
        border_width: int = 2,
        cut: int = 16,
        rail: bool = True,
    ) -> Component:
        """Create a clipped technical dossier panel.

        Passing an explicit radius intentionally switches small controls to a
        conventional rounded frame; generic surfaces keep the clipped corners.
        """

        return EndfieldPanel(
            child,
            fill=fill or self.panel_fill,
            radius=radius,
            padding=padding,
            width=width,
            height=height,
            ink_color=ink_color or self.primary,
            signal_color=signal_color or self.accent,
            border_width=border_width,
            cut=cut,
            rail=rail,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 3,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a segmented yellow/black system rule.

        An explicit color is treated as semantic caller intent and renders as a
        plain rule, matching the base-kit contract.
        """

        if color is not None:
            return KitSeparator(orientation, length, thickness, color)
        return EndfieldSeparator(
            orientation=orientation,
            length=length,
            thickness=thickness,
            color=self.primary,
            signal_color=self.accent,
        )

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
        """Create a compact operator-record strip for game boards."""

        strip_width = _pixels(width, fallback=720)
        gap = 14
        avatar_cell = round(56 * 512 / 416)
        minimum_name_width = 96
        budget = strip_width - 34 - avatar_cell - gap

        level_chip: Component | None = None
        level_width = 0
        if identity.level is not None:
            level_label = f"LV // {identity.level:02d}"
            level_width = _text_px(level_label, 17, display=True) + 28
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
                56,
                frame=identity.avatar_frame,
            ),
            Frame(
                VStack(
                    [
                        self.text(
                            "OPERATOR // REC",
                            font_size=12,
                            color=self.muted_text_color,
                            wrap=False,
                            max_lines=1,
                            font="display",
                        ),
                        self.text(
                            identity.nickname,
                            font_size=27,
                            wrap=False,
                            max_lines=1,
                            overflow="shrink",
                        ),
                    ],
                    gap=1,
                    align="start",
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

        return EndfieldPanel(
            HStack(cells, gap=gap, align="center"),
            width=_fixed(width),
            height=Fixed(86),
            padding=Insets.only(left=15, top=10, right=20, bottom=10),
            fill=self.panel_fill,
            ink_color=self.primary,
            signal_color=self.accent,
            border_width=2,
            cut=13,
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
        """Create a white operator dossier with metadata table and signal tabs."""

        title_images = [
            image for image in (title1_image, title2_image) if image is not None
        ]
        title_slot: Component | None = None
        if title_images:
            title_slot = Frame(
                HStack(
                    [self.image(image, height=Fixed(34)) for image in title_images],
                    gap=10,
                    align="center",
                ),
                height=Fixed(38),
                align_x="start",
                align_y="center",
            )

        heading_rows: list[Component] = [
            self.text(
                "ENDFIELD INDUSTRIES // PERSONNEL RECORD",
                font_size=14,
                color=self.muted_text_color,
                wrap=False,
                max_lines=1,
                font="display",
            ),
            HStack(
                [
                    Frame(
                        self.text(
                            nickname,
                            font_size=38,
                            wrap=False,
                            max_lines=1,
                            overflow="shrink",
                        ),
                        width=Fill(),
                        align_x="start",
                        align_y="center",
                    ),
                    self._label_chip(f"LV // {level:02d}"),
                ],
                gap=12,
                align="center",
            ),
        ]
        if title_slot is not None:
            heading_rows.append(title_slot)

        identity_row = HStack(
            [
                self._avatar(avatar_image, nickname, 112, frame=frame_image),
                Frame(
                    VStack(heading_rows, gap=7, align="stretch"),
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
            profile_text or "暂无公开档案。",
            font_size=21,
            color=self.text_color if profile_text else self.muted_text_color,
            max_lines=3,
            overflow="ellipsis",
            line_height=29,
        )
        stats = HStack(
            [
                self._stat_block("SEASON PT", f"{current_pt:,}"),
                self.separator(
                    orientation="vertical",
                    length=Fixed(54),
                    thickness=2,
                    color=self.rule_color,
                ),
                self._stat_block("CLEARANCE", f"LV.{level}"),
                Spacer(width=Fill()),
            ],
            gap=22,
            align="center",
        )

        left: Component = VStack(
            [
                identity_row,
                self.separator(length=Fill()),
                Frame(profile, height=Fixed(90), align_x="stretch", align_y="start"),
                Spacer(height=Fill()),
                stats,
            ],
            gap=15,
            align="stretch",
        )
        content: Component = left
        if standing_art is not None:
            content = HStack(
                [
                    Frame(left, width=Fill(), align_x="stretch", align_y="stretch"),
                    Frame(
                        self.image(standing_art, height=Fill(), fit="contain"),
                        width=Fixed(242),
                        align_x="end",
                        align_y="end",
                    ),
                ],
                gap=16,
                align="stretch",
            )

        return EndfieldPanel(
            content,
            width=_fixed(width),
            height=_fixed(height),
            padding=Insets.only(left=30, top=26, right=26, bottom=26),
            fill=self.panel_fill,
            ink_color=self.primary,
            signal_color=self.accent,
            border_width=2,
            cut=22,
        )

    def pull_reveal(
        self,
        pulls: Sequence[PullRevealItem],
        *,
        width: SizeValue | int,
    ) -> Component:
        """Create operator-file reveal tiles with encoded rarity headers."""

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
        tile_height = 218 + (106 if art_slot else 0)
        tiles = [
            self._pull_tile(
                pull,
                tile_width,
                tile_height,
                art_slot=art_slot,
                index=index,
            )
            for index, pull in enumerate(pulls, start=1)
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
                radius=max(1, size // 2 - 6),
            )

        disc: Component = EndfieldPanel(
            face,
            width=Fixed(size),
            height=Fixed(size),
            padding=5,
            fill=self.accent,
            radius=size // 2,
            ink_color=self.primary,
            signal_color=self.accent,
            border_width=2,
            rail=False,
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
        chip_width = width or _text_px(label, 17, display=True) + 28
        return EndfieldPanel(
            Frame(
                self.text(
                    label,
                    font_size=17,
                    color=self.primary,
                    align="center",
                    wrap=False,
                    max_lines=1,
                    font="display",
                ),
                align_x="center",
                align_y="center",
            ),
            width=Fixed(chip_width),
            height=Fixed(34),
            fill=self.accent,
            radius=2,
            ink_color=self.primary,
            signal_color=self.accent,
            border_width=1,
            rail=False,
        )

    def _stat_block(self, label: str, value: str) -> Component:
        return VStack(
            [
                self.text(
                    label,
                    font_size=14,
                    color=self.muted_text_color,
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
            gap=2,
            align="start",
        )

    def _pull_tile(
        self,
        pull: PullRevealItem,
        width: int,
        height: int,
        *,
        art_slot: bool,
        index: int,
    ) -> Component:
        top_rarity = pull.rarity >= 6
        header_fill = self.accent if top_rarity else self.primary
        header_text = self.primary if top_rarity else rgba(255, 255, 255, 255)
        header = Frame(
            HStack(
                [
                    self.text(
                        f"REC-{index:02d}",
                        font_size=13,
                        color=header_text,
                        wrap=False,
                        max_lines=1,
                        font="display",
                    ),
                    Spacer(width=Fill()),
                    self.text(
                        f"★{pull.rarity}",
                        font_size=19,
                        color=header_text,
                        align="right",
                        wrap=False,
                        max_lines=1,
                        font="display",
                    ),
                ],
                gap=8,
                align="center",
            ),
            height=Fixed(38),
            padding=Insets.only(left=10, right=10),
            align_x="stretch",
            align_y="center",
        )
        header_panel = EndfieldPanel(
            header,
            height=Fixed(38),
            fill=header_fill,
            radius=0,
            ink_color=self.primary,
            signal_color=self.accent,
            border_width=0,
            rail=False,
        )

        rows: list[Component] = [header_panel]
        if art_slot:
            rows.append(
                Frame(
                    self.image(
                        pull.image,
                        width=Fill(),
                        height=Fixed(98),
                        fit="contain",
                        radius=0,
                    )
                    if pull.image is not None
                    else None,
                    height=Fixed(98),
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
                height=Fixed(58),
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
        marker_text = " // ".join(markers)
        if markers and _text_px(marker_text, 14, display=True) > width - 16:
            marker_text = markers[0]
        rows.append(
            Frame(
                self.text(
                    marker_text,
                    font_size=14,
                    color=self.primary,
                    align="center",
                    wrap=False,
                    max_lines=1,
                    font="display",
                )
                if markers
                else None,
                width=Fill(),
                height=Fixed(28),
                padding=Insets.only(left=5, right=5),
                align_x="center",
                align_y="center",
            )
        )
        rows.append(
            Frame(
                self.text(
                    pull.note,
                    font_size=17,
                    color=self.muted_text_color,
                    align="center",
                    wrap=False,
                    max_lines=1,
                    overflow="ellipsis",
                )
                if pull.note
                else None,
                height=Fixed(26),
                align_x="center",
                align_y="center",
            )
        )

        return EndfieldPanel(
            VStack(rows, gap=6, align="stretch"),
            width=Fixed(width),
            height=Fixed(height),
            padding=Insets.only(left=8, top=8, right=8, bottom=9),
            fill=self.panel_fill,
            ink_color=self.primary,
            signal_color=self.accent,
            border_width=3 if top_rarity else 2,
            cut=14,
        )


def _pixels(value: SizeValue | int, *, fallback: int) -> int:
    token = as_size_value(value)
    return token.value if isinstance(token, Fixed) else fallback


def _fixed(value: SizeValue | int) -> SizeValue:
    return as_size_value(value)


def _text_px(text: str, font_size: int, *, display: bool = False) -> int:
    font = DISPLAY_FONT if display else CHINESE_FONT
    return text_width(text, load_font(font_size, font))
