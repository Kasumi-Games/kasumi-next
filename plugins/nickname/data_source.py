from typing import Optional

from nonebot import require
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from utils.content_safety import SensitiveTextPolicy
from utils.content_safety import safe_display_text

nickname_path = store.get_data_file("nickname", "data.db")
Base = declarative_base()

session = None


def init_database():
    global session
    engine = create_engine(f"sqlite:///{nickname_path.resolve()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()


class Nickname(Base):
    __tablename__ = "nicknames"

    user_id = Column(String, primary_key=True)
    nickname = Column(String)


def purge_unsafe_nicknames(
    *, policy: SensitiveTextPolicy | None = None
) -> int:
    """Delete persisted nicknames which violate the current text policy.

    This is intended for the plugin startup hook.  Only nickname records are
    removed, so the user's ID, balance, inventory, and other game data remain
    untouched.  Callers should log the returned count only; logging the text
    itself would expose the content being remediated.
    """

    if session is None:
        init_database()

    active_policy = policy or SensitiveTextPolicy.default()
    unsafe_user_ids = [
        nickname.user_id
        for nickname in session.query(Nickname).all()
        if nickname.nickname is not None and active_policy.contains(nickname.nickname)
    ]
    if not unsafe_user_ids:
        return 0

    session.query(Nickname).filter(Nickname.user_id.in_(unsafe_user_ids)).delete(
        synchronize_session=False
    )
    session.commit()
    return len(unsafe_user_ids)


def get(user_id: str) -> Optional[str]:
    """获取用户昵称

    Args:
        user_id (str): 用户 ID，推荐使用 `event.get_user_id()` 获取

    Returns:
        str: 用户昵称，如果用户没有设置昵称则返回 `None`
    """
    if session is None:
        init_database()
    nickname = session.query(Nickname).filter(Nickname.user_id == user_id).first()
    if nickname is None:
        return None
    return safe_display_text(nickname.nickname) or None


def get_id(nickname: str) -> Optional[str]:
    """根据昵称获取用户 ID

    Args:
        nickname (str): 用户昵称

    Returns:
        str: 用户 ID，如果没有找到用户则返回 `None`
    """
    if session is None:
        init_database()
    user = session.query(Nickname).filter(Nickname.nickname == nickname).first()
    if user is None:
        return None
    return user.user_id
