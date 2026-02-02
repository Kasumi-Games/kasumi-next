from typing import Optional

from nonebot import get_driver, on_command, require
from nonebot.adapters.satori import Message, MessageEvent
from nonebot.exception import MatcherException
from nonebot.log import logger
from nonebot.params import CommandArg

require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from utils import PassiveGenerator  # noqa: E402
from .. import monetary  # noqa: E402

from .database import init_database  # noqa: E402
from .messages import Messages  # noqa: E402
from .service import (  # noqa: E402
    EnvelopeCompletionInfo,  # noqa: F401
    claim_envelope,
    create_envelope,
    expire_overdue_envelopes,
    get_active_envelopes,
)
from ..nickname import nickname  # noqa: E402


@get_driver().on_startup
async def init():
    init_database()
    logger.info("红包插件初始化完成")


@get_driver().on_startup
@scheduler.scheduled_job(id="red_envelope_expire", trigger="interval", minutes=5)
async def handle_expire_job():
    try:
        count = expire_overdue_envelopes()
        if count > 0:
            logger.info(f"已处理 {count} 个过期红包")
    except Exception as e:
        logger.exception(f"处理过期红包时发生错误: {e}", exc_info=True)


create_cmd = on_command("发红包", aliases={"红包"}, priority=10, block=True)
claim_cmd = on_command("抢红包", aliases={"领红包"}, priority=10, block=True)
list_cmd = on_command(
    "红包列表", aliases={"查看红包", "红包列表"}, priority=10, block=True
)


def _get_channel_id(event: MessageEvent) -> Optional[str]:
    if hasattr(event, "channel") and event.channel:
        return event.channel.id
    return None


def _format_duration(seconds: int) -> str:
    """Format duration in a human-readable Chinese format."""
    if seconds < 60:
        return f" {seconds} 秒"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        if secs == 0:
            return f"{minutes} 分钟"
        return f" {minutes} 分 {secs} 秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes == 0:
            return f" {hours} 小时"
        return f" {hours} 小时 {minutes} 分钟"


@create_cmd.handle()
async def handle_create(event: MessageEvent, arg: Message = CommandArg()):
    user_id = event.get_user_id()
    channel_id = _get_channel_id(event)
    if not channel_id:
        await create_cmd.finish(Messages.NOT_IN_CHANNEL)

    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    parts = text.split()
    if len(parts) < 2:
        await create_cmd.finish(Messages.CREATE_USAGE + passive_generator.element)

    try:
        amount = int(parts[-2])
        count = int(parts[-1])
        title = " ".join(parts[:-2]).strip() or "红包"
    except ValueError:
        await create_cmd.finish(Messages.CREATE_USAGE + passive_generator.element)

    if amount <= 0:
        await create_cmd.finish(Messages.INVALID_AMOUNT + passive_generator.element)
    if count <= 0:
        await create_cmd.finish(Messages.INVALID_COUNT + passive_generator.element)
    if amount < count:
        await create_cmd.finish(Messages.AMOUNT_TOO_SMALL + passive_generator.element)

    balance = monetary.get(user_id)
    if balance < amount:
        await create_cmd.finish(
            Messages.INSUFFICIENT_BALANCE.format(balance=balance)
            + passive_generator.element
        )

    try:
        monetary.cost(user_id, amount, "red_envelope_create")
        envelope = create_envelope(user_id, channel_id, title, amount, count)
        await create_cmd.finish(
            Messages.CREATE_SUCCESS.format(
                envelope_id=envelope.channel_index,
                title=title,
                amount=amount,
                count=count,
            )
            + passive_generator.element
        )
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"创建红包失败: {e}", exc_info=True)
        monetary.add(user_id, amount, "red_envelope_create_refund")
        await create_cmd.finish(Messages.CREATE_FAILED + passive_generator.element)


@claim_cmd.handle()
async def handle_claim(event: MessageEvent, arg: Message = CommandArg()):
    user_id = event.get_user_id()
    channel_id = _get_channel_id(event)
    if not channel_id:
        await claim_cmd.finish(Messages.NOT_IN_CHANNEL)

    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    channel_index = None
    if text:
        if not text.isdigit():
            await claim_cmd.finish(Messages.CLAIM_USAGE + passive_generator.element)
        channel_index = int(text)

    try:
        status, amount, completion_info = claim_envelope(
            user_id, channel_id, channel_index
        )
        if status == "no_active":
            await claim_cmd.finish(Messages.CLAIM_NO_ACTIVE + passive_generator.element)
        if status == "not_found":
            await claim_cmd.finish(Messages.CLAIM_NOT_FOUND + passive_generator.element)
        if status == "expired":
            await claim_cmd.finish(Messages.CLAIM_EXPIRED + passive_generator.element)
        if status == "empty":
            await claim_cmd.finish(Messages.CLAIM_EMPTY + passive_generator.element)
        if status == "already":
            await claim_cmd.finish(Messages.CLAIM_ALREADY + passive_generator.element)
        if status == "error":
            await claim_cmd.finish(Messages.CLAIM_FAILED + passive_generator.element)
        if status == "success":
            await claim_cmd.send(
                Messages.CLAIM_SUCCESS.format(amount=amount) + passive_generator.element
            )

            # Add completion message if this was the last claim
            if completion_info:
                creator_name = nickname.get(completion_info.creator_id) or "某人"
                lucky_king_name = nickname.get(completion_info.lucky_king_id) or "某人"
                duration_str = _format_duration(completion_info.duration_seconds)
                await claim_cmd.finish(
                    Messages.CLAIM_COMPLETE.format(
                        creator=creator_name,
                        duration=duration_str,
                        lucky_king=lucky_king_name,
                        lucky_amount=completion_info.lucky_king_amount,
                    )
                    + passive_generator.element
                )
    except MatcherException:
        raise
    except Exception as e:
        logger.error(f"抢红包时发生错误: {e}", exc_info=True)
        await claim_cmd.finish(Messages.CLAIM_FAILED + passive_generator.element)


@list_cmd.handle()
async def handle_list(event: MessageEvent):
    channel_id = _get_channel_id(event)
    if not channel_id:
        await list_cmd.finish(Messages.NOT_IN_CHANNEL)

    passive_generator = PassiveGenerator(event)
    envelopes = get_active_envelopes(channel_id)
    if not envelopes:
        await list_cmd.finish(Messages.LIST_EMPTY + passive_generator.element)

    items = []
    for envelope in envelopes:
        items.append(
            Messages.LIST_ITEM.format(
                id=envelope.channel_index,
                title=envelope.title,
                remaining_amount=envelope.remaining_amount,
                total_amount=envelope.total_amount,
                remaining_count=envelope.remaining_count,
                total_count=envelope.total_count,
            )
        )

    await list_cmd.finish(
        Messages.LIST_HEADER.format(count=len(items))
        + "\n"
        + "\n".join(items)
        + passive_generator.element
    )
