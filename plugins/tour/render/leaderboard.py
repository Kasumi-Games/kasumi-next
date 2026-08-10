"""Current-season fastest-clear leaderboard for all tour difficulties."""

from __future__ import annotations

from PIL import Image

from utils.cards import card_page
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render.kits.mewtype import MewtypeKit
from plugins.render.kits.bangdream import BanGDreamKit

LeaderboardRows = list[tuple[str, float]]

_ROW_HEIGHT = 40
_TIME_WIDTH = 104


def _ranking_rows(kit: BaseKit, rows: LeaderboardRows):
    components = []
    for index in range(10):
        if index < len(rows):
            name, elapsed = rows[index]
            name_text = f"{index + 1}. {name}"
            time_text = f"{elapsed:.2f}s"
            color = kit.text_color
        else:
            name_text = f"{index + 1}. --"
            time_text = ""
            color = kit.muted_text_color
        components.append(
            Frame(
                HStack(
                    [
                        Frame(
                            kit.text(
                                name_text,
                                font_size=22,
                                color=color,
                                wrap=False,
                                max_lines=1,
                                overflow="ellipsis",
                            ),
                            width=Fill(),
                            align_x="start",
                            align_y="center",
                        ),
                        Frame(
                            kit.text(
                                time_text,
                                font_size=21,
                                color=color,
                                align="right",
                                wrap=False,
                                max_lines=1,
                            ),
                            width=Fixed(_TIME_WIDTH),
                            align_x="stretch",
                            align_y="center",
                        ),
                    ],
                    gap=12,
                ),
                height=Fixed(_ROW_HEIGHT),
                align_x="stretch",
                align_y="center",
            )
        )
    return VStack(components, gap=10, align="stretch")


def _ranking_panel(kit: BaseKit, difficulty: str, rows: LeaderboardRows):
    title = difficulty
    if isinstance(kit, MewtypeKit):
        title = {
            "初级": "EASY",
            "中级": "NORMAL",
            "高级": "HARD",
            "超级": "EXPERT",
        }[difficulty]
    return panel_section(
        kit,
        VStack(
            [
                kit.text(title, font_size=30, align="center", max_lines=1),
                kit.separator(length=Fill()),
                _ranking_rows(kit, rows),
            ],
            gap=14,
            align="stretch",
        ),
    )


def leaderboard_page(
    rows_by_difficulty: dict[str, LeaderboardRows],
    kit: BaseKit | None = None,
) -> AutoPage:
    kit = kit or BanGDreamKit()
    panels = [
        _ranking_panel(kit, difficulty, rows_by_difficulty.get(difficulty, []))
        for difficulty in ("初级", "中级", "高级", "超级")
    ]
    return card_page(
        kit,
        title="巡演",
        subtitle="赛季竞速排行榜",
        article_title="SPEED RANKING",
        body=VStack(
            [
                HStack(panels[:2], gap=24, align="stretch"),
                HStack(panels[2:], gap=24, align="stretch"),
            ],
            gap=24,
            align="stretch",
        ),
        width=1180,
    )


def render_leaderboard(
    rows_by_difficulty: dict[str, LeaderboardRows],
    kit: BaseKit | None = None,
) -> Image.Image:
    return leaderboard_page(rows_by_difficulty, kit).render()
