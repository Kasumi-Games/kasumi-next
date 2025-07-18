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


if __name__ == "__main__":
    migrate_add_level_column()
