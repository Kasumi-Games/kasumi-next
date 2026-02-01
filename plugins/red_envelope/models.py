from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class RedEnvelope(Base):
    __tablename__ = "red_envelopes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    channel_index = Column(
        Integer, nullable=False
    )  # Channel-specific index (1, 2, 3...)
    title = Column(String, nullable=False, default="红包")
    total_amount = Column(Integer, nullable=False)
    remaining_amount = Column(Integer, nullable=False)
    total_count = Column(Integer, nullable=False)
    remaining_count = Column(Integer, nullable=False)
    pending_amounts = Column(
        Text, nullable=False
    )  # JSON array of pre-generated amounts
    created_at = Column(Integer, nullable=False)
    expires_at = Column(Integer, nullable=False)
    is_expired = Column(Boolean, nullable=False, default=False)

    claims = relationship(
        "ClaimRecord", back_populates="envelope", cascade="all, delete-orphan"
    )


class ClaimRecord(Base):
    __tablename__ = "claim_records"
    __table_args__ = (
        UniqueConstraint("envelope_id", "user_id", name="uq_envelope_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    envelope_id = Column(Integer, ForeignKey("red_envelopes.id"), nullable=False)
    user_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    claimed_at = Column(Integer, nullable=False)

    envelope = relationship("RedEnvelope", back_populates="claims")
