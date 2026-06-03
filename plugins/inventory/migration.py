"""One-shot migrations into inventory."""

import time
import sqlite3

from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import SEASON_SCOPE_TYPE  # noqa: E402
from .models import PERMANENT_SCOPE_ID  # noqa: E402
from .models import PERMANENT_SCOPE_TYPE  # noqa: E402
from .models import SEASON_POINT_ITEM_ID  # noqa: E402
from .models import STAR_STICKER_ITEM_ID  # noqa: E402
from .models import UserItem  # noqa: E402
from .models import MigrationState  # noqa: E402
from .models import ItemTransaction  # noqa: E402
from .database import get_session  # noqa: E402

LEGACY_MIGRATION_KEY = "legacy_monetary_balances_v1"


def migrate_inventory_schema() -> None:
    session = get_session()
    bind = session.get_bind()

    with bind.begin() as conn:

        def columns(table_name: str) -> set[str]:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            return {row[1] for row in rows}

        if "seasons" in _table_names(conn):
            season_columns = columns("seasons")
            additions = {
                "season_key": "VARCHAR DEFAULT '' NOT NULL",
                "timezone": "VARCHAR DEFAULT 'UTC+8' NOT NULL",
                "metadata_json": "TEXT DEFAULT '{}' NOT NULL",
                "config_hash": "VARCHAR DEFAULT '' NOT NULL",
                "settled_at": "INTEGER DEFAULT 0 NOT NULL",
            }
            for column, ddl in additions.items():
                if column not in season_columns:
                    conn.exec_driver_sql(
                        f"ALTER TABLE seasons ADD COLUMN {column} {ddl}"
                    )

            rows = conn.exec_driver_sql(
                "SELECT id, season_number FROM seasons"
            ).fetchall()
            for season_id, season_number in rows:
                conn.exec_driver_sql(
                    "UPDATE seasons SET season_key = :season_key WHERE id = :id AND season_key = ''",
                    {"season_key": f"legacy-s{season_number}", "id": season_id},
                )

    from .models import Base

    Base.metadata.create_all(bind)
    session.commit()


def _table_names(conn) -> set[str]:
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def migrate_legacy_monetary_balances() -> None:
    session = get_session()
    marker = (
        session.query(MigrationState)
        .filter(MigrationState.key == LEGACY_MIGRATION_KEY)
        .first()
    )
    if marker is not None:
        return

    from .season_service import get_current_season
    from ..monetary.database import init_database as init_monetary_database

    init_monetary_database()

    monetary_db = store.get_data_file("monetary", "data.db")
    if not monetary_db.exists():
        session.add(
            MigrationState(key=LEGACY_MIGRATION_KEY, applied_at=int(time.time()))
        )
        session.commit()
        return

    conn = sqlite3.connect(monetary_db)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        if cursor.fetchone() is None:
            session.add(
                MigrationState(key=LEGACY_MIGRATION_KEY, applied_at=int(time.time()))
            )
            session.commit()
            return

        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}
        select_columns = ["user_id"]
        select_columns.append("balance" if "balance" in columns else "0 AS balance")
        select_columns.append(
            "star_stickers" if "star_stickers" in columns else "0 AS star_stickers"
        )
        rows = cursor.execute(
            f"SELECT {', '.join(select_columns)} FROM users"
        ).fetchall()
    finally:
        conn.close()

    season = get_current_season()
    if season is None:
        logger.info("Deferred legacy balance migration because no active season exists")
        return
    migrated = 0
    for user_id, balance, stickers in rows:
        if balance and int(balance) > 0:
            _seed_quantity(
                user_id,
                SEASON_POINT_ITEM_ID,
                SEASON_SCOPE_TYPE,
                str(season.id),
                int(balance),
            )
        if stickers and int(stickers) > 0:
            _seed_quantity(
                user_id,
                STAR_STICKER_ITEM_ID,
                PERMANENT_SCOPE_TYPE,
                PERMANENT_SCOPE_ID,
                int(stickers),
            )
        migrated += 1

    session.add(MigrationState(key=LEGACY_MIGRATION_KEY, applied_at=int(time.time())))
    session.commit()
    logger.info(f"Inventory migration completed for {migrated} users")


def _seed_quantity(
    user_id: str, item_id: str, scope_type: str, scope_id: str, quantity: int
) -> None:
    session = get_session()
    row = (
        session.query(UserItem)
        .filter(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id,
            UserItem.scope_type == scope_type,
            UserItem.scope_id == scope_id,
        )
        .first()
    )
    if row is None:
        row = UserItem(
            user_id=user_id,
            item_id=item_id,
            scope_type=scope_type,
            scope_id=scope_id,
            quantity=quantity,
            updated_at=int(time.time()),
        )
        session.add(row)
        quantity_after = quantity
        delta = quantity
    else:
        if row.quantity >= quantity:
            return
        delta = quantity - row.quantity
        row.quantity = quantity
        row.updated_at = int(time.time())
        quantity_after = row.quantity

    tx_key = f"migration:{LEGACY_MIGRATION_KEY}:user:{user_id}:item:{item_id}"
    exists = (
        session.query(ItemTransaction)
        .filter(ItemTransaction.idempotency_key == tx_key)
        .first()
    )
    if exists is None:
        session.add(
            ItemTransaction(
                user_id=user_id,
                item_id=item_id,
                scope_type=scope_type,
                scope_id=scope_id,
                delta=delta,
                quantity_after=quantity_after,
                reason=LEGACY_MIGRATION_KEY,
                source_type="migration",
                source_id=LEGACY_MIGRATION_KEY,
                idempotency_key=tx_key,
                created_at=int(time.time()),
            )
        )
