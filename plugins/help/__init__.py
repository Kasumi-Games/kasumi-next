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
            "/help": "显示帮助信息",
            "/help 插件名": "显示特定插件的用法",
        },
        "examples": ["/help", "/help 星之碎片"],
    },
    "info": {
        "description": "显示 Kasumi 信息",
        "usage": {
            "/关于|info": "显示 Kasumi 信息",
        },
        "examples": ["/info"],
    },
    "星之碎片": {
        "description": "Kasumi 的货币系统",
        "usage": {
            "/余额|balance": "查看余额",
            "(维修中)/转账|transfer <@用户> <数量>": "转账",
            "/签到|daily": "每日签到",
        },
        "examples": ["/余额", "/转账 @Arisa 10", "/签到"],
    },
    "猜猜看": {
        "description": "猜猜看小游戏",
        "usage": {
            "/猜猜看|cck": "开始猜猜看",
            "/猜猜看|cck -f": "强制退出猜猜看",
            "bzd": "猜不出来的时候就发这个吧",
        },
        "examples": ["/猜猜看", "/猜猜看 -f", "bzd", "ksm"],
    },
    "猜谱面": {
        "description": "猜谱面小游戏",
        "usage": {
            "/猜谱面|cpm": "开始猜谱面",
            "/猜谱面|cpm <游戏难度>": "开始猜谱面，难度可选为 easy, normal, hard, expert，支持缩写为 ez, nm, hd, ex",
            "/猜谱面|cpm <谱面难度>": "开始猜谱面，谱面难度可选为 1-30",
            "/猜谱面|cpm -f": "强制退出猜谱面",
            "<歌曲名称|ID>": "猜指定歌曲的谱面",
            "提示": "在猜谱面时获取提示",
            "bzd": "猜不出来的时候就发这个吧",
        },
        "examples": [
            "/猜谱面",
            "/猜谱面 ex",
            "/猜谱面 28",
            "/猜谱面 -f",
            "六兆年",
            "提示",
            "bzd",
        ],
    },
    "tts": {
        "description": "文本转BanG Dream! & 少女歌剧角色语音(trained by Bilibili@Mahiroshi)",
        "usage": {
            "/tts <角色> <文本>": "将文本转换为角色语音。角色和文本都可以省略，省略时会出现更多提示",
        },
        "examples": ["/tts", "/tts 你好", "/tts 香澄", "/tts 香澄 你好"],
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
            "输入“/help 插件名”查看特定插件的语法和使用示例。\n"
            "需要帮助时请加入 QQ 群 908979461"
        )

        await help.finish(msg)
    elif plugin in plugin_data:
        msg = (
            f"插件 {plugin} 的使用方法：\n"
            + "\n".join(
                [
                    f"    {command} -{usage}"
                    for command, usage in plugin_data[plugin]["usage"].items()
                ]
            )
            + "\n示例：\n    "
            + "\n    ".join(plugin_data[plugin]["examples"])
        )

        if bot.adapter.get_name() == "Satori":
            msg = escape_text(msg)

        await help.finish(msg)
    else:
        await help.finish("未找到该插件！")
