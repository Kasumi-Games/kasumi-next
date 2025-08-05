import random
from nonebot.adapters import Event
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot import on_command, get_driver
from nonebot.adapters.satori import MessageEvent, Message

from ..nickname import nickname
from .utils import is_number, get_amount_for_level
from utils import has_no_argument, PassiveGenerator
from ..monetary import (
    get,
    add,
    daily,
    transfer,
    get_top_users,
    get_user_rank,
    increase_level,
    get_user_stats,
    set as set_balance,
)


@on_command(
    "balance", aliases={"余额"}, priority=10, block=True, rule=has_no_argument
).handle()
async def balance(matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    user = get_user_stats(user_id)
    await matcher.send(f"你有 {user.level} 个星星 和 {user.balance} 个星之碎片")


@on_command(
    "daily", aliases={"签到"}, priority=10, block=True, rule=has_no_argument
).handle()
async def handle_daily(matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    if daily(user_id):
        # 使用正态分布，均值5.5，标准差2，确保在1-10范围内
        amount = max(1, min(10, round(random.gauss(5.5, 2))))
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


@on_command("upgrade", aliases={"升级", "摘星"}, priority=10, block=True).handle()
async def handle_upgrade(matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    user = get_user_stats(user_id)
    amount = get_amount_for_level(user.level + 1)
    if user.balance < amount:
        await matcher.send(f"余额不足，摘星需要 {amount} 个星之碎片")
    else:
        add(user_id, -amount, f"upgrade_{user.level + 1}")
        increase_level(user_id)
        await matcher.send(
            f"摘星成功，消耗了 {amount} 个星之碎片。你现在有 {user.level + 1} 颗星星 和 {user.balance - amount} 个星之碎片哦~"
        )


@on_command(
    "balancerank",
    aliases={"余额排行", "余额排行榜", "rank", "排行榜", "排行"},
    priority=10,
    block=True,
).handle()
async def handle_balancerank(matcher: Matcher, event: Event):
    top_users = get_top_users(10)
    user_id = event.get_user_id()
    rank_info = get_user_rank(user_id)

    # 构建排名信息
    rank_message = f"\n你当前的排名是第 {rank_info.rank} 名"

    # 添加距离信息（第一名不显示额外信息）
    if rank_info.rank != 1:
        distance_parts = []

        # 距离下一等级的等级差距
        if rank_info.distance_to_next_level > 0:
            distance_parts.append(f"{rank_info.distance_to_next_level} 个星星")

        # 距离下一名的余额差距（只在等级相同时显示）
        if rank_info.distance_to_next_rank > 0:
            distance_parts.append(f"{rank_info.distance_to_next_rank} 个星之碎片")

        # 根据差距情况组合消息
        if distance_parts:
            if len(distance_parts) == 1:
                rank_message += f"，离上一名还差 {distance_parts[0]}"
            else:
                rank_message += f"，离上一名还差 {' 和 '.join(distance_parts)}"
        else:
            # 如果两个差距都为0，说明与上一名等级和余额一样
            rank_message += "，与上一名相同"

    await matcher.send(
        "\n".join(
            [
                f"{i + 1}. {nickname.get(user.user_id) or 'Unknown'}: {user.level} 星 {user.balance} 碎片"
                for i, user in enumerate(top_users)
            ]
        )
        + rank_message
    )


@on_command(
    "balanceset", aliases={"设置余额"}, priority=10, block=False, permission=SUPERUSER
).handle()
async def set_balance_handler(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    if event.get_user_id() not in get_driver().config.superusers:
        await matcher.finish()

    try:
        text = arg.extract_plain_text().strip()
        user_id, amount, description = text.split()

        passive_generator = PassiveGenerator(event)

        set_balance(user_id, int(amount), description)

        await matcher.finish(
            f"已设置用户 {user_id} 的余额为 {amount}" + passive_generator.element
        )
    except Exception as e:
        await matcher.finish(e)
