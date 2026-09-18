"""Roselia · 蔷薇穹庭 — a restrained violet ceremonial render kit."""

import zlib
from typing import Literal
from typing import Sequence

from plugins.render.kit import BaseKit
from plugins.render.kit import PlayerIdentity
from plugins.render.kit import PullRevealItem
from plugins.render.core import Component
from plugins.render.core import Background
from plugins.render.color import ColorLike
from plugins.render.color import rgba
from plugins.render.color import normalize_color
from plugins.render.types import ImageFit
from plugins.render.types import Overflow
from plugins.render.types import TextAlign
from plugins.render.types import ImageSource
from plugins.render.layout import Grid
from plugins.render.layout import Frame
from plugins.render.layout import HStack
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

from ..atoms import KitImage
from ..atoms import KitSeparator
from .components import GOLD
from .components import ROSE
from .components import RULE
from .components import GLASS
from .components import PANEL
from .components import PAPER
from .components import PRIMARY
from .components import BODY_FONT
from .components import DISPLAY_FONT
from .components import BACKGROUND_TOP
from .components import BACKGROUND_BOTTOM
from .components import LeafPair
from .components import RoseCrest
from .components import RoseliaText
from .components import PetalScatter
from .components import RoseliaPanel
from .components import RoseliaTitle
from .components import PointedArchImage
from .components import RoseliaSeparator
from .components import RoseliaAvatarDisc
from .components import RoseliaBackground
from .components import frame_overlay

RoseliaFont = Literal["chinese", "display"]


