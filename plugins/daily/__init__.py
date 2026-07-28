import time
import random

from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent

require("mailbox")
require("daily_task")

from utils import PassiveGenerator
from utils import has_no_argument  # noqa: E402
from utils.clock import bot_date
from utils.clock import bot_today  # noqa: E402
from utils.avatar import get_avatar  # noqa: E402
from utils.images import image_segment  # noqa: E402
from utils.theming import kit_for_user  # noqa: E402
from utils.identity import identity_for  # noqa: E402

from .utils import is_number  # noqa: E402
from .render import RankRow  # noqa: E402
from .render import RankData  # noqa: E402
from .render import CheckinData  # noqa: E402
from .render import CheckinTask  # noqa: E402
from .render import rank_page  # noqa: E402
from .render import checkin_page  # noqa: E402
from ..mailbox import mail_service  # noqa: E402
from ..monetary import add  # noqa: E402
from ..monetary import get  # noqa: E402
from ..monetary import set as set_balance  # noqa: E402
from ..monetary import add_xp  # noqa: E402
from ..monetary import get_user  # noqa: E402
from ..monetary import transfer  # noqa: E402
from ..monetary import get_top_users  # noqa: E402
from ..monetary import get_user_rank  # noqa: E402
from ..monetary import add_star_stickers  # noqa: E402
from ..monetary import is_using_offseason_points  # noqa: E402
from ..nickname import nickname  # noqa: E402
from ..inventory import ProfileData  # noqa: E402
from ..inventory import profile_page  # noqa: E402
from ..inventory import assemble_profile  # noqa: E402
from ..daily_task import get_today_task  # noqa: E402
from ..daily_task import daily_task_service  # noqa: E402
from ..monetary.database import get_session as get_monetary_session  # noqa: E402
from ..monetary.level_service import LEVEL_UP_STICKERS  # noqa: E402

#: Streak window: every ``STREAK_WINDOW``-th consecutive day pays the bonus.
STREAK_WINDOW = 7

#: Sticker bonus paid at the end of each streak window.
STREAK_BONUS_STICKERS = 120


