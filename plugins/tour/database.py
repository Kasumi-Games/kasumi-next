"""SQLite connection for terminal tour records."""

from __future__ import annotations

from nonebot import require
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import Base  # noqa: E402

database_path = store.get_data_file("tour", "games.db")
session = None


def init_database() -> None:
    global session
    engine = create_engine(f"sqlite:///{database_path.resolve()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()


def get_session():
    global session
    if session is None:
        init_database()
    return session
