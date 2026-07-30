"""
邮箱系统插件 - 为玩家提供邮件和奖励功能
"""

import time
from typing import Optional

from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.exception import MatcherException
from nonebot.permission import SUPERUSER
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent

from utils.error_handler import log_error
from utils.error_handler import handle_error
from utils.error_handler import generate_error_code

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")

from arclet.alconna.action import append  # noqa: E402
from nonebot_plugin_alconna import Args  # noqa: E402
from nonebot_plugin_alconna import Option  # noqa: E402
from nonebot_plugin_alconna import Alconna  # noqa: E402
from nonebot_plugin_alconna import Arparma  # noqa: E402
from nonebot_plugin_alconna import Subcommand  # noqa: E402
from nonebot_plugin_alconna import CommandMeta  # noqa: E402
from nonebot_plugin_alconna import on_alconna  # noqa: E402
from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from utils import PassiveGenerator  # noqa: E402
from utils.clock import format_ts
from utils.content_safety import ensure_safe_text  # noqa: E402
from utils.images import image_segment_async  # noqa: E402
from utils.theming import kit_for_user  # noqa: E402

from .models import ServiceMail  # noqa: E402
from .render import mail_page  # noqa: E402
from .render import inbox_page  # noqa: E402
from .render import claim_all_page  # noqa: E402
from .service import MailService  # noqa: E402
from .service import claim_all_mails  # noqa: E402
from .database import init_database  # noqa: E402
from ..inventory.models import ItemAmount  # noqa: E402
from .scheduled_service import ScheduledMailService  # noqa: E402
from ..inventory.service import grant_many  # noqa: E402
from ..inventory.service import parse_item_amount  # noqa: E402
from ..inventory.service import display_item_amount  # noqa: E402

#: 触发一键领取的参数写法
CLAIM_KEYWORDS = {"领取", "一键领取", "全部领取", "claim", "claimall"}


# 初始化数据库
@get_driver().on_startup
async def init():
    """初始化邮箱系统"""
    init_database()
    logger.info("邮箱系统初始化完成")


# 创建服务实例
mail_service = MailService()
scheduled_service = ScheduledMailService()


# 定时任务
@get_driver().on_startup
@scheduler.scheduled_job(id="mailbox_cleanup", trigger="cron", hour=3, minute=0)
async def cleanup_expired_mails():
    """每天凌晨3点清理过期邮件"""
    try:
        expired_count = mail_service.cleanup_expired_mails()
        if expired_count > 0:
            logger.info(f"已清理 {expired_count} 封过期邮件")
    except Exception as e:
        log_error(generate_error_code(), e, context="mailbox_cleanup")


@get_driver().on_startup
@scheduler.scheduled_job(id="process_scheduled_mails", trigger="interval", seconds=5)
async def process_scheduled_mails():
    """每5分钟检查并发送到期的定时邮件"""
    try:
        processed_count = scheduled_service.process_due_mails()
        if processed_count > 0:
            logger.info(f"已发送 {processed_count} 封定时邮件")
    except Exception as e:
        log_error(generate_error_code(), e, context="mailbox_scheduler")


# 邮箱命令
mailbox_cmd = on_command("mail", aliases={"邮箱", "邮件"}, priority=10, block=True)


