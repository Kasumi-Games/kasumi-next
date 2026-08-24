import time
import uuid
import random
from typing import Tuple
from typing import Optional
from dataclasses import dataclass

from nonebot.log import logger

from .models import ClaimRecord
from .models import RedEnvelope
from .database import get_session
from ..inventory import point_hold_service as point_holds
from ..inventory.models import ItemTransaction
from ..inventory.models import PointHold
from ..inventory.database import get_session as get_inventory_session
from ..inventory.season_service import get_point_scope_at


@dataclass
class EnvelopeClaim:
    """One claim on a finished envelope, in claim order."""

    user_id: str
    amount: int


@dataclass
class EnvelopeCompletionInfo:
    """Info returned when an envelope is fully claimed.

    Built only on the final claim — which is why 手气王 exists nowhere before
    the completion card (consistency review #15).
    """

    creator_id: str
    duration_seconds: int
    lucky_king_id: str
    lucky_king_amount: int
    channel_index: int
    title: str
    total_amount: int
    total_count: int
    claims: tuple[EnvelopeClaim, ...]


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
    # Ensure each remaining claim gets at least 1
    max_amount = min(max_amount, remaining_amount - remaining_count + 1)
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

    hold_key = f"red_envelope:{uuid.uuid4().hex}"
    hold = point_holds.reserve_points(
        creator_id,
        total_amount,
        hold_key,
        "red_envelope",
        operation_key=f"{hold_key}:create",
    )
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
        hold_key=hold_key,
        scope_type=hold.scope_type,
        scope_id=hold.scope_id,
        closed_reason="",
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
        point_holds.refund_point_hold(
            hold_key, operation_key=f"{hold_key}:create_failed"
        )
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


def _close_envelope(
    envelope: RedEnvelope, *, reason: str, cutoff: int
) -> int:
    session = get_session()
    if envelope.is_expired:
        return 0

    pending_claims = (
        session.query(ClaimRecord)
        .filter(
            ClaimRecord.envelope_id == envelope.id,
            ClaimRecord.credited_at == 0,
            ClaimRecord.claimed_at <= cutoff,
        )
        .order_by(ClaimRecord.id.asc())
        .all()
    )
    for claim in pending_claims:
        _credit_claim(envelope, claim, max(cutoff, claim.claimed_at), allow_closed=True)

    refund_amount = 0
    if envelope.hold_key:
        refund = point_holds.refund_point_hold(
            envelope.hold_key,
            operation_key=f"{envelope.hold_key}:close:{reason}",
        )
        refund_amount = refund.amount

    envelope.is_expired = True
    envelope.remaining_amount = 0
    envelope.remaining_count = 0
    envelope.closed_reason = reason

    session.add(envelope)
    session.commit()

    logger.info(
        f"红包关闭处理完成: id={envelope.id} reason={reason} refund={refund_amount}"
    )
    return refund_amount


def _expire_envelope(envelope: RedEnvelope) -> int:
    return _close_envelope(
        envelope, reason="expired", cutoff=max(1, envelope.expires_at)
    )


def _build_completion_info(
    envelope: RedEnvelope, now: int
) -> Optional[EnvelopeCompletionInfo]:
    if envelope.remaining_count != 0:
        return None

    all_claims = (
        get_session()
        .query(ClaimRecord)
        .filter(ClaimRecord.envelope_id == envelope.id)
        .order_by(ClaimRecord.claimed_at, ClaimRecord.id)
        .all()
    )
    lucky_king = max(all_claims, key=lambda claim: claim.amount)
    return EnvelopeCompletionInfo(
        creator_id=envelope.creator_id,
        duration_seconds=now - envelope.created_at,
        lucky_king_id=lucky_king.user_id,
        lucky_king_amount=lucky_king.amount,
        channel_index=envelope.channel_index,
        title=envelope.title,
        total_amount=envelope.total_amount,
        total_count=envelope.total_count,
        claims=tuple(
            EnvelopeClaim(user_id=claim.user_id, amount=claim.amount)
            for claim in all_claims
        ),
    )


def _credit_claim(
    envelope: RedEnvelope,
    claim: ClaimRecord,
    now: int,
    *,
    allow_closed: bool = False,
) -> Optional[EnvelopeCompletionInfo]:
    if not envelope.hold_key:
        raise ValueError("红包缺少 Pt 托管记录")
    point_holds.capture_point_hold(
        envelope.hold_key,
        claim.user_id,
        claim.amount,
        operation_key=f"{envelope.hold_key}:claim:{claim.id}",
        allow_closed_scope=allow_closed,
        now=now,
    )
    claim.credited_at = max(1, now)
    get_session().commit()
    logger.info(
        f"红包领取成功: id={envelope.id} user={claim.user_id} amount={claim.amount}"
    )
    return _build_completion_info(envelope, now)


