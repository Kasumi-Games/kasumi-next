"""Persistent, scope-bound escrow for seasonal Pt.

The inventory database is authoritative for Pt.  Every public mutation in this
module updates the wallet, hold, audit operation, and inventory transaction in
one commit.  Business plugins may therefore safely retry after crossing their
own database boundary.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from collections.abc import Callable

from . import service as inventory_service
from .models import SEASON_SCOPE_TYPE
from .models import OFFSEASON_SCOPE_TYPE
from .models import SEASON_POINT_ITEM_ID
from .models import Season
from .models import PointHold
from .models import PointHoldOperation
from .database import get_session

HOLD_OPEN = "open"
HOLD_SETTLED = "settled"
HOLD_REFUNDED = "refunded"


class PointHoldError(ValueError):
    """Base error for invalid hold operations."""


class PointHoldClosed(PointHoldError):
    """The requested hold can no longer be mutated."""


class PointHoldScopeClosed(PointHoldError):
    """The wallet scope attached to a hold is no longer live."""


@dataclass(frozen=True)
class PointHoldResult:
    hold_key: str
    scope_type: str
    scope_id: str
    status: str
    amount: int
    remaining_amount: int
    skipped: bool = False


ScopeCloser = Callable[[str, str, int], None]
_scope_closers: dict[str, tuple[int, ScopeCloser]] = {}


def register_scope_closer(
    name: str, closer: ScopeCloser, *, priority: int = 100
) -> None:
    """Register an idempotent business reconciler run before generic refunds."""

    _scope_closers[name] = (priority, closer)


def unregister_scope_closer(name: str) -> None:
    """Test/support helper for removing one registered reconciler."""

    _scope_closers.pop(name, None)


def get_point_hold(hold_key: str) -> PointHold | None:
    return (
        get_session()
        .query(PointHold)
        .filter(PointHold.hold_key == hold_key)
        .first()
    )


def is_point_hold_scope_open(hold: PointHold, *, now: int | None = None) -> bool:
    """Return whether normal player actions may still mutate ``hold``."""

    now = int(time.time()) if now is None else now
    if hold.status != HOLD_OPEN:
        return False
    if hold.scope_type == SEASON_SCOPE_TYPE:
        season = (
            get_session()
            .query(Season)
            .filter(Season.id == int(hold.scope_id))
            .first()
        )
        return bool(
            season
            and season.status == "open"
            and season.opened_at
            and season.start_time <= now < season.end_time
        )
    if hold.scope_type == OFFSEASON_SCOPE_TYPE:
        scope_type, scope_id = inventory_service.resolve_scope(SEASON_POINT_ITEM_ID)
        return scope_type == hold.scope_type and scope_id == hold.scope_id
    return False


def reserve_points(
    user_id: str,
    amount: int,
    hold_key: str,
    kind: str,
    *,
    operation_key: str | None = None,
) -> PointHoldResult:
    """Atomically debit the current Pt wallet and create a persistent hold."""

    if amount <= 0:
        raise PointHoldError("hold amount must be positive")
    if not hold_key or not kind:
        raise PointHoldError("hold key and kind are required")
    operation_key = operation_key or f"{hold_key}:reserve"
    scope_type, scope_id = inventory_service.resolve_scope(SEASON_POINT_ITEM_ID)
    return _create_hold(
        user_id,
        amount,
        hold_key,
        kind,
        scope_type,
        scope_id,
        operation_key,
        debit=True,
    )


def create_funded_point_hold(
    user_id: str,
    amount: int,
    hold_key: str,
    kind: str,
    *,
    scope: tuple[str, str],
    operation_key: str | None = None,
) -> PointHoldResult:
    """Backfill a hold for Pt that legacy code already removed from a wallet."""

    if amount <= 0:
        raise PointHoldError("hold amount must be positive")
    operation_key = operation_key or f"{hold_key}:legacy_funded"
    return _create_hold(
        user_id,
        amount,
        hold_key,
        kind,
        scope[0],
        scope[1],
        operation_key,
        debit=False,
    )


def _create_hold(
    user_id: str,
    amount: int,
    hold_key: str,
    kind: str,
    scope_type: str,
    scope_id: str,
    operation_key: str,
    *,
    debit: bool,
) -> PointHoldResult:
    session = get_session()
    operation_type = "reserve" if debit else "legacy_funded"
    replay = _operation_result(
        operation_key,
        hold_key=hold_key,
        operation_type=operation_type,
        recipient_user_id=user_id,
        amount=amount,
    )
    if replay is not None:
        return replay
    existing = get_point_hold(hold_key)
    if existing is not None:
        if (
            existing.owner_user_id != user_id
            or existing.kind != kind
            or existing.scope_type != scope_type
            or existing.scope_id != scope_id
            or existing.reserved_amount != amount
        ):
            raise PointHoldError("hold key already exists with different data")
        return _result(existing, amount, skipped=True)

    if debit:
        inventory_service._ensure_point_wallet(user_id, scope_type, scope_id)
    try:
        if debit:
            wallet = inventory_service._get_user_item(
                user_id, SEASON_POINT_ITEM_ID, scope_type, scope_id
            )
            if wallet is None or wallet.quantity < amount:
                raise PointHoldError("insufficient quantity")
            wallet.quantity -= amount
            wallet.updated_at = int(time.time())
            inventory_service._mark_season_participation_if_needed(
                user_id, SEASON_POINT_ITEM_ID, scope_type, scope_id, -amount
            )
            inventory_service._log_transaction(
                user_id,
                SEASON_POINT_ITEM_ID,
                scope_type,
                scope_id,
                -amount,
                wallet.quantity,
                f"point_hold_reserve:{kind}",
                source_type="point_hold",
                source_id=hold_key,
                idempotency_key=f"point_hold:{operation_key}:debit",
            )

        now = int(time.time())
        hold = PointHold(
            hold_key=hold_key,
            kind=kind,
            owner_user_id=user_id,
            scope_type=scope_type,
            scope_id=scope_id,
            reserved_amount=amount,
            remaining_amount=amount,
            status=HOLD_OPEN,
            created_at=now,
            closed_at=0,
        )
        session.add(hold)
        session.add(
            PointHoldOperation(
                operation_key=operation_key,
                hold_key=hold_key,
                operation_type=operation_type,
                recipient_user_id=user_id,
                amount=amount,
                created_at=now,
            )
        )
        session.commit()
        return _result(hold, amount)
    except Exception:
        session.rollback()
        raise


def increase_point_hold(
    hold_key: str,
    user_id: str,
    amount: int,
    *,
    operation_key: str,
    now: int | None = None,
) -> PointHoldResult:
    """Debit more Pt from the original scope, used by blackjack split."""

    if amount <= 0:
        raise PointHoldError("increase amount must be positive")
    replay = _operation_result(
        operation_key,
        hold_key=hold_key,
        operation_type="increase",
        recipient_user_id=user_id,
        amount=amount,
    )
    if replay is not None:
        return replay
    hold = _require_open_hold(hold_key)
    if hold.owner_user_id != user_id:
        raise PointHoldError("hold owner mismatch")
    if not is_point_hold_scope_open(hold, now=now):
        raise PointHoldScopeClosed("point scope is closed")

    session = get_session()
    inventory_service._ensure_point_wallet(user_id, hold.scope_type, hold.scope_id)
    try:
        wallet = inventory_service._get_user_item(
            user_id, SEASON_POINT_ITEM_ID, hold.scope_type, hold.scope_id
        )
        if wallet is None or wallet.quantity < amount:
            raise PointHoldError("insufficient quantity")
        wallet.quantity -= amount
        wallet.updated_at = int(time.time())
        hold.reserved_amount += amount
        hold.remaining_amount += amount
        inventory_service._mark_season_participation_if_needed(
            user_id, SEASON_POINT_ITEM_ID, hold.scope_type, hold.scope_id, -amount
        )
        inventory_service._log_transaction(
            user_id,
            SEASON_POINT_ITEM_ID,
            hold.scope_type,
            hold.scope_id,
            -amount,
            wallet.quantity,
            f"point_hold_increase:{hold.kind}",
            source_type="point_hold",
            source_id=hold_key,
            idempotency_key=f"point_hold:{operation_key}:debit",
        )
        _add_operation(hold, operation_key, "increase", user_id, amount)
        session.commit()
        return _result(hold, amount)
    except Exception:
        session.rollback()
        raise


def capture_point_hold(
    hold_key: str,
    recipient_user_id: str,
    amount: int,
    *,
    operation_key: str,
    allow_closed_scope: bool = False,
    now: int | None = None,
) -> PointHoldResult:
    """Transfer part of a hold to a recipient in the hold's original scope."""

    if amount <= 0:
        raise PointHoldError("capture amount must be positive")
    replay = _operation_result(
        operation_key,
        hold_key=hold_key,
        operation_type="capture",
        recipient_user_id=recipient_user_id,
        amount=amount,
    )
    if replay is not None:
        return replay
    hold = _require_open_hold(hold_key)
    if not allow_closed_scope and not is_point_hold_scope_open(hold, now=now):
        raise PointHoldScopeClosed("point scope is closed")
    if hold.remaining_amount < amount:
        raise PointHoldError("insufficient held amount")

    session = get_session()
    inventory_service._ensure_point_wallet(
        recipient_user_id, hold.scope_type, hold.scope_id
    )
    try:
        wallet = inventory_service._ensure_user_item(
            recipient_user_id,
            SEASON_POINT_ITEM_ID,
            hold.scope_type,
            hold.scope_id,
        )
        wallet.quantity += amount
        wallet.updated_at = int(time.time())
        hold.remaining_amount -= amount
        if hold.remaining_amount == 0:
            hold.status = HOLD_SETTLED
            hold.closed_at = int(time.time())
        inventory_service._mark_season_participation_if_needed(
            recipient_user_id,
            SEASON_POINT_ITEM_ID,
            hold.scope_type,
            hold.scope_id,
            amount,
        )
        inventory_service._log_transaction(
            recipient_user_id,
            SEASON_POINT_ITEM_ID,
            hold.scope_type,
            hold.scope_id,
            amount,
            wallet.quantity,
            f"point_hold_capture:{hold.kind}",
            source_type="point_hold",
            source_id=hold_key,
            idempotency_key=f"point_hold:{operation_key}:credit",
        )
        _add_operation(hold, operation_key, "capture", recipient_user_id, amount)
        session.commit()
        return _result(hold, amount)
    except Exception:
        session.rollback()
        raise


def settle_point_hold(
    hold_key: str,
    payout: int,
    *,
    operation_key: str,
    now: int | None = None,
) -> PointHoldResult:
    """Consume a game hold and credit its final payout to the original scope."""

    if payout < 0:
        raise PointHoldError("payout cannot be negative")
    hold = get_point_hold(hold_key)
    if hold is None:
        raise PointHoldError("unknown hold")
    replay = _operation_result(
        operation_key,
        hold_key=hold_key,
        operation_type="settle",
        recipient_user_id=hold.owner_user_id,
        amount=payout,
    )
    if replay is not None:
        return replay
    if hold.status != HOLD_OPEN:
        raise PointHoldClosed("hold is closed")
    if not is_point_hold_scope_open(hold, now=now):
        raise PointHoldScopeClosed("point scope is closed")

    session = get_session()
    if payout:
        inventory_service._ensure_point_wallet(
            hold.owner_user_id, hold.scope_type, hold.scope_id
        )
    try:
        if payout:
            wallet = inventory_service._ensure_user_item(
                hold.owner_user_id,
                SEASON_POINT_ITEM_ID,
                hold.scope_type,
                hold.scope_id,
            )
            wallet.quantity += payout
            wallet.updated_at = int(time.time())
            inventory_service._mark_season_participation_if_needed(
                hold.owner_user_id,
                SEASON_POINT_ITEM_ID,
                hold.scope_type,
                hold.scope_id,
                payout,
            )
            inventory_service._log_transaction(
                hold.owner_user_id,
                SEASON_POINT_ITEM_ID,
                hold.scope_type,
                hold.scope_id,
                payout,
                wallet.quantity,
                f"point_hold_settle:{hold.kind}",
                source_type="point_hold",
                source_id=hold_key,
                idempotency_key=f"point_hold:{operation_key}:credit",
            )
        hold.remaining_amount = 0
        hold.status = HOLD_SETTLED
        hold.closed_at = int(time.time())
        _add_operation(hold, operation_key, "settle", hold.owner_user_id, payout)
        session.commit()
        return _result(hold, payout)
    except Exception:
        session.rollback()
        raise