@mailbox_cmd.handle()
async def handle_mailbox(event: MessageEvent, arg: Message = CommandArg()):
    """处理邮箱相关命令"""
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()

    passive_generator = PassiveGenerator(event)

    try:
        if not text:
            await send_inbox(user_id, passive_generator)
        if text.lower() in CLAIM_KEYWORDS:
            await send_claim_all(user_id, passive_generator)
        await send_mail_detail(user_id, text, passive_generator)
    except MatcherException:
        raise
    except Exception as e:
        code = handle_error(e, context="mailbox_view", user_id=user_id)
        await mailbox_cmd.finish(
            f"打开邮箱失败\n错误码：{code}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


async def send_inbox(user_id: str, passive_generator: PassiveGenerator):
    """渲染并发送邮箱列表卡片"""
    # 主题解析必须留在事件循环线程：库存 Session 是进程级共享且非线程安全，
    # 而 render_async 会把光栅化交给工作线程。
    kit = kit_for_user(user_id)
    mails = mail_service.get_user_mails(user_id)
    image = await inbox_page(mails, kit).render_async()

    await mailbox_cmd.finish(
        await image_segment_async(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


async def send_claim_all(user_id: str, passive_generator: PassiveGenerator):
    """一键领取所有带附件的未读邮件并发送汇总卡片"""
    kit = kit_for_user(user_id)
    outcome = claim_all_mails(mail_service, user_id)
    image = await claim_all_page(outcome, kit).render_async()

    await mailbox_cmd.finish(
        await image_segment_async(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


async def send_mail_detail(
    user_id: str, text: str, passive_generator: PassiveGenerator
):
    """读取指定邮件（编号或 M<id> 代码），领取附件并发送详情卡片"""
    mails = mail_service.get_user_mails(user_id)
    mail = select_mail(mails, text)

    if mail is None:
        await mailbox_cmd.finish(
            select_error_text(text, len(mails)) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if time.time() > mail.expire_time.timestamp():
        await mailbox_cmd.finish(
            "这封邮件已经过期了！" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    # 先发放再标记已读，与批量领取保持同一顺序和同一幂等键
    results = []
    if not mail.is_read:
        results = grant_many(
            user_id,
            [
                ItemAmount(
                    attachment.item_id,
                    attachment.quantity,
                    attachment.scope_type or None,
                    attachment.scope_id or None,
                )
                for attachment in mail.attachments
            ],
            reason=f"mail_reward_{mail.id}",
            source_type="mail",
            source_id=str(mail.id),
            idempotency_key=f"mail:{mail.id}",
        )

    mail_service.read_mail(user_id, mail.id)

    # 玩家理解的是邮箱里的序号（/邮件 <编号>），不是数据库 id——详情页
    # 因此展示序号。M<id> 代码仍然被 select_mail 接受，但不再显示。
    ordinal = next(
        (index for index, item in enumerate(mails, 1) if item is mail), None
    )

    kit = kit_for_user(user_id)
    image = await mail_page(mail, results, kit, ordinal=ordinal).render_async()

    await mailbox_cmd.finish(
        await image_segment_async(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def select_mail(mails: list[ServiceMail], text: str) -> Optional[ServiceMail]:
    """按序号或 M<id> 代码选中一封邮件

    序号是唯一展示给玩家的写法（邮箱列表、详情页、领取明细都用它）。
    M<id> 代码不再显示在任何卡片上，但仍然被接受，让旧消息里的代码
    不会突然失效。M 前缀让两者不会互相误认。

    Args:
        mails: 用户邮件列表
        text: 用户输入的参数

    Returns:
        Optional[ServiceMail]: 选中的邮件，无法解析或越界时返回 None
    """

    token = text.strip().lstrip("#").upper()

    if token.startswith("M") and token[1:].isdigit():
        mail_id = int(token[1:])
        return next((mail for mail in mails if mail.id == mail_id), None)

    if not token.isdigit():
        return None

    index = int(token) - 1
    if 0 <= index < len(mails):
        return mails[index]
    return None


def select_error_text(text: str, total: int) -> str:
    """选不中邮件时的纯文本提示

    保持文本：错误提示必须便宜且可复制，不值得一次渲染加一次上传。
    """

    if total == 0:
        return "你的邮箱是空的呢~"

    token = text.strip().lstrip("#").upper()
    if token.isdigit() or (token.startswith("M") and token[1:].isdigit()):
        return f"邮件编号无效，当前有 {total} 封邮件（1-{total}）"
    return f"请输入有效的邮件编号！当前有 {total} 封邮件（1-{total}）"


# schedulemail add -r all -w +1m -e 1 -k 10 -t "This Is A Test Mail Title" -c "Oh no"
# 定时邮件管理命令 - 使用 Alconna 进行高级命令解析
schedule_alc = Alconna(
    "schedulemail",
    Subcommand(
        "send",
        Option(
            "-r|--recipients",
            Args["recipients", str],
            help_text="接收者 (all 或 user1,user2,user3)",
        ),
        Option("-e|--expire", Args["expire_days", int], help_text="过期天数 (1-30)"),
        Option("-k|--kakeras", Args["star_kakeras", int], help_text="赛季积分数量"),
        Option(
            "-s|--stickers", Args["star_stickers", int], help_text="星星贴纸奖励数量"
        ),
        Option(
            "-i|--item",
            Args["item", str],
            action=append,
            help_text="附件物品 item_id:数量，可多次提供",
        ),
        Option("-t|--title", Args["title", str], help_text="邮件标题"),
        Option("-c|--content", Args["content", str], help_text="邮件内容"),
        help_text="立即发送邮件",
    ),
    Subcommand(
        "add",
        Option(
            "-r|--recipients",
            Args["recipients", str],
            help_text="接收者 (all 或 user1,user2,user3)",
        ),
        Option(
            "-w|--when",
            Args["time", str],
            help_text="预定时间 ('2024-01-15 18:00' 或 '+1h')",
        ),
        Option("-e|--expire", Args["expire_days", int], help_text="过期天数 (1-30)"),
        Option("-k|--kakeras", Args["star_kakeras", int], help_text="Pt奖励数量"),
        Option(
            "-s|--stickers", Args["star_stickers", int], help_text="星星贴纸奖励数量"
        ),
        Option(
            "-i|--item",
            Args["item", str],
            action=append,
            help_text="附件物品 item_id:数量，可多次提供",
        ),
        Option("-t|--title", Args["title", str], help_text="邮件标题"),
        Option("-c|--content", Args["content", str], help_text="邮件内容"),
        Option("--name", Args["name", str], help_text="自定义邮件名称（可选）"),
        help_text="创建定时邮件",
    ),
    Subcommand("list", help_text="查看所有定时邮件列表"),
    Subcommand("info", Args["name", str], help_text="查看指定邮件的详细信息"),
    Subcommand(
        "edit",
        Args["name", str],
        Option("-t|--title", Args["new_title", str], help_text="新标题"),
        Option("-c|--content", Args["new_content", str], help_text="新内容"),
        Option("-w|--when", Args["new_time", str], help_text="新预定时间"),
        Option("-k|--kakeras", Args["new_kakeras", int], help_text="新Pt数量"),
        Option("-s|--stickers", Args["new_stickers", int], help_text="新星星贴纸数量"),
        Option(
            "-i|--item",
            Args["new_item", str],
            action=append,
            help_text="新增附件物品 item_id:数量",
        ),
        Option("-e|--expire", Args["new_expire", int], help_text="新过期天数"),
        Option("-r|--recipients", Args["new_recipients", str], help_text="新接收者"),
        help_text="修改定时邮件",
    ),
    Subcommand("delete", Args["name", str], help_text="删除指定的定时邮件"),
    meta=CommandMeta(description="定时邮件管理系统"),
)

schedule_mail_cmd = on_alconna(
    schedule_alc,
    aliases={"定时邮件"},
    priority=10,
    block=True,
    permission=SUPERUSER,
    use_cmd_start=True,
)


@schedule_mail_cmd.assign("send")
async def handle_alconna_send(event: MessageEvent, result: Arparma):
    """处理 Alconna send 命令"""
    if event.get_user_id() not in get_driver().config.superusers:
        await schedule_mail_cmd.finish(referrer=event.referrer)

    passive_generator = PassiveGenerator(event)

    try:
        other_args = result.other_args
        recipients = other_args.get("recipients")
        expire_days = other_args.get("expire_days", 7)
        star_kakeras = other_args.get("star_kakeras", 0)
        star_stickers = other_args.get("star_stickers", 0)
        attachments = parse_item_args(other_args.get("item"))
        title = other_args.get("title")
        content = other_args.get("content")

        if not all([recipients, expire_days is not None, title, content]):
            await schedule_mail_cmd.finish(
                "参数不完整！请使用: /schedulemail send -r <接收者> -e <过期天数> "
                "-i <item_id:数量> -t <标题> -c <内容>"
                + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        await send_mail_now(
            event,
            recipients,
            expire_days,
            star_kakeras,
            star_stickers,
            attachments,
            title,
            content,
        )
    except MatcherException:
        raise
    except Exception as e:
        code = handle_error(
            e, context="mailbox_alconna_send", user_id=event.get_user_id()
        )
        await schedule_mail_cmd.finish(
            f"发送邮件失败\n错误码：{code}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


@schedule_mail_cmd.assign("add")
async def handle_alconna_add(event: MessageEvent, result: Arparma):
    """处理 Alconna add 命令"""
    if event.get_user_id() not in get_driver().config.superusers:
        await schedule_mail_cmd.finish(referrer=event.referrer)

    passive_generator = PassiveGenerator(event)

    try:
        # 提取参数
        other_args = result.other_args
        recipients = other_args.get("recipients")
        time_str = other_args.get("time")
        expire_days = other_args.get("expire_days")
        star_kakeras = other_args.get("star_kakeras", 0)
        star_stickers = other_args.get("star_stickers", 0)
        attachments = parse_item_args(other_args.get("item"))
        title = other_args.get("title")
        content = other_args.get("content")
        name = other_args.get("name")  # 可选参数

        # 验证必要参数
        if not all(
            [
                recipients,
                time_str,
                expire_days is not None,
                star_kakeras is not None,
                title,
                content,
            ]
        ):
            await schedule_mail_cmd.finish(
                "参数不完整！请使用: /schedulemail add -r <接收者> -w <时间> -e <过期天数> -k <Pt> -s <星星贴纸> -t <标题> -c <内容>"
                + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        await create_scheduled_mail(
            event,
            recipients,
            time_str,
            expire_days,
            star_kakeras,
            star_stickers,
            attachments,
            title,
            content,
            name,
        )
    except MatcherException:
        raise
    except Exception as e:
        code = handle_error(
            e, context="mailbox_alconna_add", user_id=event.get_user_id()
        )
        await schedule_mail_cmd.finish(
            f"创建定时邮件失败\n错误码：{code}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


@schedule_mail_cmd.assign("list")
async def handle_alconna_list(event: MessageEvent):
    """处理 Alconna list 命令"""
    if event.get_user_id() not in get_driver().config.superusers:
        await schedule_mail_cmd.finish(referrer=event.referrer)
    await handle_schedule_list(event)


@schedule_mail_cmd.assign("info")
async def handle_alconna_info(event: MessageEvent, result: Arparma):
    """处理 Alconna info 命令"""
    if event.get_user_id() not in get_driver().config.superusers:
        await schedule_mail_cmd.finish(referrer=event.referrer)

    passive_generator = PassiveGenerator(event)

    name = result.query("info.name")
    if not name:
        await schedule_mail_cmd.finish(
            "请提供邮件名称！" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await handle_schedule_info(event, name)


@schedule_mail_cmd.assign("edit")
async def handle_alconna_edit(event: MessageEvent, result: Arparma):
    """处理 Alconna edit 命令"""
    if event.get_user_id() not in get_driver().config.superusers:
        await schedule_mail_cmd.finish(referrer=event.referrer)

    passive_generator = PassiveGenerator(event)

    other_args = result.other_args
    name = other_args.get("name")
    if not name:
        await schedule_mail_cmd.finish(
            "请提供邮件名称！" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    # 检查哪些字段需要更新
    updates = {}
    if new_title := other_args.get("new_title"):
        updates["title"] = new_title
    if new_content := other_args.get("new_content"):
        updates["content"] = new_content
    if new_time := other_args.get("new_time"):
        updates["time"] = new_time
    # 星星奖励用 is not None 判断：-k 0 / -s 0 是「清掉这项奖励」的合法
    # 编辑，真值判断会把 0 静默丢掉，_sync_star_attachment 的删行分支
    # 就永远走不到。
    if (new_kakeras := other_args.get("new_kakeras")) is not None:
        updates["kakeras"] = new_kakeras
    if (new_stickers := other_args.get("new_stickers")) is not None:
        updates["stickers"] = new_stickers
    if new_item := other_args.get("new_item"):
        updates["item"] = new_item
    if new_expire := other_args.get("new_expire"):
        updates["expire"] = new_expire
    if new_recipients := other_args.get("new_recipients"):
        updates["recipients"] = new_recipients

    if not updates:
        await schedule_mail_cmd.finish(
            "请至少提供一个要修改的字段！" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    await handle_schedule_edit_alconna(event, name, updates)


@schedule_mail_cmd.assign("delete")
async def handle_alconna_delete(event: MessageEvent, result: Arparma):
    """处理 Alconna delete 命令"""
    if event.get_user_id() not in get_driver().config.superusers:
        await schedule_mail_cmd.finish(referrer=event.referrer)

    passive_generator = PassiveGenerator(event)

    other_args = result.other_args
    name = other_args.get("name")
    if not name:
        await schedule_mail_cmd.finish(
            "请提供邮件名称！" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await handle_schedule_delete(event, name)


async def send_mail_now(
    event: MessageEvent,
    recipients: str,
    expire_days: int,
    star_kakeras: int,
    star_stickers: int,
    attachments: list[ItemAmount],
    title: str,
    content: str,
):
    """立即发送邮件的通用函数"""
    passive_generator = PassiveGenerator(event)

    try:
        ensure_safe_text(title)
        ensure_safe_text(content)
        if expire_days < 1 or expire_days > 30:
            await schedule_mail_cmd.finish(
                "过期天数必须在1-30之间！" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        if star_kakeras < 0 or star_stickers < 0:
            await schedule_mail_cmd.finish(
                "奖励数量不能为负数！" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        if recipients.lower() == "all":
            mail_id = mail_service.send_broadcast_mail(
                title=title,
                content=content,
                star_kakeras=star_kakeras,
                star_stickers=star_stickers,
                attachments=attachments,
                expire_days=expire_days,
                sender_id=event.get_user_id(),
            )
            target_info = "全体用户"
        else:
            mail_id = 0
            recipient_ids = [uid.strip() for uid in recipients.split(",") if uid.strip()]
            if not recipient_ids:
                await schedule_mail_cmd.finish(
                    "接收者不能为空！" + passive_generator.element,
                    referrer=passive_generator.event.referrer,
                )

            for recipient_id in recipient_ids:
                mail_id = mail_service.send_mail(
                    recipient_id=recipient_id,
                    title=title,
                    content=content,
                    star_kakeras=star_kakeras,
                    star_stickers=star_stickers,
                    attachments=attachments,
                    expire_days=expire_days,
                    sender_id=event.get_user_id(),
                )
            target_info = f"{len(recipient_ids)} 位用户"

        await schedule_mail_cmd.finish(
            f"✅ 邮件已发送给{target_info}，最后邮件ID: {mail_id}"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    except MatcherException:
        raise
    except ValueError as e:
        await schedule_mail_cmd.finish(
            f"参数错误: {str(e)}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    except Exception as e:
        code = handle_error(e, context="mailbox_send", user_id=event.get_user_id())
        await schedule_mail_cmd.finish(
            f"发送失败\n错误码：{code}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


async def create_scheduled_mail(
    event: MessageEvent,
    recipients: str,
    time_str: str,
    expire_days: int,
    star_kakeras: int,
    star_stickers: int,
    attachments: list[ItemAmount],
    title: str,
    content: str,
    name: str = None,
):
    """创建定时邮件的通用函数"""
    passive_generator = PassiveGenerator(event)

    try:
        ensure_safe_text(title)
        ensure_safe_text(content)
        # 解析时间
        scheduled_time = parse_time_string(time_str)
        if scheduled_time is None:
            await schedule_mail_cmd.finish(
                "时间格式错误！支持格式: '2024-01-15 18:00' 或 '+1h' (+1小时后)"
                + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        # 验证参数
        if expire_days < 1 or expire_days > 30:
            await schedule_mail_cmd.finish(
                "过期天数必须在1-30之间！" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        if star_kakeras < 0:
            await schedule_mail_cmd.finish(
                "Pt数量不能为负数！" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        # 创建定时邮件
        mail_id = scheduled_service.create_scheduled_mail(
            recipients=recipients,
            title=title,
            content=content,
            scheduled_time=scheduled_time,
            star_kakeras=star_kakeras,
            star_stickers=star_stickers,
            attachments=attachments,
            expire_days=expire_days,
            created_by=event.get_user_id(),
            name=name,  # 可以为 None，会自动生成
        )

        # 获取生成的邮件名称
        mails = scheduled_service.get_scheduled_mails(include_sent=True)
        created_mail = next((m for m in mails if m.id == mail_id), None)

        time_str_formatted = format_ts(scheduled_time, "%Y-%m-%d %H:%M:%S")

        name_info = f" (ID: {created_mail.name})" if created_mail else ""
        await schedule_mail_cmd.finish(
            f"✅ 定时邮件创建成功{name_info}！预定发送时间: {time_str_formatted}"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    except MatcherException:
        raise
    except ValueError as e:
        await schedule_mail_cmd.finish(
            f"参数错误: {str(e)}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    except Exception as e:
        code = handle_error(e, context="mailbox_create", user_id=event.get_user_id())
        await schedule_mail_cmd.finish(
            f"创建失败\n错误码：{code}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


async def handle_schedule_list(event: MessageEvent):
    """处理列出定时邮件"""
    passive_generator = PassiveGenerator(event)

    mails = scheduled_service.get_scheduled_mails(include_sent=False)

    if not mails:
        await schedule_mail_cmd.finish(
            "📭 当前没有待发送的定时邮件。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    mail_list = []
    current_time = int(time.time())

    for mail in mails:
        status = "⏰ 待发送"
        if mail.scheduled_time <= current_time:
            status = "🔥 已到期"

        time_str = format_ts(mail.scheduled_time, "%m-%d %H:%M")
        reward_info = f" (+{mail.star_kakeras})" if mail.star_kakeras > 0 else ""
        if mail.attachments:
            reward_info = (
                " ("
                + "，".join(
                    "+" + display_item_amount(attachment.item_id, attachment.quantity)
                    for attachment in mail.attachments
                )
                + ")"
            )

        mail_list.append(
            f"{status} {mail.name}: {mail.title}{reward_info} (预定: {time_str})"
        )

    result = f"📋 定时邮件列表 ({len(mails)}封):\n" + "\n".join(mail_list)
    result += "\n\n使用 '/schedulemail info <名称>' 查看详情"

    await schedule_mail_cmd.finish(
        result + passive_generator.element, referrer=passive_generator.event.referrer
    )


async def handle_schedule_info(event: MessageEvent, name: str):
    """处理查看邮件详情"""
    passive_generator = PassiveGenerator(event)

    mail = scheduled_service.get_scheduled_mail_by_name(name)

    if not mail:
        await schedule_mail_cmd.finish(
            f"❌ 找不到名为 '{name}' 的定时邮件。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    status = "✅ 已发送" if mail.is_sent else "⏰ 待发送"
    scheduled_time_str = format_ts(mail.scheduled_time, "%Y-%m-%d %H:%M:%S")
    created_time_str = format_ts(mail.created_at, "%Y-%m-%d %H:%M:%S")

    info = f"""📧 定时邮件详情

名称: {mail.name}
状态: {status}
接收者: {mail.recipients}
标题: {mail.title}
内容: {mail.content}
Pt: {mail.star_kakeras}
星星贴纸: {mail.star_stickers}
附件: {format_scheduled_attachments(mail)}
过期天数: {mail.expire_days}
预定时间: {scheduled_time_str}
创建时间: {created_time_str}
创建者: {mail.created_by}"""

    if mail.is_sent and mail.sent_at:
        sent_time_str = format_ts(mail.sent_at, "%Y-%m-%d %H:%M:%S")
        info += f"\n实际发送时间: {sent_time_str}"

    await schedule_mail_cmd.finish(
        info + passive_generator.element, referrer=passive_generator.event.referrer
    )


async def handle_schedule_edit_alconna(event: MessageEvent, name: str, updates: dict):
    """处理编辑邮件（Alconna 版本）"""
    passive_generator = PassiveGenerator(event)

    mail = scheduled_service.get_scheduled_mail_by_name(name)
    if not mail:
        await schedule_mail_cmd.finish(
            f"❌ 找不到名为 '{name}' 的定时邮件。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if mail.is_sent:
        await schedule_mail_cmd.finish(
            f"❌ 邮件 '{name}' 已发送，无法修改。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    try:
        updated_fields = []

        for field, new_value in updates.items():
            success = False

            if field == "title":
                success = scheduled_service.update_scheduled_mail(name, title=new_value)
                updated_fields.append(f"标题: {new_value}")
            elif field == "content":
                success = scheduled_service.update_scheduled_mail(
                    name, content=new_value
                )
                updated_fields.append(f"内容: {new_value[:20]}...")
            elif field == "time":
                new_time = parse_time_string(new_value)
                if new_time is None:
                    await schedule_mail_cmd.finish(
                        f"时间格式错误: {new_value}" + passive_generator.element,
                        referrer=passive_generator.event.referrer,
                    )
                success = scheduled_service.update_scheduled_mail(
                    name, scheduled_time=new_time
                )
                time_str = format_ts(new_time, "%Y-%m-%d %H:%M:%S")
                updated_fields.append(f"时间: {time_str}")
            elif field == "kakeras":
                kakeras = int(new_value)
                if kakeras < 0:
                    await schedule_mail_cmd.finish(
                        "Pt数量不能为负数！" + passive_generator.element,
                        referrer=passive_generator.event.referrer,
                    )
                success = scheduled_service.update_scheduled_mail(
                    name, star_kakeras=kakeras
                )
                updated_fields.append(f"Pt: {kakeras}")
            elif field == "stickers":
                stickers = int(new_value)
                if stickers < 0:
                    await schedule_mail_cmd.finish(
                        "星星贴纸数量不能为负数！" + passive_generator.element,
                        referrer=passive_generator.event.referrer,
                    )
                success = scheduled_service.update_scheduled_mail(
                    name, star_stickers=stickers
                )
                updated_fields.append(f"星星贴纸: {stickers}")
            elif field == "item":
                attachments = parse_item_args(new_value)
                success = True
                for attachment in attachments:
                    success = scheduled_service.add_attachment(name, attachment)
                    if not success:
                        break
                    updated_fields.append(
                        "附件: "
                        + display_item_amount(attachment.item_id, attachment.quantity)
                    )
            elif field == "expire":
                expire_days = int(new_value)
                if expire_days < 1 or expire_days > 30:
                    await schedule_mail_cmd.finish(
                        "过期天数必须在1-30之间！" + passive_generator.element,
                        referrer=passive_generator.event.referrer,
                    )
                success = scheduled_service.update_scheduled_mail(
                    name, expire_days=expire_days
                )
                updated_fields.append(f"过期天数: {expire_days}")
            elif field == "recipients":
                success = scheduled_service.update_scheduled_mail(
                    name, recipients=new_value
                )
                updated_fields.append(f"接收者: {new_value}")

            if not success:
                await schedule_mail_cmd.finish(
                    f"❌ 更新字段 '{field}' 失败。" + passive_generator.element,
                    referrer=passive_generator.event.referrer,
                )

        await schedule_mail_cmd.finish(
            f"✅ 已更新定时邮件 '{name}':\n"
            + "\n".join(updated_fields)
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    except MatcherException:
        raise
    except ValueError as e:
        await schedule_mail_cmd.finish(
            f"参数格式错误: {str(e)}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    except Exception as e:
        code = handle_error(e, context="mailbox_edit", user_id=event.get_user_id())
        await schedule_mail_cmd.finish(
            f"编辑失败\n错误码：{code}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


async def handle_schedule_delete(event: MessageEvent, name: str):
    """处理删除邮件"""
    passive_generator = PassiveGenerator(event)

    success = scheduled_service.delete_scheduled_mail(name)

    if success:
        await schedule_mail_cmd.finish(
            f"✅ 已删除定时邮件 '{name}'。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    else:
        await schedule_mail_cmd.finish(
            f"❌ 找不到名为 '{name}' 的定时邮件。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


def parse_time_string(time_str: str) -> Optional[int]:
    """
    解析时间字符串

    支持格式:
    - "2024-01-15 18:00" (绝对时间)
    - "+1h" (+1小时后)
    - "+30m" (+30分钟后)
    - "+1d" (+1天后)

    Returns:
        Optional[int]: Unix时间戳，解析失败返回None
    """
    try:
        if time_str.startswith("+"):
            # 相对时间
            current_time = int(time.time())
            time_part = time_str[1:]

            if time_part.endswith("m"):
                # 分钟
                minutes = int(time_part[:-1])
                return current_time + (minutes * 60)
            elif time_part.endswith("h"):
                # 小时
                hours = int(time_part[:-1])
                return current_time + (hours * 3600)
            elif time_part.endswith("d"):
                # 天
                days = int(time_part[:-1])
                return current_time + (days * 86400)
        else:
            # 绝对时间
            if len(time_str.split()) == 2:
                # "2024-01-15 18:00"
                time_obj = time.strptime(time_str, "%Y-%m-%d %H:%M")
                return int(time.mktime(time_obj))
            elif len(time_str.split()) == 1:
                # "2024-01-15" (默认00:00)
                time_obj = time.strptime(time_str + " 00:00", "%Y-%m-%d %H:%M")
                return int(time.mktime(time_obj))

        return None
    except (ValueError, IndexError):
        return None


def parse_item_args(value) -> list[ItemAmount]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    items: list[ItemAmount] = []
    for raw in values:
        for part in str(raw).split(","):
            part = part.strip()
            if part:
                items.append(parse_item_amount(part))
    return items


def format_scheduled_attachments(mail) -> str:
    if not mail.attachments:
        return "无"
    return "，".join(
        display_item_amount(attachment.item_id, attachment.quantity)
        for attachment in mail.attachments
    )
