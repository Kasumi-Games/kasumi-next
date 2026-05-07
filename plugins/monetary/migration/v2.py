"""Data migration v2: refund stars, compensate XP, recalculate levels, compensate stickers.

Optimized: uses batch GROUP BY queries instead of per-user queries.
"""

import time
import sqlite3
from math import floor
from collections import defaultdict
from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402


def migrate_data():
    """Run the full v2 data migration."""
    db_path = store.get_data_file("monetary", "data.db")
    tx_path = store.get_data_file("monetary", "transaction.db")
    bj_path = store.get_data_file("blackjack", "games.db")
    mines_path = store.get_data_file("mines", "games.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if migration was already run
        cursor.execute("SELECT COUNT(*) FROM users WHERE xp > 0")
        already_migrated = cursor.fetchone()[0] > 0
        if already_migrated:
            logger.info("Data migration v2 already applied, skipping")
            return

        # Get level cost function (from old daily/utils.py)
        def get_amount_for_level(level):
            if level <= 20:
                return 3 + level
            elif level <= 60:
                return int(25 + (level - 20) ** 1.3)
            else:
                return int(150 * 1.05 ** (level - 60))

        def total_xp_for_level(n):
            if n <= 1:
                return 0
            return sum(floor(100 * 1.15 ** (i - 2) + 1e-9) for i in range(2, n + 1))

        def level_for_xp(xp):
            level = 1
            while total_xp_for_level(level + 1) <= xp:
                level += 1
            return level

        # ---- Batch 1: Load all users ----
        cursor.execute("SELECT user_id, level, balance FROM users")
        users = {
            row[0]: {"level": row[1], "balance": row[2]} for row in cursor.fetchall()
        }
        logger.info(f"Migration: loaded {len(users)} users")

        # ---- Batch 2: XP from transactions (GROUP BY query) ----
        xp_from_tx = defaultdict(int)
        if tx_path.exists():
            tx_conn = sqlite3.connect(tx_path)
            try:
                rows = tx_conn.execute(
                    """SELECT user_id, COALESCE(SUM(amount), 0)
                       FROM transactions
                       WHERE description IN ('guess_chart','cck','one_stroke','daily')
                         AND amount > 0
                       GROUP BY user_id"""
                ).fetchall()
                for uid, total in rows:
                    xp_from_tx[uid] = total
                logger.info(f"Migration: loaded {len(rows)} users with transaction XP")
            finally:
                tx_conn.close()

        # ---- Batch 3: XP from blackjack games ----
        xp_from_bj = defaultdict(int)
        if bj_path.exists():
            bj_conn = sqlite3.connect(bj_path)
            try:
                rows = bj_conn.execute(
                    "SELECT user_id, COUNT(*) FROM blackjack_games GROUP BY user_id"
                ).fetchall()
                for uid, count in rows:
                    xp_from_bj[uid] = count * 5
                logger.info(f"Migration: loaded {len(rows)} users with blackjack XP")
            except sqlite3.Error as e:
                logger.warning(f"Blackjack game count failed: {e}")
            finally:
                bj_conn.close()

        # ---- Batch 4: XP from mines games ----
        xp_from_mines = defaultdict(int)
        if mines_path.exists():
            mines_conn = sqlite3.connect(mines_path)
            try:
                rows = mines_conn.execute(
                    "SELECT user_id, COUNT(*) FROM mines_games GROUP BY user_id"
                ).fetchall()
                for uid, count in rows:
                    xp_from_mines[uid] = count * 5
                logger.info(f"Migration: loaded {len(rows)} users with mines XP")
            except sqlite3.Error as e:
                logger.warning(f"Mines game count failed: {e}")
            finally:
                mines_conn.close()

        # ---- Process all users ----
        migrated = 0
        tx_conn = sqlite3.connect(tx_path) if tx_path.exists() else None

        for user_id, data in users.items():
            level = data["level"]
            balance = data["balance"]

            # Star refund
            if level > 1:
                total_refund = sum(get_amount_for_level(i) for i in range(2, level + 1))
                balance += total_refund
                _log_transaction_batch(
                    tx_conn, user_id, total_refund, "star_refund_migration"
                )

            # Total XP
            xp = xp_from_tx[user_id] + xp_from_bj[user_id] + xp_from_mines[user_id]

            # Recalculate level
            new_level = max(1, level_for_xp(xp))

            # Sticker compensation
            stickers = (new_level - 1) * 120

            # Update user
            cursor.execute(
                "UPDATE users SET level=?, balance=?, xp=?, star_stickers=? "
                "WHERE user_id=?",
                (new_level, balance, xp, stickers, user_id),
            )

            if stickers > 0:
                tx_conn.execute(
                    """INSERT INTO sticker_transactions
                       (user_id, amount, reason, balance_after, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        user_id,
                        stickers,
                        "migration_level_compensation",
                        stickers,
                        int(time.time()),
                    ),
                )

            migrated += 1

        if tx_conn:
            tx_conn.commit()
            tx_conn.close()

        conn.commit()
        logger.info(f"Migration v2 completed: migrated {migrated}/{len(users)} users")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration v2 failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def _log_transaction_batch(conn, user_id, amount, description):
    """Log a transaction to an open connection."""
    if conn is None:
        return
    conn.execute(
        """INSERT INTO transactions (user_id, category, amount, time, description)
           VALUES (?, 'income', ?, ?, ?)""",
        (user_id, amount, int(time.time()), description),
    )
