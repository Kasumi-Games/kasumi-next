from nonebot import get_driver

from .database import init_database
from .models import UserRank, UserStats
from .ranking_service import (
    get_top_users,
    get_user_rank,
    get_user_stats,
)
from .user_service import (
    get_user,
    get_level,
    set_level,
    increase_level,
    decrease_level,
    get_balance as get,
    add_balance as add,
    set_balance as set,
    cost_balance as cost,
    daily_checkin as daily,
    transfer_balance as transfer,
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
]
