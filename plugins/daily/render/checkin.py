"""The check-in card — what ``/签到`` replies with.

Collapses the old fan-out (the assembled check-in text plus a separate
level-up message) into one themed card: outcome headline, the reward strip,
the streak meter toward the next 7-day sticker bonus, today's task, and a
level-up row only when the level actually changed.

No database access here: the handler assembles :class:`CheckinData` on the
event loop thread and passes it in, and only the raster is offloaded via
``await checkin_page(...).render_async()``. Every string routed into the card
is CJK + ASCII — the bundled font has no emoji glyphs, so the party-popper
emoji the old text carried must never reach this module.
"""

from dataclasses import dataclass

from PIL import Image

from utils.cards import LABEL_SIZE
from utils.cards import meter
from utils.cards import headline
from utils.cards import level_up
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import gain_rows
from utils.cards import panel_section
from utils.cards import task_progress
from plugins.render import Fill
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit


@dataclass(frozen=True)
class CheckinTask:
    """Today's daily task, as the check-in card shows it.

    Attributes:
        name: Task name.
        description: What the player has to do.
        reward: Sticker reward on completion.
        done: Whether the task is already completed today.
    """

    name: str
    description: str
    reward: int
    done: bool


@dataclass(frozen=True)
class CheckinData:
    """Everything the check-in card shows, assembled by the handler.

    Attributes:
        nickname: Player display name for the subtitle.
        reward_pt: Pt granted by this check-in.
        balance: Pt balance after the grant.
        offseason: Whether the Pt is offseason temporary Pt.
        streak: Consecutive check-in days including today.
        window_done: Position inside the current streak window (1-based).
        window_total: Streak window length (the 7-day bonus cycle).
        next_bonus_day: Streak day that pays the next window bonus.
        bonus_stickers: Sticker size of the window bonus.
        streak_bonus: Stickers granted today by the streak (0 unless the
            window bonus fired).
        old_level: Level before this check-in's XP.
        new_level: Level after this check-in's XP.
        level_stickers: Stickers granted by level-ups today (0 when none).
        task: Today's task, or ``None`` when the task system is unavailable.
        unread_mails: Unread mail count for the notice line.
    """

    nickname: str
    reward_pt: int
    balance: int
    offseason: bool
    streak: int
    window_done: int
    window_total: int
    next_bonus_day: int
    bonus_stickers: int
    streak_bonus: int
    old_level: int
    new_level: int
    level_stickers: int
    task: CheckinTask | None
    unread_mails: int = 0


def render_checkin(data: CheckinData, kit: BaseKit | None = None) -> Image.Image:
    """Render the check-in card.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return checkin_page(data, kit).render()


def checkin_page(data: CheckinData, kit: BaseKit | None = None) -> AutoPage:
    """Build the check-in page without rendering it.

    Handlers use this so the tree is built on the event loop thread while only
    the raster is offloaded to ``render_async``.

    Args:
        data: Pre-assembled card data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    sections: list[Component] = [
        headline(kit, "签到成功"),
        panel_section(kit, _rewards(kit, data)),
        panel_section(kit, _streak(kit, data)),
    ]
    if data.task is not None:
        sections.append(panel_section(kit, _task(kit, data.task)))
    return card_page(
        kit,
        title="签到",
        subtitle=f"第 {data.streak} 天 · {data.nickname}",
        body=VStack(sections, gap=24, align="stretch"),
        footer=_notices(kit, data),
    )


def _rewards(kit: BaseKit, data: CheckinData) -> Component:
    """Reward strip, optional level-up row, and the resulting balance."""

    gains: list[tuple[str, str]] = [(f"+{data.reward_pt} Pt", "签到奖励")]
    if data.streak_bonus > 0:
        gains.append(
            (f"+{data.streak_bonus} 星星贴纸", f"连续签到 {data.streak} 天奖励")
        )
    if data.level_stickers > 0:
        gains.append((f"+{data.level_stickers} 星星贴纸", "升级奖励"))

    rows: list[Component] = [gain_rows(kit, gains)]
    if data.new_level > data.old_level:
        rows.append(level_up(kit, data.old_level, data.new_level))
    rows.append(kit.separator(length=Fill()))
    rows.append(
        stat_row(
            kit,
            "休赛期临时 Pt" if data.offseason else "赛季 Pt",
            f"{data.balance} Pt",
        )
    )
    return VStack(rows, gap=16, align="stretch")


def _streak(kit: BaseKit, data: CheckinData) -> Component:
    """Streak count plus the meter toward the next window bonus.

    The meter label always states the numbers — the fill/track boundary is the
    first thing a chat client's downscale destroys.
    """

    if data.window_done >= data.window_total:
        label = (
            f"{data.window_done}/{data.window_total} · "
            f"本轮 {data.bonus_stickers} 星星贴纸已到账"
        )
    else:
        label = (
            f"{data.window_done}/{data.window_total} · "
            f"第 {data.next_bonus_day} 天奖励 {data.bonus_stickers} 星星贴纸"
        )
    return VStack(
        [
            stat_row(kit, "连续签到", f"{data.streak} 天"),
            meter(
                kit,
                value=data.window_done,
                total=data.window_total,
                label=label,
            ),
        ],
        gap=14,
        align="stretch",
    )


def _task(kit: BaseKit, task: CheckinTask) -> Component:
    """Today's task: the shared task row plus its description line."""

    return VStack(
        [
            kit.text(
                "今日任务",
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            ),
            task_progress(kit, task.name, 1 if task.done else 0, 1),
            kit.text(
                f"{task.description} · 奖励 {task.reward} 星星贴纸",
                font_size=LABEL_SIZE,
                max_lines=2,
                overflow="ellipsis",
            ),
        ],
        gap=12,
        align="stretch",
    )


def _notices(kit: BaseKit, data: CheckinData) -> Component | None:
    """Conditional notice lines: offseason warning, unread mail.

    Both are content the player must read, so full text color.
    """

    lines: list[str] = []
    if data.offseason:
        lines.append("本次获得的是休赛期临时 Pt，不会计入下一赛季")
    if data.unread_mails > 0:
        lines.append(f"你有 {data.unread_mails} 封未读邮件 · 发送 /邮箱 查看")
    if not lines:
        return None
    return VStack(
        [
            kit.text(line, font_size=LABEL_SIZE, wrap=False, max_lines=1)
            for line in lines
        ],
        gap=8,
        align="start",
    )
