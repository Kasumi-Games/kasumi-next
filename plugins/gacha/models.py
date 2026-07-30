"""Seasonal gacha persistence models."""

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class GachaState(Base):
    __tablename__ = "gacha_states"

    user_id = Column(String, primary_key=True)
    pity_count = Column(Integer, default=0, nullable=False)
    total_pulls = Column(Integer, default=0, nullable=False)
    updated_at = Column(Integer, nullable=False)


class GachaPull(Base):
    __tablename__ = "gacha_pulls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    banner_key = Column(String, nullable=False, index=True)
    season_key = Column(String, nullable=False, index=True)
    item_id = Column(String, nullable=False)
    character_id = Column(String, default="", nullable=False)
    rarity = Column(Integer, nullable=False)
    cost = Column(Integer, nullable=False)
    payment_item_id = Column(String, default="star_sticker", nullable=False)
    pity_before = Column(Integer, nullable=False)
    pity_after = Column(Integer, nullable=False)
    message = Column(String, default="", nullable=False)
    created_at = Column(Integer, nullable=False, index=True)