class RoseliaKit(BaseKit):
    """Night-violet space, ivory information surfaces, and botanical rules."""

    background_top = BACKGROUND_TOP
    background_bottom = BACKGROUND_BOTTOM
    text_color = rgba(33, 24, 47, 255)
    muted_text_color = rgba(114, 101, 127, 255)
    panel_fill = PANEL
    paper_fill = PAPER
    primary = PRIMARY
    rose = ROSE
    accent = GOLD
    glass = GLASS
    rule = RULE

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        bottom: ColorLike | None = None,
        petal_density: float = 0.000025,
        shard_density: float = 0.000018,
        random_seed: int = 617,
    ) -> Background:
        """Create a deterministic violet gradient with glass and petal marks."""

        top_color = normalize_color(self.background_top if fill is None else fill)
        bottom_color = normalize_color(
            self.background_bottom if bottom is None else bottom
        )
        assert top_color is not None and bottom_color is not None
        return RoseliaBackground(
            top=top_color,
            bottom=bottom_color,
            petal_density=petal_density,
            shard_density=shard_density,
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
        font: RoseliaFont = "chinese",
    ) -> Component:
        """Create Source Han Serif body text or Cormorant display text."""

        resolved_color = self.text_color if color is None else color
        normalized = normalize_color(resolved_color)
        muted = normalize_color(self.muted_text_color)
        body = normalize_color(self.text_color)
        adaptive = normalized in (body, muted)
        light_color = (
            rgba(184, 171, 197, 255)
            if normalized == muted
            else rgba(238, 230, 242, 255)
        )
        return RoseliaText(
            text,
            BODY_FONT if font == "chinese" else DISPLAY_FONT,
            font_size=font_size,
            color=resolved_color,
            align=align,
            wrap=wrap,
            max_lines=max_lines,
            overflow=overflow,
            line_height=line_height,
            letter_spacing=3 if font == "display" else 0,
            center_glyphs_in_line=True,
            light_color=light_color,
            adaptive=adaptive,
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
        """Wrap a business image without recolouring it."""

        return KitImage(
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
        outer_color: ColorLike | None = None,
        inner_color: ColorLike | None = None,
        outer_width: int = 2,
        inner_width: int = 1,
        ornate: bool = True,
    ) -> Component:
        """Create the light double-rule information surface."""

        return RoseliaPanel(
            child,
            fill=self.panel_fill if fill is None else fill,
            radius=20 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            outer_color=self.primary if outer_color is None else outer_color,
            inner_color=self.rule if inner_color is None else inner_color,
            outer_width=outer_width,
            inner_width=inner_width,
            ornate=ornate,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create the rose-diamond horizontal rule or a plain vertical rule."""

        resolved = self.rule if color is None else color
        if orientation == "vertical":
            return KitSeparator(orientation, length, thickness, resolved)
        return RoseliaSeparator(length, thickness, resolved)

    def page_title(self, text: str, *, font_size: int = 40) -> Component:
        """Create the ceremonial page-title lockup."""

        return RoseliaTitle(text, font_size)

    def game_title(
        self,
        title: str,
        subtitle: str,
        *,
        width: int,
        height: int,
    ) -> Component:
        """Create the themed two-line game heading used above game surfaces."""

        return RoseliaTitle(title, font_size=40, subtitle=subtitle)

    # ------------------------------------------------------------------
    # Tier A surfaces
    # ------------------------------------------------------------------

    def game_identity(
        self,
        identity: PlayerIdentity,
        *,
        width: SizeValue | int,
        detail: str | None = None,
    ) -> Component:
        """Compact dark programme plaque with name-first width degradation."""

        total = _pixels(width, fallback=720)
        avatar_size = 54
        avatar_cell = round(avatar_size * 512 / 416)
        gap = 12
        base_padding = 28
        min_name = 128 if total >= 300 else 96
        remaining = total - base_padding - avatar_cell - gap - min_name

        chip: Component | None = None
        chip_width = 0
        if identity.level is not None:
            label = f"Lv.{identity.level}"
            chip_width = max(76, _text_px(label, BODY_FONT, 22) + 28)
            chip = self._level_chip(label, chip_width)

        detail_component: Component | None = None
        detail_width = 0
        if detail:
            font: RoseliaFont = "display" if detail.isascii() else "chinese"
            path = DISPLAY_FONT if font == "display" else BODY_FONT
            detail_width = min(230, max(72, _text_px(detail, path, 22)))
            detail_component = Frame(
                self.text(
                    detail,
                    font_size=22,
                    color=rgba(238, 230, 242, 255),
                    align="right",
                    wrap=False,
                    max_lines=1,
                    overflow="shrink",
                    font=font,
                ),
                width=Fixed(detail_width),
                align_x="end",
                align_y="center",
            )

        reserved = (chip_width + gap if chip is not None else 0) + (
            detail_width + gap if detail_component is not None else 0
        )
        # The level is ceremonial metadata. It yields before the changing game
        # detail, then the detail yields before the player's name.
        if reserved > remaining and chip is not None:
            reserved -= chip_width + gap
            chip = None
        if reserved > remaining and detail_component is not None:
            detail_component = None

        cells: list[Component] = [
            self._framed_avatar(identity, size=avatar_size),
            Frame(
                self.text(
                    identity.nickname,
                    font_size=26,
                    color=rgba(238, 230, 242, 255),
                    wrap=False,
                    max_lines=1,
                    overflow="shrink",
                ),
                width=Fill(),
                align_x="start",
                align_y="center",
            ),
        ]
        if chip is not None:
            cells.append(chip)
        if detail_component is not None:
            cells.append(detail_component)

        return RoseliaPanel(
            HStack(cells, gap=gap, align="center"),
            width=as_size_value(width),
            height=Fixed(80),
            padding=Insets.only(left=14, top=7, right=14, bottom=7),
            fill=rgba(31, 23, 48, 255),
            radius=18,
            outer_color=self.primary,
            inner_color=self.glass,
            outer_width=2,
            inner_width=1,
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
        """Modern album-booklet profile with a stable title-asset slot."""

        total_width = _pixels(width, fallback=784)
        show_art = standing_art is not None and total_width >= 640
        show_avatar = total_width >= 360
        avatar_size = 86 if total_width >= 520 else 68
        identity = PlayerIdentity(nickname=nickname, level=level, avatar=avatar_image)

        heading_cells: list[Component] = []
        if show_avatar:
            heading_cells.append(
                self._framed_avatar(identity, size=avatar_size, frame=frame_image)
            )
        heading_cells.append(
            Frame(
                VStack(
                    [
                        self.text(
                            nickname,
                            font_size=32,
                            wrap=False,
                            max_lines=1,
                            overflow="shrink",
                        ),
                        self.text(
                            f"Lv.{level} · {current_pt:,} Pt",
                            font_size=24,
                            color=self.muted_text_color,
                            wrap=False,
                            max_lines=1,
                            overflow="shrink",
                            font="display",
                        ),
                    ],
                    gap=4,
                    align="start",
                ),
                width=Fill(),
                align_x="start",
                align_y="center",
            )
        )
        heading_cells.append(
            Frame(RoseCrest(36, self.rose), width=Fixed(42), height=Fixed(42))
        )
        heading = HStack(heading_cells, gap=16, align="center")

        title_images = [
            image for image in (title1_image, title2_image) if image is not None
        ]
        if title_images:
            title_slot: Component = Frame(
                HStack(
                    [self.image(image, height=Fixed(34)) for image in title_images],
                    gap=12,
                    align="center",
                ),
                height=Fixed(40),
                align_x="start",
                align_y="center",
            )
        else:
            title_slot = Frame(
                HStack(
                    [
                        self.separator(length=Fixed(58), thickness=1),
                        RoseCrest(24, rgba(116, 80, 168, 120)),
                        self.separator(length=Fixed(58), thickness=1),
                    ],
                    gap=8,
                    align="center",
                ),
                height=Fixed(40),
                align_x="start",
                align_y="center",
            )

        copy = Frame(
            VStack(
                [
                    heading,
                    title_slot,
                    self.separator(length=Fill(), thickness=1),
                    self.text(
                        description or "这个人还没有写简介。",
                        font_size=22,
                        color=(
                            self.text_color
                            if description
                            else self.muted_text_color
                        ),
                        max_lines=6,
                        overflow="ellipsis",
                        line_height=29,
                    ),
                ],
                gap=12,
                align="stretch",
            ),
            width=Fill(),
            align_x="stretch",
            align_y="start",
        )
        content: Component = copy
        if show_art:
            content = HStack(
                [
                    copy,
                    Frame(
                        self.image(standing_art, height=Fill(), fit="contain"),
                        width=Fixed(232),
                        align_x="end",
                        align_y="end",
                    ),
                ],
                gap=18,
                align="stretch",
            )

        return RoseliaPanel(
            content,
            width=as_size_value(width),
            height=as_size_value(height),
            padding=Insets.only(left=28, top=24, right=24, bottom=24),
            fill=self.panel_fill,
            radius=20,
            outer_color=self.primary,
            inner_color=self.rule,
            outer_width=2,
            inner_width=1,
            ornate=True,
        )

    def pull_reveal(
        self,
        pulls: Sequence[PullRevealItem],
        *,
        width: SizeValue | int,
    ) -> Component:
        """Render one to ten results as equal-height ceremonial tickets."""

        total_width = _pixels(width)
        if not pulls:
            return Frame(None, width=Fixed(total_width), height=Fixed(0))
        count = len(pulls)
        if total_width <= 240:
            columns = 1
        elif count == 1:
            columns = 1
        elif count <= 5:
            columns = min(count, max(1, total_width // 150))
        elif total_width >= 1400:
            columns = 10
        elif total_width >= 700:
            columns = 5
        else:
            columns = max(1, min(5, total_width // 150))

        gap = 12
        tile_width = max(1, (total_width - gap * (columns - 1)) // columns)
        hero = count == 1 and tile_width >= 480
        # The regular ticket keeps the note rail even when it is empty.  Its
        # fixed 360px track prevents that final rail from spilling into the
        # next row at five-column chat widths.
        tile_height = 310 if hero else 360
        grid = Grid(
            columns=columns,
            column_track=Fixed(tile_width),
            row_track=Fixed(tile_height),
            gap=gap,
            children=[
                self._pull_tile(
                    pull,
                    tile_width,
                    tile_height=tile_height,
                    hero=hero,
                )
                for pull in pulls
            ],
        )
        return Frame(
            grid,
            width=Fixed(total_width),
            align_x="center",
            align_y="start",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _framed_avatar(
        self,
        identity: PlayerIdentity,
        *,
        size: int,
        frame: ImageSource | None = None,
    ) -> Component:
        decoration = (
            frame
            if frame is not None
            else identity.avatar_frame
            if identity.avatar_frame is not None
            else frame_overlay(size)
        )
        frame_size = round(size * 512 / 416)
        return Frame(
            Overlay(
                [
                    Frame(
                        RoseliaAvatarDisc(
                            source=identity.avatar,
                            initial=identity.nickname[:1] or "?",
                            size=size,
                        ),
                        align_x="center",
                        align_y="center",
                    ),
                    self.image(
                        decoration,
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

    def _level_chip(self, label: str, width: int) -> Component:
        return RoseliaPanel(
            Frame(
                self.text(
                    label,
                    font_size=22,
                    color=rgba(238, 230, 242, 255),
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
                align_x="center",
                align_y="center",
            ),
            width=Fixed(width),
            height=Fixed(36),
            fill=rgba(26, 18, 42, 255),
            radius=18,
            outer_color=self.accent,
            inner_color=self.accent,
            outer_width=1,
            inner_width=0,
            ornate=False,
        )

    def _pull_tile(
        self,
        pull: PullRevealItem,
        width: int,
        *,
        tile_height: int,
        hero: bool = False,
    ) -> Component:
        rarity = max(1, min(6, pull.rarity))
        tags = [label for active, label in ((pull.is_new, "NEW"), (pull.featured, "PICK UP")) if active]
        tag_text = " · ".join(tags)
        if width < 170:
            if pull.is_new:
                tag_text = "NEW"
            elif pull.featured:
                tag_text = "PICK"

        rarity_label = f"★{rarity}"
        rarity_component: Component
        if rarity >= 6:
            rarity_component = RoseliaPanel(
                Frame(
                    self.text(
                        rarity_label,
                        font_size=22,
                        color=rgba(238, 230, 242, 255),
                        align="center",
                        wrap=False,
                        max_lines=1,
                    ),
                    align_x="center",
                    align_y="center",
                ),
                width=Fixed(62),
                height=Fixed(30),
                fill=rgba(39, 24, 55, 255),
                radius=15,
                outer_color=self.accent,
                inner_color=self.accent,
                outer_width=1,
                inner_width=0,
                ornate=False,
            )
        else:
            rarity_component = self.text(
                rarity_label,
                font_size=22,
                color=self.rose if rarity >= 5 else self.primary,
                wrap=False,
                max_lines=1,
            )

        header_cells: list[Component] = [rarity_component]
        if rarity == 4:
            header_cells.append(
                self.text(
                    "◆",
                    font_size=22,
                    color=self.accent,
                    wrap=False,
                    max_lines=1,
                )
            )
        elif rarity == 5:
            header_cells.append(LeafPair())
        rarity_width = 62 if rarity >= 6 else 42
        ornament_width = 30 if rarity == 5 else 20 if rarity == 4 else 0
        header_count = 4 if ornament_width else 3
        header_width = width - 20 - (252 + 18 if hero else 0)
        tag_width = max(
            0,
            header_width
            - rarity_width
            - ornament_width
            - (header_count - 1) * 5,
        )
        header_cells.extend(
            [
                Frame(None, width=Fill()),
                Frame(
                    self.text(
                        tag_text,
                        font_size=22,
                        color=self.rose,
                        align="right",
                        wrap=False,
                        max_lines=1,
                        overflow="shrink",
                        font="display",
                    ),
                    width=Fixed(tag_width),
                    align_x="end",
                    align_y="center",
                ),
            ]
        )
        header = Frame(
            HStack(header_cells, gap=5, align="center"),
            height=Fixed(32),
            align_x="stretch",
            align_y="center",
        )

        stars = "★" * rarity if rarity >= 5 else "☆" * rarity
        star_row = Frame(
            self.text(
                stars,
                font_size=22,
                color=self.accent if rarity >= 5 else self.primary,
                wrap=False,
                max_lines=1,
                overflow="shrink",
            ),
            height=Fixed(28),
            align_x="start",
            align_y="center",
        )
        note = Frame(
            self.text(
                pull.note,
                font_size=22,
                color=self.muted_text_color,
                wrap=False,
                max_lines=1,
                overflow="shrink",
            ),
            height=Fixed(28),
            align_x="start",
            align_y="center",
        )
        name = Frame(
            self.text(
                pull.name,
                font_size=28 if hero else 22,
                max_lines=2,
                overflow="ellipsis",
                line_height=38 if hero else 27,
            ),
            width=Fill(),
            height=Fixed(78 if hero else 56),
            align_x="start",
            align_y="center",
        )

        if hero:
            body: Component = HStack(
                [
                    Frame(
                        PointedArchImage(pull.image, 258, fit="contain"),
                        width=Fixed(252),
                        height=Fixed(258),
                        align_x="stretch",
                        align_y="stretch",
                    ),
                    Frame(
                        VStack(
                            [
                                header,
                                name,
                                self.separator(length=Fill(), thickness=1),
                                star_row,
                                note,
                            ],
                            gap=10,
                            align="stretch",
                        ),
                        width=Fill(),
                        align_x="stretch",
                        align_y="center",
                    ),
                ],
                gap=18,
                align="stretch",
            )
        else:
            art_height = 150
            body = VStack(
                [
                    header,
                    Frame(
                        PointedArchImage(pull.image, art_height),
                        width=Fill(),
                        height=Fixed(art_height),
                        align_x="stretch",
                        align_y="stretch",
                    ),
                    self.separator(length=Fill(), thickness=1),
                    name,
                    star_row,
                    note,
                ],
                gap=7,
                align="stretch",
            )

        if rarity >= 6:
            body = Overlay(
                [
                    body,
                    PetalScatter(
                        seed=zlib.crc32(pull.name.encode("utf-8")),
                        density=0.00060,
                        alpha_min=55,
                        alpha_max=105,
                    ),
                    Frame(
                        RoseCrest(34, self.accent),
                        padding=Insets.only(top=3),
                        align_x="center",
                        align_y="start",
                    ),
                ],
                align_x="stretch",
                align_y="stretch",
            )

        outer_width = 3 if rarity >= 6 else 2 if rarity >= 4 else 1
        inner_width = 1 if rarity >= 4 else 0
        outer_color = self.accent if rarity >= 6 else self.primary if rarity >= 4 else self.rule
        return RoseliaPanel(
            body,
            width=Fixed(width),
            height=Fixed(tile_height),
            padding=Insets.only(left=10, top=10, right=10, bottom=10),
            fill=self.paper_fill,
            radius=12,
            outer_color=outer_color,
            inner_color=self.glass,
            outer_width=outer_width,
            inner_width=inner_width,
            ornate=rarity == 5,
            force_inner=rarity >= 4,
        )


def _pixels(value: SizeValue | int, fallback: int | None = None) -> int:
    resolved = as_size_value(value)
    if isinstance(resolved, Fixed):
        return resolved.value
    if fallback is not None:
        return fallback
    raise ValueError("Roselia surface requires a concrete pixel width")


def _text_px(text: str, font_path, font_size: int) -> int:
    return text_width(text, load_font(font_size, font_path))


__all__ = ["RoseliaKit"]
