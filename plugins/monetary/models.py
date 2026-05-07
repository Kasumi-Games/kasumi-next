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
    level = Column(Integer, default=1)  # XP level, starts from 1
    xp = Column(Integer, default=0)  # Total accumulated XP
    star_stickers = Column(Integer, default=0)  # Star stickers balance
    consecutive_checkins = Column(Integer, default=0)  # Consecutive check-in days


class Transaction(TransactionBase):
    """Transaction table model"""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    category = Column(String)
    amount = Column(Integer)
    time = Column(Integer)  # Unix timestamp
    description = Column(String)


class StickerTransaction(TransactionBase):
    """Sticker transaction log table"""

    __tablename__ = "sticker_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Positive=earned, negative=spent
    reason = Column(String, nullable=False)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(Integer, nullable=False)


@dataclass
class UserRank:
    """User ranking information"""

    rank: int
    xp_gap: int  # XP gap to next rank


@dataclass
class UserStats:
    """Comprehensive user statistics"""

    user_id: str
    balance: int
    level: int
    xp: int
    star_stickers: int
    rank: int
    xp_gap: int
    last_daily_time: int
