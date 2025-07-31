import time
from .database import get_session
from .models import User, TransactionCategory
from .transaction_service import get_transaction_manager


def get_user(user_id: str) -> User:
    """Get or create a user record"""
    session = get_session()

    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, balance=0, last_daily_time=0, level=0)
        session.add(user)
        session.commit()
    return user


# Balance operations
def get_balance(user_id: str) -> int:
    """Get user's current balance"""
    return get_user(user_id).balance


def add_balance(user_id: str, amount: int, description: str):
    """Add balance to user account"""
    session = get_session()
    transaction_manager = get_transaction_manager()

    user = get_user(user_id)
    user.balance += amount
    session.commit()

    transaction_manager.add(user_id, TransactionCategory.INCOME, amount, description)


def cost_balance(user_id: str, amount: int, description: str):
    """Deduct balance from user account"""
    session = get_session()
    transaction_manager = get_transaction_manager()

    user = get_user(user_id)
    user.balance -= amount
    session.commit()

    transaction_manager.add(user_id, TransactionCategory.EXPENSE, amount, description)


def set_balance(user_id: str, amount: int, description: str):
    """Set user's balance to a specific amount"""
    session = get_session()
    transaction_manager = get_transaction_manager()

    user = get_user(user_id)
    user.balance = amount
    session.commit()

    transaction_manager.add(user_id, TransactionCategory.SET, amount, description)


def transfer_balance(from_user_id: str, to_user_id: str, amount: int, description: str):
    """Transfer balance between users"""
    session = get_session()
    transaction_manager = get_transaction_manager()

    cost_balance(from_user_id, amount, f"transfer_to_{to_user_id}")
    add_balance(to_user_id, amount, f"transfer_from_{from_user_id}")
    session.commit()

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
    user.level = max(1, user.level - levels)  # Ensure level never goes below 1
    session.commit()


# Daily operations
def daily_checkin(user_id: str) -> bool:
    """Check and record daily checkin"""
    session = get_session()

    user = get_user(user_id)
    # Check if last checkin was before today
    if time.localtime(user.last_daily_time).tm_mday != time.localtime().tm_mday:
        user.last_daily_time = time.time()
        session.commit()
        return True
    return False
