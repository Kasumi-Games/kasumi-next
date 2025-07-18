from typing import List
from .database import get_session
from .user_service import get_user
from .models import User, UserRank, UserStats


def get_top_users(limit: int = 10) -> List[User]:
    """Get top users by level (primary) and balance (secondary)

    Args:
        limit: Maximum number of users to return

    Returns:
        List of TopUser dataclasses with user_id, level, and balance
    """
    session = get_session()

    users = (
        session.query(User)
        .order_by(User.level.desc(), User.balance.desc())
        .limit(limit)
        .all()
    )
    return users


def get_user_rank(user_id: str) -> UserRank:
    """Get user's rank and distances to next rank/level (based on level first, then balance)

    Args:
        user_id: User ID to get rank for

    Returns:
        UserRank dataclass with rank, distance_to_next_rank, and distance_to_next_level
    """
    session = get_session()
    user = get_user(user_id)

    # Count users with higher level, or same level but higher balance
    rank = (
        session.query(User)
        .filter(
            (User.level > user.level)
            | ((User.level == user.level) & (User.balance > user.balance))
        )
        .count()
        + 1
    )

    # Get user with next higher rank (considering level first, then balance)
    next_rank_user = (
        session.query(User)
        .filter(
            (User.level > user.level)
            | ((User.level == user.level) & (User.balance > user.balance))
        )
        .order_by(User.level.asc(), User.balance.asc())
        .first()
    )

    # Calculate distance to next rank: if same level, return balance difference; otherwise 0
    if next_rank_user is not None and next_rank_user.level == user.level:
        distance_to_next_rank = next_rank_user.balance - user.balance
    else:
        distance_to_next_rank = 0

    # Get user with next higher level
    next_level_user = (
        session.query(User)
        .filter(User.level > user.level)
        .order_by(User.level.asc())
        .first()
    )

    # Calculate distance to next level
    if next_level_user is not None:
        distance_to_next_level = next_level_user.level - user.level
    else:
        distance_to_next_level = 0

    return UserRank(
        rank=rank,
        distance_to_next_rank=distance_to_next_rank,
        distance_to_next_level=distance_to_next_level,
    )


def get_user_stats(user_id: str) -> UserStats:
    """Get comprehensive user statistics

    Args:
        user_id: User ID to get stats for

    Returns:
        UserStats dataclass containing balance, level, rank, distances, and last_daily_time
    """
    user = get_user(user_id)
    rank_info = get_user_rank(user_id)

    return UserStats(
        user_id=user.user_id,
        balance=user.balance,
        level=user.level,
        rank=rank_info.rank,
        distance_to_next_rank=rank_info.distance_to_next_rank,
        distance_to_next_level=rank_info.distance_to_next_level,
        last_daily_time=user.last_daily_time,
    )
