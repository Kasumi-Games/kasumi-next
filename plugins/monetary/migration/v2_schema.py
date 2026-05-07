"""Schema migration for level system v2: add new columns and tables."""

import sqlite3
from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402


def migrate_schema():
    """Add new columns to existing tables and create new tables."""

    database_path = store.get_data_file("monetary", "data.db")
    transaction_path = store.get_data_file("monetary", "transaction.db")
    mailbox_path = store.get_data_file("mailbox", "mailbox.db")

    # Migrate main database (users table)
    if database_path.exists():
        _migrate_users_table(database_path)
        _create_daily_tasks(database_path)

    # Create sticker_transactions in transaction database
    _create_sticker_transactions(transaction_path)

    # Mailbox database migrations
    if mailbox_path.exists():
        _migrate_mailbox_tables(mailbox_path)


def _migrate_users_table(db_path):
    """Add xp, star_stickers, consecutive_checkins to users table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        if "xp" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
            logger.info("Added xp column to users table")

        if "star_stickers" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN star_stickers INTEGER DEFAULT 0"
            )
            logger.info("Added star_stickers column to users table")

        if "consecutive_checkins" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN consecutive_checkins INTEGER DEFAULT 0"
            )
            logger.info("Added consecutive_checkins column to users table")

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Users table migration failed: {}", e, exc_info=True)
        raise
    finally:
        conn.close()


def _create_sticker_transactions(db_path):
    """Create sticker_transactions table if not exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sticker_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                balance_after INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sticker_tx_user
            ON sticker_transactions(user_id)
            """
        )
        conn.commit()
        logger.info("Created sticker_transactions table")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("sticker_transactions table creation failed: {}", e, exc_info=True)
        raise
    finally:
        conn.close()


def _create_daily_tasks(db_path):
    """Create daily_tasks table if not exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                task_id TEXT NOT NULL,
                is_completed INTEGER DEFAULT 0,
                completed_at INTEGER,
                UNIQUE(user_id, date)
            )
            """
        )
        conn.commit()
        logger.info("Created daily_tasks table")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("daily_tasks table creation failed: {}", e, exc_info=True)
        raise
    finally:
        conn.close()


def _migrate_mailbox_tables(db_path):
    """Add star_stickers to mails and scheduled_mails tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add to mails table
        cursor.execute("PRAGMA table_info(mails)")
        columns = [col[1] for col in cursor.fetchall()]

        if "star_stickers" not in columns:
            cursor.execute(
                "ALTER TABLE mails ADD COLUMN star_stickers INTEGER DEFAULT 0"
            )
            logger.info("Added star_stickers column to mails table")

        # Add to scheduled_mails table
        cursor.execute("PRAGMA table_info(scheduled_mails)")
        columns = [col[1] for col in cursor.fetchall()]

        if "star_stickers" not in columns:
            cursor.execute(
                "ALTER TABLE scheduled_mails ADD COLUMN star_stickers INTEGER DEFAULT 0"
            )
            logger.info("Added star_stickers column to scheduled_mails table")

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Mailbox tables migration failed: {}", e, exc_info=True)
        raise
    finally:
        conn.close()
