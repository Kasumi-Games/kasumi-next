from typing import Optional
from nonebot import require
from sqlalchemy import create_engine
from sqlalchemy import Column, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store


nickname_path = store.get_data_file("nickname", "data.db")

Base = declarative_base()
engine = create_engine(f"sqlite:///{nickname_path.resolve()}")
Base.metadata.create_all(engine)
session = sessionmaker(bind=engine)()


class Nickname(Base):
    __tablename__ = "nicknames"

    user_id = Column(String, primary_key=True)
    nickname = Column(String)


def get(user_id: str) -> Optional[str]:
    """获取用户昵称

    Args:
        user_id (str): 用户 ID，推荐使用 `event.get_user_id()` 获取

    Returns:
        str: 用户昵称，如果用户没有设置昵称则返回 `None`
    """
    nickname = session.query(Nickname).filter(Nickname.user_id == user_id).first()
    if nickname is None:
        return None
    return nickname.nickname


def get_id(nickname: str) -> Optional[str]:
    """根据昵称获取用户 ID

    Args:
        nickname (str): 用户昵称

    Returns:
        str: 用户 ID，如果没有找到用户则返回 `None`
    """
    user = session.query(Nickname).filter(Nickname.nickname == nickname).first()
    if user is None:
        return None
    return user.user_id
