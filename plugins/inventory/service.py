"""Inventory service APIs."""

import time
from typing import Iterable, Optional

from .database import get_session
from .models import (
    CosmeticItem,
    EquippedItem,
    GrantResult,
    Item,
    ItemAmount,
    ItemScope,
    ItemTransaction,
    OFFSEASON_SCOPE_TYPE,
    PERMANENT_SCOPE_ID,
    PERMANENT_SCOPE_TYPE,
    SEASON_POINT_ITEM_ID,
    SEASON_SCOPE_TYPE,
    STAR_STICKER_ITEM_ID,
    UserItem,
)
from .season_service import get_offseason_starting_points, get_point_scope


def get_item(item_id: str) -> Item | None:
    return get_session().query(Item).filter(Item.item_id == item_id).first()


def resolve_scope(item_id: str, scope: Optional[ItemScope | tuple[str, str]] = None):
    if scope is not None:
        if isinstance(scope, ItemScope):
            return scope.scope_type, scope.scope_id
        return scope

    item = get_item(item_id)
    if item and item.currency and item.currency.currency_kind == "seasonal":
        scope_type, scope_id, _ = get_point_scope()
        return scope_type, scope_id

    return PERMANENT_SCOPE_TYPE, PERMANENT_SCOPE_ID


def get_quantity(
    user_id: str, item_id: str, scope: Optional[ItemScope | tuple[str, str]] = None
) -> int:
    scope_type, scope_id = resolve_scope(item_id, scope)
    if item_id == SEASON_POINT_ITEM_ID:
        _ensure_point_wallet(user_id, scope_type, scope_id)
    row = _get_user_item(user_id, item_id, scope_type, scope_id)
    return row.quantity if row else 0


def grant_many(
    user_id: str,
    items: Iterable[ItemAmount | tuple[str, int]],
    reason: str,
    scope: Optional[ItemScope | tuple[str, str]] = None,
    source_type: str = "",
    source_id: str = "",
    idempotency_key: str | None = None,
) -> list[GrantResult]:
    results = []
    for item in items:
        if isinstance(item, ItemAmount):
            item_scope = (
                (item.scope_type, item.scope_id)
                if item.scope_type and item.scope_id
                else scope
            )
            item_id = item.item_id
            quantity = item.quantity
        else:
            item_id, quantity = item
            item_scope = scope

        results.append(
            grant_item(
                user_id,
                item_id,
                quantity,
                reason,
                scope=item_scope,
                source_type=source_type,
                source_id=source_id,
                idempotency_key=idempotency_key,
            )
        )
    return results


def grant_item(
    user_id: str,
    item_id: str,
    quantity: int,
    reason: str,
    scope: Optional[ItemScope | tuple[str, str]] = None,
    source_type: str = "",
    source_id: str = "",
    idempotency_key: str | None = None,
) -> GrantResult:
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    session = get_session()
    item = _require_item(item_id)
    scope_type, scope_id = resolve_scope(item_id, scope)
    if item_id == SEASON_POINT_ITEM_ID:
        _ensure_point_wallet(user_id, scope_type, scope_id)
    tx_key = _tx_key(idempotency_key, user_id, item_id, scope_type, scope_id)
    if tx_key and _has_transaction(tx_key):
        current = get_quantity(user_id, item_id, (scope_type, scope_id))
        return GrantResult(item_id, quantity, 0, current, skipped=True, message="done")

    row = _ensure_user_item(user_id, item_id, scope_type, scope_id)
    if not item.stackable and row.quantity > 0:
        _log_transaction(
            user_id,
            item_id,
            scope_type,
            scope_id,
            0,
            row.quantity,
            reason,
            source_type,
            source_id,
            tx_key,
        )
        session.commit()
        return GrantResult(
            item_id, quantity, 0, row.quantity, skipped=True, message="already_owned"
        )

    granted = quantity if item.stackable else 1
    row.quantity += granted
    row.updated_at = int(time.time())
    _log_transaction(
        user_id,
        item_id,
        scope_type,
        scope_id,
        granted,
        row.quantity,
        reason,
        source_type,
        source_id,
        tx_key,
    )
    session.commit()
    return GrantResult(item_id, quantity, granted, row.quantity)


