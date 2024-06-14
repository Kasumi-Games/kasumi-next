from enum import StrEnum
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()
TransactionBase = declarative_base()


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
    last_daily_time = Column(Integer) # Unix timestamp


class Transaction(TransactionBase):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    category = Column(String)
    amount = Column(Integer)
    time = Column(Integer) # Unix timestamp
    description = Column(String)
