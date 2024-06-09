from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters import Bot, Message


def escape_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


plugin_data = {
    "help": {
        "description": "显示帮助信息",
        "usage": {
            "help": "显示帮助信息",
            "help 插件名": "显示特定插件的用法",
        },
    },
    "星之碎片": {
        "description": "Kasumi 的货币系统",
        "usage": {
            "余额|balance": "查看余额",
            "转账|transfer <@用户> <数量>": "转账",
            "签到|daily": "每日签到",
        }
    },
    "猜谱面": {
        "description": "猜谱面小游戏",
        "usage": {
            "猜谱面|cpm": "开始猜谱面",
            "猜谱面|cpm <难度>": "开始猜谱面，难度可选为 easy, normal, hard, expert, special，支持缩写为 ez, nm, hd, ex, sp",
            "<歌曲名称|ID>": "猜指定歌曲的谱面",
            "提示": "在猜谱面时获取提示",
            "bzd": "猜不出来的时候就发这个吧",
        },
    },
}


help = on_command("help", priority=1)


@help.handle()
async def _(bot: Bot, plugin: Message = CommandArg()):
    plugin: str = plugin.extract_plain_text().strip()

    if plugin == "":
        plugin_msg = "\n    ".join(
            [
                f"{plugin_name} -{plugin_info['description']}"
                for plugin_name, plugin_info in plugin_data.items()
            ]
        )
        msg = (
            "当前可用的插件有：\n"
            f"    {plugin_msg}\n"
            "输入“help 插件名”查看特定插件的语法和使用示例。"
        )

        await help.finish(msg)
    elif plugin in plugin_data:
        msg = f"插件 {plugin} 可用的指令有：\n    " + "\n    ".join(
            [
                f"{command} -{usage}"
                for command, usage in plugin_data[plugin]["usage"].items()
            ]
        )

        if bot.adapter.get_name() == "Satori":
            msg = escape_text(msg)

        await help.finish(msg)
    else:
        await help.finish("未找到该插件！")
