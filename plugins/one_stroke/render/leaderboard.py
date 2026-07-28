from PIL import Image

from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.kasumi import KasumiKit

LeaderboardRows = list[tuple[str, float]]

_ROW_HEIGHT = 44
_ROW_GAP = 14


def _ranking_rows(kit: BaseKit, rows: LeaderboardRows):
    row_components = []
    for idx in range(10):
        if idx < len(rows):
            name, elapsed = rows[idx]
            name_text = f"{idx + 1}. {name}"
            time_text = f"{elapsed:.2f}s"
            color = kit.text_color
            time_color = kit.text_color
        else:
            name_text = f"{idx + 1}. --"
            time_text = ""
            color = kit.muted_text_color
            time_color = color
        row_components.append(
            Frame(
                HStack(
                    [
                        Frame(
                            kit.text(
                                name_text,
                                font_size=23,
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
                                font_size=22,
                                color=time_color,
                                align="right",
                                wrap=False,
                                max_lines=1,
                            ),
                            width=Fixed(72),
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
    return VStack(row_components, gap=_ROW_GAP, align="stretch")


def render_leaderboard(
    easy_rows: LeaderboardRows,
    normal_rows: LeaderboardRows,
    hard_rows: LeaderboardRows,
    kit: BaseKit | None = None,
) -> Image.Image:
    kit = kit or BanGDreamKit()
    page = AutoPage(
        max_width=1500,
        background=kit.background(),
        padding=Insets.only(left=70, top=36, right=70, bottom=56),
        child=VStack(
            [
                _title_bar(kit, "一笔画", "竞速排行榜", width=420, height=57),
                HStack(
                    [
                        _ranking_panel(kit, "简单", easy_rows),
                        _ranking_panel(kit, "普通", normal_rows),
                        _ranking_panel(kit, "困难", hard_rows),
                    ],
                    gap=30,
                ),
            ],
            gap=46,
            align="stretch",
        ),
    )
    return page.render()


def _ranking_panel(kit: BaseKit, title: str, rows: LeaderboardRows):
    if isinstance(kit, BanGDreamKit):
        return kit.titled_panel(
            title,
            Frame(
                _ranking_rows(kit, rows),
                padding=Insets.only(left=30, top=28, right=30, bottom=22),
                align_x="stretch",
                align_y="stretch",
            ),
            title_width=180,
            title_height=64,
            main_width=Fill(),
            main_height=695,
            title_font_size=34,
            stroke_width=6,
            title_radius=32,
            main_radius=48,
            main_fill=(255, 255, 255, 208),
        )
    return kit.panel(
        VStack(
            [
                Frame(
                    kit.text(
                        title,
                        font_size=40,
                        align="center",
                        max_lines=1,
                    ),
                    height=Fixed(72),
                    align_x="center",
                    align_y="center",
                ),
                Frame(
                    _ranking_rows(kit, rows),
                    align_x="stretch",
                    align_y="stretch",
                ),
            ],
            gap=8,
            align="stretch",
        ),
        width=Fixed(360),
        height=Fixed(759),
        padding=Insets.only(left=20, top=18, right=20, bottom=24),
        radius=48,
    )


def _title_bar(
    kit: BaseKit,
    title: str,
    subtitle: str,
    *,
    width: int,
    height: int,
):
    if isinstance(kit, KasumiKit):
        return kit.game_title(title, subtitle, width=width, height=height)
    if isinstance(kit, BanGDreamKit):
        return kit.title_pill(
            title,
            subtitle,
            pill_width=width,
            pill_height=height,
        )
    return kit.panel(
        Frame(
            kit.text(
                f"{title} - {subtitle}",
                font_size=24,
                align="center",
                max_lines=1,
            ),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(width),
        height=Fixed(height),
        radius=height // 2,
    )
