"""Theme-aware rules card for ``/巡演 -h``."""

from __future__ import annotations

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

_ROW_GAP = 18
_SECTION_GAP = 24
_ACTION_BADGE_WIDTH = 64


def render_help(kit: BaseKit | None = None) -> Image.Image:
    """Render the tour rules card."""

    return help_page(kit).render()


def help_page(kit: BaseKit | None = None) -> AutoPage:
    """Build the tour rules card without rendering it."""

    kit = kit or BanGDreamKit()
    section_gap = 18 if isinstance(kit, MewtypeKit) else _SECTION_GAP
    return card_page(
        kit,
        title="巡演",
        subtitle="规则与指令",
        article_title="HOW TO PLAY",
        show_subtitle=False,
        body=VStack(
            [
                _getting_started_panel(kit),
                _daily_flow_panel(kit),
                _actions_panel(kit),
                _rules_and_rewards_panel(kit),
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
                "完成 26 场演出；体力降至 0 或以下即失败。",
            ),
            _rule(
                kit,
                "开始游戏",
                "/巡演 [初级|中级|高级|超级]；不填难度默认初级。",
            ),
            _rule(
                kit,
                "显示模式",
                "/巡演 模式 [图片|文本]；按用户保存，默认为图片。",
            ),
        ],
    )


def _daily_flow_panel(kit: BaseKit) -> Component:
    return _section(
        kit,
        "牌库与每日流程",
        [
            _rule(
                kit,
                "牌库",
                "巡演牌 2-14 各两张；乐器和食物 2-10 各一张。开局 4 张手牌。",
            ),
            _rule(
                kit,
                "每日流程",
                "每天最多 3 次计数行动；完成后进入下一天并补 3 张牌。0 不计行动。",
            ),
            _rule(
                kit,
                "食物与休息",
                "每天第一张食物才恢复体力；5 只能在当天尚未行动且前一天未休息时使用。",
            ),
        ],
    )


def _actions_panel(kit: BaseKit) -> Component:
    actions = [
        ("1-4", "选择手牌", "每次选择一张；最多把 0-4 连成 6 位输入。"),
        (
            "0",
            "操作乐器",
            "超级难度：0 丢弃乐器；其他难度：已装备时 0 卸下装备，未装备时 0 穿上装备。",
        ),
        ("5", "整日休息", "把当前手牌排到日程末尾；不能连续休息两天。"),
        ("q", "退出", "结束当前巡演，不发放通关奖励。"),
    ]
    return _section(
        kit,
        "回合操作",
        [_action_row(kit, key, name, detail) for key, name, detail in actions],
    )


def _rules_and_rewards_panel(kit: BaseKit) -> Component:
    return _section(
        kit,
        "乐器与奖励",
        [
            _rule(
                kit,
                "乐器",
                "巡演消耗 max(0, 难度 - 底力)；同一乐器后续必须严格低于上次演出难度。",
            ),
            _rule(
                kit,
                "通关奖励",
                "初级 12 Pt + 12 XP；中级 18 Pt + 18 XP；高级 24 Pt + 24 XP；超级 30 Pt + 30 XP。",
            ),
            _rule(
                kit,
                "生日加成",
                "角色生日当天，通关奖励和 XP 均为 2 倍。",
            ),
        ],
    )


def _section(kit: BaseKit, title: str, rows: list[Component]) -> Component:
    return panel_section(
        kit,
        VStack(
            [
                kit.text(title, font_size=SUBTITLE_SIZE, wrap=False, max_lines=1),
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
                        kit.text(name, font_size=BODY_SIZE, wrap=False, max_lines=1),
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