def refund_point_hold(
    hold_key: str,
    *,
    operation_key: str | None = None,
) -> PointHoldResult:
    """Refund the unconsumed amount to the hold owner's original scope."""

    operation_key = operation_key or f"{hold_key}:refund"
    hold = get_point_hold(hold_key)
    if hold is None:
        raise PointHoldError("unknown hold")
    replay = _operation_result(
        operation_key,
        hold_key=hold_key,
        operation_type="refund",
        recipient_user_id=hold.owner_user_id,
    )
    if replay is not None:
        return replay
    if hold.status != HOLD_OPEN:
        return _result(hold, 0, skipped=True)

    amount = hold.remaining_amount
    session = get_session()
    if amount:
        inventory_service._ensure_point_wallet(
            hold.owner_user_id, hold.scope_type, hold.scope_id
        )
    try:
        if amount:
            wallet = inventory_service._ensure_user_item(
                hold.owner_user_id,
                SEASON_POINT_ITEM_ID,
                hold.scope_type,
                hold.scope_id,
            )
            wallet.quantity += amount
            wallet.updated_at = int(time.time())
            inventory_service._mark_season_participation_if_needed(
                hold.owner_user_id,
                SEASON_POINT_ITEM_ID,
                hold.scope_type,
                hold.scope_id,
                amount,
            )
            inventory_service._log_transaction(
                hold.owner_user_id,
                SEASON_POINT_ITEM_ID,
                hold.scope_type,
                hold.scope_id,
                amount,
                wallet.quantity,
                f"point_hold_refund:{hold.kind}",
                source_type="point_hold",
                source_id=hold_key,
                idempotency_key=f"point_hold:{operation_key}:credit",
            )
        hold.remaining_amount = 0
        hold.status = HOLD_REFUNDED
        hold.closed_at = int(time.time())
        _add_operation(hold, operation_key, "refund", hold.owner_user_id, amount)
        session.commit()
        return _result(hold, amount)
    except Exception:
        session.rollback()
        raise


