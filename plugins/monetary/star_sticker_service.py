import time

from nonebot.log import logger

from .models import StickerTransaction, User
from .database import get_session, get_transaction_session


LEVEL_UP_STICKERS = 120
CHECKIN_STICKERS = 120


def add_star_stickers(user_id: str, amount: int, reason: str) -> int:
    """Add star stickers to a user, log the transaction, return new balance."""
    session = get_session()
    user = session.query(User).filter(User.user_id == user_id).first()

    if not user:
        logger.warning(f"User {user_id} not found for sticker add")
        return 0

    user.star_stickers += amount
    balance_after = user.star_stickers
    session.commit()

    _log_sticker_tx(user_id, amount, reason, balance_after)

    return balance_after


def get_star_stickers(user_id: str) -> int:
    """Query star sticker balance."""
    session = get_session()
    user = session.query(User).filter(User.user_id == user_id).first()
    return user.star_stickers if user else 0


def cost_star_stickers(user_id: str, amount: int, reason: str) -> bool:
    """Spend star stickers (for gacha). Returns True if sufficient balance."""
    session = get_session()
    user = session.query(User).filter(User.user_id == user_id).first()

    if not user or user.star_stickers < amount:
        return False

    user.star_stickers -= amount
    balance_after = user.star_stickers
    session.commit()

    _log_sticker_tx(user_id, -amount, reason, balance_after)

    return True


def admin_add_stickers(user_id: str, amount: int, reason: str) -> None:
    """Admin direct sticker add/subtract."""
    add_star_stickers(user_id, amount, f"admin_{reason}")


def _log_sticker_tx(user_id: str, amount: int, reason: str, balance_after: int):
    session = get_transaction_session()
    tx = StickerTransaction(
        user_id=user_id,
        amount=amount,
        reason=reason,
        balance_after=balance_after,
        created_at=int(time.time()),
    )
    session.add(tx)
    session.commit()
