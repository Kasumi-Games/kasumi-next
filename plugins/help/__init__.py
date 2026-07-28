from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters import Message
from nonebot.adapters.satori import MessageEvent

from utils import PassiveGenerator
from utils.images import image_segment
from utils.theming import kit_for_user

from .render import board_page
from .render import detail_page
from .entries import entries_from
from .entries import find_entries
from .entries import suggest_names


def escape_text(text: str) -> str:
    """Escape Satori markup in a text reply.

    Only the text branches need this now: the board and the detail card are
    images, and an image has no markup to escape. It survives because the miss
    and ambiguity replies quote back whatever the player typed.
    """

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
            "/help|帮助": "显示帮助信息",
            "/help 插件名": "显示特定插件的用法",
        },
        "examples": ["/help", "/help 常用功能"],
    },
    "about": {
        "description": "显示 Kasumi 信息",
        "usage": {
            "/关于|about": "显示 Kasumi 信息",
        },
        "examples": ["/about"],
    },
    "常用功能": {
        "description": "个人信息、转账、签到等常用功能",
        "usage": {
            "/资料|信息|余额|info": "查看个人信息",
            "/转账|transfer <昵称> <数量>": "转账",
            "/签到|daily": "每日签到",
            "/等级排行|等级排行榜|levelrank": "查看等级排行榜。赛季 Pt 排行请用 /排行榜",
        },
        "examples": ["/信息", "/转账 喵喵 10", "/签到", "/等级排行"],
    },
    "每日任务": {
        "description": "每日任务系统，完成任务获得星星贴纸",
        "usage": {
            "/每日任务|任务|每日": "查看今日任务及完成状态",
        },
        "examples": ["/每日任务"],
    },
    "昵称": {
        "description": "设置 Kasumi 对你的称呼",
        "usage": {
            "/设置昵称|setnick <昵称>": "设置昵称。首次免费，之后修改需要 30 个Pt",
            "/我的昵称|getnick": "查看昵称",
        },
        "examples": ["/设置昵称 喵喵", "/我的昵称"],
    },
    "抽卡": {
        "description": "赛季限定卡池，消耗星星贴纸抽取装扮",
        "usage": {
            "/抽卡|gacha": "查看当前限定卡池、概率与保底进度",
            "/抽卡 卡池": "查看卡池内容，和直接发送 /抽卡 相同",
            "/抽卡 单抽": "消耗星星贴纸抽取一次",
            "/抽卡 十连": "消耗星星贴纸连抽十次",
            "/抽卡 记录 <页码>": "查看抽卡记录，页码可省略",
        },
        "examples": ["/抽卡", "/抽卡 单抽", "/抽卡 十连", "/抽卡 记录 2"],
    },
    "仓库": {
        "description": "查看你拥有的货币、装扮和道具",
        "usage": {
            "/仓库|背包|inventory": "查看仓库里的全部物品",
            "/仓库 <分类:全部|货币|装扮|道具>": "按分类查看仓库",
        },
        "examples": ["/仓库", "/仓库 装扮"],
    },
    "装扮": {
        "description": "查看和更换头像框、主题、立绘",
        "usage": {
            "/装扮|cosmetic": "查看当前装备与拥有的装扮",
            "/装扮 装备 <装扮ID>": "装备指定装扮，装扮ID 可在 /装扮 中查看",
            "/装扮 卸下 <位置:头像框|主题|立绘>": "卸下指定位置的装扮",
        },
        # No 装备 example: real item ids exceed the 224px example cell and an
        # ellipsized example cannot be copied; the usage row shows the shape.
        "examples": ["/装扮", "/装扮 卸下 头像框"],
    },
    "个人资料": {
        "description": "个人资料卡与个人简介",
        "usage": {
            "/个人资料|档案|profile": "查看个人资料卡",
            "/个人资料 简介 <文本>": "设置资料卡上的个人简介，180 字以内",
        },
        "examples": ["/个人资料", "/个人资料 简介 你好呀"],
    },
    "赛季": {
        "description": "赛季 Pt、排行与历史",
        "usage": {
            "/赛季|season": "查看当前赛季信息和自己的 Pt、排名",
            "/赛季排行|排行|排行榜|赛季排行榜|seasonrank": "查看赛季 Pt 排行榜，休赛期显示上赛季最终排名",
            "/赛季趋势|seasontrend": "查看赛季排名趋势图",
            "/赛季历史|seasonhistory": "查看历届赛季和个人结算记录",
        },
        "examples": ["/赛季", "/排行榜", "/赛季趋势", "/赛季历史"],
    },
    "猜卡面": {
        "description": "猜卡面小游戏",
        "usage": {
            "/猜卡面|cck|猜猜看": "开始猜卡面（随机难度）",
            "/猜卡面 <难度>": "开始指定难度的猜卡面，难度可选为 easy, normal, hard, expert, hard++, expert++, 黑白木筏, 高闪大图, 五只小猫, 超级猫猫, 寻找记忆, 6块床板",
            "/猜卡面 -f": "强制退出猜卡面",
            "/猜卡面 -h": "查看帮助和可用难度",
            "bzd": "猜不出来的时候就发这个吧",
        },
        "examples": [
            "/猜卡面",
            "/猜卡面 easy",
            "/猜卡面 超级猫猫",
            "/猜卡面 -f",
            "/猜卡面 -h",
            "bzd",
        ],
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
    "一笔画": {
        "description": "一笔画小游戏",
        "usage": {
            "/一笔画|os <难度:简单|普通|困难>": "开始一笔画并选择难度，默认为普通",
            "r": "重置到起点",
            "q": "放弃本局",
            "/一笔画排行榜|osr": "查看竞速排行榜",
        },
        "examples": ["/一笔画", "/一笔画 困难", "r", "q", "/一笔画排行榜"],
    },
    "黑香澄": {
        "description": "BlackKasumi 小游戏",
        "usage": {
            "/黑香澄": "开始游戏",
            "/黑香澄 <数量>": "开始游戏，并下注指定数量的Pt",
            "/黑香澄 -h": "查看帮助",
            "/黑香澄统计": "查看统计信息",
        },
        "examples": ["/黑香澄", "/黑香澄 10", "/黑香澄 -h", "/黑香澄统计"],
    },
    "探险": {
        "description": "Arisa 的地下室探险小游戏",
        "usage": {
            "/探险|mines": "开始探险",
            "/探险 <下注Pt> <雷的数量>": "开始探险，并下注指定数量的Pt和雷（Arisa）的数量",
            "/探险 -h": "查看帮助",
            "/探险 -f": "强制退出游戏",
            "/探险统计": "查看统计信息",
        },
        "examples": ["/探险", "/探险 10", "/探险 10 3", "/探险 -f", "/探险统计"],
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
            "/邮箱 领取": "一键领取所有未读邮件的奖励",
        },
        "examples": ["/邮箱", "/邮件 1", "/邮箱 领取"],
    },
    "红包": {
        "description": "红包系统",
        "usage": {
            "/发红包|红包 <标题> <金额> <份数>": "发红包",
            "/抢红包|领红包 <编号>": "抢红包。编号可选，不填则抢最新红包。红包编号为红包列表中的编号",
            "/红包列表|查看红包": "查看红包列表",
        },
        "examples": ["/发红包 100 10", "/抢红包 1", "/红包列表"],
    },
}


