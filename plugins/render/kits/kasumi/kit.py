"""Kasumi character theme: the starry night she looks up at.

Authored against ``docs/design/tier-a-authoring.md``. Palette rationale:

- The base is deep violet, not black — pure black flattens the sparkles and
  reads cold. The gradient warms slightly toward the bottom.
- ``primary`` is Kasumi's coral red, lifted for dark backgrounds (her member
  color ``#FF5522`` sinks on violet). Used for rings and borders, never as a
  fill under white text.
- The second voice is champagne gold — star light — used for chips and glints.
  Gold chips carry dark violet text (measured ≈ 13.8:1).
- Distinct from the ``midnight`` kit on purpose: midnight is cool, sober
  indigo; this sky is warm, nebular, and glinting. キラキラドキドキ.
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
from .components import STANDING_ART
from .components import KasumiPanel
from .components import SparkleScatter
from .components import KasumiAvatarDisc
from .components import KasumiBackground
from .components import frame_overlay

KasumiFont = Literal["chinese", "display"]


class KasumiKit(BaseKit):
    """香澄 · 星之鼓动 — warm starlight on deep violet night."""

    primary = rgba(255, 118, 98, 255)
    accent = rgba(255, 209, 128, 255)
    text_color = rgba(244, 238, 232, 255)
    muted_text_color = rgba(170, 160, 194, 255)
    panel_fill = rgba(32, 26, 54, 230)
    night_top = rgba(10, 9, 20, 255)
    night_bottom = rgba(30, 22, 48, 255)

    def background(
        self,
        *,
        fill: ColorLike | None = None,
        bottom: ColorLike | None = None,
        glint_density: float = 0.00006,
        random_seed: int = 425,
    ) -> Background:
        """Create the starry-night background.

        Args:
            fill: Optional top gradient color override.
            bottom: Optional bottom gradient color override.
            glint_density: Four-point glints per logical pixel of page area.
            random_seed: Seed making the sky reproducible.

        Returns:
            Background renderer.
        """

        return KasumiBackground(
            top=fill or self.night_top,
            bottom=bottom or self.night_bottom,
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
        """Create a deep violet panel with a warm hairline.

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
        """Create a dusk-violet divider."""

        return KitSeparator(
            orientation, length, thickness, color or rgba(96, 84, 128, 255)
        )

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
    ) -> Component:
        """The showcase: identity on the left, the starry-sky art on the right.

        The title slot is a fixed-height row so title assets can land later
        without reflow: a coral accent bar holds the space until then
        (authoring guide §3, None handling).
        """

        identity = PlayerIdentity(nickname=nickname, level=level, avatar=avatar_image)

        titles = [
            image for image in (title1_image, title2_image) if image is not None
        ]
        if titles:
            slot_child: Component = HStack(
                [self.image(image, height=Fixed(36)) for image in titles],
                gap=12,
                align="center",
            )
        else:
            slot_child = self.separator(
                length=Fixed(96), thickness=5, color=self.primary
            )
        title_slot = Frame(
            slot_child, height=Fixed(40), align_x="start", align_y="center"
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
                                HStack(
                                    [
                                        self._gold_chip(f"Lv.{level}"),
                                        self.text(
                                            f"{current_pt} Pt",
                                            font_size=24,
                                            wrap=False,
                                            max_lines=1,
                                            font="display",
                                        ),
                                    ],
                                    gap=12,
                                    align="center",
                                ),
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
                align="center",
            ),
            title_slot,
            self.separator(length=Fill()),
            self.text(
                description or "抬头看，星星在跳动。",
                font_size=22,
                color=self.text_color if description else self.muted_text_color,
                max_lines=3,
                overflow="ellipsis",
            ),
        ]

        art_column = Frame(
            self.image(STANDING_ART, height=Fill(), fit="contain"),
            width=Fixed(288),
            align_x="end",
            align_y="end",
        )

        content = HStack(
            [
                Frame(
                    VStack(left_rows, gap=14, align="stretch"),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
                art_column,
            ],
            gap=16,
            align="stretch",
        )

        return KasumiPanel(
            Overlay(
                [
                    content,
                    SparkleScatter(seed=573, glint_density=0.00012),
                ],
                align_x="stretch",
                align_y="stretch",
            ),
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
        """Reveal grid where a ★6 is a small event: coral border, gold sky."""

        total_width = _pixels(width)
        columns = 5 if len(pulls) > 5 else max(1, len(pulls))
        gap = 12
        tile_width = (total_width - gap * (columns - 1)) // columns

        # Batch-driven art slot: when any pull carries art, every tile in the
        # grid reserves the slot so all tiles stay one uniform height. An
        # art-less batch keeps the exact 196px tile from before art existed —
        # the common all-filler ten-pull should not grow 104px of empty sky
        # just because the capability exists.
        art_slot = any(pull.image is not None for pull in pulls)
        return Grid(
            columns=columns,
            gap=gap,
            children=[
                self._pull_tile(pull, tile_width, art_slot=art_slot)
                for pull in pulls
            ],
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
        # Gold fill with dark violet text: measured ≈ 13.8:1, well past AA.
        return KasumiPanel(
            Frame(
                self.text(
                    label,
                    font_size=22,
                    color=self.night_top,
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

    #: Height of the reveal-tile art slot. Contain-fit, so the ★6 standing
    #: art letterboxes into it whatever its aspect ratio.
    _ART_SLOT_HEIGHT = 96

    #: Reveal tile height without an art slot. Every row below is capped by a
    #: fixed-height frame, so the budget is exact: 36 (chip) + 24 (stars) +
    #: 60 (two name lines) + 26 (markers) + 26 (note) + 4 × 8 gaps + 14 + 12
    #: padding = 230, plus 2px slack. The former 196 fit only one-line names;
    #: the production filler names wrap to two lines and pushed the note over
    #: the border.
    _TILE_HEIGHT = 232

    def _pull_tile(
        self, pull: PullRevealItem, width: int, *, art_slot: bool = False
    ) -> Component:
        is_top = pull.rarity >= 6

        star_row = self.text(
            "★" * pull.rarity + "☆" * (6 - pull.rarity),
            font_size=18,
            color=self.accent if is_top else self.muted_text_color,
            align="center",
            wrap=False,
            max_lines=1,
        )
        if is_top:
            head: Component = self._gold_chip(f"★{pull.rarity}")
        else:
            head = self.text(
                f"★{pull.rarity}", font_size=22, align="center", wrap=False
            )

        # Every row is height-capped so the fixed tile height always fits the
        # content — an uncapped two-line name used to push the note outside
        # the panel border.
        rows: list[Component] = [
            Frame(head, height=Fixed(36), align_x="center", align_y="center"),
            Frame(star_row, height=Fixed(24), align_x="center", align_y="center"),
        ]
        if art_slot:
            # The slot is reserved on every tile of an art-carrying batch —
            # empty on art-less pulls — so the fixed tile height below keeps
            # the whole grid uniform.
            rows.append(
                Frame(
                    self.image(
                        pull.image,
                        width=Fill(),
                        height=Fixed(self._ART_SLOT_HEIGHT),
                        fit="contain",
                    )
                    if pull.image is not None
                    else None,
                    height=Fixed(self._ART_SLOT_HEIGHT),
                    align_x="center",
                    align_y="center",
                )
            )
        rows.append(
            Frame(
                self.text(
                    pull.name,
                    font_size=22,
                    align="center",
                    max_lines=2,
                    overflow="ellipsis",
                ),
                width=Fill(),
                height=Fixed(60),
                align_x="center",
                align_y="center",
            ),
        )

        markers = []
        if pull.is_new:
            markers.append("NEW")
        if pull.featured:
            markers.append("PICK UP")
        # A ten-pull tile is too narrow for 「NEW · PICK UP」; rather than an
        # ellipsis, keep the first marker — NEW is information the tile shows
        # nowhere else, while featured is already told by the coral border.
        marker_text = " · ".join(markers)
        if markers and _text_px(marker_text, CHINESE_FONT, 22) > width - 16:
            marker_text = markers[0]
        rows.append(
            Frame(
                self.text(
                    marker_text,
                    font_size=22,
                    color=self.primary,
                    align="center",
                    wrap=False,
                    max_lines=1,
                )
                if markers
                else None,
                height=Fixed(26),
                align_x="center",
                align_y="center",
            )
        )
        rows.append(
            Frame(
                self.text(
                    pull.note,
                    font_size=22,
                    color=self.muted_text_color,
                    align="center",
                    wrap=False,
                    max_lines=1,
                )
                if pull.note
                else None,
                height=Fixed(26),
                align_x="center",
                align_y="center",
            )
        )

        body = VStack(rows, gap=8, align="stretch")
        if is_top:
            # crc32, not hash(): str hashing is salted per process, and the
            # same pull must sparkle the same way on every render.
            seed = zlib.crc32(pull.name.encode("utf-8"))
            body = Overlay(
                [body, SparkleScatter(seed=seed, glint_density=0.0006)],
                align_x="stretch",
                align_y="stretch",
            )

        # An art batch adds the slot plus one 8px row gap to every tile, so
        # mixed batches stay uniform.
        tile_height = self._TILE_HEIGHT + (self._ART_SLOT_HEIGHT + 8 if art_slot else 0)
        return KasumiPanel(
            body,
            width=Fixed(width),
            height=Fixed(tile_height),
            radius=20,
            padding=Insets.only(left=8, top=14, right=8, bottom=12),
            fill=rgba(44, 36, 70, 235) if is_top else self.panel_fill,
            border_color=self.primary if is_top else rgba(255, 205, 160, 56),
            border_width=3 if is_top else 1,
            glow_blur=12 if is_top else 0,
            glow_color=rgba(255, 118, 98, 70),
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
