"""The live tour board."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from utils import cards
from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit

from ..models import CardType
from ..models import TourCard
from ..models import TourSnapshot
from ..messages import Messages

BOARD_WIDTH = cards.CONTENT_WIDTH


@dataclass(frozen=True)
class TourRenderData:
    snapshot: TourSnapshot


def _card_cell(kit: BaseKit, index: int, card: TourCard | None) -> Component:
    if card is None:
        children = [
            kit.text(
                f"[{index}] 空槽",
                font_size=24,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            )
        ]
    else:
        if card.type is CardType.TOUR:
            label = "巡演"
            value = f"难度 {card.value}"
        elif card.type is CardType.INSTRUMENT:
            label = "乐器"
            value = f"底力 +{card.value}"
        else:
            label = "食物"
            value = f"体力 +{card.value}"
        children = [
            HStack(
                [cards.badge(kit, str(index), width=42, height=38), kit.text(label, font_size=22)],
                gap=10,
                align="center",
            ),
            kit.text(card.name, font_size=25, wrap=False, max_lines=1),
            kit.text(value, font_size=22, color=kit.muted_text_color, wrap=False, max_lines=1),
        ]
    return kit.panel(
        Frame(VStack(children, gap=8, align="start"), align_x="start", align_y="center"),
        width=Fixed(350),
        padding=18,
        radius=18,
    )


def _hand_panel(kit: BaseKit, snapshot: TourSnapshot) -> Component:
    cells = [
        _card_cell(kit, index, card)
        for index, card in enumerate(snapshot.hand[:4], start=1)
    ]
    while len(cells) < 4:
        cells.append(_card_cell(kit, len(cells) + 1, None))
    return cards.panel_section(
        kit,
        VStack(
            [
                HStack(
                    [
                        kit.text("今日手牌", font_size=28, wrap=False, max_lines=1),
                        Frame(
                            kit.text(
                                f"牌库剩余 {snapshot.deck_size} 张",
                                font_size=22,
                                color=kit.muted_text_color,
                                align="right",
                                wrap=False,
                                max_lines=1,
                            ),
                            width=Fill(),
                            align_x="end",
                            align_y="center",
                        ),
                    ],
                    gap=18,
                    align="center",
                ),
                Grid(
                    children=cells,
                    columns=2,
                    rows=2,
                    column_track=Fixed(350),
                    gap=16,
                ),
            ],
            gap=18,
            align="stretch",
        ),
    )


def _instrument_panel(kit: BaseKit, snapshot: TourSnapshot) -> Component:
    status = (
        "无乐器"
        if snapshot.instrument is None
        else "已装备" if snapshot.instrument_equipped else "未装备"
    )
    rows: list[Component] = [
        HStack(
            [
                kit.text("当前乐器", font_size=28, wrap=False, max_lines=1),
                Frame(
                    cards.badge(kit, status, width=112, height=40, font_size=22),
                    width=Fill(),
                    align_x="end",
                    align_y="center",
                ),
            ],
            gap=18,
            align="center",
        )
    ]
    if snapshot.instrument is None:
        rows.append(
            HStack(
                [
                    kit.separator(orientation="vertical", length=Fixed(54), thickness=4),
                    kit.text(
                        "选择乐器牌后会自动装备。",
                        font_size=24,
                        color=kit.muted_text_color,
                        wrap=False,
                        max_lines=1,
                    ),
                ],
                gap=14,
                align="center",
            )
        )
    else:
        rows.extend(
            [
                kit.text(
                    snapshot.instrument.name,
                    font_size=30,
                    wrap=True,
                    max_lines=2,
                    overflow="ellipsis",
                ),
                kit.separator(length=Fill()),
                HStack(
                    [
                        Frame(
                            VStack(
                                [
                                    kit.text("底力", font_size=22, color=kit.muted_text_color, wrap=False, max_lines=1),
                                    kit.text(f"+{snapshot.instrument.value}", font_size=24, wrap=False, max_lines=1),
                                ],
                                gap=4,
                                align="start",
                            ),
                            width=Fill(),
                            align_x="start",
                            align_y="center",
                        ),
                        kit.separator(orientation="vertical", length=Fixed(52), thickness=2),
                        Frame(
                            VStack(
                                [
                                    kit.text("契合度", font_size=22, color=kit.muted_text_color, wrap=False, max_lines=1),
                                    kit.text(
                                        "可演出任意难度"
                                        if snapshot.last_performance is None
                                        else f"下一场难度低于 {snapshot.last_performance}",
                                        font_size=24,
                                        wrap=False,
                                        max_lines=1,
                                        overflow="ellipsis",
                                    ),
                                ],
                                gap=4,
                                align="start",
                            ),
                            width=Fill(),
                            align_x="start",
                            align_y="center",
                        ),
                    ],
                    gap=20,
                    align="center",
                ),
            ]
        )
    return cards.panel_section(
        kit,
        VStack(rows, gap=16, align="stretch"),
    )


def _status_panel(kit: BaseKit, snapshot: TourSnapshot) -> Component:
    return cards.panel_section(
        kit,
        VStack(
            [
                HStack(
                    [
                        kit.text("体力", font_size=28),
                        Frame(
                            kit.text(
                                f"{snapshot.stamina}/{snapshot.max_stamina}",
                                font_size=28,
                                align="right",
                            ),
                            width=Fill(),
                            align_x="end",
                            align_y="center",
                        ),
                    ],
                    gap=18,
                    align="center",
                ),
                cards.meter(
                    kit,
                    value=snapshot.stamina,
                    total=snapshot.max_stamina,
                    width=BOARD_WIDTH - 64,
                    height=22,
                    label="",
                ),
                HStack(
                    [
                        kit.text(
                            f"第 {snapshot.day} 天 · 今日行动 {snapshot.selection_count}/3",
                            font_size=22,
                            color=kit.muted_text_color,
                        ),
                        Frame(
                            kit.text(
                                f"已完成 {snapshot.tour_played_count}/26 场",
                                font_size=22,
                                color=kit.muted_text_color,
                                align="right",
                            ),
                            width=Fill(),
                            align_x="end",
                            align_y="center",
                        ),
                    ],
                    gap=18,
                    align="center",
                ),
            ],
            gap=16,
            align="stretch",
        ),
    )


def render_state(
    data: TourRenderData,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
    detail: str | None = None,
) -> Image.Image:
    kit = kit or BanGDreamKit()
    snapshot = data.snapshot
    sections: list[Component] = []
    if identity is not None:
        sections.append(cards.game_identity(kit, identity, width=BOARD_WIDTH, detail=detail))
    sections.extend(
        [
            _status_panel(kit, snapshot),
            _hand_panel(kit, snapshot),
            _instrument_panel(kit, snapshot),
            cards.panel_section(
                kit,
                kit.text(
                    Messages.compact_prompt(snapshot)
                    + "\n可连续输入最多 6 个 0-4；每天完成 3 次行动后进入下一天。",
                    font_size=22,
                    wrap=True,
                    max_lines=2,
                ),
            ),
        ]
    )
    return cards.card_page(
        kit,
        title="巡演",
        subtitle=f"{snapshot.difficulty} · {snapshot.tour_played_count}/26",
        article_title="TOUR",
        body=VStack(sections, gap=20, align="stretch"),
        owner_name=identity.nickname if identity is not None else None,
    ).render()
