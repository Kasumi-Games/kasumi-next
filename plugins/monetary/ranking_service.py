from typing import List
from .database import get_session
from .user_service import get_user
from .models import User, UserRank, UserStats


def get_top_users(limit: int = 10) -> List[User]:
    """Get top users by level (primary) and xp (secondary)

    Args:
        limit: Maximum number of users to return

    Returns:
        List of User objects
    """
    session = get_session()

    users = (
        session.query(User)
        .order_by(User.level.desc(), User.xp.desc())
        .limit(limit)
        .all()
    )
    return users


def get_user_rank(user_id: str) -> UserRank:
    """Get user's rank and XP gap to next rank

    Args:
        user_id: User ID to get rank for

    Returns:
        UserRank dataclass with rank and xp_gap
    """
    session = get_session()
    user = get_user(user_id)

    # Count users with higher level, or same level but higher xp
    rank = (
        session.query(User)
        .filter(
            (User.level > user.level)
            | ((User.level == user.level) & (User.xp > user.xp))
        )
        .count()
        + 1
    )

    # Get user with next higher rank
    next_rank_user = (
        session.query(User)
        .filter(
            (User.level > user.level)
            | ((User.level == user.level) & (User.xp > user.xp))
        )
        .order_by(User.level.asc(), User.xp.asc())
        .first()
    )

    xp_gap = (next_rank_user.xp - user.xp) if next_rank_user else 0

    return UserRank(rank=rank, xp_gap=xp_gap)


def get_user_stats(user_id: str) -> UserStats:
    """Get comprehensive user statistics

    Args:
        user_id: User ID to get stats for

    Returns:
        UserStats dataclass containing balance, level, xp, star_stickers, rank, and last_daily_time
    """
    user = get_user(user_id)
    rank_info = get_user_rank(user_id)

    return UserStats(
        user_id=user.user_id,
        balance=user.balance,
        level=user.level,
        xp=user.xp,
        star_stickers=user.star_stickers,
        rank=rank_info.rank,
        xp_gap=rank_info.xp_gap,
        last_daily_time=user.last_daily_time,
    )
