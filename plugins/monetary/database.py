from nonebot import require
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402

from .models import Base, TransactionBase  # noqa: E402
from .migration import (  # noqa: E402
    migrate_add_level_column,
    migrate_fix_balance_column,
)


# Database paths
database_path = store.get_data_file("monetary", "data.db")
transaction_path = store.get_data_file("monetary", "transaction.db")

# Global session variables
session = None
transaction_session = None


def init_database():
    """Initialize database connections and create tables"""
    global session, transaction_session

    # Run migrations first (before creating tables with SQLAlchemy)
    migrate_add_level_column()
    migrate_fix_balance_column()

    # Initialize main database
    engine = create_engine(f"sqlite:///{database_path.resolve()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    # Initialize transaction database
    transaction_engine = create_engine(f"sqlite:///{transaction_path.resolve()}")
    TransactionBase.metadata.create_all(transaction_engine)
    transaction_session = sessionmaker(bind=transaction_engine)()


def get_session():
    """Get the main database session"""
    if session is None:
        init_database()
    return session


def get_transaction_session():
    """Get the transaction database session"""
    if transaction_session is None:
        init_database()
    return transaction_session
