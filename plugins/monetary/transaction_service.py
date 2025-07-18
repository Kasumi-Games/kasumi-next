import time
from sqlalchemy.orm import Session

from .database import get_transaction_session
from .models import Transaction, TransactionCategory


class TransactionManager:
    """Manager class for handling transaction logging"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self, user_id: str, category: TransactionCategory, amount: int, description: str
    ) -> None:
        """Add a transaction record"""
        transaction = Transaction(
            user_id=user_id,
            category=category,
            amount=amount,
            description=description,
            time=int(time.time()),
        )
        self.session.add(transaction)
        self.session.commit()


# Global transaction manager instance
_transaction_manager = None


def get_transaction_manager() -> TransactionManager:
    """Get the global transaction manager instance"""
    global _transaction_manager
    if _transaction_manager is None:
        session = get_transaction_session()
        _transaction_manager = TransactionManager(session)
    return _transaction_manager
