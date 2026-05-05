import random
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from nonebot.log import logger

from .. import monetary
from .database import get_session
from .models import ClaimRecord, RedEnvelope


@dataclass
class EnvelopeCompletionInfo:
    """Info returned when an envelope is fully claimed."""

    creator_id: str
    duration_seconds: int
    lucky_king_id: str
    lucky_king_amount: int


EXPIRE_SECONDS = 24 * 60 * 60
MAX_ENVELOPE_COUNT = 10_000


def _generate_next_amount(remaining_amount: int, remaining_count: int) -> int:
    """
    WeChat-style double-average algorithm. O(1) per claim.
    Each claim generates a random integer between 1 and
    floor(2 * remaining_amount / remaining_count), except the last claim
    which takes the full remaining amount.
    """
    if remaining_count <= 0 or remaining_amount < remaining_count:
        raise ValueError("Invalid amount or count")

    if remaining_count == 1:
        return remaining_amount

    max_amount = (2 * remaining_amount) // remaining_count
    return random.randint(1, max_amount)


def _get_next_channel_index(session, channel_id: str) -> int:
    """Get the next sequential index for a channel."""
    from sqlalchemy import func

    max_index = (
        session.query(func.max(RedEnvelope.channel_index))
        .filter(RedEnvelope.channel_id == channel_id)
        .scalar()
    )
    return (max_index or 0) + 1


def create_envelope(
    creator_id: str,
    channel_id: str,
    title: str,
    total_amount: int,
    total_count: int,
) -> RedEnvelope:
    if total_count > MAX_ENVELOPE_COUNT:
        raise ValueError(f"红包数量不能超过 {MAX_ENVELOPE_COUNT}")

    session = get_session()
    now = int(time.time())
    channel_index = _get_next_channel_index(session, channel_id)
    envelope = RedEnvelope(
        creator_id=creator_id,
        channel_id=channel_id,
        channel_index=channel_index,
        title=title,
        total_amount=total_amount,
        remaining_amount=total_amount,
        total_count=total_count,
        remaining_count=total_count,
        created_at=now,
        expires_at=now + EXPIRE_SECONDS,
        is_expired=False,
    )

    try:
        session.add(envelope)
        session.commit()
        logger.info(
            f"红包已创建: channel_index={channel_index} creator={creator_id} channel={channel_id} amount={total_amount} count={total_count}"
        )
        return envelope
    except Exception as e:
        session.rollback()
        logger.error("创建红包时发生错误: {}", e)
        raise


def get_active_envelopes(channel_id: str) -> list[RedEnvelope]:
    session = get_session()
    now = int(time.time())
    return (
        session.query(RedEnvelope)
        .filter(
            RedEnvelope.channel_id == channel_id,
            RedEnvelope.is_expired == False,  # noqa: E712
            RedEnvelope.remaining_count > 0,
            RedEnvelope.expires_at > now,
        )
        .order_by(RedEnvelope.created_at.desc())
        .all()
    )


def get_active_envelope_by_index(
    channel_id: str, channel_index: int
) -> Optional[RedEnvelope]:
    session = get_session()
    now = int(time.time())
    return (
        session.query(RedEnvelope)
        .filter(
            RedEnvelope.channel_index == channel_index,
            RedEnvelope.channel_id == channel_id,
            RedEnvelope.is_expired == False,  # noqa: E712
            RedEnvelope.expires_at > now,
        )
        .first()
    )


def _expire_envelope(envelope: RedEnvelope) -> int:
    session = get_session()
    if envelope.is_expired:
        return 0

    refund_amount = max(0, envelope.remaining_amount)
    if refund_amount > 0:
        monetary.add(
            envelope.creator_id,
            refund_amount,
            f"red_envelope_refund_{envelope.id}",
        )

    envelope.is_expired = True
    envelope.remaining_amount = 0
    envelope.remaining_count = 0

    session.add(envelope)
    session.commit()

    logger.info(f"红包过期处理完成: id={envelope.id} refund={refund_amount}")
    return refund_amount


def claim_envelope(
    user_id: str, channel_id: str, channel_index: Optional[int] = None
) -> Tuple[str, Optional[int], Optional[EnvelopeCompletionInfo]]:
    session = get_session()
    now = int(time.time())

    if channel_index is None:
        envelope = (
            session.query(RedEnvelope)
            .filter(
                RedEnvelope.channel_id == channel_id,
                RedEnvelope.is_expired == False,  # noqa: E712
                RedEnvelope.remaining_count > 0,
                RedEnvelope.expires_at > now,
            )
            .order_by(RedEnvelope.created_at.desc())
            .first()
        )
    else:
        envelope = (
            session.query(RedEnvelope)
            .filter(
                RedEnvelope.channel_index == channel_index,
                RedEnvelope.channel_id == channel_id,
            )
            .first()
        )

    if not envelope:
        return ("no_active" if channel_index is None else "not_found", None, None)

    if envelope.is_expired or envelope.expires_at <= now:
        _expire_envelope(envelope)
        return ("expired", None, None)

    if envelope.remaining_count <= 0 or envelope.remaining_amount <= 0:
        return ("empty", None, None)

    already_claimed = (
        session.query(ClaimRecord)
        .filter(
            ClaimRecord.envelope_id == envelope.id,
            ClaimRecord.user_id == user_id,
        )
        .first()
    )
    if already_claimed:
        return ("already", None, None)

    # Generate amount on-the-fly using WeChat double-average algorithm
    amount = _generate_next_amount(
        envelope.remaining_amount, envelope.remaining_count
    )

    try:
        envelope.remaining_amount -= amount
        envelope.remaining_count -= 1
        is_last_claim = envelope.remaining_count == 0

        claim = ClaimRecord(
            envelope_id=envelope.id,
            user_id=user_id,
            amount=amount,
            claimed_at=now,
        )
        session.add(claim)
        session.commit()

        monetary.add(user_id, amount, f"red_envelope_claim_{envelope.id}")
        logger.info(f"红包领取成功: id={envelope.id} user={user_id} amount={amount}")

        # If this was the last claim, find the lucky king
        completion_info = None
        if is_last_claim:
            all_claims = (
                session.query(ClaimRecord)
                .filter(ClaimRecord.envelope_id == envelope.id)
                .all()
            )
            lucky_king = max(all_claims, key=lambda c: c.amount)
            duration = now - envelope.created_at
            completion_info = EnvelopeCompletionInfo(
                creator_id=envelope.creator_id,
                duration_seconds=duration,
                lucky_king_id=lucky_king.user_id,
                lucky_king_amount=lucky_king.amount,
            )

        return ("success", amount, completion_info)
    except Exception as e:
        session.rollback()
        logger.error("领取红包时发生错误: {}", e)
        return ("error", None, None)


def expire_overdue_envelopes() -> int:
    session = get_session()
    now = int(time.time())
    expired = (
        session.query(RedEnvelope)
        .filter(
            RedEnvelope.is_expired == False,  # noqa: E712
            RedEnvelope.expires_at <= now,
        )
        .all()
    )

    count = 0
    for envelope in expired:
        _expire_envelope(envelope)
        count += 1

    return count
