"""The season Pt ladder card — what ``/赛季排行`` replies with in season.

Two sections inside one panel: the top ten via ``utils.cards.ladder_rows``
(filled badges for the podium, the self rule on the viewer's row), and — only
when the viewer is outside the top ten — a 「你的附近」 section with the
viewer's ±5 neighbourhood so "where am I" is a position on the ladder, not a
number to imagine. The footer states the viewer's rank and points either way.

The off-season keeps the old text reply (final settled rankings), so this
module only ever renders an active season.

No database access here: the handler assembles :class:`SeasonRankData` on the
event loop thread (the inventory session is process-global and not thread
safe) and only the raster is offloaded via
``await season_rank_page(...).render_async()``.
"""

from dataclasses import dataclass

from PIL import Image

from utils.cards import LABEL_SIZE
from utils.cards import card_page
from utils.cards import empty_state
from utils.cards import ladder_rows
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit


@dataclass(frozen=True)
class SeasonRankRow:
    """One Pt ladder row.

    Attributes:
        rank: 1-based rank.
        name: Display name.
        points: Season Pt.
    """

    rank: int
    name: str
    points: int
    user_id: str = ""
    identity: PlayerIdentity | None = None


@dataclass(frozen=True)
class SeasonRankData:
    """Everything the Pt ladder card shows, assembled by the handler.

    Attributes:
        season_name: Active season name, for the subtitle.
        rows: Top rows, rank ascending.
        nearby: The viewer's neighbourhood (viewer ±5, rank ascending), only
            when the viewer is outside ``rows``; empty otherwise.
        viewer_name: Display name whose rows get the self marker.
        viewer_rank: The viewer's 1-based rank.
        viewer_points: The viewer's season Pt.
    """

    season_name: str
    rows: tuple[SeasonRankRow, ...]
    nearby: tuple[SeasonRankRow, ...]
    viewer_name: str
    viewer_rank: int
    viewer_points: int


def render_season_rank(data: SeasonRankData, kit: BaseKit | None = None) -> Image.Image:
    """Render the season Pt ladder card.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return season_rank_page(data, kit).render()


def season_rank_page(data: SeasonRankData, kit: BaseKit | None = None) -> AutoPage:
    """Build the season Pt ladder page without rendering it.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    if not data.rows:
        body: Component = panel_section(
            kit, empty_state(kit, "本赛季还没有 Pt 记录\n玩一局游戏赚取第一份 Pt")
        )
    else:
        body = panel_section(kit, _ladder(kit, data))
    return card_page(
        kit,
        title="赛季排行",
        subtitle=f"{data.season_name} · Pt 榜",
        body=body,
        footer=_footer(kit, data),
    )


def _ladder(kit: BaseKit, data: SeasonRankData) -> Component:
    """The top rows, plus the viewer's neighbourhood when they sit below."""

    children: list[Component] = [
        ladder_rows(
            kit,
            [
                (row.rank, row.name, _value(row), row.identity)
                for row in data.rows
            ],
            highlight=data.viewer_name,
        )
    ]
    if data.nearby:
        children.append(kit.separator(length=Fill()))
        children.append(
            kit.text(
                "你的附近",
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            )
        )
        children.append(
            ladder_rows(
                kit,
                [
                    (row.rank, row.name, _value(row), row.identity)
                    for row in data.nearby
                ],
                highlight=data.viewer_name,
            )
        )
    return VStack(children, gap=18, align="stretch")


def _value(row: SeasonRankRow) -> str:
    return f"{row.points:,} Pt"


def _footer(kit: BaseKit, data: SeasonRankData) -> Component:
    """The viewer's own standing. Must-read, so full text color."""

    return kit.text(
        f"你当前排名第 {data.viewer_rank} 名 · {data.viewer_points:,} Pt",
        font_size=LABEL_SIZE,
        wrap=False,
        max_lines=1,
    )
