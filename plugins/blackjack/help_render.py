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
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.mewtype import MewtypeKit

_ROW_GAP = 18
_SECTION_GAP = 24
_ACTION_BADGE_WIDTH = 64


def render_help(kit: BaseKit | None = None) -> Image.Image:
    """Render the BlackKasumi rules card."""

    return help_page(kit).render()


def help_page(kit: BaseKit | None = None) -> AutoPage:
    """Build the BlackKasumi rules card without rendering it."""

    kit = kit or BanGDreamKit()
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
    return _section(
        kit,
        "目标与开局",
        [
            _rule(
                kit,
                "游戏目标",
                "手牌不超过 21 点，并尽量高于 Kasumi；Kasumi 会补牌到至少 17 点。",
            ),
            _rule(
                kit,
                "开始游戏",
                "/黑香澄 <下注 Pt>，例如 /黑香澄 10。",
            ),
        ],
    )


def _actions_panel(kit: BaseKit) -> Component:
    actions = [
        ("h", "补牌", "再抽一张牌。"),
        ("s", "停牌", "结束你的回合，交给 Kasumi。"),
        ("d", "双倍", "仅限最初两张牌；加注一倍、补一张牌后停牌。"),
        ("q", "投降", "仅限最初两张牌；结束本手并损失一半下注。"),
    ]
    return _section(
        kit,
        "回合操作",
        [_action_row(kit, key, name, detail) for key, name, detail in actions],
    )


def _special_rules_panel(kit: BaseKit) -> Component:
    return _section(
        kit,
        "特殊规则",
        [
            _rule(
                kit,
                "BlackKasumi",
                "玩家最初两张牌为 21 点时获得 1.5 倍下注奖励；"
                "Kasumi 若初始 21 点会立即亮牌结算。",
            ),
            _rule(
                kit,
                "分牌",
                "最初两张牌点数相同时可分成两手；需要追加同额下注，并分别结算。",
            ),
        ],
    )


def _card_values_panel(kit: BaseKit) -> Component:
    return _section(
        kit,
        "牌面点数",
        [
            _rule(kit, "星星", "黄星 1 点，彩星 2 点。"),
            _rule(
                kit,
                "Kasumi",
                "红框 Kasumi 可计作 1 或 11 点，系统会自动选择不爆牌的最优值。",
            ),
        ],
    )


def _section(
    kit: BaseKit, title: str, rows: list[Component]
) -> Component:
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


def _action_row(
    kit: BaseKit, key: str, name: str, detail: str
) -> Component:
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
