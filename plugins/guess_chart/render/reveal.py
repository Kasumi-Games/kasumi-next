"""The 猜谱面 round-exit reveal — one card instead of an answer text plus a
trailing jacket image (plus task/level notifications on a win).

Every round exit (win / bzd / 不知道 / timeout) previously sent the answer as
text and then the jacket as a separate message — on a win the jacket arrived
*fourth*, after the daily-task and level-up notifications. This card carries
the jacket, the song identity (title + difficulty as must-read), the reward
strip and the winner's identity strip in one message. The chart-image puzzle
post, hints and every mid-round refusal are untouched.

The handler assembles :class:`GuessChartRevealData` on the event loop thread;
this module computes nothing from a database and renders through
``await reveal_page(...).render_async()``.
"""

from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import CONTENT_WIDTH
from utils.cards import headline
from utils.cards import level_up
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import gain_rows
from utils.cards import game_identity
from utils.cards import panel_section
from utils.cards import task_progress
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.types import ImageSource
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.mewtype import MewtypeKit

#: Jacket display size. Bestdori jackets are square; 280px leaves a
#: 416px text column inside the 720px panel for the song identity.
JACKET_SIZE = 280


@dataclass(frozen=True)
class TaskCompletion:
    """A daily task this win completed.

    Attributes:
        name: Task display name from the task config.
        reward: Star stickers the completion granted.
    """

    name: str
    reward: int


@dataclass(frozen=True)
class LevelGain:
    """A level-up this win triggered.

    Attributes:
        old_level: Level before the XP grant.
        new_level: Level after the XP grant.
        stickers: Star stickers granted for the level-up.
    """

    old_level: int
    new_level: int
    stickers: int


@dataclass(frozen=True)
class GuessChartRevealData:
    """Everything the reveal card shows, assembled in the handler.

    Attributes:
        outcome: ``"win"`` / ``"bzd"`` / ``"timeout"``.
        song_name: The answer; must-read.
        band_name: Band the song belongs to.
        difficulty: Chart difficulty key (``easy`` … ``special``); must-read.
        play_level: Chart level, when known.
        bpm: Main BPM, when known.
        notes: Note count, when known.
        pool_size: How many songs the puzzle was drawn from — what the
            reward is computed from.
        hints_used: Hints consumed this round (0-3).
        jacket: Jacket image, or ``None`` when it could not be decoded.
        winner: Winner identity; ``None`` unless someone won.
        base_amount: Pt reward before any birthday multiplier.
        final_amount: Pt actually granted.
        birthday_names: Characters whose birthday multiplied the reward.
        multiplier: Birthday multiplier actually applied (1 / 2).
        task: Daily task completed by this win, when any.
        level: Level-up triggered by this win, when any.
        owner_name: Whose theme the card renders in, for the signature.
    """

    outcome: str
    song_name: str
    band_name: str
    difficulty: str
    play_level: int | None = None
    bpm: int | None = None
    notes: int | None = None
    pool_size: int = 0
    hints_used: int = 0
    jacket: ImageSource | None = None
    winner: PlayerIdentity | None = None
    base_amount: int = 0
    final_amount: int = 0
    birthday_names: tuple[str, ...] = ()
    multiplier: int = 1
    task: TaskCompletion | None = None
    level: LevelGain | None = None
    owner_name: str | None = None


def render_reveal(
    data: GuessChartRevealData, kit: BaseKit | None = None
) -> Image.Image:
    """Render the round-exit reveal card.

    Args:
        data: Pre-assembled reveal data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return reveal_page(data, kit).render()


def reveal_page(
    data: GuessChartRevealData, kit: BaseKit | None = None
) -> AutoPage:
    """Build the reveal page without rendering it.

    Args:
        data: Pre-assembled reveal data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    won = data.outcome == "win"

    sections: list[Component] = [
        headline(kit, _headline_text(data), positive=won),
        _song_panel(kit, data),
    ]
    if won and data.winner is not None:
        sections.append(
            game_identity(kit, data.winner, width=CONTENT_WIDTH, detail="答对")
        )
    if won:
        sections.append(_rewards_panel(kit, data))

    return card_page(
        kit,
        title="猜谱面",
        subtitle=(
            _mewtype_detail(data)
            if isinstance(kit, MewtypeKit)
            else _subtitle(data)
        ),
        article_title="ANSWER",
        body=VStack(sections, gap=18, align="stretch"),
        owner_name=data.owner_name,
    )


