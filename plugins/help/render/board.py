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
    if groups:
        body: Component = VStack(
            [_category_section(kit, name, commands) for name, commands in groups],
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


def _category_section(
    kit: BaseKit, category: str, commands: Sequence[HelpCommand]
) -> Component:
    return VStack(
        [
            _section_head(kit, category, f"{len(commands)} 项"),
            kit.separator(length=Fixed(CONTENT_WIDTH)),
            Grid(
                children=[_tile(kit, command) for command in commands],
                columns=COLUMNS,
                column_track=Fixed(TILE_WIDTH),
                row_track=Fixed(TILE_HEIGHT),
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


def _tile(kit: BaseKit, command: HelpCommand) -> Component:
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
