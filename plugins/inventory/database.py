"""Database setup for the inventory plugin."""

from nonebot import require
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import Base  # noqa: E402

database_path = store.get_data_file("inventory", "inventory.db")

session = None


def init_database():
    """Initialize database, catalog data, and one-shot migrations."""
    global session

    engine = create_engine(f"sqlite:///{database_path.resolve()}")
    session = sessionmaker(bind=engine)()

    from .catalog import sync_catalog
    from .migration import migrate_inventory_schema
    from .migration import migrate_legacy_monetary_balances
    from .season_service import sync_seasons_config

    Base.metadata.create_all(engine)
    migrate_inventory_schema()
    sync_catalog()
    sync_seasons_config()
    migrate_legacy_monetary_balances()


def get_session():
    if session is None:
        init_database()
    return session
