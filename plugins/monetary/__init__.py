from nonebot import get_driver

from .models import UserRank
from .models import UserStats
from .database import init_database
from .user_service import get_user
from .user_service import get_level
from .user_service import set_level
from .user_service import add_balance as add
from .user_service import get_balance as get
from .user_service import set_balance as set
from .user_service import cost_balance as cost
from .user_service import daily_checkin as daily
from .user_service import get_all_users
from .user_service import decrease_level
from .user_service import increase_level
from .user_service import transfer_balance as transfer
from .user_service import is_using_offseason_points
from .level_service import add_xp
from .level_service import admin_set_xp
from .level_service import level_for_xp
from .level_service import xp_per_level
from .level_service import xp_to_next_level
from .level_service import total_xp_for_level
from .ranking_service import get_top_users
from .ranking_service import get_user_rank
from .ranking_service import get_user_stats
from .transaction_service import get_user_transactions
from .star_sticker_service import add_star_stickers
from .star_sticker_service import get_star_stickers
from .star_sticker_service import admin_add_stickers
from .star_sticker_service import cost_star_stickers


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
    "is_using_offseason_points",
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
