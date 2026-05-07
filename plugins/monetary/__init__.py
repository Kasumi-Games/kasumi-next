from nonebot import get_driver

from .database import init_database
from .models import UserRank, UserStats
from .ranking_service import (
    get_top_users,
    get_user_rank,
    get_user_stats,
)
from .transaction_service import get_user_transactions
from .user_service import (
    get_user,
    get_level,
    set_level,
    get_all_users,
    increase_level,
    decrease_level,
    get_balance as get,
    add_balance as add,
    set_balance as set,
    cost_balance as cost,
    daily_checkin as daily,
    transfer_balance as transfer,
)
from .level_service import (
    add_xp,
    xp_per_level,
    level_for_xp,
    admin_set_xp,
    xp_to_next_level,
    total_xp_for_level,
)
from .star_sticker_service import (
    add_star_stickers,
    get_star_stickers,
    cost_star_stickers,
    admin_add_stickers,
)


@get_driver().on_startup
async def init():
    init_database()


__all__ = [
    "get",
    "add",
    "set",
    "cost",
    "daily",
    "transfer",
    "get_user",
    "get_all_users",
    "get_top_users",
    "get_user_rank",
    "get_user_stats",
    "get_level",
    "set_level",
    "increase_level",
    "decrease_level",
    "init_database",
    "UserRank",
    "UserStats",
    "get_user_transactions",
    "add_xp",
    "xp_per_level",
    "total_xp_for_level",
    "level_for_xp",
    "xp_to_next_level",
    "admin_set_xp",
    "add_star_stickers",
    "get_star_stickers",
    "cost_star_stickers",
    "admin_add_stickers",
]
