from nonebot import on_command
from nonebot.matcher import Matcher


@on_command("info", aliases={"关于"}, priority=1, block=True).handle()
async def handle_info(matcher: Matcher):
    await matcher.finish(
        "「キラキラドキドキ」的小游戏合集机器人 Kasumi!\n"
        "项目地址: https://github.com/Kasumi-Games/kasumi-next\n"
        "联系我们: 666808414"
    )