#: The dict above, re-shaped into one record per plugin and one command per
#: typeable string. Built once at import; ``plugin_data`` stays the source.
HELP_ENTRIES = entries_from(plugin_data)


help = on_command("help", priority=1, aliases={"帮助", "帮助信息"})


@help.handle()
async def _(event: MessageEvent, plugin: Message = CommandArg()):  # type: ignore
    token: str = plugin.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)
    # Resolve the theme on the event loop thread: the inventory Session behind
    # it is process-global and not thread safe, and render_async offloads to a
    # worker. See utils/theming.py.
    kit = kit_for_user(event.get_user_id())

    if token == "":
        image = await board_page(HELP_ENTRIES, kit).render_async()
        await help.finish(
            image_segment(image) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    matches = find_entries(HELP_ENTRIES, token)

    if len(matches) == 1:
        image = await detail_page(matches[0], kit).render_async()
        await help.finish(
            image_segment(image) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    # Misses and ambiguity stay text: the player is mid-guess, the answer is a
    # word they will retype immediately, and an image costs a render plus an
    # upload to say it.
    if matches:
        names = " / ".join(entry.name for entry in matches)
        message = f"「{token}」对应了好几个功能：{names}。发送 /help 加上其中一个看详情。"
    else:
        suggestions = suggest_names(HELP_ENTRIES, token)
        message = (
            f"没有叫「{token}」的功能，最接近的是 {' / '.join(suggestions)}。发送 /help 看全部。"
            if suggestions
            else f"没有叫「{token}」的功能，发送 /help 看看都有哪些吧。"
        )

    await help.finish(
        escape_text(message) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )
