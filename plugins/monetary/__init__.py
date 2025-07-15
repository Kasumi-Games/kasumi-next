from nonebot import get_driver

from .monetary import (
    get as get,
    add as add,
    set as set,
    cost as cost,
    daily as daily,
    transfer as transfer,
    get_user as get_user,
    get_top_users as get_top_users,
    get_user_rank as get_user_rank,
    init_database as init_database,
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
    "init_database",
]
