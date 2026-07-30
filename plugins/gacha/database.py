"""Database setup for the gacha plugin."""

from nonebot import require
from sqlalchemy import text
from sqlalchemy import inspect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import Base  # noqa: E402

database_path = store.get_data_file("gacha", "gacha.db")

session = None


def init_database():
    global session

    engine = create_engine(f"sqlite:///{database_path.resolve()}")
    Base.metadata.create_all(engine)
    migrate_gacha_schema(engine)
    session = sessionmaker(bind=engine)()


def migrate_gacha_schema(engine) -> None:
    """Add columns introduced after the first local gacha database shipped."""

    columns = {column["name"] for column in inspect(engine).get_columns("gacha_pulls")}
    if "payment_item_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE gacha_pulls "
                    "ADD COLUMN payment_item_id VARCHAR "
                    "DEFAULT 'star_sticker' NOT NULL"
                )
            )


def get_session():
    if session is None:
        init_database()
    return session
