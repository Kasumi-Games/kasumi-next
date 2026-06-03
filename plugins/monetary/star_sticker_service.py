import time

from .models import StickerTransaction
from .database import get_transaction_session

LEVEL_UP_STICKERS = 120
CHECKIN_STICKERS = 120


def _inventory():
    from ..inventory import service

    return service


def add_star_stickers(user_id: str, amount: int, reason: str) -> int:
    """Add star stickers to a user, log the transaction, return new balance."""
    from .user_service import get_user

    if amount <= 0:
        return get_star_stickers(user_id)

    get_user(user_id)
    result = _inventory().grant_item(user_id, "star_sticker", amount, reason)
    balance_after = result.quantity_after

    _log_sticker_tx(user_id, amount, reason, balance_after)

    return balance_after


def get_star_stickers(user_id: str) -> int:
    """Query star sticker balance."""
    return _inventory().get_quantity(user_id, "star_sticker")


def cost_star_stickers(user_id: str, amount: int, reason: str) -> bool:
    """Spend star stickers (for gacha). Returns True if sufficient balance."""
    if amount <= 0:
        return True
    if get_star_stickers(user_id) < amount:
        return False

    balance_after = _inventory().cost_item(user_id, "star_sticker", amount, reason)

    _log_sticker_tx(user_id, -amount, reason, balance_after)

    return True


def admin_add_stickers(user_id: str, amount: int, reason: str) -> None:
    """Admin direct sticker add/subtract."""
    if amount >= 0:
        add_star_stickers(user_id, amount, f"admin_{reason}")
    else:
        cost_star_stickers(user_id, abs(amount), f"admin_{reason}")


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
