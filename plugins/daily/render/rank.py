"""The level leaderboard card — what ``/排行榜`` replies with.

Replaces ten unaligned text lines plus a trailing prose sentence with real
columns: :func:`utils.cards.ladder_rows` gives the top three filled badges and
marks the viewer's row with the self rule. A viewer outside the top rows gets
their own row appended under a separator, so "how far am I" is a position, not
a sentence to parse. The subtitle names the ladder — the repo has two (level
and season Pt) and the old text never said which one this is.

No database access here: the handler assembles :class:`RankData` on the event
loop thread and passes it in; only the raster is offloaded via
``await rank_page(...).render_async()``.
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
class RankRow:
    """One leaderboard row.

    Attributes:
        rank: 1-based rank.
        name: Display name.
        level: Player level.
        xp: Total XP.
    """

    rank: int
    name: str
    level: int
    xp: int
    user_id: str = ""
    identity: PlayerIdentity | None = None


@dataclass(frozen=True)
class RankData:
    """Everything the leaderboard card shows, assembled by the handler.

    Attributes:
        rows: Top rows, rank ascending.
        viewer: The viewer's own row, only when they are outside ``rows``;
            ``None`` when the viewer already appears in the top rows.
        viewer_name: Display name whose row gets the self marker.
        viewer_rank: The viewer's 1-based rank.
        xp_gap: XP to the player one rank above; ``<= 0`` means a tie.
    """

    rows: tuple[RankRow, ...]
    viewer: RankRow | None
    viewer_name: str
    viewer_rank: int
    xp_gap: int


def render_rank(data: RankData, kit: BaseKit | None = None) -> Image.Image:
    """Render the leaderboard card.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return rank_page(data, kit).render()


def rank_page(data: RankData, kit: BaseKit | None = None) -> AutoPage:
    """Build the leaderboard page without rendering it.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    if not data.rows:
        body: Component = panel_section(
            kit, empty_state(kit, "还没有人上榜\n发送 /签到 赚取第一份 XP")
        )
    else:
        body = panel_section(kit, _ladder(kit, data))
    return card_page(
        kit,
        title="排行榜",
        subtitle=f"等级榜 · Top {len(data.rows)}" if data.rows else "等级榜",
        body=body,
        footer=_footer(kit, data),
    )


def _ladder(kit: BaseKit, data: RankData) -> Component:
    """Top rows, plus the viewer pinned under a separator when outside them."""

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
    if data.viewer is not None:
        children.append(kit.separator(length=Fill()))
        children.append(
            ladder_rows(
                kit,
                [
                    (
                        data.viewer.rank,
                        data.viewer.name,
                        _value(data.viewer),
                        data.viewer.identity,
                    )
                ],
                highlight=data.viewer_name,
            )
        )
    return VStack(children, gap=18, align="stretch")


def _value(row: RankRow) -> str:
    return f"Lv.{row.level} · {row.xp:,} XP"


def _footer(kit: BaseKit, data: RankData) -> Component:
    """The viewer's own standing. Must-read, so full text color."""

    text = f"你当前排名第 {data.viewer_rank} 名"
    if data.viewer_rank != 1:
        if data.xp_gap > 0:
            text += f" · 距上一名 {data.xp_gap} XP"
        else:
            text += " · 与上一名相同"
    return kit.text(text, font_size=LABEL_SIZE, wrap=False, max_lines=1)