def cost_item(
    user_id: str,
    item_id: str,
    quantity: int,
    reason: str,
    scope: Optional[ItemScope | tuple[str, str]] = None,
) -> int:
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    session = get_session()
    _require_item(item_id)
    scope_type, scope_id = resolve_scope(item_id, scope)
    if item_id == SEASON_POINT_ITEM_ID:
        _ensure_point_wallet(user_id, scope_type, scope_id)
    row = _get_user_item(user_id, item_id, scope_type, scope_id)
    if row is None or row.quantity < quantity:
        raise ValueError("insufficient quantity")

    row.quantity -= quantity
    row.updated_at = int(time.time())
    _log_transaction(
        user_id,
        item_id,
        scope_type,
        scope_id,
        -quantity,
        row.quantity,
        reason,
    )
    session.commit()
    return row.quantity


def set_quantity(
    user_id: str,
    item_id: str,
    quantity: int,
    reason: str,
    scope: Optional[ItemScope | tuple[str, str]] = None,
) -> int:
    if quantity < 0:
        raise ValueError("quantity cannot be negative")

    session = get_session()
    item = _require_item(item_id)
    if not item.stackable and quantity > 1:
        quantity = 1

    scope_type, scope_id = resolve_scope(item_id, scope)
    if item_id == SEASON_POINT_ITEM_ID:
        _ensure_point_wallet(user_id, scope_type, scope_id)
    row = _ensure_user_item(user_id, item_id, scope_type, scope_id)
    delta = quantity - row.quantity
    row.quantity = quantity
    row.updated_at = int(time.time())
    _log_transaction(
        user_id,
        item_id,
        scope_type,
        scope_id,
        delta,
        row.quantity,
        reason,
    )
    session.commit()
    return row.quantity


def list_inventory(
    user_id: str, category: str | None = None, include_season: bool = True
) -> list[UserItem]:
    session = get_session()
    query = session.query(UserItem).join(Item).filter(UserItem.user_id == user_id)
    if category:
        query = query.filter(Item.category == category)
    if not include_season:
        query = query.filter(UserItem.scope_type == PERMANENT_SCOPE_TYPE)
    return (
        query.filter(UserItem.quantity > 0)
        .order_by(Item.sort_order.asc(), Item.item_id.asc())
        .all()
    )


def equip_cosmetic(user_id: str, item_id: str) -> EquippedItem:
    session = get_session()
    item = _require_item(item_id)
    cosmetic = (
        session.query(CosmeticItem).filter(CosmeticItem.item_id == item.item_id).first()
    )
    if cosmetic is None:
        raise ValueError("item is not cosmetic")
    if get_quantity(user_id, item_id) <= 0:
        raise ValueError("cosmetic not owned")

    equipped = (
        session.query(EquippedItem)
        .filter(EquippedItem.user_id == user_id, EquippedItem.slot == cosmetic.cosmetic_type)
        .first()
    )
    if equipped is None:
        equipped = EquippedItem(user_id=user_id, slot=cosmetic.cosmetic_type)
        session.add(equipped)
    equipped.item_id = item_id
    equipped.updated_at = int(time.time())
    session.commit()
    return equipped


def unequip_cosmetic(user_id: str, slot: str) -> bool:
    slot = _normalize_slot(slot)
    session = get_session()
    equipped = (
        session.query(EquippedItem)
        .filter(EquippedItem.user_id == user_id, EquippedItem.slot == slot)
        .first()
    )
    if equipped is None:
        return False
    session.delete(equipped)
    session.commit()
    return True


def get_equipped(user_id: str) -> dict[str, str]:
    rows = get_session().query(EquippedItem).filter(EquippedItem.user_id == user_id).all()
    return {row.slot: row.item_id for row in rows}


def parse_item_amount(text: str) -> ItemAmount:
    item_id, sep, amount_text = text.rpartition(":")
    if not sep or not item_id:
        raise ValueError("item amount must be item_id:quantity")
    quantity = int(amount_text)
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    _require_item(item_id)
    return ItemAmount(item_id=item_id, quantity=quantity)


