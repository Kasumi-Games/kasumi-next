"""One plugin's detailed usage, for ``/help <功能名>``.

Tier B: ``BaseKit`` atoms through ``utils.cards`` only, so the same composition
renders in all eight kits.

The card exists for the case the board cannot serve. ``猜卡面`` documents twelve
difficulty names inside a single sentence of prose — an enumerable value set
masquerading as a paragraph. ``plugins.help.entries`` pulls those sets back out
of the text, and this module lays them out as chips, one value per chip, so they
can be read and retyped one at a time.

Two notes:

* Chips are ``utils.cards.badge``, not nested panels. A panel inside a panel is
  invisible in ``MinimalKit``, whose panel is a flat fill with no border; the
  badge fills with ``emphasis(kit)`` and is measured at 6.58:1 or better
  everywhere.
* The meaning under each command is drawn in ``text_color``, not
  ``muted_text_color``. It is content a player has to read, and muted measures
  2.72:1 in ``sakura``. Hierarchy comes from size and order instead.
"""

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import SUBTITLE_SIZE
from utils.cards import badge
from utils.cards import card_page
from utils.cards import empty_state
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit

from ..entries import HelpEntry

#: ``5 * 132 + 4 * 15 == 720 == INNER_WIDTH``.
CHIP_COLUMNS = 5
CHIP_WIDTH = 132
CHIP_HEIGHT = 44
CHIP_GAP_X = 15
CHIP_GAP_Y = 12

#: ``3 * 224 + 2 * 24 == 720 == INNER_WIDTH``.
EXAMPLE_COLUMNS = 3
EXAMPLE_WIDTH = 224
EXAMPLE_HEIGHT = 44
EXAMPLE_GAP_X = 24
EXAMPLE_GAP_Y = 12

HEADER_HEIGHT = 38
SECTION_GAP = 24
HEADING_GAP = 14
ROW_GAP = 18


def detail_page(entry: HelpEntry, kit: BaseKit | None = None) -> AutoPage:
    """Build the usage page for one documented plugin.

    Args:
        entry: The plugin to describe.
        kit: Active kit; defaults to BanG Dream!.

    Returns:
        Page ready to ``render()`` or ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    sections: list[Component] = [_usage_panel(kit, entry)]
    if entry.params:
        sections.append(_params_panel(kit, entry))
    if entry.examples:
        sections.append(_examples_panel(kit, entry))

    return card_page(
        kit,
        title="帮助",
        subtitle=entry.name,
        body=VStack(sections, gap=SECTION_GAP, align="stretch"),
        footer=_meta_panel(kit),
    )


def render_detail(entry: HelpEntry, kit: BaseKit | None = None) -> Image.Image:
    """Render one plugin's usage card.

    Args:
        entry: The plugin to describe.
        kit: Active kit; defaults to BanG Dream!.

    Returns:
        Rendered card.
    """

    return detail_page(entry, kit).render()


def _usage_panel(kit: BaseKit, entry: HelpEntry) -> Component:
    if not entry.usage:
        return panel_section(kit, empty_state(kit, "这个功能还没有写用法"))

    children: list[Component] = []
    if entry.description:
        children.append(kit.text(entry.description, font_size=BODY_SIZE))
        children.append(kit.separator(length=Fill()))
    children.append(_section_head(kit, "用法", f"{len(entry.usage)} 条"))
    children.append(
        VStack(
            [_usage_row(kit, command, meaning) for command, meaning in entry.usage],
            gap=ROW_GAP,
            align="stretch",
        )
    )
    return panel_section(kit, VStack(children, gap=HEADING_GAP, align="stretch"))


def _usage_row(kit: BaseKit, command: str, meaning: str) -> Component:
    return VStack(
        [
            kit.text(command, font_size=SUBTITLE_SIZE, wrap=False, max_lines=1),
            kit.text(meaning, font_size=LABEL_SIZE, max_lines=2),
        ],
        gap=4,
        align="stretch",
    )


def _params_panel(kit: BaseKit, entry: HelpEntry) -> Component:
    groups: list[Component] = []
    for label, values in entry.params:
        groups.append(
            VStack(
                [
                    _section_head(kit, label, f"{len(values)} 种"),
                    Grid(
                        children=[
                            badge(
                                kit,
                                value,
                                width=CHIP_WIDTH,
                                height=CHIP_HEIGHT,
                                font_size=LABEL_SIZE,
                            )
                            for value in values
                        ],
                        columns=CHIP_COLUMNS,
                        column_track=Fixed(CHIP_WIDTH),
                        row_track=Fixed(CHIP_HEIGHT),
                        gap=(CHIP_GAP_X, CHIP_GAP_Y),
                    ),
                ],
                gap=HEADING_GAP,
                align="start",
            )
        )
    return panel_section(kit, VStack(groups, gap=SECTION_GAP, align="start"))


def _examples_panel(kit: BaseKit, entry: HelpEntry) -> Component:
    cells = [
        Frame(
            kit.text(example, font_size=BODY_SIZE, wrap=False, max_lines=1),
            width=Fixed(EXAMPLE_WIDTH),
            height=Fixed(EXAMPLE_HEIGHT),
            align_x="start",
            align_y="center",
        )
        for example in entry.examples
    ]
    return panel_section(
        kit,
        VStack(
            [
                _section_head(kit, "示例", f"{len(entry.examples)} 条"),
                Grid(
                    children=cells,
                    columns=EXAMPLE_COLUMNS,
                    column_track=Fixed(EXAMPLE_WIDTH),
                    row_track=Fixed(EXAMPLE_HEIGHT),
                    gap=(EXAMPLE_GAP_X, EXAMPLE_GAP_Y),
                ),
            ],
            gap=HEADING_GAP,
            align="start",
        ),
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
        width=Fixed(INNER_WIDTH),
        height=Fixed(HEADER_HEIGHT),
        align_x="stretch",
        align_y="center",
    )


def _meta_panel(kit: BaseKit) -> Component:
    return panel_section(
        kit,
        kit.text("输入 /help 查看全部功能", font_size=BODY_SIZE, wrap=False, max_lines=1),
    )
