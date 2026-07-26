import time
import datetime
from typing import List

from utils.clock import bot_date
from utils.clock import bot_today

from .models import User
from .models import TransactionCategory
from .database import get_session
from .transaction_service import get_transaction_manager


def _inventory():
    from ..inventory import service

    return service


def get_all_users() -> List[User]:
    """Get all users"""
    session = get_session()
    return session.query(User).all()


def get_user(user_id: str) -> User:
    """Get or create a user record"""
    session = get_session()

    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(
            user_id=user_id,
            balance=0,
            last_daily_time=0,
            level=1,
            xp=0,
            star_stickers=0,
            consecutive_checkins=0,
        )
        session.add(user)
        session.commit()
    return user


# Balance operations
def get_balance(user_id: str) -> int:
    """Get user's current balance"""
    get_user(user_id)
    return _inventory().get_quantity(user_id, "season_point")


def is_using_offseason_points() -> bool:
    from ..inventory.models import OFFSEASON_SCOPE_TYPE
    from ..inventory.season_service import get_point_scope

    scope_type, _, _ = get_point_scope()
    return scope_type == OFFSEASON_SCOPE_TYPE


def add_balance(user_id: str, amount: int, description: str):
    """Add balance to user account"""
    transaction_manager = get_transaction_manager()

    get_user(user_id)
    if amount < 0:
        return cost_balance(user_id, abs(amount), description)
    if amount > 0:
        _inventory().grant_item(user_id, "season_point", amount, description)

    transaction_manager.add(user_id, TransactionCategory.INCOME, amount, description)


def cost_balance(user_id: str, amount: int, description: str):
    """Deduct balance from user account"""
    transaction_manager = get_transaction_manager()

    get_user(user_id)
    if amount < 0:
        return add_balance(user_id, abs(amount), description)
    if amount > 0:
        _inventory().cost_item(user_id, "season_point", amount, description)

    transaction_manager.add(user_id, TransactionCategory.EXPENSE, amount, description)


def set_balance(user_id: str, amount: int, description: str):
    """Set user's balance to a specific amount"""
    transaction_manager = get_transaction_manager()

    get_user(user_id)
    _inventory().set_quantity(user_id, "season_point", amount, description)

    transaction_manager.add(user_id, TransactionCategory.SET, amount, description)


def transfer_balance(from_user_id: str, to_user_id: str, amount: int, description: str):
    """Transfer balance between users"""
    transaction_manager = get_transaction_manager()

    cost_balance(from_user_id, amount, f"transfer_to_{to_user_id}")
    add_balance(to_user_id, amount, f"transfer_from_{from_user_id}")

    transaction_manager.add(
        to_user_id, TransactionCategory.TRANSFER, amount, description
    )


# Level operations
def get_level(user_id: str) -> int:
    """Get user's current level"""
    user = get_user(user_id)
    return user.level


def set_level(user_id: str, level: int):
    """Set user's level to a specific value"""
    if level < 1:
        raise ValueError("Level must be at least 1")

    session = get_session()
    user = get_user(user_id)
    user.level = level
    session.commit()


def increase_level(user_id: str, levels: int = 1):
    """Increase user's level by specified amount"""
    if levels < 0:
        raise ValueError("Level increase must be positive")

    session = get_session()
    user = get_user(user_id)
    user.level += levels
    session.commit()


def decrease_level(user_id: str, levels: int = 1):
    """Decrease user's level by specified amount (minimum level is 1)"""
    if levels < 0:
        raise ValueError("Level decrease must be positive")

    session = get_session()
    user = get_user(user_id)
    user.level = max(1, user.level - levels)
    session.commit()


# Daily operations
def daily_checkin(user_id: str) -> bool:
    """Check and record daily checkin"""
    session = get_session()
    user = get_user(user_id)

    # Convert last_daily_time to date at the product-timezone day boundary
    # (utils/clock.py): check-in must reset at Beijing midnight everywhere.
    last_checkin_date = bot_date(user.last_daily_time)
    today = bot_today()

    if last_checkin_date != today:
        user.last_daily_time = time.time()
        session.commit()
        return True
    return False
