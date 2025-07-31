from nonebot import get_plugin_config
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.adapters.satori import MessageEvent

from .config import Config


plugin_config = get_plugin_config(Config)


@event_preprocessor
async def check_blocked(event: MessageEvent):
    whitelist = plugin_config.whitelist

    if event.platform in ["qq", "qqguild"] or event.platform.startswith("sandbox"):
        # 官方 Bot 或沙盒调试，直接放行
        return None

    if whitelist is None:
        return None

    if event.self_id == event.get_user_id():
        raise IgnoredException("Blocked for self message")

    if event.channel.id in whitelist:
        return None

    elif (
        event.member is not None
        and event.member.user is not None
        and event.member.user.id in whitelist
    ):
        return None

    elif event.guild is not None and event.guild.id in whitelist:
        return None

    raise IgnoredException("Blocked by whitelist")
