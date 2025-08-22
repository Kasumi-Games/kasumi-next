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

    def get_transactions_by_description(
        self, user_id: str, description: str, limit: int = None
    ) -> list:
        """Get transactions filtered by user and description"""
        query = (
            self.session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .filter(Transaction.description == description)
            .order_by(Transaction.time.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()


# Global transaction manager instance
_transaction_manager = None


def get_transaction_manager() -> TransactionManager:
    """Get the global transaction manager instance"""
    global _transaction_manager
    if _transaction_manager is None:
        session = get_transaction_session()
        _transaction_manager = TransactionManager(session)
    return _transaction_manager


def get_user_transactions(
    user_id: str, description: str = None, limit: int = None
) -> list:
    """
    Get user transactions with optional filtering

    Args:
        user_id: User ID to get transactions for
        description: Optional description filter
        limit: Optional limit on number of results

    Returns:
        List of Transaction objects ordered by time (newest first)
    """
    transaction_manager = get_transaction_manager()

    if description:
        return transaction_manager.get_transactions_by_description(
            user_id, description, limit
        )
    else:
        # Get all transactions for user if no description filter
        session = get_transaction_session()
        query = (
            session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.time.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()
