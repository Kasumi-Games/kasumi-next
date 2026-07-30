import time
from typing import Optional

from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent

from utils.error_handler import log_error
from utils.error_handler import handle_error
from utils.error_handler import generate_error_code

require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from utils import PassiveGenerator  # noqa: E402
from utils.avatar import get_avatar  # noqa: E402
from utils.content_safety import ContentSafetyError  # noqa: E402
from utils.content_safety import ensure_safe_text  # noqa: E402
from utils.content_safety import safe_display_text  # noqa: E402
from utils.images import image_segment_async  # noqa: E402
from utils.theming import kit_for_user  # noqa: E402
from utils.identity import identity_for  # noqa: E402

from .. import monetary  # noqa: E402
from .render import ClaimRow  # noqa: E402
from .render import EnvelopeListItem  # noqa: E402
from .render import EnvelopeCreateData  # noqa: E402
from .render import EnvelopeCompletionData  # noqa: E402
from .render import list_page  # noqa: E402
from .render import create_page  # noqa: E402
from .render import completion_page  # noqa: E402
from .service import EXPIRE_SECONDS  # noqa: E402
from .service import EnvelopeCompletionInfo  # noqa: E402
from .service import claim_envelope  # noqa: E402
from .service import create_envelope  # noqa: E402
from .service import get_active_envelopes  # noqa: E402
from .service import expire_overdue_envelopes  # noqa: E402
from .database import init_database  # noqa: E402
from .messages import Messages  # noqa: E402
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
        log_error(generate_error_code(), e, context="red_envelope_expire")


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
        await create_cmd.finish(Messages.NOT_IN_CHANNEL, referrer=event.referrer)

    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    parts = text.split()
    if len(parts) < 2:
        await create_cmd.finish(
            Messages.CREATE_USAGE + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    try:
        amount = int(parts[-2])
        count = int(parts[-1])
        title = " ".join(parts[:-2]).strip() or "红包"
    except ValueError:
        await create_cmd.finish(
            Messages.CREATE_USAGE + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    try:
        ensure_safe_text(title)
    except ContentSafetyError as error:
        await create_cmd.finish(
            str(error) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if amount <= 0:
        await create_cmd.finish(
            Messages.INVALID_AMOUNT + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    if count <= 0:
        await create_cmd.finish(
            Messages.INVALID_COUNT + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    if count > 10000:
        await create_cmd.finish(
            Messages.MAX_COUNT_EXCEEDED + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    if amount < count:
        await create_cmd.finish(
            Messages.AMOUNT_TOO_SMALL + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    balance = monetary.get(user_id)
    if balance < amount:
        await create_cmd.finish(
            Messages.INSUFFICIENT_BALANCE.format(balance=balance)
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    try:
        monetary.cost(user_id, amount, "red_envelope_create")
        envelope = create_envelope(user_id, channel_id, title, amount, count)
    except MatcherException:
        raise
    except Exception as e:
        monetary.add(user_id, amount, "red_envelope_create_refund")
        code = handle_error(e, context="red_envelope_create", user_id=user_id)
        await create_cmd.finish(
            "错误码：{}\n".format(code)
            + Messages.CREATE_FAILED
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    # 红包已建好、Pt 已扣：之后的任何失败都不能再走上面的退款分支。
    # 广播创建卡片（成本纪律：整个红包只在创建与抢完时各渲染一次）。
    await _send_create_card(
        envelope.channel_index, title, amount, count, user_id, passive_generator
    )


async def _send_create_card(
    channel_index: int,
    title: str,
    amount: int,
    count: int,
    user_id: str,
    passive_generator: PassiveGenerator,
):
    """渲染并发送红包创建卡片；渲染失败时退化为原文本公告。

    主题与身份解析必须留在事件循环线程（库存/昵称的 Session 是进程级共享且
    非线程安全），``render_async`` 只把光栅化交给工作线程。卡片用创建者的
    主题渲染——这是全群都会看的广播面，发红包就是在展示自己的主题。
    """
    kit = kit_for_user(user_id)
    data = EnvelopeCreateData(
        channel_index=channel_index,
        title=title,
        total_amount=amount,
        total_count=count,
        # 缓存头像（utils/avatar.py）：拿不到时返回 None，身份条退化为首字徽章
        creator=identity_for(user_id, avatar=await get_avatar(user_id)),
        validity_text=f"{EXPIRE_SECONDS // 3600} 小时",
    )
    try:
        image = await create_page(data, kit).render_async()
    except Exception as e:
        log_error(generate_error_code(), e, context="red_envelope_create_card")
        await create_cmd.finish(
            Messages.CREATE_SUCCESS.format(
                envelope_id=channel_index,
                title=title,
                amount=amount,
                count=count,
            )
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await create_cmd.finish(
        await image_segment_async(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


@claim_cmd.handle()
async def handle_claim(event: MessageEvent, arg: Message = CommandArg()):
    user_id = event.get_user_id()
    channel_id = _get_channel_id(event)
    if not channel_id:
        await claim_cmd.finish(Messages.NOT_IN_CHANNEL, referrer=event.referrer)

    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    channel_index = None
    if text:
        if not text.isdigit():
            await claim_cmd.finish(
                Messages.CLAIM_USAGE + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        channel_index = int(text)

    try:
        status, amount, completion_info = claim_envelope(
            user_id, channel_id, channel_index
        )
        if status == "no_active":
            await claim_cmd.finish(
                Messages.CLAIM_NO_ACTIVE + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        if status == "not_found":
            await claim_cmd.finish(
                Messages.CLAIM_NOT_FOUND + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        if status == "expired":
            await claim_cmd.finish(
                Messages.CLAIM_EXPIRED + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        if status == "empty":
            await claim_cmd.finish(
                Messages.CLAIM_EMPTY + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        if status == "already":
            await claim_cmd.finish(
                Messages.CLAIM_ALREADY + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        if status == "error":
            await claim_cmd.finish(
                Messages.CLAIM_FAILED + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        if status == "success":
            # 单次抢红包保持文本（成本纪律：一句一个数字的回执配不上一次渲染）
            await claim_cmd.send(
                Messages.CLAIM_SUCCESS.format(amount=amount)
                + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

            # 最后一份被抢走：这一条播报升级为带完整账本的结算卡片
            if completion_info:
                await _send_completion_card(completion_info, passive_generator)
    except MatcherException:
        raise
    except Exception as e:
        code = handle_error(e, context="red_envelope_claim", user_id=user_id)
        await claim_cmd.finish(
            "错误码：{}\n".format(code)
            + Messages.CLAIM_FAILED
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


async def _send_completion_card(
    info: EnvelopeCompletionInfo, passive_generator: PassiveGenerator
):
    """渲染并发送红包结算卡片；渲染失败时退化为原文本播报。

    卡片用创建者的主题渲染并署名（与创建卡同一条规则：红包是创建者的广播
    面）。手气王只在这里出现——``EnvelopeCompletionInfo`` 只在最后一份被领取
    时构建，中途标手气王会与终局矛盾（一致性评审 #15）。
    """
    creator_name = _display_name(info.creator_id)
    lucky_king_name = _display_name(info.lucky_king_id)
    data = EnvelopeCompletionData(
        channel_index=info.channel_index,
        title=safe_display_text(info.title, fallback="红包"),
        total_amount=info.total_amount,
        total_count=info.total_count,
        creator_name=creator_name,
        duration_text=_format_duration(info.duration_seconds).strip(),
        lucky_king_name=lucky_king_name,
        lucky_king_amount=info.lucky_king_amount,
        claims=tuple(
            ClaimRow(
                name=_display_name(claim.user_id),
                amount=claim.amount,
                is_lucky_king=claim.user_id == info.lucky_king_id,
            )
            for claim in info.claims
        ),
    )
    kit = kit_for_user(info.creator_id)
    try:
        image = await completion_page(data, kit).render_async()
    except Exception as e:
        log_error(generate_error_code(), e, context="red_envelope_completion_card")
        await claim_cmd.finish(
            Messages.CLAIM_COMPLETE.format(
                creator=creator_name,
                duration=_format_duration(info.duration_seconds),
                lucky_king=lucky_king_name,
                lucky_amount=info.lucky_king_amount,
            )
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await claim_cmd.finish(
        await image_segment_async(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _display_name(user_id: str) -> str:
    """昵称，缺省时退化为可区分的 玩家XXXX——结算榜每一行都要能对上人。"""
    name = nickname.get(user_id)
    if name:
        return str(name)
    return f"玩家{user_id[-4:]}" if len(user_id) >= 4 else f"玩家{user_id}"


def _validity_state(remaining_seconds: int) -> tuple[str, bool]:
    """列表行的剩余有效期文本与紧迫标记（不足 1 小时算紧迫）。"""

    if remaining_seconds < 3600:
        return f"剩 {max(1, remaining_seconds // 60)} 分钟", True
    return f"剩 {remaining_seconds // 3600} 小时", False


@list_cmd.handle()
async def handle_list(event: MessageEvent):
    channel_id = _get_channel_id(event)
    if not channel_id:
        await list_cmd.finish(Messages.NOT_IN_CHANNEL, referrer=event.referrer)

    passive_generator = PassiveGenerator(event)
    envelopes = get_active_envelopes(channel_id)

    # 列表卡用请求者的主题渲染：这是玩家自己的查询面，不是创建者的广播面。
    # 主题解析必须留在事件循环线程（库存 Session 非线程安全），
    # render_async 只把光栅化交给工作线程。
    kit = kit_for_user(event.get_user_id())
    now = int(time.time())
    items = []
    for envelope in envelopes:
        validity_text, urgent = _validity_state(envelope.expires_at - now)
        items.append(
            EnvelopeListItem(
                channel_index=envelope.channel_index,
                title=safe_display_text(envelope.title, fallback="红包"),
                remaining_amount=envelope.remaining_amount,
                total_amount=envelope.total_amount,
                remaining_count=envelope.remaining_count,
                total_count=envelope.total_count,
                validity_text=validity_text,
                urgent=urgent,
            )
        )

    try:
        image = await list_page(items, kit).render_async()
    except Exception as e:
        # 渲染失败退化为原文本列表；空列表退化为原文本提示。
        log_error(generate_error_code(), e, context="red_envelope_list_card")
        if not envelopes:
            await list_cmd.finish(
                Messages.LIST_EMPTY + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        lines = [
            Messages.LIST_ITEM.format(
                id=envelope.channel_index,
                title=safe_display_text(envelope.title, fallback="红包"),
                remaining_amount=envelope.remaining_amount,
                total_amount=envelope.total_amount,
                remaining_count=envelope.remaining_count,
                total_count=envelope.total_count,
            )
            for envelope in envelopes
        ]
        await list_cmd.finish(
            Messages.LIST_HEADER.format(count=len(lines))
            + "\n"
            + "\n".join(lines)
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    await list_cmd.finish(
        await image_segment_async(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )
