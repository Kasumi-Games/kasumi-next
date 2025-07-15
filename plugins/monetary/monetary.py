import time
from enum import StrEnum
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from nonebot import require
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store  # noqa: E402


Base = declarative_base()
TransactionBase = declarative_base()


database_path = store.get_data_file("monetary", "data.db")
transaction_path = store.get_data_file("monetary", "transaction.db")

session = None
transaction_session = None
transaction = None


def init_database():
    global session, transaction_session, transaction
    engine = create_engine(f"sqlite:///{database_path.resolve()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    transaction_engine = create_engine(f"sqlite:///{transaction_path.resolve()}")
    TransactionBase.metadata.create_all(transaction_engine)
    transaction_session = sessionmaker(bind=transaction_engine)()

    transaction = TransactionManager(transaction_session)


class TransactionCategory(StrEnum):
    """
    交易类型
    """

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    SET = "set"


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    balance = Column(Integer)
    last_daily_time = Column(Integer)  # Unix timestamp


class Transaction(TransactionBase):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    category = Column(String)
    amount = Column(Integer)
    time = Column(Integer)  # Unix timestamp
    description = Column(String)


class TransactionManager:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self, user_id: str, category: TransactionCategory, amount: int, description: str
    ) -> None:
        transaction = Transaction(
            user_id=user_id,
            category=category,
            amount=amount,
            description=description,
            time=int(time.time()),
        )
        self.session.add(transaction)
        self.session.commit()


def get_user(user_id: str) -> User:
    if session is None:
        init_database()

    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, balance=0, last_daily_time=0)
        session.add(user)
        session.commit()
    return user


def add(user_id: str, amount: int, description: str):
    if session is None:
        init_database()

    user = get_user(user_id)
    user.balance += amount
    session.commit()

    transaction.add(user_id, TransactionCategory.INCOME, amount, description)


def cost(user_id: str, amount: int, description: str):
    if session is None:
        init_database()

    user = get_user(user_id)
    user.balance -= amount
    session.commit()

    transaction.add(user_id, TransactionCategory.EXPENSE, amount, description)


def set(user_id: str, amount: int, description: str):
    if session is None:
        init_database()

    user = get_user(user_id)
    user.balance = amount
    session.commit()

    transaction.add(user_id, TransactionCategory.SET, amount, description)


def get(user_id: str) -> int:
    return get_user(user_id).balance


def transfer(from_user_id: str, to_user_id: str, amount: int, description: str):
    if session is None:
        init_database()

    cost(from_user_id, amount, f"transfer_to_{to_user_id}")
    add(to_user_id, amount, f"transfer_from_{from_user_id}")
    session.commit()

    transaction.add(to_user_id, TransactionCategory.TRANSFER, amount, description)


def daily(user_id: str) -> bool:
    if session is None:
        init_database()

    user = get_user(user_id)
    # 如果上次签到在今日 0 点之前
    if time.localtime(user.last_daily_time).tm_mday != time.localtime().tm_mday:
        user.last_daily_time = time.time()
        session.commit()
        return True
    return False


def get_top_users(limit: int = 10) -> list[dict]:
    """Get top users by balance

    Args:
        limit: Maximum number of users to return

    Returns:
        List of dicts with 'user_id' and 'balance' keys
    """
    if session is None:
        init_database()

    users = session.query(User).order_by(User.balance.desc()).limit(limit).all()
    return [{"user_id": user.user_id, "balance": user.balance} for user in users]


def get_user_rank(user_id: str) -> tuple[int, int]:
    """Get user's rank and distance to next rank

    Args:
        user_id: User ID to get rank for

    Returns:
        Tuple of (rank, distance_to_next_rank)
    """
    if session is None:
        init_database()

    user = get_user(user_id)
    rank = session.query(User).filter(User.balance > user.balance).count() + 1

    # Get user with next higher balance
    next_user = (
        session.query(User)
        .filter(User.balance > user.balance)
        .order_by(User.balance.asc())
        .first()
    )

    distance = next_user.balance - user.balance if next_user is not None else 0
    return rank, distance
