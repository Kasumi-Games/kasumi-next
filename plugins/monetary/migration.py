import sqlite3
from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402


def migrate_add_level_column():
    """Add level column to existing users table and set default level to 1"""

    database_path = store.get_data_file("monetary", "data.db")

    if not database_path.exists():
        logger.info("Database does not exist yet. No migration needed.")
        return

    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    try:
        # Check if level column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if "level" in columns:
            logger.info("Level column already exists. No migration needed.")
            return

        # Add level column with default value 1
        cursor.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")

        # Update all existing users to have level 1
        cursor.execute("UPDATE users SET level = 1 WHERE level IS NULL")

        conn.commit()
        logger.info(
            "Successfully added level column to users table and set default level to 1 for all existing users."
        )

    except sqlite3.Error as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        conn.rollback()
        raise

    finally:
        conn.close()


def migrate_fix_balance_column():
    """Fix balance column in users table by converting float to integer"""

    database_path = store.get_data_file("monetary", "data.db")

    if not database_path.exists():
        logger.info("数据库尚未创建，无需迁移。")
        return

    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    try:
        # Ensure users table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        if cursor.fetchone() is None:
            logger.info("未找到 users 表，无需余额修复。")
            return

        # Round up any float balances to integers (ceil behavior)
        cursor.execute(
            """
            UPDATE users
            SET balance = CAST(balance AS INTEGER)
                        + CASE WHEN balance > CAST(balance AS INTEGER) THEN 1 ELSE 0 END
            WHERE balance != CAST(balance AS INTEGER)
            """
        )
        affected = cursor.rowcount if cursor.rowcount is not None else 0
        conn.commit()
        logger.info(f"余额字段修复完成，已更新 {affected} 行。")

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"余额字段修复迁移失败: {e}", exc_info=True)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_add_level_column()
