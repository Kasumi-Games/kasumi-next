from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.satori import MessageEvent

from .. import monetary
from utils import PassiveGenerator

from .data_source import Nickname, session


set_nickname = on_command("setnick", priority=30, aliases={"叫我", "设置昵称"})
get_nickname = on_command("getnick", priority=30, aliases={"我的昵称"})


@set_nickname.handle()
async def handle_set_nickname(event: MessageEvent, arg: Message = CommandArg()):
    text = arg.extract_plain_text().strip()

    passive_generator = PassiveGenerator(event)

    if text == "":
        await set_nickname.finish(
            "格式错误！正确使用方法：/设置昵称 &lt;昵称&gt;" + passive_generator.element
        )

    if len(text) > 20:
        await set_nickname.finish(
            "昵称长度不能超过 20 个字符" + passive_generator.element
        )

    if "\n" in text:
        await set_nickname.finish("昵称不能包含换行符" + passive_generator.element)

    nickname = (
        session.query(Nickname).filter(Nickname.user_id == event.get_user_id()).first()
    )
    # Check if nickname is changed
    if nickname is not None and nickname.nickname == text:
        await set_nickname.finish(
            f"你一直是{text}啊，我知道的，不用修改啦" + passive_generator.element
        )

    # Check if nickname is unique
    if (
        session.query(Nickname)
        .filter(Nickname.nickname == text)
        .filter(Nickname.user_id != event.get_user_id())
        .first()
        is not None
    ):
        await set_nickname.finish(
            f"昵称 {text} 已经被其他人使用啦，换一个试试吧" + passive_generator.element
        )

    if nickname is None:
        nickname = Nickname(user_id=event.get_user_id(), nickname=text)
        session.add(nickname)
        await set_nickname.send(
            f"设置成功！以后 Kasumi 就会叫你{text}啦~" + passive_generator.element
        )
        await set_nickname.send(
            "首次设置昵称免费，下次修改需要 30 个星之碎片哦" + passive_generator.element
        )
    else:
        # Update nickname cost 30 coins
        balance = monetary.get(user_id=event.get_user_id())
        if balance < 30:
            await set_nickname.finish(
                "余额不足！修改昵称需要 30 个星之碎片" + passive_generator.element
            )
        monetary.cost(
            user_id=event.get_user_id(), amount=30, description="change nickname"
        )
        nickname.nickname = text

        await set_nickname.send(
            f"修改成功！以后 Kasumi 就会叫你{text}啦~" + passive_generator.element
        )

    session.commit()


@get_nickname.handle()
async def handle_get_nickname(event: MessageEvent):
    nickname = (
        session.query(Nickname).filter(Nickname.user_id == event.get_user_id()).first()
    )

    passive_generator = PassiveGenerator(event)

    if nickname is None:
        await get_nickname.finish("你还没有设置昵称哦！" + passive_generator.element)

    await get_nickname.finish(
        f"你的昵称是{nickname.nickname}~" + passive_generator.element
    )


__all__ = ["get"]
