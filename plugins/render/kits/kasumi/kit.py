"""Kasumi character theme: starlight lingering into a warm dawn.

Authored against ``docs/design/tier-a-authoring.md``. Palette rationale:

- The base is a pale lilac-to-blush sky. It keeps the glints and nebula drift
  that identify Starbeat without making the shared grey and colourful game
  components look pasted onto a black card.
- ``primary`` is Kasumi's coral red. Used for rings and borders, never as a
  fill under white text.
- The second voice is champagne gold — star light — used for chips and glints.
  Gold chips carry dark violet text.
- Distinct from the ``midnight`` kit on purpose: midnight is cool, sober
  indigo; this sky is bright, warm, nebular, and glinting. キラキラドキドキ.
"""

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

from ..atoms import KitText
from ..atoms import KitImage
from ..atoms import KitSeparator
from ..fonts import CHINESE_FONT
from ..fonts import DISPLAY_FONT
from .components import KasumiPanel
from .components import SparkleScatter
from .components import KasumiAvatarDisc
from .components import KasumiBackground
from .components import frame_overlay
from .components import sparkle

KasumiFont = Literal["chinese", "display"]


class KasumiKit(BaseKit):
    """香澄 · 星之鼓动 — coral starlight in a lilac dawn sky."""

    primary = rgba(239, 91, 108, 255)
    accent = rgba(246, 194, 92, 255)
    text_color = rgba(62, 48, 89, 255)
    muted_text_color = rgba(116, 101, 139, 255)
    panel_fill = rgba(255, 251, 252, 238)
    sky_top = rgba(242, 238, 255, 255)
    sky_bottom = rgba(255, 232, 226, 255)
    theme_signature_enabled = False

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        bottom: ColorLike | None = None,
        glint_density: float = 0.00006,
        random_seed: int = 425,
    ) -> Background:
        """Create the bright Starbeat sky background.

        Args:
            fill: Optional top gradient color override.
            bottom: Optional bottom gradient color override.
            glint_density: Four-point glints per logical pixel of page area.
            random_seed: Seed making the sky reproducible.

        Returns:
            Background renderer.
        """

        return KasumiBackground(
            top=fill or self.sky_top,
            bottom=bottom or self.sky_bottom,
            glint_density=glint_density,
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
        font: KasumiFont = "chinese",
    ) -> Component:
        """Create warm starlight text."""

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
        """Create a translucent warm-white panel with a coral hairline.

        Args:
            child: Optional child component.
            width: Optional width sizing token or pixel value.
            height: Optional height sizing token or pixel value.
            padding: Insets between the panel and child.
            fill: Optional panel fill color override.
            radius: Optional corner radius override.
            glow: Whether to draw the faint coral outer glow.

        Returns:
            Panel component.
        """

        return KasumiPanel(
            child,
            fill=fill or self.panel_fill,
            radius=28 if radius is None else radius,
            padding=padding,
            width=width,
            height=height,
            glow_blur=10 if glow else 0,
        )

    def separator(
        self,
        *,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        length: SizeValue | int | None = None,
        thickness: int = 2,
        color: ColorLike | None = None,
    ) -> Component:
        """Create a soft lilac divider."""

        return KitSeparator(
            orientation, length, thickness, color or rgba(207, 192, 220, 255)
        )

    # ------------------------------------------------------------------
    # Tier A surfaces
    # ------------------------------------------------------------------

    def game_title(
        self,
        title: str,
        subtitle: str,
        *,
        width: int,
        height: int,
    ) -> Component:
        """Large star-medallion heading, open directly onto the sky.

        The generic non-BanG-Dream fallback is a pill with one centred line.
        Starbeat instead treats the heading like a chapter mark: a compact
        circular medallion carries the hero glint, the title is deliberately
        oversized, and a tiny coral star introduces the subtitle. A loose pair
        of glints closes the composition without an enclosing title panel.
        """

        lockup_width = max(width, 720)
        lockup_height = max(height, 104)
        lead_glint = sparkle(36, self.accent)
        badge_glint = sparkle(13, self.primary)
        subtitle_glint = sparkle(11, self.primary)
        closing_gold = sparkle(18, self.accent)
        closing_coral = sparkle(11, self.primary)
        medallion = KasumiPanel(
            Overlay(
                [
                    Frame(
                        self.image(
                            lead_glint,
                            width=Fixed(36),
                            height=Fixed(36),
                        ),
                        align_x="center",
                        align_y="center",
                    ),
                    Frame(
                        self.image(
                            badge_glint,
                            width=Fixed(13),
                            height=Fixed(13),
                        ),
                        padding=Insets.only(left=42, bottom=42),
                        align_x="center",
                        align_y="center",
                    ),
                ],
                align_x="stretch",
                align_y="stretch",
            ),
            width=Fixed(64),
            height=Fixed(64),
            fill=rgba(255, 251, 252, 205),
            radius=32,
            border_color=rgba(239, 91, 108, 105),
            border_width=2,
            glow_blur=10,
        )
        copy = VStack(
            [
                self.text(
                    title,
                    font_size=38,
                    wrap=False,
                    max_lines=1,
                ),
                HStack(
                    [
                        self.image(
                            subtitle_glint,
                            width=Fixed(11),
                            height=Fixed(11),
                        ),
                        Frame(
                            self.text(
                                subtitle,
                                font_size=22,
                                wrap=False,
                                max_lines=1,
                            ),
                            width=Fill(),
                            align_x="start",
                            align_y="center",
                        ),
                    ],
                    gap=9,
                    align="center",
                ),
            ],
            gap=4,
            align="start",
        )
        constellation = Overlay(
            [
                Frame(
                    self.image(
                        closing_gold,
                        width=Fixed(18),
                        height=Fixed(18),
                    ),
                    padding=Insets.only(right=18, bottom=30),
                    align_x="center",
                    align_y="center",
                ),
                Frame(
                    self.image(
                        closing_coral,
                        width=Fixed(11),
                        height=Fixed(11),
                    ),
                    padding=Insets.only(left=25, top=30),
                    align_x="center",
                    align_y="center",
                ),
            ],
            align_x="stretch",
            align_y="stretch",
        )
        return Frame(
            HStack(
                [
                    Frame(
                        medallion,
                        width=Fixed(72),
                        height=Fill(),
                        align_x="start",
                        align_y="center",
                    ),
                    Frame(
                        copy,
                        width=Fill(),
                        height=Fill(),
                        align_x="start",
                        align_y="center",
                    ),
                    Frame(
                        constellation,
                        width=Fixed(52),
                        height=Fill(),
                        align_x="stretch",
                        align_y="stretch",
                    ),
                ],
                gap=12,
                align="center",
            ),
            width=Fixed(lockup_width),
            height=Fixed(lockup_height),
            align_x="stretch",
            align_y="center",
        )

    def game_identity(
        self,
        identity: PlayerIdentity,
        *,
        width: SizeValue | int,
        detail: str | None = None,
    ) -> Component:
        """Capsule strip: framed avatar, starlight name, gold level chip.

        The chip and the detail are dropped, in that order, when the strip is
        too narrow for them plus a readable nickname — the name is the one cell
        that must never collapse to an ellipsis (authoring guide §2.4).
        """

        strip_width = _budget_px(width, fallback=720)
        gap = 14
        avatar_cell = round(52 * 512 / 416)
        min_name_width = 96
        budget = strip_width - 14 - 22 - avatar_cell - gap

        chip: Component | None = None
        chip_width = 0
        if identity.level is not None:
            chip_label = f"Lv.{identity.level}"
            chip_width = _chip_width(chip_label)
            chip = self._gold_chip(chip_label)

        detail_component: Component | None = None
        detail_width = 0
        if detail:
            detail_font: KasumiFont = "display" if detail.isascii() else "chinese"
            detail_width = _text_px(
                detail, DISPLAY_FONT if detail_font == "display" else CHINESE_FONT, 24
            )
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
            self._framed_avatar(identity, size=52),
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

        return KasumiPanel(
            HStack(cells, gap=14, align="center"),
            width=_as_fixed(width),
            height=Fixed(78),
            radius=39,
            padding=Insets.only(left=14, top=10, right=22, bottom=10),
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
        """The showcase: identity on the left, the starry-sky art on the right.

        Equipped title assets occupy a compact fixed-height row; without
        assets the row simply disappears so it never turns into a decorative
        rule below the player's identity.

        An explicitly supplied standing art is shown in the right column.
        The profile surface now owns the theme's default art and places it
        beside this panel, so ``None`` keeps this identity card art-free.
        """

        identity = PlayerIdentity(nickname=nickname, level=level, avatar=avatar_image)

        titles = [
            image for image in (title1_image, title2_image) if image is not None
        ]
        title_slot: Component | None = None
        if titles:
            title_slot = Frame(
                HStack(
                    [self.image(image, height=Fixed(36)) for image in titles],
                    gap=12,
                    align="center",
                ),
                height=Fixed(40),
                align_x="start",
                align_y="center",
            )

        stats = HStack(
            [
                Frame(
                    self._gold_chip(f"Lv.{level}"),
                    width=Fill(),
                    align_x="start",
                    align_y="center",
                ),
                Frame(
                    self.text(
                        f"{current_pt} Pt",
                        font_size=24,
                        wrap=False,
                        max_lines=1,
                        font="display",
                    ),
                    width=Fill(),
                    padding=Insets.only(top=16),
                    align_x="start",
                    align_y="center",
                ),
            ],
            gap=12,
            align="center",
        )

        left_rows: list[Component] = [
            HStack(
                [
                    self._framed_avatar(identity, size=84, frame=frame_image),
                    Frame(
                        VStack(
                            [
                                self.text(
                                    nickname, font_size=32, wrap=False, max_lines=1
                                ),
                                stats,
                            ],
                            gap=8,
                            align="start",
                        ),
                        width=Fill(),
                        align_x="start",
                        align_y="center",
                    ),
                ],
                gap=18,
                align="start",
            ),
            self.separator(length=Fill()),
            self.text(
                description or "抬头看，星星在跳动。",
                font_size=22,
                color=self.text_color if description else self.muted_text_color,
                max_lines=3,
                overflow="ellipsis",
            ),
        ]
        if title_slot is not None:
            left_rows.insert(1, title_slot)

        content: Component = Frame(
            VStack(left_rows, gap=14, align="stretch"),
            width=Fill(),
            align_x="stretch",
            align_y="start",
        )
        if standing_art is not None:
            content = HStack(
                [
                    content,
                    Frame(
                        self.image(standing_art, height=Fill(), fit="contain"),
                        width=Fixed(288),
                        align_x="end",
                        align_y="end",
                    ),
                ],
                gap=16,
                align="stretch",
            )

        return KasumiPanel(
            content,
            width=_as_fixed(width),
            height=_as_fixed(height),
            padding=Insets.only(left=28, top=24, right=20, bottom=20),
        )

    def pull_reveal(
        self,
        pulls: Sequence[PullRevealItem],
        *,
        width: SizeValue | int,
    ) -> Component:
        """Vertical character tickets inspired by modern gacha result screens.

        Results read as a roster rather than a dashboard: character art owns
        most of each tall ticket, rarity and acquisition state sit on the top
        rail, and the name/reward information forms a grounded lower caption.
        """

        total_width = _pixels(width)
        count = max(1, len(pulls))
        columns = (
            10
            if len(pulls) > 5 and total_width >= 1200
            else 5
            if len(pulls) > 5
            else count
        )
        gap = 12
        available = (total_width - gap * (columns - 1)) // columns
        tile_width = min(300, available)
        art_slot = any(pull.image is not None for pull in pulls)
        grid = Grid(
            columns=columns,
            column_track=Fixed(tile_width),
            gap=gap,
            children=[
                self._pull_tile(pull, tile_width, art_slot=art_slot)
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
        overlay = frame if frame is not None else frame_overlay(size)
        frame_size = round(size * 512 / 416)
        return Frame(
            Overlay(
                [
                    Frame(
                        KasumiAvatarDisc(
                            source=identity.avatar,
                            initial=identity.nickname[:1] or "?",
                            size=size,
                        ),
                        align_x="center",
                        align_y="center",
                    ),
                    self.image(overlay, width=Fixed(frame_size), height=Fixed(frame_size)),
                ],
                align_x="center",
                align_y="center",
            ),
            width=Fixed(frame_size),
            height=Fixed(frame_size),
            align_x="center",
            align_y="center",
        )

    def _gold_chip(self, label: str) -> Component:
        # Gold fill with dark violet text.
        return KasumiPanel(
            Frame(
                self.text(
                    label,
                    font_size=22,
                    color=self.text_color,
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
                align_x="center",
                align_y="center",
            ),
            width=Fixed(_chip_width(label)),
            height=Fixed(36),
            fill=self.accent,
            radius=18,
            border_width=0,
            glow_blur=0,
        )

    def _pull_tile(
        self, pull: PullRevealItem, width: int, *, art_slot: bool = False
    ) -> Component:
        is_top = pull.rarity >= 6
        compact = width < 180
        art_height = 160 if compact else 300
        name_height = 54 if compact else 70
        font_size = 18 if compact else 24
        footer_size = 16 if compact else 20

        markers: list[str] = []
        if pull.is_new:
            markers.append("NEW")
        if pull.featured:
            markers.append("PICK UP")
        marker_text = " / ".join(markers)
        if markers and _text_px(marker_text, CHINESE_FONT, footer_size) > width - 58:
            marker_text = markers[0]

        compact_rarity = f"{pull.rarity}★" if compact else ""
        header = HStack(
            [
                self.text(
                    compact_rarity,
                    font_size=footer_size,
                    wrap=False,
                    max_lines=1,
                )
                if compact_rarity
                else Frame(None, width=Fixed(0)),
                Frame(None, width=Fill()),
                self.text(
                    marker_text,
                    font_size=footer_size,
                    color=self.primary,
                    align="right",
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=4,
            align="center",
        )

        visual = Frame(
            self.image(
                pull.image,
                width=Fill(),
                height=Fixed(art_height),
                fit="cover" if compact else "contain",
            )
            if pull.image is not None
            else self.text(
                "★",
                font_size=54 if compact else 88,
                color=rgba(126, 105, 156, 72),
                align="center",
                wrap=False,
                max_lines=1,
            ),
            width=Fill(),
            height=Fixed(art_height),
            align_x="center",
            align_y="end",
        )
        caption = VStack(
            [
                Frame(
                    self.text(
                        pull.name,
                        font_size=font_size,
                        max_lines=2,
                        overflow="ellipsis",
                    ),
                    width=Fill(),
                    height=Fixed(name_height),
                    align_x="start",
                    align_y="center",
                ),
                HStack(
                    [
                        Frame(
                            self.text(
                                "" if compact else "★" * pull.rarity,
                                font_size=footer_size,
                                color=self.accent if is_top else self.primary,
                                wrap=False,
                                max_lines=1,
                            ),
                            width=Fill(),
                            align_x="start",
                            align_y="center",
                        ),
                        self.text(
                            pull.note,
                            font_size=footer_size,
                            color=self.muted_text_color,
                            align="right",
                            wrap=False,
                            max_lines=1,
                        ),
                    ],
                    gap=6,
                    align="center",
                ),
            ],
            gap=4,
            align="stretch",
        )
        body: Component = VStack(
            [
                Frame(header, height=Fixed(28), align_x="stretch", align_y="center"),
                visual,
                self.separator(length=Fill(), thickness=1),
                caption,
            ],
            gap=8,
            align="stretch",
        )
        if is_top:
            seed = zlib.crc32(pull.name.encode("utf-8"))
            body = Overlay(
                [
                    body,
                    SparkleScatter(
                        seed=seed,
                        glint_density=0.00045,
                        opacity=0.30,
                    ),
                ],
                align_x="stretch",
                align_y="stretch",
            )

        tile_height = (
            28 + art_height + 1 + name_height + 28 + 3 * 8 + 22
        )
        rarity_fills = {
            6: rgba(255, 244, 218, 245),
            5: rgba(242, 232, 255, 242),
            4: rgba(229, 239, 255, 242),
            3: rgba(247, 247, 252, 242),
        }
        return KasumiPanel(
            body,
            width=Fixed(width),
            height=Fixed(tile_height),
            radius=12,
            padding=Insets.only(left=10, top=10, right=10, bottom=12),
            fill=rarity_fills.get(pull.rarity, self.panel_fill),
            border_color=self.accent if is_top else rgba(126, 105, 156, 72),
            border_width=3 if is_top else 1,
            glow_blur=14 if is_top else 0,
            glow_color=rgba(246, 194, 92, 72),
        )


def _as_fixed(value: SizeValue | int) -> SizeValue:
    return as_size_value(value)


def _pixels(value: SizeValue | int) -> int:
    resolved = as_size_value(value)
    if isinstance(resolved, Fixed):
        return resolved.value
    if isinstance(resolved, int):
        return resolved
    raise ValueError("pull_reveal requires a concrete pixel width")


def _budget_px(value: SizeValue | int, *, fallback: int) -> int:
    """Resolve a sizing token to pixels for build-time layout budgeting."""

    try:
        return _pixels(value)
    except ValueError:
        return fallback


def _text_px(text: str, font_path, font_size: int) -> int:
    """Measure a single-line text width at build time."""

    return text_width(text, load_font(font_size, font_path))


def _chip_width(label: str) -> int:
    """Gold chip width: the measured label plus pill padding."""

    return max(76, _text_px(label, CHINESE_FONT, 22) + 30)