@on_command(
    "info",
    aliases={"balance", "余额", "信息", "个人信息", "我的信息"},
    priority=10,
    block=True,
    rule=has_no_argument,
).handle()
async def info(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    passive_generator = PassiveGenerator(event)

    # The same card as /资料: assembly (DB) stays on the event loop thread —
    # the inventory/monetary sessions are process-global and not thread safe —
    # and only the raster is offloaded. Render failures degrade to text.
    kit = kit_for_user(user_id)
    data = assemble_profile(user_id, avatar=await get_avatar(user_id))
    try:
        image = await profile_page(data, kit).render_async()
    except Exception:
        logger.opt(exception=True).warning("info card render failed")
        await matcher.finish(
            _info_text(data) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _info_text(data: ProfileData) -> str:
    """Text fallback with the same information as the profile card."""

    lines: list[str] = []
    if data.xp_level_span > 0:
        needed = data.xp_level_span - data.xp_in_level
        lines.append(
            f"Lv.{data.identity.level} | "
            f"XP: {data.xp_in_level}/{data.xp_level_span} (还需 {needed})"
        )
    elif data.identity.level is not None:
        lines.append(f"Lv.{data.identity.level}")
    point_label = "休赛期临时 Pt" if data.offseason else "赛季 Pt"
    lines.append(f"{point_label}: {data.current_pt} Pt")
    lines.append(f"星星贴纸: {data.star_stickers}")
    if data.offseason:
        lines.append("休赛期临时 Pt 不会计入下一赛季。")
    return "\n".join(lines)


@on_command(
    "daily", aliases={"签到"}, priority=10, block=True, rule=has_no_argument
).handle()
async def handle_daily(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    passive_generator = PassiveGenerator(event)

    user = get_user(user_id)
    # Product-timezone day boundary: the streak day must flip at Beijing
    # midnight regardless of the server's timezone (utils/clock.py).
    today = bot_today()

    # Broken streak detection and duplicate check (must use old last_daily_time)
    if user.last_daily_time:
        last_date = bot_date(user.last_daily_time)
        if last_date == today:
            await matcher.finish(
                "今天已经签到过了" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        days_diff = (today - last_date).days
        if days_diff > 1:
            user.consecutive_checkins = 0

    # Mark today's check-in
    user.last_daily_time = int(time.time())

    # Shard reward (normal distribution 1-10)
    amount = max(1, min(10, round(random.gauss(5.5, 2))))
    add(user_id, amount, "daily")

    old_level = user.level
    await add_xp(user_id, amount)
    new_level = user.level

    # Update consecutive check-in
    user.consecutive_checkins += 1
    streak = user.consecutive_checkins

    # Every 7th day bonus stickers
    streak_bonus = 0
    if streak % STREAK_WINDOW == 0:
        streak_bonus = STREAK_BONUS_STICKERS
        add_star_stickers(user_id, streak_bonus, f"checkin_day_{streak}")

    # The streak/last_daily mutations used to persist only because a later
    # commit on the shared monetary session happened to fire; commit them
    # explicitly so reordering the calls above can never silently drop them.
    get_monetary_session().commit()

    task = get_today_task(user_id)
    task_row = daily_task_service.get_today_task(user_id)
    unread_mails = len(
        [mail for mail in mail_service.get_user_mails(user_id) if not mail.is_read]
    )

    data = CheckinData(
        nickname=identity_for(user_id, avatar=await get_avatar(user_id)).nickname,
        reward_pt=amount,
        balance=get(user_id),
        offseason=is_using_offseason_points(),
        streak=streak,
        window_done=(streak - 1) % STREAK_WINDOW + 1,
        window_total=STREAK_WINDOW,
        next_bonus_day=((streak - 1) // STREAK_WINDOW + 1) * STREAK_WINDOW,
        bonus_stickers=STREAK_BONUS_STICKERS,
        streak_bonus=streak_bonus,
        old_level=old_level,
        new_level=new_level,
        level_stickers=(
            (new_level - old_level) * LEVEL_UP_STICKERS
            if new_level > old_level
            else 0
        ),
        task=CheckinTask(
            name=task.name,
            description=task.description,
            reward=task.reward,
            done=bool(task_row.is_completed) if task_row is not None else False,
        ),
        unread_mails=unread_mails,
    )

    # Theme resolution and data assembly stay on the event loop thread; only
    # the raster is offloaded. The check-in is already committed, so a render
    # failure must degrade to text rather than swallow the result.
    kit = kit_for_user(user_id)
    try:
        image = await checkin_page(data, kit).render_async()
    except Exception:
        logger.opt(exception=True).warning("checkin card render failed")
        await matcher.finish(
            _checkin_text(data) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _checkin_text(data: CheckinData) -> str:
    """Text fallback with the same information as the card. No emoji."""

    lines = [f"签到成功，获得 {data.reward_pt} Pt"]
    if data.offseason:
        lines.append("当前是休赛期，本次获得的是临时 Pt，不会计入下一赛季。")
    lines.append(f"当前连续签到：{data.streak} 天")
    if data.streak_bonus:
        lines.append(
            f"连续签到 {data.streak} 天！额外获得 {data.streak_bonus} 个星星贴纸！"
        )
    if data.new_level > data.old_level:
        lines.append(
            f"升级了！Lv.{data.old_level} → Lv.{data.new_level}，"
            f"获得 {data.level_stickers} 个星星贴纸！"
        )
    if data.task is not None:
        lines.append(f"今日任务：【{data.task.name}】{data.task.description}")
        lines.append(f"奖励：{data.task.reward} 个星星贴纸")
    if data.unread_mails:
        lines.append(f"你有 {data.unread_mails} 封邮件，记得查看哦～")
    return "\n".join(lines)


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
            "转账格式错误！示例：转账 &lt;昵称&gt; 10" + passive_generator.element,
            referrer=passive_generator.event.referrer,
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
            "格式错误！示例：转账 &lt;昵称&gt; 10" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    to_user_id = nickname.get_id(to_user_nick)

    if to_user_id is None:
        await matcher.finish(
            f"Kasumi 不认识{to_user_nick}呢..." + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if to_user_id == user_id:
        await matcher.finish(
            "不能给自己转账哦！" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if amount <= 0:
        await matcher.finish(
            "转账金额必须大于 0" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if get(user_id) < amount:
        await matcher.finish(
            "余额不足！" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    transfer(user_id, to_user_id, amount, "transfer_by_command")

    await matcher.finish(
        f"转账成功，已转账 {amount} Pt 给{to_user_nick}"
        + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


# 排行/排行榜 belong to the season Pt ladder (plugins/inventory seasonrank)
# now that seasons are live; this command answers to 等级排行 only. The two
# trigger sets must stay disjoint or nonebot logs duplicated-prefix warnings.
@on_command(
    "levelrank",
    aliases={"等级排行", "等级排行榜"},
    priority=10,
    block=True,
).handle()
async def handle_levelrank(matcher: Matcher, event: MessageEvent):
    top_users = get_top_users(10)
    user_id = event.get_user_id()
    rank_info = get_user_rank(user_id)
    passive_generator = PassiveGenerator(event)

    rows = tuple(
        RankRow(
            rank=index + 1,
            name=_display_name(user.user_id),
            level=user.level,
            xp=user.xp,
        )
        for index, user in enumerate(top_users)
    )
    viewer_name = _display_name(user_id)
    viewer_row = None
    if all(user.user_id != user_id for user in top_users):
        viewer = get_user(user_id)
        viewer_row = RankRow(
            rank=rank_info.rank,
            name=viewer_name,
            level=viewer.level,
            xp=viewer.xp,
        )

    data = RankData(
        rows=rows,
        viewer=viewer_row,
        viewer_name=viewer_name,
        viewer_rank=rank_info.rank,
        xp_gap=rank_info.xp_gap,
    )

    kit = kit_for_user(user_id)
    try:
        image = await rank_page(data, kit).render_async()
    except Exception:
        logger.opt(exception=True).warning("rank card render failed")
        await matcher.finish(
            _rank_text(data) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _display_name(user_id: str) -> str:
    """Display name for a ladder row.

    Falls back to the id tail rather than the old shared ``Unknown`` string so
    rows stay distinguishable and the viewer highlight cannot collide.
    """

    name = nickname.get(user_id)
    if name:
        return str(name)
    return f"玩家{user_id[-4:]}" if len(user_id) >= 4 else f"玩家{user_id}"


def _rank_text(data: RankData) -> str:
    """Text fallback with the same information as the card."""

    lines = [f"{row.rank}. {row.name}: Lv.{row.level} (XP: {row.xp})" for row in data.rows]
    message = f"你当前的排名是第 {data.viewer_rank} 名"
    if data.viewer_rank != 1:
        if data.xp_gap > 0:
            message += f"，离上一名还差 {data.xp_gap} XP"
        else:
            message += "，与上一名相同"
    lines.append(message)
    return "\n".join(lines)


@on_command(
    "balanceset", aliases={"设置余额"}, priority=10, block=False, permission=SUPERUSER
).handle()
async def set_balance_handler(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    if event.get_user_id() not in get_driver().config.superusers:
        await matcher.finish(referrer=event.referrer)

    passive_generator = PassiveGenerator(event)

    try:
        text = arg.extract_plain_text().strip()
        user_id, amount, description = text.split()

        set_balance(user_id, int(amount), description)

        await matcher.finish(
            f"已设置用户 {user_id} 的余额为 {amount}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    except Exception:
        await matcher.finish(
            "设置余额失败，请检查参数格式：设置余额 <用户ID> <金额> <描述>"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
