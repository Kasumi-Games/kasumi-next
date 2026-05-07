"""Daily task plugin - assign, track and complete daily challenges."""

from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.adapters.satori import MessageEvent
from nonebot import on_command, on_message, get_driver

from utils import PassiveGenerator
from .models import DailyTaskConfig
from .database import init_database
from .service import DailyTaskService


daily_task_service = DailyTaskService()

# ========== Command: /每日任务 ==========
task_cmd = on_command("每日任务", aliases={"每日", "任务"}, priority=10, block=True)


@task_cmd.handle()
async def handle_daily_task(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    passive_generator = PassiveGenerator(event)

    # Ensure task is assigned (lazy allocation)
    task = daily_task_service.get_today_task(user_id)
    if task is None:
        task = daily_task_service.ensure_daily_task(user_id)

    if task is None:
        await matcher.finish("任务系统暂时不可用" + passive_generator.element)

    cfg = daily_task_service.task_configs.get(task.task_id)
    if not cfg:
        await matcher.finish("任务配置异常" + passive_generator.element)

    if task.is_completed:
        completed_time = ""
        if task.completed_at:
            from datetime import datetime

            completed_time = datetime.fromtimestamp(task.completed_at).strftime(
                "%H 时 %M 分"
            )
        await matcher.finish(
            f"【{cfg['name']}】{cfg['description']}\n"
            f"奖励：{cfg['reward']} 张星星贴纸\n"
            f"完成时间：{completed_time}" + passive_generator.element
        )
    else:
        await matcher.finish(
            "你还没有完成每日任务，快来完成吧！\n"
            f"【{cfg['name']}】{cfg['description']}\n"
            f"奖励：{cfg['reward']} 张星星贴纸" + passive_generator.element
        )


# ========== on_message listener: auto-assign task on first daily message ==========
message_listener = on_message(priority=99, block=False)


@message_listener.handle()
async def auto_assign_task(event: MessageEvent):
    user_id = event.get_user_id()
    daily_task_service.ensure_daily_task(user_id)


# ========== Public functions for game plugins ==========
async def check_progress(
    user_id: str,
    event_type: str,
    data: dict | None = None,
) -> str | None:
    """Check and potentially complete a daily task based on game events.

    Called by game plugins after relevant game events.
    Returns a notification message if the task was completed, None otherwise.
    """
    return await daily_task_service.check_progress(user_id, event_type, data or {})


def ensure_daily_task(user_id: str):
    """Ensure the user has a daily task assigned (for sign-in integration)."""
    return daily_task_service.ensure_daily_task(user_id)


def get_today_task(user_id: str) -> DailyTaskConfig:
    daily_task_service.ensure_daily_task(user_id)
    task = daily_task_service.get_today_task(user_id)
    assert task is not None
    return DailyTaskConfig.model_validate(daily_task_service.task_configs[task.task_id])


# Initialize database
@get_driver().on_startup
async def init():
    init_database()
    logger.info("每日任务系统初始化完成")
