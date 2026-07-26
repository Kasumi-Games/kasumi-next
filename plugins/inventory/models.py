"""Inventory and season data models."""

from typing import Optional
from dataclasses import dataclass

from sqlalchemy import Text
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

PERMANENT_SCOPE_TYPE = "permanent"
PERMANENT_SCOPE_ID = "0"
SEASON_SCOPE_TYPE = "season"
OFFSEASON_SCOPE_TYPE = "offseason"

STAR_STICKER_ITEM_ID = "star_sticker"
SEASON_POINT_ITEM_ID = "season_point"
BONSAI_ITEM_ID = "bonsai"


class Item(Base):
    __tablename__ = "items"

    item_id = Column(String, primary_key=True)
    category = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    stackable = Column(Boolean, default=True, nullable=False)
    visible = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)

    currency = relationship("CurrencyItem", uselist=False, back_populates="item")
    cosmetic = relationship("CosmeticItem", uselist=False, back_populates="item")


class CurrencyItem(Base):
    __tablename__ = "currency_items"

    item_id = Column(String, ForeignKey("items.item_id"), primary_key=True)
    currency_kind = Column(String, nullable=False)  # permanent | seasonal
    unit_name = Column(String, default="", nullable=False)
    rankable = Column(Boolean, default=False, nullable=False)
    reset_policy = Column(String, default="none", nullable=False)

    item = relationship("Item", back_populates="currency")


class CosmeticItem(Base):
    __tablename__ = "cosmetic_items"

    item_id = Column(String, ForeignKey("items.item_id"), primary_key=True)
    cosmetic_type = Column(String, nullable=False)  # avatar_frame | title | theme | standing_art
    rarity = Column(Integer, default=1, nullable=False)

    item = relationship("Item", back_populates="cosmetic")


class UserItem(Base):
    __tablename__ = "user_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    item_id = Column(String, ForeignKey("items.item_id"), nullable=False, index=True)
    scope_type = Column(String, nullable=False, default=PERMANENT_SCOPE_TYPE)
    scope_id = Column(String, nullable=False, default=PERMANENT_SCOPE_ID)
    quantity = Column(Integer, default=0, nullable=False)
    updated_at = Column(Integer, nullable=False)

    item = relationship("Item")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "item_id",
            "scope_type",
            "scope_id",
            name="uq_user_item_scope",
        ),
    )


class EquippedItem(Base):
    __tablename__ = "equipped_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    slot = Column(String, nullable=False)
    item_id = Column(String, ForeignKey("items.item_id"), nullable=False)
    updated_at = Column(Integer, nullable=False)

    item = relationship("Item")

    __table_args__ = (UniqueConstraint("user_id", "slot", name="uq_user_equip_slot"),)


class ItemTransaction(Base):
    __tablename__ = "item_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    item_id = Column(String, nullable=False, index=True)
    scope_type = Column(String, nullable=False)
    scope_id = Column(String, nullable=False)
    delta = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    source_type = Column(String, default="", nullable=False)
    source_id = Column(String, default="", nullable=False)
    idempotency_key = Column(String, unique=True, nullable=True)
    created_at = Column(Integer, nullable=False)


class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_key = Column(String, unique=True, nullable=False)
    season_number = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, default=0, nullable=False)
    timezone = Column(String, default="UTC+8", nullable=False)
    status = Column(String, default="planned", nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)
    config_hash = Column(String, default="", nullable=False)
    settled_at = Column(Integer, default=0, nullable=False)


class SeasonRanking(Base):
    __tablename__ = "season_rankings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    final_points = Column(Integer, nullable=False)
    rank = Column(Integer, nullable=False)
    reward_summary_json = Column(Text, default="{}", nullable=False)

    __table_args__ = (
        UniqueConstraint("season_id", "user_id", name="uq_season_ranking_user"),
    )


class SeasonRankSnapshot(Base):
    __tablename__ = "season_rank_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_id = Column(Integer, nullable=False, index=True)
    captured_at = Column(Integer, nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    user_id = Column(String, default="", nullable=False)
    points = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "captured_at",
            "rank",
            name="uq_season_snapshot_rank",
        ),
    )


class SeasonReward(Base):
    __tablename__ = "season_rewards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    tier_key = Column(String, nullable=False)
    rank = Column(Integer, nullable=False)
    points = Column(Integer, nullable=False)
    reward_json = Column(Text, default="{}", nullable=False)
    mail_id = Column(Integer, default=0, nullable=False)
    created_at = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("season_id", "user_id", name="uq_season_reward_user"),
    )


class SeasonParticipation(Base):
    __tablename__ = "season_participation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    season_id = Column(Integer, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    first_participated_at = Column(Integer, nullable=False)
    last_participated_at = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("season_id", "user_id", name="uq_season_participation_user"),
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True)
    profile_description = Column(Text, default="", nullable=False)
    updated_at = Column(Integer, nullable=False)


class MigrationState(Base):
    __tablename__ = "migration_state"

    key = Column(String, primary_key=True)
    applied_at = Column(Integer, nullable=False)


@dataclass(frozen=True)
class ItemAmount:
    item_id: str
    quantity: int
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None


@dataclass(frozen=True)
class ItemScope:
    scope_type: str
    scope_id: str


@dataclass(frozen=True)
class GrantResult:
    item_id: str
    quantity: int
    granted: int
    quantity_after: int
    skipped: bool = False
    message: str = ""
