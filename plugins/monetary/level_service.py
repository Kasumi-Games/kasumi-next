"""XP and level calculation service."""

from math import floor
from typing import Optional

from nonebot.log import logger

from .database import get_session
from .models import User
from .star_sticker_service import add_star_stickers

LEVEL_UP_STICKERS = 120


def xp_per_level(n: int) -> int:
    """XP needed to go from level n-1 to level n."""
    return floor(100 * 1.15 ** (n - 2) + 1e-9)


def total_xp_for_level(n: int) -> int:
    """Total XP needed to reach level n."""
    if n <= 1:
        return 0
    return sum(xp_per_level(i) for i in range(2, n + 1))


def level_for_xp(xp: int) -> int:
    """Given total XP, calculate the current level."""
    level = 1
    while total_xp_for_level(level + 1) <= xp:
        level += 1
    return level


def xp_to_next_level(xp: int) -> tuple[int, int]:
    """Return (xp_needed_for_next_level, total_xp_at_next_level)."""
    current_level = level_for_xp(xp)
    next_level_total = total_xp_for_level(current_level + 1)
    xp_needed = next_level_total - xp
    return xp_needed, next_level_total


async def add_xp(
    user_id: str,
    amount: int,
) -> Optional[str]:
    """Add XP to a user, automatically handling level-ups.

    Returns a level-up notification message if the user leveled up,
    or None if no level-up occurred.
    """
    session = get_session()
    user = session.query(User).filter(User.user_id == user_id).first()

    if not user:
        logger.warning(f"User {user_id} not found for XP add")
        return None

    old_level = user.level
    new_xp = user.xp + amount
    new_level = level_for_xp(new_xp)

    user.xp = new_xp
    user.level = new_level
    session.commit()

    levels_gained = list(range(old_level + 1, new_level + 1))

    if levels_gained:
        # Grant star stickers for level-ups
        stickers = (new_level - old_level) * LEVEL_UP_STICKERS
        add_star_stickers(user_id, stickers, f"level_up_{old_level + 1}_to_{new_level}")
        return (
            f"🎉 升级了！Lv.{old_level} → Lv.{new_level}\n获得 {stickers} 个星星贴纸！"
        )

    return None


def admin_set_xp(user_id: str, xp: int) -> None:
    """Admin direct XP set (recalculates level, no notification)."""
    session = get_session()
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        return
    user.xp = xp
    user.level = max(1, level_for_xp(xp))
    session.commit()
