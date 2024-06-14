import time
import random
from typing import List
from nonebot.adapters import Event
from nonebot.matcher import Matcher
from sqlalchemy import create_engine
from nonebot.params import CommandArg
from nonebot import require, on_command
from sqlalchemy.orm import sessionmaker
from nonebot.adapters.satori import MessageEvent, Message, MessageSegment


require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store

from .utils import is_number
from .transaction import Transaction
from .data_source import Base, TransactionBase, User, TransactionCategory


database_path = store.get_data_file("monetary", "data.db")
transaction_path = store.get_data_file("monetary", "transaction.db")

engine = create_engine(f"sqlite:///{database_path.resolve()}")
Base.metadata.create_all(engine)
session = sessionmaker(bind=engine)()

transaction_engine = create_engine(f"sqlite:///{transaction_path.resolve()}")
TransactionBase.metadata.create_all(transaction_engine)
transaction_session = sessionmaker(bind=transaction_engine)()

transaction = Transaction(transaction_session)


def get_user(user_id: str) -> User:
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, balance=0, last_daily_time=0)
        session.add(user)
        session.commit()
    return user


def add(user_id: str, amount: int, description: str):
    user = get_user(user_id)
    user.balance += amount
    session.commit()

    transaction.add(user_id, TransactionCategory.INCOME, amount, description)


def cost(user_id: str, amount: int, description: str):
    user = get_user(user_id)
    user.balance -= amount
    session.commit()

    transaction.add(user_id, TransactionCategory.EXPENSE, amount, description)


def set(user_id: str, amount: int, description: str):
    user = get_user(user_id)
    user.balance = amount
    session.commit()

    transaction.add(user_id, TransactionCategory.SET, amount, description)


def get(user_id: str) -> int:
    return get_user(user_id).balance


def transfer(from_user_id: str, to_user_id: str, amount: int, description: str):
    cost(from_user_id, amount)
    add(to_user_id, amount)
    session.commit()

    transaction.add(to_user_id, TransactionCategory.TRANSFER, amount, description)


def daily(user_id: str) -> bool:
    user = get_user(user_id)
    # 如果上次签到在今日 0 点之前
    if time.localtime(user.last_daily_time).tm_mday != time.localtime().tm_mday:
        user.last_daily_time = time.time()
        session.commit()
        return True
    return False


__all__ = ["add", "cost", "set", "get", "transfer", "daily"]


@on_command("balance", aliases={"余额"}, priority=10, block=True).handle()
async def balance(matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    await matcher.send(f"你还有 {get(user_id)} 个星之碎片")


@on_command("daily", aliases={"签到"}, priority=10, block=True).handle()
async def handle_daily(matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    if daily(user_id):
        amount = random.randint(1, 10)
        add(user_id, amount, "daily")
        await matcher.send(f"签到成功，获得 {amount} 个星之碎片")
    else:
        await matcher.send("今天已经签到过了")


@on_command("transfer", aliases={"转账"}, priority=10, block=True).handle()
async def handle_transfer(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    to_user_segs: List[MessageSegment] = []

    for message_seg in arg:
        if message_seg.type == "at":
            to_user_segs.append(message_seg)
        elif message_seg.is_text() and is_number(message_seg.data["text"].strip()):
            amount = int(message_seg.data["text"].strip())

    if not to_user_segs:
        await matcher.finish("使用 @ 指定要转账的对象哦！示例：转账 @xxx 10")

    if len(to_user_segs) > 1:
        await matcher.finish("一次只能转账给一个人哦！")

    to_user_id = to_user_segs[0].data["id"]
    to_user_name = to_user_segs[0].data["name"]

    if to_user_id == user_id:
        await matcher.finish("不能给自己转账哦！")

    if amount <= 0:
        await matcher.finish("转账金额必须大于 0")

    if get(user_id) < amount:
        await matcher.finish("余额不足！")

    transfer(user_id, to_user_id, amount, "transfer_by_command")

    await matcher.finish(
        f"转账成功，已转账 {amount} 个星之碎片给 {MessageSegment.at(to_user_id) if to_user_name is None else to_user_name}"
    )
