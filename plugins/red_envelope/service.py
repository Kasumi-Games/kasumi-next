import json
import random
import time
from typing import List, Optional, Tuple

from nonebot.log import logger

from .. import monetary
from .database import get_session
from .models import ClaimRecord, RedEnvelope


EXPIRE_SECONDS = 24 * 60 * 60


def _generate_random_distribution(total_amount: int, count: int) -> List[int]:
    """
    Pre-generate a random distribution of coins using "random cut" algorithm.
    Creates exciting variance - some get a lot, some get little!
    Each recipient gets at least 1 coin.
    """
    if count <= 0 or total_amount < count:
        raise ValueError("Invalid amount or count")

    if count == 1:
        return [total_amount]

    # Reserve 1 coin per person to ensure minimum
    reserved = count
    pool = total_amount - reserved

    if pool <= 0:
        # Everyone gets exactly 1 coin
        return [1] * count

    # "Random cut" algorithm: imagine a line of length `pool`
    # Generate (count - 1) random cut points, then calculate segment lengths
    cuts = sorted(random.random() for _ in range(count - 1))

    # Calculate segment lengths based on cut points
    amounts = []
    prev = 0.0
    for cut in cuts:
        segment = cut - prev
        amounts.append(segment)
        prev = cut
    amounts.append(1.0 - prev)  # Last segment

    # Convert proportions to actual coin amounts
    # Use a multiplier to amplify variance
    raw_amounts = [max(0, int(proportion * pool)) for proportion in amounts]

    # Distribute any rounding remainder randomly
    remainder = pool - sum(raw_amounts)
    for _ in range(remainder):
        idx = random.randint(0, count - 1)
        raw_amounts[idx] += 1

    # Add the reserved 1 coin per person
    final_amounts = [amt + 1 for amt in raw_amounts]

    # Shuffle for extra randomness in claim order
    random.shuffle(final_amounts)
    return final_amounts


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
    session = get_session()
    now = int(time.time())
    channel_index = _get_next_channel_index(session, channel_id)
    pending_amounts = _generate_random_distribution(total_amount, total_count)
    envelope = RedEnvelope(
        creator_id=creator_id,
        channel_id=channel_id,
        channel_index=channel_index,
        title=title,
        total_amount=total_amount,
        remaining_amount=total_amount,
        total_count=total_count,
        remaining_count=total_count,
        pending_amounts=json.dumps(pending_amounts),
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
        logger.error(f"创建红包时发生错误: {e}")
        raise


def get_active_envelopes(channel_id: str) -> List[RedEnvelope]:
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
) -> Tuple[str, Optional[int]]:
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
        return ("no_active" if channel_index is None else "not_found", None)

    if envelope.is_expired or envelope.expires_at <= now:
        _expire_envelope(envelope)
        return ("expired", None)

    if envelope.remaining_count <= 0 or envelope.remaining_amount <= 0:
        return ("empty", None)

    already_claimed = (
        session.query(ClaimRecord)
        .filter(
            ClaimRecord.envelope_id == envelope.id,
            ClaimRecord.user_id == user_id,
        )
        .first()
    )
    if already_claimed:
        return ("already", None)

    # Pop the next pre-generated amount
    pending = json.loads(envelope.pending_amounts)
    if not pending:
        return ("empty", None)
    amount = pending.pop(0)

    try:
        envelope.pending_amounts = json.dumps(pending)
        envelope.remaining_amount -= amount
        envelope.remaining_count -= 1

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
        return ("success", amount)
    except Exception as e:
        session.rollback()
        logger.error(f"领取红包时发生错误: {e}")
        return ("error", None)


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
