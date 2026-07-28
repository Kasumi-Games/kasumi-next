"""One-shot migrations into inventory."""

import time
import sqlite3

from nonebot import require
from nonebot.log import logger

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import SEASON_SCOPE_TYPE  # noqa: E402
from .models import OFFSEASON_SCOPE_TYPE  # noqa: E402
from .models import PERMANENT_SCOPE_ID  # noqa: E402
from .models import PERMANENT_SCOPE_TYPE  # noqa: E402
from .models import SEASON_POINT_ITEM_ID  # noqa: E402
from .models import STAR_STICKER_ITEM_ID  # noqa: E402
from .models import UserItem  # noqa: E402
from .models import MigrationState  # noqa: E402
from .models import ItemTransaction  # noqa: E402
from .models import SeasonParticipation  # noqa: E402
from .database import get_session  # noqa: E402

LEGACY_MIGRATION_KEY = "legacy_monetary_balances_v1"
LEGACY_BRIDGE_KEY = "legacy_monetary_balance_bridge_v1"
LEGACY_PARTICIPATION_MIGRATION_KEY = "legacy_season_participation_v1"


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
                "opened_at": "INTEGER DEFAULT 0 NOT NULL",
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
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_seasons_season_key "
                "ON seasons(season_key)"
            )

    from .models import Base

    Base.metadata.create_all(bind)
    session.commit()


def _table_names(conn) -> set[str]:
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def get_legacy_balance_for_bridge(user_id: str, scope_id: str) -> int | None:
    """Return old Pt for the inventory wallet used before season one opens."""

    if not scope_id.startswith("before-first-season_to_"):
        return None
    session = get_session()
    if (
        session.query(MigrationState)
        .filter(MigrationState.key == LEGACY_MIGRATION_KEY)
        .first()
        is not None
    ):
        return None

    monetary_db = store.get_data_file("monetary", "data.db")
    if not monetary_db.exists():
        return None
    conn = sqlite3.connect(monetary_db)
    try:
        table = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='users'"
        ).fetchone()
        if table is None:
            return None
        row = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return max(0, int(row[0] or 0)) if row is not None else 0


def migrate_legacy_monetary_balances(*, season=None) -> None:
    session = get_session()
    marker = (
        session.query(MigrationState)
        .filter(MigrationState.key == LEGACY_MIGRATION_KEY)
        .first()
    )
    if marker is not None:
        return

    if season is None:
        from .season_service import get_current_season

        season = get_current_season()
    if season is None:
        logger.info("Deferred legacy balance migration because no active season exists")
        return

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

    bridged_balances = _bridged_point_balances(season.season_key)
    migrated = 0
    for user_id, balance, stickers in rows:
        bridged_balance = bridged_balances.pop(str(user_id), None)
        point_balance = (
            bridged_balance
            if bridged_balance is not None
            else max(0, int(balance or 0))
        )
        if point_balance > 0:
            _add_legacy_quantity(
                user_id,
                SEASON_POINT_ITEM_ID,
                SEASON_SCOPE_TYPE,
                str(season.id),
                point_balance,
            )
        if stickers and int(stickers) > 0:
            _add_legacy_quantity(
                user_id,
                STAR_STICKER_ITEM_ID,
                PERMANENT_SCOPE_TYPE,
                PERMANENT_SCOPE_ID,
                int(stickers),
            )
        migrated += 1
    for user_id, point_balance in bridged_balances.items():
        if point_balance > 0:
            _add_legacy_quantity(
                user_id,
                SEASON_POINT_ITEM_ID,
                SEASON_SCOPE_TYPE,
                str(season.id),
                point_balance,
            )
        migrated += 1

    session.add(MigrationState(key=LEGACY_MIGRATION_KEY, applied_at=int(time.time())))
    session.commit()
    migrate_legacy_season_participation(season=season)
    logger.info(f"Inventory migration completed for {migrated} users")


