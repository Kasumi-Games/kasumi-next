"""
邮箱系统数据库管理
"""

from nonebot import require
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import Base  # noqa: E402

# 数据库路径
database_path = store.get_data_file("mailbox", "mailbox.db")

# 全局数据库会话
session = None


def init_database():
    """初始化数据库连接并创建表"""
    global session

    # 创建数据库引擎
    engine = create_engine(f"sqlite:///{database_path.resolve()}")

    # 创建所有表
    Base.metadata.create_all(engine)
    migrate_mailbox_schema(engine)

    # 创建会话
    session = sessionmaker(bind=engine)()


def get_session():
    """获取数据库会话"""
    if session is None:
        init_database()
    return session


def migrate_mailbox_schema(engine) -> None:
    """Add columns/indexes that ``create_all`` cannot retrofit.

    ``external_key`` is the exactly-once boundary used by cross-database
    outboxes such as season settlement rewards. SQLite permits multiple NULL
    values in a unique index, so ordinary mails remain unrestricted.
    """

    with engine.begin() as conn:
        columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(mails)").fetchall()
        }
        if "external_key" not in columns:
            conn.exec_driver_sql("ALTER TABLE mails ADD COLUMN external_key VARCHAR")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_mails_external_key "
            "ON mails(external_key)"
        )
