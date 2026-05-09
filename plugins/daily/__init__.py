import time
import random
from datetime import datetime

from nonebot import require
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot import on_command, get_driver
from nonebot.adapters.satori import MessageEvent, Message

require("mailbox")
require("daily_task")

from .utils import is_number  # noqa: E402
from ..nickname import nickname  # noqa: E402
from ..mailbox import mail_service  # noqa: E402
from ..daily_task import get_today_task  # noqa: E402
from utils import has_no_argument, PassiveGenerator  # noqa: E402
from ..monetary import (  # noqa: E402
    get,
    add,
    add_xp,
    transfer,
    get_user,
    get_top_users,
    get_user_rank,
    xp_to_next_level,
    add_star_stickers,
    total_xp_for_level,
    set as set_balance,
)


@on_command(
    "info",
    aliases={"balance", "余额", "信息", "个人信息", "我的信息"},
    priority=10,
    block=True,
    rule=has_no_argument,
).handle()
async def info(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    user = get_user(user_id)
    passive_generator = PassiveGenerator(event)

    xp_needed, next_level_total = xp_to_next_level(user.xp)
    current_level_base = total_xp_for_level(user.level)
    progress_xp = user.xp - current_level_base
    level_xp_range = next_level_total - current_level_base

    await matcher.send(
        f"Lv.{user.level} | XP: {progress_xp}/{level_xp_range} (还需 {xp_needed})\n"
        f"星之碎片: {user.balance}\n"
        f"星星贴纸: {user.star_stickers}" + passive_generator.element
    )


@on_command(
    "daily", aliases={"签到"}, priority=10, block=True, rule=has_no_argument
).handle()
async def handle_daily(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    passive_generator = PassiveGenerator(event)

    user = get_user(user_id)
    today = datetime.now().date()

    # Broken streak detection and duplicate check (must use old last_daily_time)
    if user.last_daily_time:
        last_date = datetime.fromtimestamp(user.last_daily_time).date()
        if last_date == today:
            await matcher.finish("今天已经签到过了" + passive_generator.element)
        days_diff = (today - last_date).days
        if days_diff > 1:
            user.consecutive_checkins = 0

    # Mark today's check-in
    user.last_daily_time = int(time.time())

    # Shard reward (normal distribution 1-10)
    amount = max(1, min(10, round(random.gauss(5.5, 2))))
    add(user_id, amount, "daily")
    level_msg = await add_xp(user_id, amount)

    # Update consecutive check-in
    user.consecutive_checkins += 1

    msg = f"签到成功，获得 {amount} 个星之碎片\n"
    msg += f"当前连续签到：{user.consecutive_checkins} 天\n"

    # Every 7th day bonus stickers
    if user.consecutive_checkins % 7 == 0:
        add_star_stickers(user_id, 120, f"checkin_day_{user.consecutive_checkins}")
        msg += (
            f"🎉 连续签到 {user.consecutive_checkins} 天！额外获得 120 个星星贴纸！\n"
        )

    task = get_today_task(user_id)
    msg += f"今日任务：【{task.name}】{task.description}\n"
    msg += f"奖励：{task.reward} 个星星贴纸\n"

    if mails := [
        mail for mail in mail_service.get_user_mails(user_id) if not mail.is_read
    ]:
        msg += f"你有 {len(mails)} 封邮件，记得查看哦～\n"

    await matcher.send(msg + passive_generator.element)
    if level_msg:
        await matcher.send(level_msg + passive_generator.element)
    await matcher.finish()


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
    "levelrank",
    aliases={"等级排行", "等级排行榜", "rank", "排行榜", "排行"},
    priority=10,
    block=True,
).handle()
async def handle_levelrank(matcher: Matcher, event: MessageEvent):
    top_users = get_top_users(10)
    user_id = event.get_user_id()
    rank_info = get_user_rank(user_id)
    passive_generator = PassiveGenerator(event)

    rank_message = f"\n你当前的排名是第 {rank_info.rank} 名"

    if rank_info.rank != 1:
        if rank_info.xp_gap > 0:
            rank_message += f"，离上一名还差 {rank_info.xp_gap} XP"
        else:
            rank_message += "，与上一名相同"

    await matcher.send(
        "\n".join(
            [
                f"{i + 1}. {nickname.get(user.user_id) or 'Unknown'}: Lv.{user.level} (XP: {user.xp}) "
                for i, user in enumerate(top_users)
            ]
        )
        + rank_message
        + passive_generator.element
    )


@on_command(
    "balanceset", aliases={"设置余额"}, priority=10, block=False, permission=SUPERUSER
).handle()
async def set_balance_handler(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    if event.get_user_id() not in get_driver().config.superusers:
        await matcher.finish()

    passive_generator = PassiveGenerator(event)

    try:
        text = arg.extract_plain_text().strip()
        user_id, amount, description = text.split()

        set_balance(user_id, int(amount), description)

        await matcher.finish(
            f"已设置用户 {user_id} 的余额为 {amount}" + passive_generator.element
        )
    except Exception:
        await matcher.finish(
            "设置余额失败，请检查参数格式：设置余额 <用户ID> <金额> <描述>"
            + passive_generator.element
        )
