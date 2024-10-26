import random
from nonebot.adapters import Event
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot import require, on_command, get_driver
from nonebot.adapters.satori import MessageEvent, Message

require("nonebot_plugin_localstore")


from ..nickname import nickname
from utils import has_no_argument, PassiveGenerator

from .utils import is_number
from .data_source import (
    get,
    add,
    User,
    daily,
    session,
    get_user,
    transfer,
    init_database,
)


@get_driver().on_startup
async def init():
    global session
    init_database()
    from .data_source import session


@on_command(
    "balance", aliases={"余额"}, priority=10, block=True, rule=has_no_argument
).handle()
async def balance(matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    await matcher.send(f"你还有 {get(user_id)} 个星之碎片")


@on_command(
    "daily", aliases={"签到"}, priority=10, block=True, rule=has_no_argument
).handle()
async def handle_daily(matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    if daily(user_id):
        amount = random.randint(1, 10)
        add(user_id, amount, "daily")
        await matcher.send(f"签到成功，获得 {amount} 个星之碎片")
    else:
        await matcher.send("今天已经签到过了")


@on_command("transfer", aliases={"转账"}, priority=10, block=True).handle()
async def handle_transfer(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()

    passive_generator = PassiveGenerator(event)

    to_user_segs = text.split(" ")
    if len(to_user_segs) != 2:
        await matcher.finish(
            "转账格式错误！示例：转账 &lt;昵称&gt; 10" + passive_generator.element
        )

    to_user_nick = (
        to_user_segs[0] if not is_number(to_user_segs[0]) else to_user_segs[1]
    )
    try:
        amount = (
            int(to_user_segs[0]) if is_number(to_user_segs[0]) else int(to_user_segs[1])
        )
    except ValueError:
        await matcher.finish(
            "格式错误！示例：转账 &lt;昵称&gt; 10" + passive_generator.element
        )

    to_user_id = nickname.get_id(to_user_nick)

    if to_user_id is None:
        await matcher.finish(
            f"Kasumi 不认识{to_user_nick}呢..." + passive_generator.element
        )

    if to_user_id == user_id:
        await matcher.finish("不能给自己转账哦！" + passive_generator.element)

    if amount <= 0:
        await matcher.finish("转账金额必须大于 0" + passive_generator.element)

    if get(user_id) < amount:
        await matcher.finish("余额不足！" + passive_generator.element)

    transfer(user_id, to_user_id, amount, "transfer_by_command")

    await matcher.finish(
        f"转账成功，已转账 {amount} 个星之碎片给{to_user_nick}"
        + passive_generator.element
    )


@on_command(
    "balancerank", aliases={"余额排行", "余额排行榜"}, priority=10, block=True
).handle()
async def handle_balancerank(matcher: Matcher, event: Event):
    users = session.query(User).order_by(User.balance.desc()).limit(10).all()
    user_id = event.get_user_id()
    user = get_user(user_id)
    rank = session.query(User).filter(User.balance > user.balance).count() + 1
    # 离上一名的距离
    previous_user = (
        session.query(User)
        .filter(User.balance > user.balance)
        .order_by(User.balance.asc())
        .first()
    )
    distance = previous_user.balance - user.balance if previous_user is not None else 0
    await matcher.send(
        "\n".join(
            [
                f"{i+1}. {nickname.get(user.user_id) or 'Unknown'}: {user.balance} 个星之碎片"
                for i, user in enumerate(users)
            ]
        )
        + f"\n你当前的排名是第 {rank} 名"
        + (f"，离上一名还差 {distance} 个星之碎片" if rank != 1 else "")
    )
