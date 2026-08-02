"""The round-end card — what 收手/全清/踩雷 settle with.

One card replaces the three-message end sequence (result text beside the
board, the daily-task notice, the level-up notice). The final revealed board
stays its own send — it is the game state — and this card carries the verdict:
a headline distinguished by shape (filled band for wins, plain for losses),
the money ledger, and the task/level rewards when they fired this round.

:class:`MinesResultData` is assembled entirely by the handler on the event
loop thread; this module computes nothing from the database. Async handlers
render via ``await result_page(...).render_async()``.

Timeouts, aborts, and mid-game corrections never reach this card — they stay
text by design.
"""

from dataclasses import dataclass

from PIL import Image

from utils import cards
from plugins.render import Fill
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit

from ..models import GameResult


@dataclass(frozen=True)
class MinesResultData:
    """Everything the round-end card shows.

    Attributes:
        outcome: How the round ended. ``TIMEOUT`` stays a text reply and
            never reaches this card.
        bet_amount: The stake paid at game start.
        payout: Amount settled back into the balance; ``0`` on a loss.
        multiplier: Final multiplier at settlement (``1.0`` before any dig).
        revealed_count: Safe cells revealed this round.
        safe_cells: Total safe cells on the board.
        mines: Number of Arisas hiding on the board.
        balance: Balance after settlement.
        task_name: Daily task completed by this round, when one fired.
        task_reward: Star stickers that task granted.
        old_level: Level before this round's XP, when the round leveled the
            player.
        new_level: Level after this round's XP, when the round leveled the
            player.
        level_stickers: Star stickers the level-up granted.
    """

    outcome: GameResult
    bet_amount: int
    payout: int
    multiplier: float
    revealed_count: int
    safe_cells: int
    mines: int
    balance: int
    task_name: str | None = None
    task_reward: int | None = None
    old_level: int | None = None
    new_level: int | None = None
    level_stickers: int | None = None

    @property
    def net(self) -> int:
        """Signed net Pt for the round."""

        return self.payout - self.bet_amount

    @property
    def positive(self) -> bool:
        """Whether this is a win-like outcome (cashout or full clear)."""

        return self.outcome in (GameResult.CASHOUT, GameResult.WIN)


#: Outcome verb per result. Win-likeness picks the headline's *shape* (filled
#: band for wins, plain text for losses) so the two read differently even in
#: the monochrome kit.
_HEADLINES = {
    GameResult.CASHOUT: "带着战利品撤退！",
    GameResult.WIN: "地下室搬空了！",
    GameResult.LOSE: "被 Arisa 逮到了",
}

_SUBTITLE_VERBS = {
    GameResult.CASHOUT: "收手",
    GameResult.WIN: "全清",
    GameResult.LOSE: "踩雷",
}


def render_result(
    data: MinesResultData,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
) -> Image.Image:
    """Render the round-end card.

    Args:
        data: Pre-assembled round data.
        kit: Active kit. Defaults to the BanG Dream! kit.
        identity: Player identity for the Tier A strip, when available.

    Returns:
        Rendered card.
    """

    return result_page(data, kit, identity=identity).render()


def result_page(
    data: MinesResultData,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
) -> AutoPage:
    """Build the round-end page without rendering it.

    Args:
        data: Pre-assembled round data.
        kit: Active kit. Defaults to the BanG Dream! kit.
        identity: Player identity for the Tier A strip, when available.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()

    sections: list[Component] = []
    if identity is not None:
        sections.append(
            cards.game_identity(
                kit,
                identity,
                width=cards.CONTENT_WIDTH,
                detail=f"押注 {data.bet_amount} Pt",
            )
        )
    sections.append(
        cards.headline(kit, _HEADLINES[data.outcome], positive=data.positive)
    )
    sections.append(_ledger_panel(kit, data))
    rewards = _rewards_panel(kit, data)
    if rewards is not None:
        sections.append(rewards)

    return cards.card_page(
        kit,
        title="探险",
        subtitle=f"{_SUBTITLE_VERBS[data.outcome]} · {data.net:+d} Pt",
        article_title="RESULT",
        show_subtitle=False,
        body=VStack(sections, gap=24, align="stretch"),
        owner_name=identity.nickname if identity is not None else None,
    )


def _ledger_panel(kit: BaseKit, data: MinesResultData) -> Component:
    """The money story: gains strip on top, the ledger rows below."""

    gains: list[tuple[str, str]] = []
    if data.payout > 0:
        gains.append((f"+{data.payout} Pt", "结算入账"))
    gains.append((f"{data.net:+d} Pt", "本局净收益"))

    rows: list[Component] = [
        cards.gain_rows(kit, gains),
        kit.separator(length=Fill()),
        cards.stat_row(kit, "押注", f"{data.bet_amount} Pt"),
    ]
    if data.positive:
        rows.append(cards.stat_row(kit, "结算倍率", f"x{data.multiplier:.2f}"))
    rows.append(
        cards.stat_row(kit, "已翻开", f"{data.revealed_count}/{data.safe_cells}")
    )
    rows.append(cards.stat_row(kit, "Arisa 数量", f"{data.mines} 个"))
    rows.append(cards.stat_row(kit, "当前余额", f"{data.balance} Pt"))
    return cards.panel_section(kit, VStack(rows, gap=16, align="stretch"))


def _rewards_panel(kit: BaseKit, data: MinesResultData) -> Component | None:
    """Task/level rewards, only when something actually fired this round."""

    rows: list[Component] = []
    stickers = 0
    if data.task_name:
        rows.append(cards.task_progress(kit, f"每日任务 · {data.task_name}", 1, 1))
        stickers += data.task_reward or 0
    if data.old_level is not None and data.new_level is not None:
        rows.append(cards.level_up(kit, data.old_level, data.new_level))
        stickers += data.level_stickers or 0
    if stickers:
        # One strip row for the stickers, labeled by the thing gained. The
        # earlier thing-plus-source labels broke the gain_rows convention and
        # read misaligned in the live test; the task and level rows above
        # already say where the stickers came from.
        rows.append(cards.gain_rows(kit, [(f"+{stickers} 张", "星星贴纸")]))
    if not rows:
        return None
    return cards.panel_section(kit, VStack(rows, gap=16, align="stretch"))