def claim_envelope(
    user_id: str, channel_id: str, channel_index: Optional[int] = None
) -> Tuple[str, Optional[int], Optional[EnvelopeCompletionInfo]]:
    session = get_session()
    now = int(time.time())

    # A claim reservation is committed before crossing into the inventory
    # database. Retry any reserved-but-uncredited claim first, including after
    # the envelope became full or expired.
    pending_query = (
        session.query(ClaimRecord)
        .join(RedEnvelope, RedEnvelope.id == ClaimRecord.envelope_id)
        .filter(
            ClaimRecord.user_id == user_id,
            ClaimRecord.credited_at == 0,
            RedEnvelope.channel_id == channel_id,
        )
    )
    if channel_index is not None:
        pending_query = pending_query.filter(
            RedEnvelope.channel_index == channel_index
        )
    pending_claim = pending_query.order_by(ClaimRecord.id.desc()).first()
    if pending_claim is not None:
        envelope = pending_claim.envelope
        try:
            completion = _credit_claim(envelope, pending_claim, now)
            return ("success", pending_claim.amount, completion)
        except Exception as e:
            session.rollback()
            logger.error("补发红包到账时发生错误: {}", e)
            return ("error", None, None)

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

    hold = point_holds.get_point_hold(envelope.hold_key or "")
    if hold is None or not point_holds.is_point_hold_scope_open(hold, now=now):
        _close_envelope(envelope, reason="season_end", cutoff=now)
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

        claim = ClaimRecord(
            envelope_id=envelope.id,
            user_id=user_id,
            amount=amount,
            claimed_at=now,
            credited_at=0,
        )
        session.add(claim)
        session.commit()

        completion_info = _credit_claim(envelope, claim, now)
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


def close_scope_envelopes(scope_type: str, scope_id: str, cutoff: int) -> None:
    """Honor pre-cutoff claims, then refund active envelopes in one Pt scope."""

    session = get_session()
    envelopes = (
        session.query(RedEnvelope)
        .filter(
            RedEnvelope.scope_type == scope_type,
            RedEnvelope.scope_id == scope_id,
            RedEnvelope.is_expired == False,  # noqa: E712
        )
        .order_by(RedEnvelope.created_at.asc(), RedEnvelope.id.asc())
        .all()
    )
    for envelope in envelopes:
        _close_envelope(envelope, reason="season_end", cutoff=cutoff)


def refund_orphaned_envelope_holds() -> int:
    """Refund open holds left before their envelope row could be committed.

    Creation crosses two SQLite databases: the inventory hold commits first,
    followed by the red-envelope row.  A hard process exit between those
    commits bypasses the normal exception refund.  Startup/lifecycle
    reconciliation runs without live command interleaving and can therefore
    safely treat an unreferenced open hold as abandoned.
    """

    inventory_session = get_inventory_session()
    hold_keys = [
        row[0]
        for row in inventory_session.query(PointHold.hold_key)
        .filter(
            PointHold.kind == "red_envelope",
            PointHold.status == point_holds.HOLD_OPEN,
        )
        .order_by(PointHold.created_at.asc(), PointHold.hold_key.asc())
        .all()
    ]
    if not hold_keys:
        return 0

    referenced = {
        row[0]
        for row in get_session()
        .query(RedEnvelope.hold_key)
        .filter(RedEnvelope.hold_key.is_not(None))
        .all()
    }
    orphaned = [hold_key for hold_key in hold_keys if hold_key not in referenced]
    for hold_key in orphaned:
        point_holds.refund_point_hold(
            hold_key,
            operation_key=f"{hold_key}:orphan_refund",
        )
    return len(orphaned)


def reconcile_legacy_envelope_holds(now: int | None = None) -> int:
    """Attach old active envelope rows to funded holds without debiting twice."""

    now = int(time.time()) if now is None else now
    session = get_session()
    envelopes = (
        session.query(RedEnvelope)
        .filter(
            RedEnvelope.is_expired == False,  # noqa: E712
            RedEnvelope.remaining_count > 0,
            RedEnvelope.hold_key.is_(None),
        )
        .all()
    )
    migrated = 0
    for envelope in envelopes:
        pending_amount = 0
        pending_claims = (
            session.query(ClaimRecord)
            .filter(
                ClaimRecord.envelope_id == envelope.id,
                ClaimRecord.credited_at == 0,
            )
            .all()
        )
        for claim in pending_claims:
            legacy_key_prefix = (
                f"red_envelope_claim:{envelope.id}:{claim.user_id}:"
            )
            legacy_credit = (
                get_inventory_session()
                .query(ItemTransaction)
                .filter(ItemTransaction.idempotency_key.like(f"{legacy_key_prefix}%"))
                .first()
            )
            if legacy_credit is not None:
                # Old code may have committed the inventory credit immediately
                # before crashing ahead of credited_at. Adopt that durable
                # outcome instead of funding and paying the claim twice.
                claim.credited_at = max(1, legacy_credit.created_at)
            else:
                pending_amount += claim.amount
        session.commit()
        funded_amount = max(0, envelope.remaining_amount + pending_amount)
        scope_type, scope_id, _ = get_point_scope_at(envelope.created_at)
        hold_key = f"red_envelope:legacy:{envelope.id}"
        if funded_amount:
            point_holds.create_funded_point_hold(
                envelope.creator_id,
                funded_amount,
                hold_key,
                "red_envelope",
                scope=(scope_type, scope_id),
                operation_key=f"{hold_key}:backfill",
            )
        envelope.hold_key = hold_key if funded_amount else None
        envelope.scope_type = scope_type
        envelope.scope_id = scope_id
        session.commit()
        migrated += 1

        hold = point_holds.get_point_hold(hold_key) if funded_amount else None
        if envelope.expires_at <= now or (
            hold is not None
            and not point_holds.is_point_hold_scope_open(hold, now=now)
        ):
            _close_envelope(
                envelope,
                reason="expired" if envelope.expires_at <= now else "season_end",
                cutoff=min(now, envelope.expires_at),
            )
    return migrated


point_holds.register_scope_closer(
    "red_envelope", close_scope_envelopes, priority=10
)