def close_point_scope(scope_type: str, scope_id: str, *, cutoff: int) -> int:
    """Reconcile business state, then refund every orphaned hold in a scope."""

    for _, closer in sorted(_scope_closers.values(), key=lambda entry: entry[0]):
        closer(scope_type, scope_id, cutoff)

    session = get_session()
    hold_keys = [
        row[0]
        for row in session.query(PointHold.hold_key)
        .filter(
            PointHold.scope_type == scope_type,
            PointHold.scope_id == scope_id,
            PointHold.status == HOLD_OPEN,
        )
        .order_by(PointHold.created_at.asc(), PointHold.hold_key.asc())
        .all()
    ]
    for hold_key in hold_keys:
        refund_point_hold(
            hold_key,
            operation_key=f"scope_close:{scope_type}:{scope_id}:{hold_key}",
        )

    remaining = (
        session.query(PointHold)
        .filter(
            PointHold.scope_type == scope_type,
            PointHold.scope_id == scope_id,
            PointHold.status == HOLD_OPEN,
        )
        .count()
    )
    if remaining:
        raise PointHoldError(f"scope still has {remaining} open holds")
    return len(hold_keys)


def refund_abandoned_game_holds(kinds: tuple[str, ...]) -> int:
    """Refund game holds left open because a previous process disappeared."""

    session = get_session()
    hold_keys = [
        row[0]
        for row in session.query(PointHold.hold_key)
        .filter(PointHold.kind.in_(kinds), PointHold.status == HOLD_OPEN)
        .all()
    ]
    for hold_key in hold_keys:
        refund_point_hold(hold_key, operation_key=f"startup_refund:{hold_key}")
    return len(hold_keys)


def _operation_result(
    operation_key: str,
    *,
    hold_key: str,
    operation_type: str,
    recipient_user_id: str | None = None,
    amount: int | None = None,
) -> PointHoldResult | None:
    """Return an exact idempotent replay and reject key reuse for another request."""

    session = get_session()
    operation = (
        session.query(PointHoldOperation)
        .filter(PointHoldOperation.operation_key == operation_key)
        .first()
    )
    if operation is None:
        return None
    if (
        operation.hold_key != hold_key
        or operation.operation_type != operation_type
        or (
            recipient_user_id is not None
            and operation.recipient_user_id != recipient_user_id
        )
        or (amount is not None and operation.amount != amount)
    ):
        raise PointHoldError("operation key already exists with different data")
    hold = get_point_hold(operation.hold_key)
    if hold is None:
        raise PointHoldError("hold operation has no hold")
    return _result(hold, operation.amount, skipped=True)


def _require_open_hold(hold_key: str) -> PointHold:
    hold = get_point_hold(hold_key)
    if hold is None:
        raise PointHoldError("unknown hold")
    if hold.status != HOLD_OPEN:
        raise PointHoldClosed("hold is closed")
    return hold


def _add_operation(
    hold: PointHold,
    operation_key: str,
    operation_type: str,
    recipient_user_id: str,
    amount: int,
) -> None:
    get_session().add(
        PointHoldOperation(
            operation_key=operation_key,
            hold_key=hold.hold_key,
            operation_type=operation_type,
            recipient_user_id=recipient_user_id,
            amount=amount,
            created_at=int(time.time()),
        )
    )


def _result(
    hold: PointHold, amount: int, *, skipped: bool = False
) -> PointHoldResult:
    return PointHoldResult(
        hold_key=hold.hold_key,
        scope_type=hold.scope_type,
        scope_id=hold.scope_id,
        status=hold.status,
        amount=amount,
        remaining_amount=hold.remaining_amount,
        skipped=skipped,
    )