def migrate_legacy_season_participation(*, season=None) -> int:
    """Put inherited positive Pt wallets on season one's live ladder.

    The live ranking intentionally joins ``season_participation`` so merely
    reading a zero-point wallet does not put someone on the ladder. Season one
    is exceptional: its migrated historical Pt already represents real play,
    so every positive inherited wallet must count as participation.

    This has its own marker because some deployments already applied the
    balance migration before this backfill existed.
    """

    session = get_session()
    marker = (
        session.query(MigrationState)
        .filter(MigrationState.key == LEGACY_PARTICIPATION_MIGRATION_KEY)
        .first()
    )
    if marker is not None:
        return 0

    if season is None:
        from .season_service import get_current_season

        season = get_current_season()
    if season is None:
        return 0

    eligible_users = {
        user_id
        for (user_id,) in session.query(UserItem.user_id)
        .filter(
            UserItem.item_id == SEASON_POINT_ITEM_ID,
            UserItem.scope_type == SEASON_SCOPE_TYPE,
            UserItem.scope_id == str(season.id),
            UserItem.quantity > 0,
        )
        .all()
    }
    existing_users = {
        user_id
        for (user_id,) in session.query(SeasonParticipation.user_id)
        .filter(SeasonParticipation.season_id == season.id)
        .all()
    }
    participated_at = int(time.time())
    missing_users = eligible_users - existing_users
    session.add_all(
        SeasonParticipation(
            season_id=season.id,
            user_id=user_id,
            first_participated_at=participated_at,
            last_participated_at=participated_at,
        )
        for user_id in missing_users
    )
    session.add(
        MigrationState(
            key=LEGACY_PARTICIPATION_MIGRATION_KEY,
            applied_at=participated_at,
        )
    )
    session.commit()
    logger.info(
        "Legacy season participation backfill completed for "
        f"{len(missing_users)} users"
    )
    return len(missing_users)


def _bridged_point_balances(season_key: str) -> dict[str, int]:
    session = get_session()
    bridge_transactions = {
        (row.user_id, row.scope_id)
        for row in session.query(ItemTransaction)
        .filter(
            ItemTransaction.item_id == SEASON_POINT_ITEM_ID,
            ItemTransaction.scope_type == OFFSEASON_SCOPE_TYPE,
            ItemTransaction.reason == LEGACY_BRIDGE_KEY,
        )
        .all()
    }
    if not bridge_transactions:
        return {}
    rows = (
        session.query(UserItem)
        .filter(
            UserItem.item_id == SEASON_POINT_ITEM_ID,
            UserItem.scope_type == OFFSEASON_SCOPE_TYPE,
        )
        .all()
    )
    balances: dict[str, int] = {}
    for row in rows:
        if not row.scope_id.endswith(f"_to_{season_key}"):
            continue
        if (row.user_id, row.scope_id) in bridge_transactions:
            balances[row.user_id] = max(0, int(row.quantity))
    return balances


def _add_legacy_quantity(
    user_id: str, item_id: str, scope_type: str, scope_id: str, quantity: int
) -> None:
    session = get_session()
    tx_key = f"migration:{LEGACY_MIGRATION_KEY}:user:{user_id}:item:{item_id}"
    exists = (
        session.query(ItemTransaction)
        .filter(ItemTransaction.idempotency_key == tx_key)
        .first()
    )
    if exists is not None:
        return

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
    else:
        row.quantity += quantity
        row.updated_at = int(time.time())
        quantity_after = row.quantity

    session.add(
        ItemTransaction(
            user_id=user_id,
            item_id=item_id,
            scope_type=scope_type,
            scope_id=scope_id,
            delta=quantity,
            quantity_after=quantity_after,
            reason=LEGACY_MIGRATION_KEY,
            source_type="migration",
            source_id=LEGACY_MIGRATION_KEY,
            idempotency_key=tx_key,
            created_at=int(time.time()),
        )
    )
