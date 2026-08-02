"""The round-end result card — what a completed 一笔画 replies with.

Collapses the former three-message win sequence (board + win text, the daily
task text, the level-up text) into the final board plus this one composed
card, and makes the speed-reward math visible: base reward, the time-decay
multiplier and the birthday doubling are separate rows instead of one
pre-multiplied number the player could never reconstruct.

The handler assembles everything into :class:`OneStrokeResultData` on the
event-loop thread (ambition review #8: the personal-best comparison is one
read-only query made *before* the finished round is recorded); this module
computes nothing from a database and renders identically for the same data.
"""

from dataclasses import dataclass

from PIL import Image

from utils import cards
from plugins.render import Fill
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit


@dataclass(frozen=True)
class OneStrokeResultData:
    """Everything the result card shows, assembled by the handler.

    Attributes:
        difficulty: Difficulty label (简单 / 普通 / 困难).
        elapsed_seconds: Clear time of this round.
        base_reward: Reward before time decay (``session.reward``).
        decay_factor: The time-decay multiplier that was applied, in ``(0, 1]``.
        final_reward: Pt actually granted, after decay and any birthday
            doubling.
        balance: Pt balance after the grant.
        birthday_characters: Characters whose birthday doubled the reward;
            empty on a normal day.
        previous_best_seconds: The player's fastest clear on this difficulty
            before this round, or ``None`` for a first clear.
        is_new_record: Whether this round set a personal best (a first clear
            counts: it is the record now).
        task_name: Name of the daily task this round completed, or ``None``
            when no task completed.
        task_reward: Star stickers the completed task granted.
        old_level: Level before the XP grant, only when a level-up happened.
        new_level: Level after the XP grant, only when a level-up happened.
        level_stickers: Star stickers granted by the level-up.
    """

    difficulty: str
    elapsed_seconds: float
    base_reward: int
    decay_factor: float
    final_reward: int
    balance: int
    birthday_characters: tuple[str, ...] = ()
    previous_best_seconds: float | None = None
    is_new_record: bool = False
    task_name: str | None = None
    task_reward: int = 0
    old_level: int | None = None
    new_level: int | None = None
    level_stickers: int = 0

    @property
    def leveled_up(self) -> bool:
        """Whether this round's XP produced a level-up."""

        return (
            self.old_level is not None
            and self.new_level is not None
            and self.new_level > self.old_level
        )


def gain_entries(data: OneStrokeResultData) -> list[tuple[str, str]]:
    """``(amount, label)`` pairs for the reward strip.

    The clear reward always leads; sticker gains from the daily task and the
    level-up follow so every grant this round produced is on one strip.
    """

    gains: list[tuple[str, str]] = [(f"+{data.final_reward} Pt", "通关奖励")]
    if data.task_name is not None and data.task_reward > 0:
        gains.append((f"+{data.task_reward} 贴纸", "每日任务奖励"))
    if data.leveled_up and data.level_stickers > 0:
        gains.append((f"+{data.level_stickers} 贴纸", "升级奖励"))
    return gains


def record_text(data: OneStrokeResultData) -> str:
    """The sentence next to the 新纪录 badge."""

    if data.previous_best_seconds is None:
        return f"首次通关{data.difficulty}难度"
    return (
        f"个人最佳 {data.previous_best_seconds:.2f} 秒 → "
        f"{data.elapsed_seconds:.2f} 秒"
    )


def render_result(
    data: OneStrokeResultData,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
) -> Image.Image:
    """Render the result card.

    Args:
        data: Pre-assembled result data.
        kit: Active kit. Defaults to the BanG Dream! kit.
        identity: Player identity for the strip on top; omitted when ``None``.

    Returns:
        Rendered card.
    """

    return result_page(data, kit=kit, identity=identity).render()


def result_page(
    data: OneStrokeResultData,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
) -> AutoPage:
    """Build the result card page without rendering it.

    Args:
        data: Pre-assembled result data.
        kit: Active kit. Defaults to the BanG Dream! kit.
        identity: Player identity for the strip on top; omitted when ``None``.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()

    sections: list[Component] = []
    if identity is not None:
        sections.append(
            cards.game_identity(kit, identity, width=cards.CONTENT_WIDTH)
        )
    sections.append(cards.headline(kit, "挑战成功"))
    sections.append(cards.panel_section(kit, _settlement(kit, data)))
    extras = _extras(kit, data)
    if extras is not None:
        sections.append(cards.panel_section(kit, extras))

    return cards.card_page(
        kit,
        title="一笔画",
        subtitle=data.difficulty,
        article_title="RESULT",
        body=VStack(sections, gap=24, align="stretch"),
        owner_name=identity.nickname if identity is not None else None,
    )


def _settlement(kit: BaseKit, data: OneStrokeResultData) -> Component:
    """Time, the reward math, the gains, and the balance — one panel."""

    rows: list[Component] = []
    if data.is_new_record:
        rows.append(_record_row(kit, data))
    rows.append(
        cards.stat_row(kit, "耗时", f"{data.elapsed_seconds:.2f} 秒", value_size=26)
    )
    rows.append(cards.stat_row(kit, "基础奖励", f"{data.base_reward} Pt"))
    rows.append(cards.stat_row(kit, "速度系数", f"× {data.decay_factor:.2f}"))
    if data.birthday_characters:
        rows.append(
            cards.stat_row(
                kit, "生日加成", f"× 2 · {'和'.join(data.birthday_characters)}"
            )
        )
    rows.append(kit.separator(length=Fill()))
    rows.append(cards.gain_rows(kit, gain_entries(data)))
    rows.append(cards.stat_row(kit, "当前余额", f"{data.balance} Pt"))
    return VStack(rows, gap=18, align="stretch")


def _record_row(kit: BaseKit, data: OneStrokeResultData) -> Component:
    """Personal-best marker: a filled chip plus the comparison text.

    The record state is encoded by the chip's shape (the only filled pill in
    the panel), not by hue, so it survives the monochrome kit.
    """

    return HStack(
        [
            cards.badge(kit, "新纪录", width=116, height=40),
            Frame(
                kit.text(
                    record_text(data),
                    font_size=cards.BODY_SIZE,
                    wrap=False,
                    max_lines=1,
                ),
                width=Fill(),
                align_x="start",
                align_y="center",
            ),
        ],
        gap=14,
        align="center",
    )


def _extras(kit: BaseKit, data: OneStrokeResultData) -> Component | None:
    """Daily-task and level-up rows, or ``None`` when neither happened."""

    rows: list[Component] = []
    if data.task_name is not None:
        rows.append(
            cards.task_progress(kit, f"每日任务 · {data.task_name}", 1, 1)
        )
    if data.leveled_up:
        assert data.old_level is not None and data.new_level is not None
        rows.append(cards.level_up(kit, data.old_level, data.new_level))
    if not rows:
        return None
    return VStack(rows, gap=18, align="stretch")
