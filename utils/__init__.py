from nonebot.params import CommandArg
from nonebot.adapters import Message


async def has_no_argument(arg: Message = CommandArg()):
    if arg.extract_plain_text().strip() == "":
        return True
    return False
