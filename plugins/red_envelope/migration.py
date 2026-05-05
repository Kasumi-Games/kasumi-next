import sqlite3
from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402


def migrate_drop_pending_amounts():
    """Drop the pending_amounts column from red_envelopes table and reclaim disk space."""

    database_path = store.get_data_file("red_envelope", "data.db")

    if not database_path.exists():
        logger.info("红包数据库尚未创建，无需迁移。")
        return

    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='red_envelopes'"
        )
        if cursor.fetchone() is None:
            logger.info("未找到 red_envelopes 表，无需迁移。")
            return

        cursor.execute("PRAGMA table_info(red_envelopes)")
        columns = [column[1] for column in cursor.fetchall()]

        if "pending_amounts" not in columns:
            logger.info("pending_amounts 列不存在，无需迁移。")
            return

        cursor.execute("ALTER TABLE red_envelopes DROP COLUMN pending_amounts")
        conn.commit()
        logger.info("已删除 pending_amounts 列。")

        cursor.execute("VACUUM")
        logger.info("已完成数据库空间回收 (VACUUM)。")

    except sqlite3.Error as e:
        logger.error("红包数据库迁移失败: {}", e, exc_info=True)
        conn.rollback()
        raise

    finally:
        conn.close()