def _headline_text(data: GuessChartRevealData) -> str:
    if data.outcome == "win":
        return "正解！"
    if data.outcome == "timeout":
        return "时间到"
    return "答案揭晓"


def _subtitle(data: GuessChartRevealData) -> str:
    if data.outcome == "win":
        hints = f"用了 {data.hints_used} 条提示" if data.hints_used else "没有用提示"
        return f"有人猜中了 · {hints}"
    if data.outcome == "timeout":
        return "没有人猜中"
    return "要再试一次吗"


def _mewtype_detail(data: GuessChartRevealData) -> str | None:
    """Keep only result metadata not already stated by the headline or body."""

    if data.outcome != "win":
        return None
    return f"{data.hints_used} 条提示" if data.hints_used else "无提示"


def _song_panel(kit: BaseKit, data: GuessChartRevealData) -> Component:
    """Jacket beside the song identity. Title and difficulty are the answer,
    so both stay in the full text color at display sizes."""

    info: list[Component] = [
        kit.text(data.song_name, font_size=32, max_lines=2, overflow="ellipsis"),
        kit.text(data.band_name, font_size=BODY_SIZE, wrap=False, max_lines=1),
        kit.separator(length=Fill(), thickness=2),
        kit.text(_difficulty_text(data), font_size=28, wrap=False, max_lines=1),
    ]
    stats = _stats_text(data)
    if stats:
        info.append(kit.text(stats, font_size=LABEL_SIZE, wrap=False, max_lines=1))
    if data.pool_size > 0:
        info.append(
            kit.text(
                f"候选池 {data.pool_size} 首",
                font_size=LABEL_SIZE,
                wrap=False,
                max_lines=1,
            )
        )

    info_column = Frame(
        VStack(info, gap=12, align="stretch"),
        width=Fill(),
        align_x="stretch",
        align_y="center",
    )

    if data.jacket is None:
        return panel_section(kit, info_column)
    return panel_section(
        kit,
        HStack(
            [
                kit.image(
                    data.jacket,
                    width=Fixed(JACKET_SIZE),
                    height=Fixed(JACKET_SIZE),
                    fit="cover",
                    radius=16,
                ),
                info_column,
            ],
            gap=24,
            align="center",
        ),
    )


def _difficulty_text(data: GuessChartRevealData) -> str:
    text = data.difficulty.upper()
    if data.play_level is not None:
        text += f" · LV.{data.play_level}"
    return text


def _stats_text(data: GuessChartRevealData) -> str:
    parts: list[str] = []
    if data.bpm is not None:
        parts.append(f"BPM {data.bpm}")
    if data.notes is not None:
        parts.append(f"{data.notes} NOTES")
    return " · ".join(parts)


def _rewards_panel(kit: BaseKit, data: GuessChartRevealData) -> Component:
    """The reward strip plus the task/level rows a win used to send as two
    extra messages."""

    gains: list[tuple[str, str]] = [(f"+{data.final_amount} Pt", "答对奖励")]
    if data.task is not None:
        # The task's name lives in the task_progress row below; the gain label
        # stays a short reward name like its siblings (house convention).
        gains.append((f"+{data.task.reward} 贴纸", "每日任务奖励"))
    if data.level is not None:
        gains.append((f"+{data.level.stickers} 贴纸", "升级奖励"))

    rows: list[Component] = [gain_rows(kit, gains)]
    if data.multiplier > 1 and data.birthday_names:
        rows.append(
            stat_row(
                kit,
                "生日加成",
                f"×{data.multiplier} · {'和'.join(data.birthday_names)}",
            )
        )
    if data.task is not None or data.level is not None:
        rows.append(kit.separator(length=Fixed(INNER_WIDTH), thickness=2))
    if data.task is not None:
        rows.append(task_progress(kit, f"每日任务 · {data.task.name}", 1, 1))
    if data.level is not None:
        rows.append(level_up(kit, data.level.old_level, data.level.new_level))
    return panel_section(kit, VStack(rows, gap=14, align="stretch"))
