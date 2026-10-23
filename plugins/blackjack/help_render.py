"""Theme-aware help card for ``/黑香澄 -h``.

The old response was a checked-in screenshot of ``instruction.md``.  This
module keeps the player-facing rules in a compact Tier B card assembled only
from ``BaseKit`` atoms, so the help follows the player's selected image kit
and stays readable when chat clients downscale it.
"""

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import SUBTITLE_SIZE
from utils.cards import badge
from utils.cards import card_page
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.mewtype import MewtypeKit
from plugins.render.kits.bangdream import BanGDreamKit

from .help_content import RULE_SECTIONS

_ROW_GAP = 18
_SECTION_GAP = 24
_ACTION_BADGE_WIDTH = 64


def render_help(kit: BaseKit | None = None) -> Image.Image:
    """Render the BlackKasumi rules card."""

    return help_page(kit).render()


def help_page(kit: BaseKit | None = None) -> AutoPage:
    """Build the BlackKasumi rules card without rendering it."""

    kit = kit or BanGDreamKit()

    from plugins.render.kits.manosaba.layouts import page_for

    if (themed := page_for(kit, "blackjack.help")) is not None:
        return themed
    section_gap = 18 if isinstance(kit, MewtypeKit) else _SECTION_GAP
    return card_page(
        kit,
        title="黑香澄",
        subtitle="规则与指令",
        article_title="HOW TO PLAY",
        show_subtitle=False,
        body=VStack(
            [
                _getting_started_panel(kit),
                _actions_panel(kit),
                _special_rules_panel(kit),
                _card_values_panel(kit),
            ],
            gap=section_gap,
            align="stretch",
        ),
    )


def _getting_started_panel(kit: BaseKit) -> Component:
    return _content_section(kit, 0)


def _actions_panel(kit: BaseKit) -> Component:
    return _content_section(kit, 1)


def _special_rules_panel(kit: BaseKit) -> Component:
    return _content_section(kit, 2)


def _card_values_panel(kit: BaseKit) -> Component:
    return _content_section(kit, 3)


def _section(kit: BaseKit, title: str, rows: list[Component]) -> Component:
    return panel_section(
        kit,
        VStack(
            [
                kit.text(
                    title,
                    font_size=SUBTITLE_SIZE,
                    wrap=False,
                    max_lines=1,
                ),
                kit.separator(length=Fill()),
                VStack(rows, gap=_ROW_GAP, align="stretch"),
            ],
            gap=14,
            align="stretch",
        ),
    )


def _rule(kit: BaseKit, label: str, detail: str) -> Component:
    return VStack(
        [
            kit.text(
                label,
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            ),
            kit.text(detail, font_size=BODY_SIZE, max_lines=3),
        ],
        gap=4,
        align="stretch",
    )


def _action_row(kit: BaseKit, key: str, name: str, detail: str) -> Component:
    return HStack(
        [
            badge(
                kit,
                key,
                width=_ACTION_BADGE_WIDTH,
                height=44,
                font_size=BODY_SIZE,
            ),
            Frame(
                VStack(
                    [
                        kit.text(
                            name,
                            font_size=BODY_SIZE,
                            wrap=False,
                            max_lines=1,
                        ),
                        kit.text(detail, font_size=LABEL_SIZE, max_lines=2),
                    ],
                    gap=4,
                    align="stretch",
                ),
                width=Fill(),
                align_x="stretch",
                align_y="center",
            ),
        ],
        gap=18,
        align="center",
    )


def _content_section(kit: BaseKit, index: int) -> Component:
    title, rows = RULE_SECTIONS[index]
    return _section(
        kit,
        title,
        [
            _action_row(kit, key, label, text) if key else _rule(kit, label, text)
            for key, label, text in rows
        ],
    )
