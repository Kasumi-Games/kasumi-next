"""Static tour rules and command parsing."""

from __future__ import annotations

from typing import Literal
from dataclasses import dataclass

from .models import TourDisplayMode

INSTRUMENT_NAMES = (
    "香澄的吉他", "多惠的吉他", "里美的贝斯", "沙绫的鼓", "有咲的键盘",
    "美竹兰的吉他", "摩卡的吉他", "绯玛丽的贝斯", "宇田川巴的鼓", "羽泽鸫的键盘",
    "丸山彩的话筒", "日菜的吉他", "千圣的贝斯", "麻弥的鼓", "伊芙的键盘",
    "友希那的话筒", "纱夜的吉他", "莉莎的贝斯", "亚子的鼓", "燐子的键盘",
    "弦卷心的话筒", "濑田薰的吉他", "育美的贝斯", "花音的鼓", "米歇尔的DJ台",
    "真白的话筒", "透子的吉他", "七深的贝斯", "筑紫的鼓", "瑠唯的小提琴",
    "LAYER的贝斯", "LOCK的吉他", "MASKING的鼓", "CHU²的DJ台", "PAREO的吉他",
    "高松灯的话筒", "爱音的吉他", "要乐奈的吉他", "素世的贝斯", "立希的鼓",
    "阿拉蕾的喇叭", "野乃花的吉他", "由乃的DJ", "都子的键盘", "峰月律的吉他",
    "Doloris的吉他", "Mortis的吉他", "Timoris的贝斯", "Amoris的鼓手", "Oblivionis的键盘",
)

STAMINA_NAMES = (
    "可乐饼", "巧克力螺", "极上咖啡", "特调拿铁", "银河拉面",
    "抹茶巴菲", "米歇尔红豆饼", "live boost", "牛肉干", "肉酱意大利面",
    "紫莓冰霜", "马卡龙塔", "水果挞",
)

TOUR_NAMES = (
    "CiRCLE演出", "SPACE演出", "RiNG演出", "Galaxy演出", "武道馆演出",
    "花咲川演出", "羽丘演出", "月之森演出", "海边沙滩演出", "商店街演出",
    "露天广场演出", "庆丰大学演出", "四叶大学演出", "大剧院演出",
)


@dataclass(frozen=True)
class TourDifficultyConfig:
    key: str
    initial_stamina: int
    reward_pt: int
    allow_unequip: bool


@dataclass(frozen=True)
class ParsedAction:
    kind: str
    digits: str = ""


@dataclass(frozen=True)
class DisplayModeRequest:
    kind: Literal["none", "query", "set", "invalid"]
    mode: TourDisplayMode | None = None


DIFFICULTIES = {
    "初级": TourDifficultyConfig("初级", 99, 20, True),
    "中级": TourDifficultyConfig("中级", 30, 40, True),
    "高级": TourDifficultyConfig("高级", 20, 60, True),
    "超级": TourDifficultyConfig("超级", 20, 80, False),
}

DIFFICULTY_ALIASES = {
    "初级": "初级", "ez": "初级", "xyez": "初级", "初级巡演": "初级",
    "中级": "中级", "nm": "中级", "xynm": "中级", "中级巡演": "中级",
    "高级": "高级", "hd": "高级", "xyhd": "高级", "高级巡演": "高级",
    "超级": "超级", "ex": "超级", "xyex": "超级", "超级巡演": "超级",
}


def normalize_difficulty(value: str) -> str | None:
    return DIFFICULTY_ALIASES.get(value.strip().casefold())


def difficulty_for_command(command_text: str, argument: str) -> TourDifficultyConfig | None:
    """Resolve a unified or legacy command to a difficulty.

    A bare ``巡演/tour/xy`` starts the onboarding-friendly 初级 game.
    """

    arg = argument.strip()
    if arg:
        key = normalize_difficulty(arg)
        return DIFFICULTIES.get(key) if key else None
    first = command_text.strip().split(maxsplit=1)[0].lstrip("/")
    key = normalize_difficulty(first)
    if key:
        return DIFFICULTIES[key]
    return DIFFICULTIES["初级"]


def difficulty_help() -> str:
    return (
        "巡演难度：初级 / 中级 / 高级 / 超级\n"
        "例如：巡演 中级。\n"
        "发送「巡演 -h」查看完整规则。"
    )


def parse_action(raw: str) -> ParsedAction:
    """Parse one in-game message without mutating a session."""

    value = raw.strip().casefold()
    if value in {"q", "quit"}:
        return ParsedAction("quit")
    if value == "5":
        return ParsedAction("rest")
    if 1 <= len(value) <= 6 and value.isdigit() and all(c in "01234" for c in value):
        return ParsedAction("sequence", value)
    return ParsedAction("invalid")


def parse_display_mode_request(raw: str) -> DisplayModeRequest:
    value = raw.strip().casefold()
    for command in ("/巡演", "巡演", "/tour", "tour", "/xy", "xy"):
        prefix = command + " "
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
            break
    direct = {
        "图片模式": TourDisplayMode.IMAGE,
        "文本模式": TourDisplayMode.TEXT,
    }
    if value in direct:
        return DisplayModeRequest("set", direct[value])

    parts = value.split()
    if not parts or parts[0] not in {"模式", "mode"}:
        return DisplayModeRequest("none")
    if len(parts) == 1:
        return DisplayModeRequest("query")
    if len(parts) != 2:
        return DisplayModeRequest("invalid")

    aliases = {
        "图片": TourDisplayMode.IMAGE,
        "图": TourDisplayMode.IMAGE,
        "image": TourDisplayMode.IMAGE,
        "img": TourDisplayMode.IMAGE,
        "文本": TourDisplayMode.TEXT,
        "文字": TourDisplayMode.TEXT,
        "text": TourDisplayMode.TEXT,
    }
    mode = aliases.get(parts[1])
    if mode is None:
        return DisplayModeRequest("invalid")
    return DisplayModeRequest("set", mode)
