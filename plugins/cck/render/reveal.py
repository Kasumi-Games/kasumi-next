"""The 猜卡面 round-exit reveal — one card instead of an answer text plus a
bare illustration (plus task/level notifications on a win).

Every round exit (win / bzd / timeout) previously sent the answer as
``答案是———{name}card_id: {id}`` followed by the raw full card image, and a win
appended up to two more reward messages. This card carries the full card art,
the answer as must-read text, the reward strip and the winner's identity strip
in one message. Mid-round guesses, the attempt refusal and the puzzle post
itself are untouched.

The handler assembles :class:`CckRevealData` on the event loop thread; this
module computes nothing from a database and renders through
``await reveal_page(...).render_async()``.
"""

from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
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
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.types import ImageSource
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.mewtype import MewtypeKit

#: Card art slot. ``INNER_WIDTH`` x 540 is exactly the 4:3 of bestdori's
#: 1334x1002 full card art, so ``fit="contain"`` leaves no letterbox bars.
ART_HEIGHT = 540

#: Player-facing names for bestdori card types. Unknown types pass through
#: raw rather than disappearing.
_CARD_TYPE_NAMES = {
    "initial": "初始",
    "permanent": "常驻",
    "event": "活动",
    "limited": "期间限定",
    "campaign": "联动",
    "dreamfes": "梦幻祭",
    "birthday": "生日",
    "kirafes": "闪光祭",
    "special": "特殊",
}


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
class CckRevealData:
    """Everything the reveal card shows, assembled in the handler.

    Attributes:
        outcome: ``"win"`` / ``"bzd"`` / ``"timeout"``.
        character_name: The answer; must-read.
        card_id: Bestdori card id, shown as a small ``#id`` suffix.
        card_image: Full card art source (a path, so the render image cache
            applies), or ``None`` when the art is unavailable.
        card_title: Card title (localized ``prefix``), when known.
        rarity: Card rarity 1-5, when known.
        card_type: Raw bestdori card type, when known.
        difficulty: Round difficulty label, e.g. ``easy``.
        winner: Winner identity; ``None`` unless someone won.
        winner_attempt: Which of the winner's attempts hit (1-based).
        base_amount: Pt reward before any birthday multiplier.
        final_amount: Pt actually granted.
        birthday_names: Characters whose birthday multiplied the reward.
        multiplier: Birthday multiplier actually applied (1 / 2 / 4).
        task: Daily task completed by this win, when any.
        level: Level-up triggered by this win, when any.
        owner_name: Whose theme the card renders in, for the signature.
    """

    outcome: str
    character_name: str
    card_id: str
    card_image: ImageSource | None
    card_title: str | None = None
    rarity: int | None = None
    card_type: str | None = None
    difficulty: str | None = None
    winner: PlayerIdentity | None = None
    winner_attempt: int | None = None
    base_amount: int = 0
    final_amount: int = 0
    birthday_names: tuple[str, ...] = ()
    multiplier: int = 1
    task: TaskCompletion | None = None
    level: LevelGain | None = None
    owner_name: str | None = None


def render_reveal(data: CckRevealData, kit: BaseKit | None = None) -> Image.Image:
    """Render the round-exit reveal card.

    Args:
        data: Pre-assembled reveal data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return reveal_page(data, kit).render()


def reveal_page(data: CckRevealData, kit: BaseKit | None = None) -> AutoPage:
    """Build the reveal page without rendering it.

    Args:
        data: Pre-assembled reveal data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    won = data.outcome == "win"

    sections: list[Component] = [headline(kit, _headline_text(data), positive=won)]
    if data.card_image is not None:
        sections.append(
            panel_section(
                kit,
                kit.image(
                    data.card_image,
                    width=Fixed(INNER_WIDTH),
                    height=Fixed(ART_HEIGHT),
                    fit="contain",
                    radius=12,
                ),
            )
        )
    sections.append(_answer_panel(kit, data))
    if won and data.winner is not None:
        sections.append(
            game_identity(
                kit,
                data.winner,
                width=CONTENT_WIDTH,
                detail=_attempt_text(data.winner_attempt),
            )
        )
    if won:
        sections.append(_rewards_panel(kit, data))

    return card_page(
        kit,
        title="猜卡面",
        subtitle=(
            data.difficulty
            if isinstance(kit, MewtypeKit)
            else _subtitle(data)
        ),
        article_title="ANSWER",
        body=VStack(sections, gap=18, align="stretch"),
        owner_name=data.owner_name,
    )


def _headline_text(data: CckRevealData) -> str:
    if data.outcome == "win":
        return "正解！"
    if data.outcome == "timeout":
        return "时间到"
    return "答案揭晓"


def _subtitle(data: CckRevealData) -> str:
    parts: list[str] = []
    if data.difficulty:
        parts.append(data.difficulty)
    if data.outcome == "win":
        parts.append("有人猜中了")
    elif data.outcome == "timeout":
        parts.append("没有人猜中")
    # bzd: the headline already says 答案揭晓; the subtitle keeps only the
    # difficulty. (下次再挑战吧 was removed after live feedback.)
    return " · ".join(parts)


def _attempt_text(attempt: int | None) -> str:
    return f"第 {attempt} 次答对" if attempt else "答对"


def _answer_panel(kit: BaseKit, data: CckRevealData) -> Component:
    """The answer block. The character name is the payload, so it leads at
    display size in the full text color."""

    rows: list[Component] = [
        Frame(
            kit.text(data.character_name, font_size=34, wrap=False, max_lines=1),
            width=Fixed(INNER_WIDTH),
            align_x="start",
            align_y="center",
        )
    ]
    if data.card_title:
        rows.append(
            Frame(
                kit.text(
                    data.card_title,
                    font_size=BODY_SIZE,
                    max_lines=2,
                    overflow="ellipsis",
                ),
                width=Fixed(INNER_WIDTH),
                align_x="stretch",
                align_y="center",
            )
        )
    rows.append(kit.separator(length=Fixed(INNER_WIDTH), thickness=2))
    if data.rarity:
        rows.append(stat_row(kit, "稀有度", "★" * data.rarity))
    rows.append(stat_row(kit, "卡池", _pool_text(data)))
    return panel_section(kit, VStack(rows, gap=14, align="stretch"))


def _pool_text(data: CckRevealData) -> str:
    type_name = _CARD_TYPE_NAMES.get(data.card_type or "", data.card_type or "")
    return f"{type_name} · #{data.card_id}" if type_name else f"#{data.card_id}"


def _rewards_panel(kit: BaseKit, data: CckRevealData) -> Component:
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
