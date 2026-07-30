"""Persistent purchase records for 流星堂."""

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SeasonPullPurchase(Base):
    __tablename__ = "season_pull_purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    season_id = Column(Integer, nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(Integer, nullable=False)
    completed_at = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "season_id",
            "sequence",
            name="uq_ryuseido_season_pull_sequence",
        ),
    )
