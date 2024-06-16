from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.satori import MessageEvent


async def has_no_argument(arg: Message = CommandArg()):
    if arg.extract_plain_text().strip() == "":
        return True
    return False


async def is_qq_bot(event: MessageEvent):
    return event.platform in ["qq", "qqguild"]
