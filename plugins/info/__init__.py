from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.internal.adapter import Event

from utils import has_no_argument


@on_command(
    "info", aliases={"关于"}, priority=1, block=True, rule=has_no_argument
).handle()
async def handle_info(matcher: Matcher):
    await matcher.finish(
        "「キラキラドキドキ」的小游戏合集机器人 Kasumi!\n"
        "项目地址: Kasumi-Games/kasumi-next\n"
        "联系我们: 908979461"
    )


@on_command("id", priority=10, block=False, rule=has_no_argument).handle()
async def handle_id(event: Event, matcher: Matcher):
    await matcher.finish(f"你的 ID 是: {event.get_user_id()}")
