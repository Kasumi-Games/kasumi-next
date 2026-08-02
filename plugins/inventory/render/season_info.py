"""The themed season overview card behind ``/赛季``.

The handler resolves the season, player standing, reward item names, and
banner metadata on the event-loop thread.  This module is deliberately pure:
it only arranges render-kit atoms, so ``render_async`` can safely offload the
raster work and every equipped theme gets the same information hierarchy.
"""

from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import CONTENT_WIDTH
from utils.cards import LABEL_SIZE
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import panel_section
from utils.clock import format_ts
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit


@dataclass(frozen=True)
class SeasonRewardRow:
    """One configured placement tier on the season card."""

    placement: str
    rewards: tuple[str, ...]


@dataclass(frozen=True)
class SeasonInfoData:
    """Everything shown on an active or upcoming season card."""

    season_name: str
    state: str  # active | upcoming
    starts_at: int
    ends_at: int
    now: int
    points: int | None
    rank: int | None
    reward_rows: tuple[SeasonRewardRow, ...]
    banner_name: str | None = None
    featured_names: tuple[str, ...] = ()


def render_season_info(
    data: SeasonInfoData, kit: BaseKit | None = None
) -> Image.Image:
    """Render a season overview card."""

    return season_info_page(data, kit).render()


def season_info_page(
    data: SeasonInfoData, kit: BaseKit | None = None
) -> AutoPage:
    """Build the season overview page for sync or async rendering."""

    kit = kit or BanGDreamKit()
    sections: list[Component] = [
        _status_panel(kit, data),
        _standing_panel(kit, data),
    ]
    if data.reward_rows:
        sections.append(_rewards_panel(kit, data))
    if data.banner_name or data.featured_names:
        sections.append(_banner_panel(kit, data))

    return card_page(
        kit,
        title="赛季",
        subtitle=data.season_name,
        article_title="赛季详情",
        body=VStack(sections, gap=24, align="stretch"),
        footer=_footer(kit),
    )


def _status_panel(kit: BaseKit, data: SeasonInfoData) -> Component:
    label = "进行中" if data.state == "active" else "即将开始"
    target = data.ends_at if data.state == "active" else data.starts_at
    countdown_label = "距赛季结束" if data.state == "active" else "距赛季开始"
    return panel_section(
        kit,
        HStack(
            [
                Frame(
                    VStack(
                        [
                            kit.text(
                                "赛季状态",
                                font_size=LABEL_SIZE,
                                color=kit.muted_text_color,
                                wrap=False,
                                max_lines=1,
                            ),
                            kit.text(
                                label,
                                font_size=34,
                                wrap=False,
                                max_lines=1,
                            ),
                        ],
                        gap=6,
                        align="start",
                    ),
                    width=Fill(),
                    align_x="start",
                    align_y="center",
                ),
                Frame(
                    VStack(
                        [
                            kit.text(
                                countdown_label,
                                font_size=LABEL_SIZE,
                                color=kit.muted_text_color,
                                align="right",
                                wrap=False,
                                max_lines=1,
                            ),
                            kit.text(
                                _countdown(target - data.now),
                                font_size=34,
                                align="right",
                                wrap=False,
                                max_lines=1,
                            ),
                        ],
                        gap=6,
                        align="end",
                    ),
                    width=Fill(),
                    align_x="end",
                    align_y="center",
                ),
            ],
            gap=24,
            align="center",
        ),
    )


def _standing_panel(kit: BaseKit, data: SeasonInfoData) -> Component:
    rows: list[Component] = [
        stat_row(
            kit,
            "赛季时间",
            f"{format_ts(data.starts_at, '%m-%d %H:%M')} — "
            f"{format_ts(data.ends_at, '%m-%d %H:%M')}",
        )
    ]
    if data.state == "active":
        rows.extend(
            [
                stat_row(kit, "我的 Pt", f"{data.points or 0:,} Pt"),
                stat_row(
                    kit,
                    "当前排名",
                    f"第 {data.rank} 名" if data.rank is not None else "暂未上榜",
                ),
            ]
        )
    else:
        rows.append(
            kit.text(
                "开赛后 Pt、战绩与排行榜将从零开始统计",
                font_size=LABEL_SIZE,
                wrap=False,
                max_lines=1,
            )
        )
    return panel_section(
        kit, VStack(rows, gap=18, align="stretch")
    )


def _rewards_panel(kit: BaseKit, data: SeasonInfoData) -> Component:
    children: list[Component] = [_section_label(kit, "排名奖励")]
    for row in data.reward_rows:
        children.append(_reward_row(kit, row))
    return panel_section(
        kit, VStack(children, gap=16, align="stretch")
    )


def _reward_row(kit: BaseKit, row: SeasonRewardRow) -> Component:
    placement_width = 160
    placement = Frame(
        kit.text(
            row.placement,
            font_size=BODY_SIZE,
            wrap=False,
            max_lines=1,
        ),
        width=Fixed(placement_width),
        align_x="start",
        align_y="center",
    )
    return HStack(
        [
            placement,
            kit.separator(orientation="vertical", length=Fixed(30), thickness=3),
            Frame(
                VStack(
                    [
                        kit.text(
                            reward,
                            font_size=LABEL_SIZE,
                            wrap=False,
                            max_lines=1,
                        )
                        for reward in row.rewards
                    ],
                    gap=6,
                    align="start",
                ),
                width=Fill(),
                align_x="start",
                align_y="center",
            ),
        ],
        gap=16,
        align="center",
    )


def _banner_panel(kit: BaseKit, data: SeasonInfoData) -> Component:
    rows: list[Component] = [_section_label(kit, "限定卡池")]
    if data.banner_name:
        rows.append(stat_row(kit, "卡池", data.banner_name))
    if data.featured_names:
        rows.append(stat_row(kit, "当期角色", "、".join(data.featured_names)))
    rows.append(
        kit.text(
            "发送 /抽卡 查看卡池详情与保底进度",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        )
    )
    return panel_section(kit, VStack(rows, gap=16, align="stretch"))


def _section_label(kit: BaseKit, text: str) -> Component:
    return HStack(
        [
            kit.separator(orientation="vertical", length=Fixed(24), thickness=5),
            kit.text(text, font_size=26, wrap=False, max_lines=1),
        ],
        gap=12,
        align="center",
    )


def _footer(kit: BaseKit) -> Component:
    return Frame(
        kit.text(
            "/赛季排行 · /赛季趋势 · /抽卡",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        width=Fixed(CONTENT_WIDTH),
        align_x="start",
        align_y="center",
    )


def _countdown(seconds: int) -> str:
    remaining = max(0, int(seconds))
    days, remainder = divmod(remaining, 24 * 60 * 60)
    hours, remainder = divmod(remainder, 60 * 60)
    minutes = remainder // 60
    if days:
        return f"{days} 天 {hours} 小时"
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    return f"{minutes} 分钟"
