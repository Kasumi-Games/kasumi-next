"""
Database models and data structures for the monetary plugin.
"""

from enum import StrEnum
from dataclasses import dataclass
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


# Database table base classes
Base = declarative_base()
TransactionBase = declarative_base()


class TransactionCategory(StrEnum):
    """Transaction categories for monetary operations"""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    SET = "set"


class User(Base):
    """User table model"""

    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    balance = Column(Integer)
    last_daily_time = Column(Integer)  # Unix timestamp
    level = Column(Integer, default=1)  # User level, starts from 1


class Transaction(TransactionBase):
    """Transaction table model"""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    category = Column(String)
    amount = Column(Integer)
    time = Column(Integer)  # Unix timestamp
    description = Column(String)


@dataclass
class UserRank:
    """User ranking information"""

    rank: int
    distance_to_next_rank: int
    distance_to_next_level: int


@dataclass
class UserStats:
    """Comprehensive user statistics"""

    user_id: str
    balance: int
    level: int
    rank: int
    distance_to_next_rank: int
    distance_to_next_level: int
    last_daily_time: int
