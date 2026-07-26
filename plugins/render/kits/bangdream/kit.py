from typing import Literal
from typing import Sequence
from pathlib import Path

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

from .components import BanGDreamPill
from .components import BanGDreamText
from .components import BanGDreamImage
from .components import BanGDreamPanel
from .components import BanGDreamSeparator
from .components import BanGDreamTileFrame
from .components import BanGDreamTitlePill
from .components import BanGDreamBannerChip
from .components import BanGDreamStarScatter
from .components import BanGDreamTitledPanel
from .components import BanGDreamRingedAvatar
from .backgrounds import BanGDreamImageBackground
from .backgrounds import BanGDreamPatternBackground

KIT_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = KIT_DIR / "resources"
FONTS_DIR = RESOURCES_DIR / "Fonts"
BG_DIR = RESOURCES_DIR / "BG"
CHINESE_FONT = FONTS_DIR / "old.ttf"
DISPLAY_FONT = FONTS_DIR / "Orbitron Black.ttf"
BanGDreamFont = Literal["chinese", "display"]

#: Height of the reveal-tile art slot (contain-fit, so any aspect letterboxes).
_ART_SLOT_HEIGHT = 96


class BanGDreamKit(BaseKit):
    """BanG Dream!-styled rendering kit.

    The kit implements the neutral ``BaseKit`` atom contract and also exposes
    theme-specific helpers such as badges, board frames, and title pills. Those
    helpers are concrete BanG Dream! conveniences rather than shared base-kit
    promises.
    """

    primary = rgba(234, 78, 116, 255)
    text_color = rgba(80, 80, 80, 255)
    muted_text_color = rgba(130, 130, 145, 255)
    panel_fill = rgba(255, 255, 255, 208)

    def background(self, *, source: ImageSource | None = None, **props) -> Background:
        """Create a BanG Dream! background.

        When ``source`` is omitted, this returns the simple repeating-pattern
        background. When ``source`` is provided, it builds the richer image
        treatment with blur, triangle facets, scattered stars, and repeated
        watermark text. Extra keyword props configure that image treatment.
        """

        if source is None:
            return self.background_simple()
        return BanGDreamImageBackground(
            source,
            fill=props.get("fill", rgba(252, 243, 240, 255)),
            text=props.get("text", "BanG Dream!"),
            blur_radius=props.get("blur_radius", 25),
            triangle_size=props.get("triangle_size", 200),
            brightness_add=props.get("brightness_add", 20),
            brightness_difference=props.get("brightness_difference", 0.04),
            opacity=props.get("opacity", 1.0),
            star_density=props.get("star_density", 0.00001),
            star_angle_range=props.get("star_angle_range", 72),
            star_size_range=props.get("star_size_range", (25, 75)),
            text_opacity=props.get("text_opacity", 0.5),
            random_seed=props.get("random_seed", 0),
        )

    def background_simple(
        self, *, fill: ColorLike = rgba(252, 243, 240, 255)
    ) -> Background:
        """Create the simple tiled BanG Dream! background."""

        return BanGDreamPatternBackground(
            fill=fill, pattern=BG_DIR / "bg_object_big.png"
        )

    def board_frame(
        self,
        child: Component,
        *,
        width: SizeValue | int | None = None,
        height: SizeValue | int | None = None,
        padding: InsetsLike = 0,
        max_size: int | None = None,
        fill: ColorLike | None = None,
        radius: int | None = None,
    ) -> Component:
        """Create a square-ish translucent board container."""

        outer = Frame(
            child,
            width=width or Fill(),
            height=height or Fill(),
            padding=padding,
            align_x="stretch",
            align_y="stretch",
            aspect_ratio=1,
            max_width=max_size,
            max_height=max_size,
        )
        return self.panel(
            outer,
            width=width,
            height=height,
            fill=fill,
            radius=radius,
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
        font: BanGDreamFont = "chinese",
    ) -> Component:
        """Create themed text using the bundled BanG Dream! font."""

        return BanGDreamText(
            text,
            _resolve_font(font),
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
        """Create a themed image component with optional opacity and rounding."""

        return BanGDreamImage(
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
        """Create a translucent rounded panel for grouping content."""

        return BanGDreamPanel(
            child,
            fill=fill or self.panel_fill,
            radius=48 if radius is None else radius,
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
        """Create a rounded horizontal or vertical separator."""

        return BanGDreamSeparator(
            orientation, length, thickness, color or (170, 170, 170, 255)
        )

    def title_pill(
        self,
        title: str,
        subtitle: str,
        *,
        pill_width: int = 500,
        pill_height: int = 57,
        title_fill: ColorLike | None = None,
        subtitle_fill: ColorLike | None = None,
        title_text_color: ColorLike | None = None,
        subtitle_text_color: ColorLike | None = None,
        title_font: BanGDreamFont = "chinese",
        subtitle_font: BanGDreamFont = "chinese",
    ) -> Component:
        """Create the two-layer BanG Dream! title pill header."""

        return BanGDreamTitlePill(
            title,
            subtitle,
            _resolve_font(title_font),
            _resolve_font(subtitle_font),
            pill_width=pill_width,
            pill_height=pill_height,
            title_fill=title_fill or self.primary,
            subtitle_fill=subtitle_fill or (255, 255, 255, 255),
            title_text_color=title_text_color or (255, 255, 255, 255),
            subtitle_text_color=subtitle_text_color or (80, 80, 80, 255),
        )

    def titled_panel(
        self,
        title: str,
        child: Component | None = None,
        *,
        title_width: SizeValue | int,
        title_height: SizeValue | int,
        main_width: SizeValue | int,
        main_height: SizeValue | int,
        title_font_size: int = 40,
        title_font: BanGDreamFont = "chinese",
        stroke_width: int = 6,
        title_radius: int | None = None,
        main_radius: int | None = None,
        title_fill: ColorLike | None = None,
        main_fill: ColorLike | None = None,
    ) -> Component:
        """Create a tabbed panel with a BanG Dream!-style title."""

        return BanGDreamTitledPanel(
            title,
            child,
            _resolve_font(title_font),
            title_width=title_width,
            title_height=title_height,
            main_width=main_width,
            main_height=main_height,
            title_font_size=title_font_size,
            stroke_width=stroke_width,
            title_radius=title_radius,
            main_radius=main_radius,
            title_fill=title_fill or self.primary,
            main_fill=main_fill or (255, 255, 255, 255),
        )

    def pill(
        self,
        text: str,
        *,
        width: SizeValue | int,
        height: SizeValue | int,
        font_size: int = 30,
        fill: ColorLike | None = None,
        text_color: ColorLike | None = None,
        align: TextAlign = "center",
        font: BanGDreamFont = "chinese",
    ) -> Component:
        """Create a generic pill-shaped label."""

        return BanGDreamPill(
            text,
            _resolve_font(font),
            width=width,
            height=height,
            font_size=font_size,
            fill=fill or (230, 230, 230, 255),
            text_color=text_color or (255, 255, 255, 255),
            align=align,
        )

    # ------------------------------------------------------------------
    # Tier A surfaces — bespoke BanG Dream! treatments.
    #
    # Callers reach these through the dispatchers in ``utils.cards``; the
    # dispatcher passes data through untouched, so every ``None`` case
    # (avatar, frame, titles, detail) is handled here.
    # ------------------------------------------------------------------

    def game_identity(
        self,
        identity: PlayerIdentity,
        *,
        width: SizeValue | int,
        detail: str | None = None,
    ) -> Component:
        """Create the BanG Dream! identity strip for a game board.

        A 76px capsule — the title-pill silhouette at strip scale — carrying a
        primary-ringed avatar (initial fallback when no avatar exists), the
        nickname in the chinese font, the level in a dark chip, and optional
        game detail right-aligned in the display font when it is pure ASCII.
        Chip and detail are dropped, in that order, when the strip is too
        narrow for them plus a readable nickname.
        """

        strip_width = _as_px(width, fallback=720)
        strip_height = 76
        gap = 14
        avatar_size = 52
        min_name_width = 96
        budget = strip_width - 14 - 26 - avatar_size - gap

        chip: Component | None = None
        chip_width = 0
        if identity.level is not None:
            chip_text = f"Lv.{identity.level}"
            chip_width = _text_px(chip_text, CHINESE_FONT, 22) + 30
            chip = self.pill(
                chip_text,
                width=Fixed(chip_width),
                height=Fixed(32),
                font_size=22,
                fill=self.text_color,
            )

        detail_component: Component | None = None
        detail_width = 0
        if detail:
            detail_font: BanGDreamFont = "display" if detail.isascii() else "chinese"
            detail_width = _text_px(detail, _resolve_font(detail_font), 24)
            detail_component = self.text(
                detail,
                font_size=24,
                align="right",
                wrap=False,
                max_lines=1,
                font=detail_font,
            )

        def _fits() -> bool:
            reserved = 0
            if chip is not None:
                reserved += chip_width + gap
            if detail_component is not None:
                reserved += detail_width + gap
            return budget - reserved >= min_name_width

        if not _fits() and chip is not None:
            chip = None
        if not _fits() and detail_component is not None:
            detail_component = None

        cells: list[Component] = [
            BanGDreamRingedAvatar(
                source=identity.avatar,
                initial=identity.nickname[:1] or "?",
                size=avatar_size,
                ring_color=self.primary,
                initial_color=self.text_color,
                initial_font=CHINESE_FONT,
            ),
            Frame(
                self.text(identity.nickname, font_size=26, wrap=False, max_lines=1),
                width=Fill(),
                align_x="start",
                align_y="center",
            ),
        ]
        if chip is not None:
            cells.append(chip)
        if detail_component is not None:
            cells.append(detail_component)

        return self.panel(
            HStack(cells, gap=gap, align="center"),
            width=Fixed(strip_width),
            height=Fixed(strip_height),
            padding=Insets.only(left=14, top=12, right=26, bottom=12),
            radius=strip_height // 2,
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
    ) -> Component:
        """Create the BanG Dream! player identity card.

        Top block: a 160px cosmetic box holding the primary-ringed avatar
        (frame art overlays it once assets exist), then nickname + level chip,
        a fixed-height title slot (a primary accent bar until title art
        exists, so titles land later without reflow), and the profile line.
        Bottom band: season Pt and level as display-font numerals, with a
        muted watermark. All must-read text is ``text_color`` or white on
        ``text_color``; the primary appears only as ring, accent bar, and
        panel chrome.
        """

        card_width = _as_px(width, fallback=784)
        card_height = _as_px(height, fallback=420)
        cosmetic_box = 160

        avatar_layers: list[Component] = [
            BanGDreamRingedAvatar(
                source=avatar_image,
                initial=nickname[:1] or "?",
                size=128,
                ring_color=self.primary,
                ring_width=4,
                ring_gap=3,
                initial_color=self.text_color,
                initial_font=CHINESE_FONT,
            )
        ]
        if frame_image is not None:
            avatar_layers.append(
                self.image(
                    frame_image, width=Fixed(cosmetic_box), height=Fixed(cosmetic_box)
                )
            )
        avatar_block = Frame(
            Overlay(avatar_layers, align_x="center", align_y="center"),
            width=Fixed(cosmetic_box),
            height=Fixed(cosmetic_box),
        )

        chip_text = f"Lv.{level}"
        chip = self.pill(
            chip_text,
            width=Fixed(_text_px(chip_text, CHINESE_FONT, 22) + 32),
            height=Fixed(36),
            font_size=22,
            fill=self.text_color,
        )
        name_row = HStack(
            [
                Frame(
                    self.text(nickname, font_size=34, wrap=False, max_lines=1),
                    width=Fill(),
                    align_x="start",
                    align_y="center",
                ),
                chip,
            ],
            gap=12,
            align="center",
        )

        titles = [
            image for image in (title1_image, title2_image) if image is not None
        ]
        if titles:
            slot_child: Component = HStack(
                [self.image(image, height=Fixed(40)) for image in titles],
                gap=12,
                align="center",
            )
        else:
            slot_child = self.separator(
                length=Fixed(96), thickness=6, color=self.primary
            )
        title_slot = Frame(
            slot_child, height=Fixed(44), align_x="start", align_y="center"
        )

        profile_text = description.strip()
        profile = self.text(
            profile_text or "这个人还没有写简介。",
            font_size=24,
            color=self.text_color if profile_text else self.muted_text_color,
            max_lines=2,
            overflow="ellipsis",
        )

        top = HStack(
            [
                avatar_block,
                Frame(
                    VStack([name_row, title_slot, profile], gap=10, align="stretch"),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
            ],
            gap=28,
            align="center",
        )

        stats = HStack(
            [
                self._stat_block("赛季 Pt", f"{current_pt:,}"),
                self.separator(orientation="vertical", length=Fixed(52), thickness=3),
                self._stat_block("等级", chip_text),
                Spacer(width=Fill()),
                Frame(
                    self.text(
                        "BanG Dream!",
                        font_size=20,
                        color=self.muted_text_color,
                        wrap=False,
                        max_lines=1,
                        font="display",
                    ),
                    align_x="end",
                    align_y="end",
                ),
            ],
            gap=24,
            align="center",
        )

        return self.panel(
            VStack(
                [top, Spacer(height=Fill()), self.separator(length=Fill()), stats],
                gap=18,
                align="stretch",
            ),
            width=Fixed(card_width),
            height=Fixed(card_height),
            padding=Insets.only(left=36, top=32, right=36, bottom=30),
            fill=rgba(255, 255, 255, 222),
        )

    def pull_reveal(
        self,
        pulls: Sequence[PullRevealItem],
        *,
        width: SizeValue | int,
    ) -> Component:
        """Create the BanG Dream! gacha reveal grid.

        Up to five columns of uniform 220px tiles. A rarity-6 tile is an
        event: a soft pink tile fill, a primary border traced around the tile,
        a seeded star scatter from the kit's own sprites, and a two-layer
        banner chip in the title-pill silhouette. Lower rarities carry a plain
        ``★n`` numeral. Rarity is always encoded by shape and weight — chip
        versus numeral, border versus none, filled versus empty star slots —
        never by hue alone.
        """

        grid_width = _as_px(width, fallback=720)
        count = max(1, len(pulls))
        columns = 5 if len(pulls) > 5 else count
        gap = 12
        tile_width = min(240, (grid_width - gap * (columns - 1)) // columns)
        # Batch-driven art slot: when any pull carries art, every tile grows
        # by the slot plus one 6px row gap and reserves the space, keeping the
        # whole grid one uniform tile height. An art-less batch keeps the
        # original 220px tile unchanged.
        art_slot = any(pull.image is not None for pull in pulls)
        tile_height = 220 + (_ART_SLOT_HEIGHT + 6 if art_slot else 0)
        tiles = [
            self._pull_tile(
                pull, tile_width, tile_height, seed=index, art_slot=art_slot
            )
            for index, pull in enumerate(pulls)
        ]
        grid = Grid(
            children=tiles,
            columns=columns,
            column_track=Fixed(tile_width),
            row_track=Fixed(tile_height),
            gap=gap,
        )
        return Frame(grid, width=Fixed(grid_width), align_x="center", align_y="start")

    def _stat_block(self, label: str, value: str) -> Component:
        """Create a muted label over a display-font value for the stat band."""

        return VStack(
            [
                self.text(
                    label,
                    font_size=22,
                    color=self.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
                self.text(value, font_size=42, wrap=False, max_lines=1, font="display"),
            ],
            gap=4,
            align="start",
        )

    def _pull_tile(
        self,
        pull: PullRevealItem,
        tile_width: int,
        tile_height: int,
        *,
        seed: int,
        art_slot: bool = False,
    ) -> Component:
        """Create one reveal tile; rarity-6 tiles get the celebration layers."""

        is_top = pull.rarity >= 6
        tile_radius = 24

        if is_top:
            rarity_marker: Component = BanGDreamBannerChip(
                f"★{pull.rarity}",
                CHINESE_FONT,
                width=82,
                height=38,
                font_size=22,
                band_fill=self.text_color,
                ring_color=self.primary,
            )
        else:
            rarity_marker = self.text(
                f"★{pull.rarity}", font_size=24, align="center", wrap=False, max_lines=1
            )

        filled = max(0, min(pull.rarity, 6))
        star_cells: list[Component] = []
        if filled:
            star_cells.append(
                self.text("★" * filled, font_size=18, color=self.primary, wrap=False)
            )
        if filled < 6:
            star_cells.append(
                self.text(
                    "☆" * (6 - filled),
                    font_size=18,
                    color=self.muted_text_color,
                    wrap=False,
                )
            )

        markers = [text for flag, text in ((pull.is_new, "NEW"), (pull.featured, "PICK UP")) if flag]
        # A ten-pull tile is too narrow for 「NEW · PICK UP」; rather than an
        # ellipsis, keep the first marker — NEW is information the tile shows
        # nowhere else, while featured is already told by the tile frame.
        marker_text = " · ".join(markers)
        if markers and _text_px(marker_text, CHINESE_FONT, 22) > tile_width - 20:
            marker_text = markers[0]
        marker_row: Component
        if markers:
            marker_row = self.text(
                marker_text, font_size=22, align="center", wrap=False, max_lines=1
            )
        else:
            marker_row = Spacer()
        note_row: Component
        if pull.note:
            note_row = self.text(
                pull.note,
                font_size=22,
                color=self.muted_text_color,
                align="center",
                wrap=False,
                max_lines=1,
            )
        else:
            note_row = Spacer()

        content_rows: list[Component] = [
            Frame(rarity_marker, height=Fixed(38), align_x="center", align_y="center"),
            Frame(
                HStack(star_cells, gap=2, align="center"),
                height=Fixed(22),
                align_x="center",
                align_y="center",
            ),
        ]
        if art_slot:
            # Reserved on every tile of an art-carrying batch (empty for
            # art-less pulls) so the fixed tile height keeps the grid uniform.
            content_rows.append(
                Frame(
                    self.image(
                        pull.image,
                        width=Fill(),
                        height=Fixed(_ART_SLOT_HEIGHT),
                        fit="contain",
                    )
                    if pull.image is not None
                    else None,
                    height=Fixed(_ART_SLOT_HEIGHT),
                    align_x="center",
                    align_y="center",
                )
            )
        content_rows.extend(
            [
                Frame(
                    self.text(
                        pull.name,
                        font_size=22,
                        align="center",
                        max_lines=2,
                        overflow="ellipsis",
                        line_height=26,
                    ),
                    height=Fixed(56),
                    align_x="center",
                    align_y="center",
                ),
                Frame(marker_row, height=Fixed(26), align_x="center", align_y="center"),
                Frame(note_row, height=Fixed(26), align_x="center", align_y="center"),
            ]
        )
        content = Frame(
            VStack(content_rows, gap=6, align="stretch"),
            width=Fixed(tile_width),
            height=Fixed(tile_height),
            padding=Insets.only(left=10, top=12, right=10, bottom=10),
            align_x="stretch",
            align_y="start",
        )

        layers: list[Component] = [
            self.panel(
                None,
                width=Fixed(tile_width),
                height=Fixed(tile_height),
                fill=rgba(255, 246, 249, 244) if is_top else rgba(255, 255, 255, 224),
                radius=tile_radius,
            )
        ]
        if is_top:
            layers.append(
                Frame(
                    BanGDreamStarScatter(
                        seed=seed * 2 + 1,
                        count=7,
                        size_range=(14, 30),
                        opacity=0.4,
                        tint=self.primary,
                    ),
                    width=Fixed(tile_width),
                    height=Fixed(tile_height),
                    align_x="stretch",
                    align_y="stretch",
                )
            )
        layers.append(content)
        if is_top:
            layers.append(
                Frame(
                    BanGDreamTileFrame(radius=tile_radius, color=self.primary),
                    width=Fixed(tile_width),
                    height=Fixed(tile_height),
                    align_x="stretch",
                    align_y="stretch",
                )
            )
        return Overlay(layers, align_x="center", align_y="center")


def _as_px(value: SizeValue | int, *, fallback: int) -> int:
    """Resolve a sizing token to concrete pixels for build-time layout math."""

    size_value = as_size_value(value)
    if isinstance(size_value, Fixed):
        return size_value.value
    return fallback


def _text_px(text: str, font_path: Path, font_size: int) -> int:
    """Measure a single-line text width at build time."""

    return text_width(text, load_font(font_size, font_path))


def _resolve_font(font: BanGDreamFont) -> Path:
    if font == "chinese":
        return CHINESE_FONT
    if font == "display":
        return DISPLAY_FONT
    raise ValueError(f"unknown BanG Dream! font: {font!r}")