def display_item_amount(item_id: str, quantity: int) -> str:
    item = get_item(item_id)
    name = item.name if item else item_id
    if quantity == 1 and item and not item.stackable:
        return name
    unit = item.currency.unit_name if item and item.currency else ""
    return f"{name} x{quantity}{unit}"


def display_scope(scope_type: str, scope_id: str) -> str:
    if scope_type == PERMANENT_SCOPE_TYPE:
        return ""
    if scope_type == SEASON_SCOPE_TYPE:
        from .season_service import get_season_name

        return get_season_name(scope_id)
    if scope_type == OFFSEASON_SCOPE_TYPE:
        return "休赛期临时 Pt"
    return f"{scope_type}:{scope_id}"


def _normalize_slot(slot: str) -> str:
    aliases = {
        "头像框": "avatar_frame",
        "头框": "avatar_frame",
        "frame": "avatar_frame",
        "avatar_frame": "avatar_frame",
        "称号": "title",
        "title": "title",
    }
    if slot not in aliases:
        raise ValueError("unknown cosmetic slot")
    return aliases[slot]


def _require_item(item_id: str) -> Item:
    item = get_item(item_id)
    if item is None:
        raise ValueError(f"unknown item: {item_id}")
    return item


def _get_user_item(
    user_id: str, item_id: str, scope_type: str, scope_id: str
) -> UserItem | None:
    return (
        get_session()
        .query(UserItem)
        .filter(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id,
            UserItem.scope_type == scope_type,
            UserItem.scope_id == scope_id,
        )
        .first()
    )


def _ensure_user_item(
    user_id: str, item_id: str, scope_type: str, scope_id: str
) -> UserItem:
    session = get_session()
    row = _get_user_item(user_id, item_id, scope_type, scope_id)
    if row is None:
        row = UserItem(
            user_id=user_id,
            item_id=item_id,
            scope_type=scope_type,
            scope_id=scope_id,
            quantity=0,
            updated_at=int(time.time()),
        )
        session.add(row)
        session.flush()
    return row


def _ensure_point_wallet(user_id: str, scope_type: str, scope_id: str) -> UserItem:
    session = get_session()
    row = _ensure_user_item(user_id, SEASON_POINT_ITEM_ID, scope_type, scope_id)
    if scope_type != OFFSEASON_SCOPE_TYPE:
        session.commit()
        return row

    tx_key = _tx_key(
        f"offseason_start:{scope_id}",
        user_id,
        SEASON_POINT_ITEM_ID,
        scope_type,
        scope_id,
    )
    if tx_key and not _has_transaction(tx_key):
        amount = get_offseason_starting_points()
        if amount > 0:
            row.quantity += amount
            row.updated_at = int(time.time())
            _log_transaction(
                user_id,
                SEASON_POINT_ITEM_ID,
                scope_type,
                scope_id,
                amount,
                row.quantity,
                "offseason_starting_points",
                source_type="season",
                source_id=scope_id,
                idempotency_key=tx_key,
            )
    session.commit()
    return row


def _tx_key(
    idempotency_key: str | None,
    user_id: str,
    item_id: str,
    scope_type: str,
    scope_id: str,
) -> str | None:
    if not idempotency_key:
        return None
    return f"{idempotency_key}:user:{user_id}:item:{item_id}:scope:{scope_type}:{scope_id}"


def _has_transaction(idempotency_key: str) -> bool:
    return (
        get_session()
        .query(ItemTransaction)
        .filter(ItemTransaction.idempotency_key == idempotency_key)
        .first()
        is not None
    )


def _log_transaction(
    user_id: str,
    item_id: str,
    scope_type: str,
    scope_id: str,
    delta: int,
    quantity_after: int,
    reason: str,
    source_type: str = "",
    source_id: str = "",
    idempotency_key: str | None = None,
) -> None:
    tx = ItemTransaction(
        user_id=user_id,
        item_id=item_id,
        scope_type=scope_type,
        scope_id=scope_id,
        delta=delta,
        quantity_after=quantity_after,
        reason=reason,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        created_at=int(time.time()),
    )
    get_session().add(tx)
