import re
import contextlib
from typing import Dict, Any
from nonebot.log import logger
from nonebot import on_message, require
from nonebot.adapters.satori import MessageEvent, Bot

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from utils import is_qq_bot  # noqa: E402

from .manager import PassiveManager  # noqa: E402


passive_manager = PassiveManager()

scheduler.add_job(passive_manager.clear_timeout_data, "interval", minutes=1)


@on_message(rule=is_qq_bot, priority=-1, block=False).handle()
async def handle_message(event: MessageEvent):
    await passive_manager.add_event(event)


@Bot.on_calling_api
async def _(bot: Bot, api: str, data: Dict[str, Any]):
    with contextlib.suppress(Exception):
        if bot.platform not in ["qq", "qqguild"]:
            # Only for QQ platform
            return None

        if api != "message_create":
            return None

        # 已存在 passive 标签，不再添加
        if re.search(r"<qq:passive\s+[^>]*?\/?>", data["content"]):
            logger.debug("Already has passive tag, skip")
            return None

        passive_data = passive_manager.get_available_data(api, data)

        if passive_data is None:
            logger.warning(
                f"No available passive data, failed to send passive message: {data}"
            )
            raise Exception("No available passive data")

        data["content"] += (
            "<qq:passive "
            + f'id="{passive_data.message_id}" '
            + f'seq="{passive_data.seq}"/>'
        )

        logger.debug(
            f'Send passive message: <qq:passive id="{passive_data.message_id}" seq="{passive_data.seq}"/>'
        )
