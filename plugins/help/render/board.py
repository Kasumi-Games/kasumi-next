"""The ``/help`` command board.

The first image a new player sees, and the one surface where every command in
the bot is printed as the string you actually type. It is Tier B: composed only
from ``BaseKit`` atoms through ``utils.cards``, so one implementation renders in
all eight kits.

Three structural decisions are load-bearing:

* **Tiles sit on the page background, not inside a category panel.**
  ``MinimalKit`` paints its panel as a flat ``(245,245,245,255)`` fill with no
  border, so a panel nested in another panel is invisible there — the tile grid
  would silently collapse into loose text in one of the eight kits. On the
  background every tile keeps its own kit-decided corner, which is also the
  whole theme-showcase argument for this card: 23 tiles is 23 corners.
* **The tile ``Grid`` pins ``columns`` and omits ``rows`` on purpose.**
  ``Grid._tracks`` derives ``ceil(len(children) / columns)`` when ``rows`` is
  ``None`` and ``Grid.render`` guards ``child_index < len(self.children)``, so a
  ragged final row is safe. Do not "fix" this by pinning ``rows``: a category
  whose count is not a multiple of three would clip.
* **The command is the only thing in full ink.** Aliases are optional shortcuts
  and stay in ``muted_text_color``; the command a player must be able to read
  and retype never does.
* **Past ``COMPACT_THRESHOLD`` commands, tiles drop the alias sub-line.** This
  is the density mitigation from the board's design spec
  (docs/design/image-responses/15-cluster-utility.md, "Help board height"):
  past roughly 1700px the board stops reading as one page, so once the command
  census grows beyond the threshold every tile keeps only the full-ink command
  line and the row track shrinks from ``TILE_HEIGHT`` to
  ``COMPACT_TILE_HEIGHT``. Aliases remain on the detail cards
  (``/help 功能名``). The switch depends only on the entry list, so renders
  stay deterministic.
"""

from typing import Sequence

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import CONTENT_WIDTH
from utils.cards import SUBTITLE_SIZE
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import empty_state
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit

from ..entries import SUPPORT_GROUP
from ..entries import HelpEntry
from ..entries import HelpCommand
from ..entries import total_commands
from ..entries import commands_by_category

#: Tiles per row. ``3 * 240 + 2 * 32 == 784 == CONTENT_WIDTH``.
COLUMNS = 3
TILE_WIDTH = 240
TILE_HEIGHT = 92
TILE_GAP_X = 32
TILE_GAP_Y = 18
TILE_PADDING = Insets.only(left=20, top=12, right=20, bottom=12)

#: Corner radius for the command tiles alone. At 92px tall, the kit-default
#: radius (48 in bangdream) rounds more than half the tile height and 23 tiles
#: read as a wall of bubbles — measured on a live server, not taste. 20 keeps a
#: visibly themed corner without eating the tile. Full-width panels (the footer
#: below, every ``panel_section``) keep the kit default: at 784px wide the
#: default radius is proportionate there.
TILE_RADIUS = 20

#: Density mitigation switch (module docstring, last bullet): boards with more
#: commands than this drop the tile sub-line. 23 commands — the pre-census
#: board — measured 1500-1550px in the two-line layout and stays two-line; the
#: 31-command census board would measure ~1900px two-line, past the ~1700px
#: budget, so it flips to compact.
COMPACT_THRESHOLD = 27

#: Compact tile: one BODY_SIZE line, vertically centred.
COMPACT_TILE_HEIGHT = 60
COMPACT_TILE_PADDING = Insets.only(left=20, right=20)

HEADER_HEIGHT = 38
SECTION_GAP = 28
HEADING_GAP = 14

#: Width one glyph occupies, as a multiple of the font size. Full-width glyphs
#: are square plus the letter-spacing the kit fonts carry; Latin averages a
#: little over half. Used only to decide how many aliases fit on a tile before
#: the renderer would ellipsize them anyway, so it errs high on purpose — a
#: dropped alias reads better than a trailing "…".
_WIDE_GLYPH = 1.05
_NARROW_GLYPH = 0.55
_ALIAS_SEPARATOR = " · "


