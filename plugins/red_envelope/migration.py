import sqlite3

from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402


def migrate_red_envelope_schema():
    """Bring existing red-envelope databases up to the current schema."""

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
        dropped_column = False
        if cursor.fetchone() is not None:
            cursor.execute("PRAGMA table_info(red_envelopes)")
            columns = [column[1] for column in cursor.fetchall()]
            if "pending_amounts" in columns:
                cursor.execute("ALTER TABLE red_envelopes DROP COLUMN pending_amounts")
                dropped_column = True
                logger.info("已删除 pending_amounts 列。")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='claim_records'"
        )
        if cursor.fetchone() is not None:
            cursor.execute("PRAGMA table_info(claim_records)")
            claim_columns = [column[1] for column in cursor.fetchall()]
            if "credited_at" not in claim_columns:
                cursor.execute(
                    "ALTER TABLE claim_records "
                    "ADD COLUMN credited_at INTEGER DEFAULT 0 NOT NULL"
                )
                # Old claims completed before delivery state existed. Treat
                # them as credited to avoid duplicating historical payouts.
                cursor.execute(
                    "UPDATE claim_records SET credited_at = claimed_at "
                    "WHERE credited_at = 0"
                )
                logger.info("已添加红包到账状态列。")

        conn.commit()
        if dropped_column:
            cursor.execute("VACUUM")
            logger.info("已完成数据库空间回收 (VACUUM)。")

    except sqlite3.Error as e:
        logger.error("红包数据库迁移失败: {}", e, exc_info=True)
        conn.rollback()
        raise

    finally:
        conn.close()


def migrate_drop_pending_amounts():
    """Backward-compatible entry point for older callers."""

    migrate_red_envelope_schema()
