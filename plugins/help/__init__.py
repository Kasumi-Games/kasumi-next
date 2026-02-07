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
            "/转账|transfer <昵称> <数量>": "转账",
            "/签到|daily": "每日签到",
            "/摘星|upgrade <数量>": "使用星之碎片升级",
            "/观星|watch <数量>": "观测之后的星星价值多少碎片",
            "/碎星|shatter <数量>": "碎星，消耗星星，获得一半数量的星之碎片",
            "/排行榜|rank": "查看排行榜",
        },
        "examples": ["/余额", "/转账 喵喵 10", "/签到", "/摘星", "/摘星 10", "/排行榜"],
    },
    "昵称": {
        "description": "设置 Kasumi 对你的称呼",
        "usage": {
            "/设置昵称|setnick <昵称>": "设置昵称。首次免费，之后修改需要 30 个星之碎片",
            "/我的昵称|getnick": "查看昵称",
        },
        "examples": ["/设置昵称 喵喵", "/我的昵称"],
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
    "黑香澄": {
        "description": "BlackKasumi 小游戏",
        "usage": {
            "/黑香澄": "开始游戏",
            "/黑香澄 <数量>": "开始游戏，并下注指定数量的碎片",
            "/黑香澄 -h": "查看帮助",
            "/黑香澄统计": "查看统计信息",
        },
        "examples": ["/黑香澄", "/黑香澄 10", "/黑香澄 -h", "/黑香澄统计"],
    },
    "探险": {
        "description": "Arisa 的地下室探险小游戏",
        "usage": {
            "/探险|mines": "开始探险",
            "/探险 <下注碎片> <雷的数量>": "开始探险，并下注指定数量的碎片和雷（Arisa）的数量",
            "/探险 -h": "查看帮助",
            "/探险统计": "查看统计信息",
        },
        "examples": ["/探险", "/探险 10", "/探险 10 3", "/探险统计"],
    },
    "tts": {
        "description": "文本转BanG Dream! & 少女歌剧角色语音(trained by Bilibili@Mahiroshi)",
        "usage": {
            "/tts <角色> <文本>": "将文本转换为角色语音。角色和文本都可以省略，省略时会出现更多提示",
        },
        "examples": ["/tts", "/tts 你好", "/tts 香澄", "/tts 香澄 你好"],
    },
    "娶群友": {
        "description": "获得随机一个其他 群友/频道成员 的一张随机 BanG Dream! 卡牌风格的图片",
        "usage": {"/娶群友|qqy|ccb": "获取一张卡面"},
        "examples": ["/娶群友", "/qqy", "/ccb"],
    },
    "邮箱": {
        "description": "邮件系统，支持接收奖励和系统通知",
        "usage": {
            "/邮箱|邮件|mail": "查看邮箱列表",
            "/邮件 <编号>": "读取指定邮件并领取奖励",
        },
        "examples": ["/邮箱", "/邮件 1"],
    },
    "红包": {
        "description": "红包系统",
        "usage": {
            "/发红包|红包 <标题> <金额> <份数>": "发红包",
            "/抢红包|领红包 <编号>": "抢红包。编号可选，不填则抢最新红包。红包编号为红包列表中的编号",
            "/红包列表": "查看红包列表",
        },
        "examples": ["/发红包 100 10", "/抢红包 1", "/红包列表"],
    },
    "魔裁": {
        "description": "魔法少女的魔女审判相关功能",
        "usage": {
            "/安安说 <文本> <表情:害羞|生气|病娇|无语|开心>": "让安安说话",
            "【疑问|反驳|伪证|赞同】<文本>": "生成审判选择图片。多行输入表示多个选项",
            "/切换角色 <角色名:艾玛|希罗>": "切换审判选择中的角色",
        },
        "examples": [
            "/安安说 吾辈现在不想说话",
            "/安安说 吾辈命令你现在【猛击自己的魔丸一百下】 生气",
            "【伪证】我和艾玛不是恋人\n【赞同】我们初中的时候就确认关系了",
            "【疑问】汉娜和雪莉约会没有邀请我很可疑",
            "/切换角色 希罗",
        ],
    },
}


help = on_command("help", priority=1, aliases={"帮助", "帮助信息"})


@help.handle()
async def _(bot: Bot, plugin: Message = CommandArg()):  # type: ignore
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