def board_page(
    entries: Sequence[HelpEntry], kit: BaseKit | None = None
) -> AutoPage:
    """Build the command board page.

    Args:
        entries: Documented plugins, from ``plugins.help.entries``.
        kit: Active kit; defaults to BanG Dream!.

    Returns:
        Page ready to ``render()`` or ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    groups = commands_by_category(entries)
    compact = _use_compact_tiles(entries)
    if groups:
        body: Component = VStack(
            [
                _category_section(kit, name, commands, compact)
                for name, commands in groups
            ],
            gap=SECTION_GAP,
            align="start",
        )
    else:
        body = empty_state(kit, "还没有可用的功能")

    return card_page(
        kit,
        title="帮助",
        subtitle=f"共 {total_commands(entries)} 条指令",
        body=body,
        footer=_meta_panel(kit),
    )


def render_board(
    entries: Sequence[HelpEntry], kit: BaseKit | None = None
) -> Image.Image:
    """Render the command board.

    Args:
        entries: Documented plugins, from ``plugins.help.entries``.
        kit: Active kit; defaults to BanG Dream!.

    Returns:
        Rendered board.
    """

    return board_page(entries, kit).render()


def _use_compact_tiles(entries: Sequence[HelpEntry]) -> bool:
    """Whether the density mitigation is on for this entry list."""

    return total_commands(entries) > COMPACT_THRESHOLD


def _category_section(
    kit: BaseKit, category: str, commands: Sequence[HelpCommand], compact: bool
) -> Component:
    return VStack(
        [
            _section_head(kit, category, f"{len(commands)} 项"),
            kit.separator(length=Fixed(CONTENT_WIDTH)),
            Grid(
                children=[_tile(kit, command, compact) for command in commands],
                columns=COLUMNS,
                column_track=Fixed(TILE_WIDTH),
                row_track=Fixed(
                    COMPACT_TILE_HEIGHT if compact else TILE_HEIGHT
                ),
                gap=(TILE_GAP_X, TILE_GAP_Y),
            ),
        ],
        gap=HEADING_GAP,
        align="start",
    )


def _section_head(kit: BaseKit, title: str, count: str) -> Component:
    return Frame(
        HStack(
            [
                Frame(
                    kit.text(
                        title, font_size=SUBTITLE_SIZE, wrap=False, max_lines=1
                    ),
                    width=Fill(),
                    align_x="start",
                    align_y="center",
                ),
                kit.text(
                    count,
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    align="right",
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=16,
            align="center",
        ),
        width=Fixed(CONTENT_WIDTH),
        height=Fixed(HEADER_HEIGHT),
        align_x="stretch",
        align_y="center",
    )


def _tile(kit: BaseKit, command: HelpCommand, compact: bool = False) -> Component:
    if compact:
        return kit.panel(
            Frame(
                kit.text(
                    command.command, font_size=BODY_SIZE, wrap=False, max_lines=1
                ),
                width=Fill(),
                height=Fill(),
                align_x="start",
                align_y="center",
            ),
            width=Fixed(TILE_WIDTH),
            height=Fixed(COMPACT_TILE_HEIGHT),
            padding=COMPACT_TILE_PADDING,
            radius=TILE_RADIUS,
        )
    return kit.panel(
        VStack(
            [
                kit.text(
                    command.command, font_size=BODY_SIZE, wrap=False, max_lines=1
                ),
                kit.text(
                    _sub_line(command),
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=2,
            align="start",
        ),
        width=Fixed(TILE_WIDTH),
        height=Fixed(TILE_HEIGHT),
        padding=TILE_PADDING,
        radius=TILE_RADIUS,
    )


def _sub_line(command: HelpCommand) -> str:
    """What goes under the command on a tile.

    Aliases first, because they are the shortest thing worth knowing. A command
    whose only extra spelling is an argument form — ``/tts <角色> <文本>`` — shows
    the arguments instead, and one with neither — ``/红包列表``, ``/探险统计`` —
    borrows its own one-line summary, so the muted line is never blank.
    """

    tokens = [alias for alias in command.aliases if not alias.startswith("<")]
    tokens = tokens or list(command.aliases) or [command.summary]

    budget = TILE_WIDTH - TILE_PADDING.horizontal
    separator = _text_width(_ALIAS_SEPARATOR, LABEL_SIZE)
    chosen: list[str] = []
    used = 0.0
    for token in tokens:
        step = _text_width(token, LABEL_SIZE) + (separator if chosen else 0.0)
        if chosen and used + step > budget:
            break
        chosen.append(token)
        used += step
    return _ALIAS_SEPARATOR.join(chosen)


def _text_width(text: str, font_size: int) -> float:
    units = sum(
        _WIDE_GLYPH if ord(char) >= 0x2E80 else _NARROW_GLYPH for char in text
    )
    return units * font_size


def _meta_panel(kit: BaseKit) -> Component:
    return panel_section(
        kit,
        VStack(
            [
                kit.text(
                    "输入 /help 功能名，查看用法和示例",
                    font_size=BODY_SIZE,
                    wrap=False,
                    max_lines=1,
                ),
                stat_row(kit, "需要帮助", f"QQ 群 {SUPPORT_GROUP}"),
            ],
            gap=14,
            align="stretch",
        ),
    )
