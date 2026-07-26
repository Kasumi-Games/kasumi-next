"""The 探险统计 card — replaces the emoji text block and the matplotlib chart.

The matplotlib figure this supersedes was the most theme-blind image the
plugin produced: green/red bars on a white canvas, identical under every kit.
Here everything comes from the kit — background, panels, typography — and the
recent-form strip encodes win/loss by *position* (above/below a rule), which
survives the monochrome kit and downscaling alike.

The handler passes in a fully computed ``MinesStats``; this module reads its
fields and never touches the database (the import below is type-checking
only, so importing this module never pulls in the DB layer either).
"""

from typing import TYPE_CHECKING

from PIL import Image

from utils import cards
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Spacer
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit

if TYPE_CHECKING:
    from ..stats_service import MinesStats

#: How many of the most recent games the form strip shows. 30 cells of 20px
#: with 4px gaps is 716px, inside the 720px panel interior.
_FORM_SLOTS = 30
_FORM_CELL_WIDTH = 20
_FORM_CELL_GAP = 4
_FORM_BAR_HEIGHT = 22


def render_stats(data: "MinesStats", kit: BaseKit | None = None) -> Image.Image:
    """Render the stats card.

    Args:
        data: Pre-computed player statistics (``total_games`` must be > 0;
            the empty case stays a text reply).
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return stats_page(data, kit).render()


def stats_page(data: "MinesStats", kit: BaseKit | None = None) -> AutoPage:
    """Build the stats page without rendering it.

    Args:
        data: Pre-computed player statistics.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()

    sections: list[Component] = [
        _summary_panel(kit, data),
        _detail_panel(kit, data),
    ]
    form = _recent_form_panel(kit, data)
    if form is not None:
        sections.append(form)

    return cards.card_page(
        kit,
        title="探险统计",
        subtitle=f"战绩 · {data.total_games} 局",
        body=VStack(sections, gap=24, align="stretch"),
    )


def _summary_panel(kit: BaseKit, data: "MinesStats") -> Component:
    """Net profit and win rate as the two big numbers, with a win-rate meter."""

    headline = HStack(
        [
            VStack(
                [
                    kit.text(
                        "净收益",
                        font_size=cards.LABEL_SIZE,
                        color=kit.muted_text_color,
                        wrap=False,
                        max_lines=1,
                    ),
                    kit.text(
                        f"{data.net_profit:+d} Pt",
                        font_size=48,
                        wrap=False,
                        max_lines=1,
                    ),
                ],
                gap=8,
                align="start",
            ),
            Frame(None, width=Fill()),
            VStack(
                [
                    kit.text(
                        "胜率",
                        font_size=cards.LABEL_SIZE,
                        color=kit.muted_text_color,
                        align="right",
                        wrap=False,
                        max_lines=1,
                    ),
                    kit.text(
                        f"{data.win_rate:.1%}",
                        font_size=48,
                        align="right",
                        wrap=False,
                        max_lines=1,
                    ),
                ],
                gap=8,
                align="end",
            ),
        ],
        gap=16,
        align="center",
    )
    rate_meter = cards.meter(
        kit,
        value=data.wins,
        total=data.total_games,
        label=f"{data.wins} 胜 / {data.total_games} 局",
    )
    return cards.panel_section(
        kit, VStack([headline, rate_meter], gap=20, align="stretch")
    )


def _detail_panel(kit: BaseKit, data: "MinesStats") -> Component:
    """The full ledger as label/value rows."""

    rows: list[Component] = [
        cards.stat_row(kit, "局数", f"{data.total_games}"),
        cards.stat_row(kit, "胜 / 负", f"{data.wins} / {data.losses}"),
        cards.stat_row(kit, "总投入", f"{data.total_wagered} Pt"),
        cards.stat_row(kit, "总赢得", f"{data.total_won} Pt"),
        cards.stat_row(kit, "总输掉", f"{data.total_lost} Pt"),
        cards.stat_row(kit, "平均下注", f"{data.avg_bet:.1f} Pt"),
        cards.stat_row(kit, "平均赢得", f"{data.avg_win:.1f} Pt"),
        cards.stat_row(kit, "平均输掉", f"{data.avg_loss:.1f} Pt"),
        cards.stat_row(kit, "最高赢", f"{data.biggest_win} Pt"),
        cards.stat_row(kit, "最高输", f"{data.biggest_loss} Pt"),
    ]
    return cards.panel_section(kit, VStack(rows, gap=14, align="stretch"))


def _recent_form_panel(kit: BaseKit, data: "MinesStats") -> Component | None:
    """Recent-form strip: wins above the rule, losses below it.

    Two geometric cues (position relative to the rule, plus the rule itself)
    and zero hue dependence, so it reads identically in the monochrome kit.
    Rounds with zero net (a cashout before any dig) leave their slot empty.
    """

    records = list(reversed(data.recent_games))[-_FORM_SLOTS:]
    if not records:
        return None

    fill_color, _ = cards.emphasis(kit)

    def bar() -> Component:
        return kit.panel(
            None,
            width=Fixed(_FORM_CELL_WIDTH),
            height=Fixed(_FORM_BAR_HEIGHT),
            fill=fill_color,
            radius=6,
        )

    def slot() -> Component:
        return Spacer(width=Fixed(_FORM_CELL_WIDTH), height=Fixed(_FORM_BAR_HEIGHT))

    top = [bar() if record.amount > 0 else slot() for record in records]
    bottom = [bar() if record.amount < 0 else slot() for record in records]

    strip = VStack(
        [
            HStack(top, gap=_FORM_CELL_GAP, align="end"),
            kit.separator(length=Fill()),
            HStack(bottom, gap=_FORM_CELL_GAP, align="start"),
        ],
        gap=6,
        align="stretch",
    )
    caption = kit.text(
        f"最近 {len(records)} 局 · 上为胜，下为负 · 右端最新",
        font_size=cards.LABEL_SIZE,
        color=kit.muted_text_color,
        wrap=False,
        max_lines=1,
    )
    return cards.panel_section(kit, VStack([strip, caption], gap=14, align="start"))
