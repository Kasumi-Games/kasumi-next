"""The stats card — what ``/黑香澄统计`` replies with.

One themed card replaces the emoji text block and the unthemed matplotlib
chart the command used to send: the Tier A identity strip on top, a record
panel (hands, wins/losses/pushes, BlackJack count, net profit) closed by the
win-rate meter, and a Pt ledger panel (totals, averages, extremes).

This module lives beside ``render.py`` (the Tier A table renderer) rather
than inside a ``render/`` package because that module already owns the name.

:func:`stats_card_data` is the one place that maps :class:`BlackjackStats`
onto the card. It is pure — the stats query and identity resolution both
happen in the handler on the event-loop thread — so this module never touches
a database and only the raster is offloaded via
``await stats_page(...).render_async()``.
"""

from typing import TYPE_CHECKING
from dataclasses import dataclass

from PIL import Image

from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import CONTENT_WIDTH
from utils.cards import meter
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import game_identity
from utils.cards import panel_section
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit

if TYPE_CHECKING:
    from .stats_service import BlackjackStats


@dataclass(frozen=True)
class StatsCardData:
    """Everything the stats card shows, assembled by :func:`stats_card_data`.

    Attributes:
        identity: Player identity for the Tier A strip on top.
        total_games: Hands played.
        wins: Won hands (normal wins plus BlackJack wins).
        losses: Lost hands.
        pushes: Pushed hands.
        blackjacks: Natural-21 wins, a subset of ``wins``.
        win_rate: ``wins / total_games``.
        total_wagered: Sum of every bet.
        total_won: Sum of positive winnings.
        total_lost: Sum of losses, as a positive number.
        net_profit: ``total_won - total_lost``; may be negative.
        avg_bet: Average bet per hand.
        avg_win: Average amount won per winning hand.
        avg_loss: Average amount lost per losing hand.
        biggest_win: Largest single-hand win.
        biggest_loss: Largest single-hand loss, as a positive number.
    """

    identity: PlayerIdentity
    total_games: int
    wins: int
    losses: int
    pushes: int
    blackjacks: int
    win_rate: float
    total_wagered: int
    total_won: int
    total_lost: int
    net_profit: int
    avg_bet: float
    avg_win: float
    avg_loss: float
    biggest_win: int
    biggest_loss: int


def stats_card_data(
    stats: "BlackjackStats", identity: PlayerIdentity
) -> StatsCardData:
    """Map service stats onto the card's data.

    Args:
        stats: Result of ``stats_service.get_blackjack_stats``.
        identity: Player identity resolved by the handler.

    Returns:
        Card data ready for :func:`stats_page`.
    """

    return StatsCardData(
        identity=identity,
        total_games=stats.total_games,
        wins=stats.wins,
        losses=stats.losses,
        pushes=stats.pushes,
        blackjacks=stats.blackjacks,
        win_rate=stats.win_rate,
        total_wagered=stats.total_wagered,
        total_won=stats.total_won,
        total_lost=stats.total_lost,
        net_profit=stats.net_profit,
        avg_bet=stats.avg_bet,
        avg_win=stats.avg_win,
        avg_loss=stats.avg_loss,
        biggest_win=stats.biggest_win,
        biggest_loss=stats.biggest_loss,
    )


def render_stats(data: StatsCardData, kit: BaseKit | None = None) -> Image.Image:
    """Render the stats card.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return stats_page(data, kit).render()


def stats_page(data: StatsCardData, kit: BaseKit | None = None) -> AutoPage:
    """Build the stats card page without rendering it.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    return card_page(
        kit,
        title="黑香澄",
        subtitle=f"战绩 · {data.total_games} 局",
        article_title="STATISTICS",
        show_subtitle=False,
        body=VStack(
            [
                game_identity(kit, data.identity, width=CONTENT_WIDTH),
                _record_panel(kit, data),
                _ledger_panel(kit, data),
            ],
            gap=24,
            align="stretch",
        ),
        footer=_footer(kit),
        owner_name=data.identity.nickname,
    )


def _record_panel(kit: BaseKit, data: StatsCardData) -> Component:
    """Hands and outcomes, closed by the win-rate meter.

    Net profit is the number a bystander asks about, so it gets the larger
    value size; the meter always carries its numeric label because the
    fill/track boundary is the first casualty of chat-client downscaling.
    """

    rows: list[Component] = [
        stat_row(kit, "总局数", f"{data.total_games} 局"),
        stat_row(
            kit,
            "胜 / 负 / 平",
            f"{data.wins} / {data.losses} / {data.pushes}",
        ),
        stat_row(kit, "BlackJack 达成", f"{data.blackjacks} 次"),
        stat_row(kit, "净收益", f"{data.net_profit:+d} Pt", value_size=26),
        meter(
            kit,
            value=data.wins,
            total=data.total_games,
            label=f"胜率 {data.win_rate:.1%}",
        ),
    ]
    return panel_section(kit, VStack(rows, gap=16, align="stretch"))


def _ledger_panel(kit: BaseKit, data: StatsCardData) -> Component:
    """The Pt ledger: totals, per-hand averages, single-hand extremes."""

    rows: list[Component] = [
        stat_row(kit, "总投入", f"{data.total_wagered} Pt"),
        stat_row(kit, "总赢得", f"{data.total_won} Pt"),
        stat_row(kit, "总输掉", f"{data.total_lost} Pt"),
        kit.separator(length=Fixed(INNER_WIDTH), thickness=2),
        stat_row(kit, "平均下注", f"{data.avg_bet:.1f} Pt"),
        stat_row(kit, "平均赢得", f"{data.avg_win:.1f} Pt"),
        stat_row(kit, "平均输掉", f"{data.avg_loss:.1f} Pt"),
        kit.separator(length=Fixed(INNER_WIDTH), thickness=2),
        stat_row(kit, "单局最高赢得", f"{data.biggest_win} Pt"),
        stat_row(kit, "单局最高输掉", f"{data.biggest_loss} Pt"),
    ]
    return panel_section(kit, VStack(rows, gap=16, align="stretch"))


def _footer(kit: BaseKit) -> Component:
    """Command hint; scaffolding, so muted."""

    return Frame(
        kit.text(
            "/黑香澄 <下注 Pt> 再来一局",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )
