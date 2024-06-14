import time
from sqlalchemy.orm import Session
from .data_source import Transaction as TransactionData
from .data_source import TransactionCategory


class Transaction:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self, user_id: str, category: TransactionCategory, amount: int, description: str
    ) -> None:
        transaction = TransactionData(
            user_id=user_id,
            category=category,
            amount=amount,
            description=description,
            time=int(time.time()),
        )
        self.session.add(transaction)
        self.session.commit()
