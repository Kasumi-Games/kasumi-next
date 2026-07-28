"""Inventory service APIs."""

import json
import re
import time
from pathlib import Path
from typing import Iterable
from typing import Optional

from nonebot.log import logger

from .models import BONSAI_ITEM_ID
from .models import SEASON_SCOPE_TYPE
from .models import PERMANENT_SCOPE_ID
from .models import OFFSEASON_SCOPE_TYPE
from .models import PERMANENT_SCOPE_TYPE
from .models import SEASON_POINT_ITEM_ID
from .models import Item
from .models import UserItem
from .models import ItemScope
from .models import ItemAmount
from .models import GrantResult
from .models import UserProfile
from .models import CosmeticItem
from .models import EquippedItem
from .models import ItemTransaction
from .database import get_session
from .season_service import get_point_scope
from .season_service import get_season_starting_points
from .season_service import get_offseason_starting_points

PROFILE_DESCRIPTION_MAX_LENGTH = 100
PROFILE_DESCRIPTION_PATTERN = re.compile(
    r"^[A-Za-z0-9\u3400-\u4dbf\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff"
    r" .,!?~\-_/：:;'\"()\[\]，。！？、；\n]*$"
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

DUPLICATE_BONSAI_COMPENSATION = {
    "avatar_frame": {
        6: 12,
        5: 10,
        4: 8,
        3: 6,
        2: 3,
        1: 2,
    },
    "standing_art": {
        6: 60,
        5: 50,
        4: 40,
        3: 30,
        2: 15,
        1: 10,
    },
    "theme": {
        6: 120,
    },
}


def get_item(item_id: str) -> Item | None:
    return get_session().query(Item).filter(Item.item_id == item_id).first()


def get_item_art(item_id: str | None) -> Path | None:
    """Resolve a catalog item's repo-relative ``metadata.art`` safely."""

    if not item_id:
        return None
    item = get_item(item_id)
    if item is None:
        return None
    try:
        metadata = json.loads(item.metadata_json or "{}")
    except (TypeError, ValueError):
        return None
    value = metadata.get("art") if isinstance(metadata, dict) else None
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path if path.exists() else None


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
        compensation = _duplicate_compensation(item)
        if compensation > 0:
            _grant_duplicate_compensation(
                user_id,
                compensation,
                reason,
                source_type,
                source_id,
                tx_key,
            )
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
        message = (
            f"already_owned_compensated:{compensation}"
            if compensation > 0
            else "already_owned"
        )
        return GrantResult(
            item_id, quantity, 0, row.quantity, skipped=True, message=message
        )

    granted = quantity if item.stackable else 1
    row.quantity += granted
    row.updated_at = int(time.time())
    _mark_season_participation_if_needed(
        user_id, item_id, scope_type, scope_id, granted
    )
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
    _mark_season_participation_if_needed(
        user_id, item_id, scope_type, scope_id, -quantity
    )
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
    _mark_season_participation_if_needed(user_id, item_id, scope_type, scope_id, delta)
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
        .filter(
            EquippedItem.user_id == user_id, EquippedItem.slot == cosmetic.cosmetic_type
        )
        .first()
    )
    if equipped is None:
        equipped = EquippedItem(user_id=user_id, slot=cosmetic.cosmetic_type)
        session.add(equipped)
    equipped.item_id = item_id
    equipped.updated_at = int(time.time())
    session.commit()
    _invalidate_theme_cache(user_id, cosmetic.cosmetic_type)
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
    _invalidate_theme_cache(user_id, slot)
    return True


def _invalidate_theme_cache(user_id: str, slot: str) -> None:
    """Drop this user's cached render kit after a theme equip changes.

    The theme cache has a TTL backstop, so a miss here costs at most a couple of
    minutes of stale theme rather than correctness. Import is function-local
    because ``utils.theming`` reaches back into this module.
    """

    if slot != "theme":
        return
    try:
        from utils.theming import invalidate_user

        invalidate_user(user_id)
    except Exception:
        logger.opt(exception=True).debug("theme cache invalidation skipped")


def get_equipped(user_id: str) -> dict[str, str]:
    rows = (
        get_session().query(EquippedItem).filter(EquippedItem.user_id == user_id).all()
    )
    return {row.slot: row.item_id for row in rows}


def set_profile_description(user_id: str, description: str) -> UserProfile:
    normalized = validate_profile_description(description)
    session = get_session()
    profile = session.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id, updated_at=int(time.time()))
        session.add(profile)
    profile.profile_description = normalized
    profile.updated_at = int(time.time())
    session.commit()
    return profile


def get_profile_description(user_id: str) -> str:
    profile = (
        get_session().query(UserProfile).filter(UserProfile.user_id == user_id).first()
    )
    return profile.profile_description if profile else ""


def validate_profile_description(description: str) -> str:
    normalized = description.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    normalized = "\n".join(line for line in normalized.split("\n") if line)
    if len(normalized) > PROFILE_DESCRIPTION_MAX_LENGTH:
        raise ValueError("个人简介最多 100 个字符")
    if not PROFILE_DESCRIPTION_PATTERN.fullmatch(normalized):
        raise ValueError("个人简介只能使用常见中日英文字、数字、空格和基础标点")
    return normalized


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
        "主题": "theme",
        "theme": "theme",
        "立绘": "standing_art",
        "standing_art": "standing_art",
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


def _duplicate_compensation(item: Item) -> int:
    if item.cosmetic is None:
        return 0
    by_rarity = DUPLICATE_BONSAI_COMPENSATION.get(item.cosmetic.cosmetic_type, {})
    return by_rarity.get(int(item.cosmetic.rarity), 0)


def _grant_duplicate_compensation(
    user_id: str,
    amount: int,
    reason: str,
    source_type: str,
    source_id: str,
    idempotency_key: str | None,
) -> None:
    bonsai = _require_item(BONSAI_ITEM_ID)
    scope_type, scope_id = resolve_scope(bonsai.item_id)
    tx_key = None if idempotency_key is None else f"{idempotency_key}:duplicate_bonsai"
    if tx_key and _has_transaction(tx_key):
        return
    row = _ensure_user_item(user_id, bonsai.item_id, scope_type, scope_id)
    row.quantity += amount
    row.updated_at = int(time.time())
    _log_transaction(
        user_id,
        bonsai.item_id,
        scope_type,
        scope_id,
        amount,
        row.quantity,
        f"duplicate_compensation:{reason}",
        source_type,
        source_id,
        tx_key,
    )


def _mark_season_participation_if_needed(
    user_id: str, item_id: str, scope_type: str, scope_id: str, delta: int
) -> None:
    if item_id != SEASON_POINT_ITEM_ID or scope_type != SEASON_SCOPE_TYPE or delta == 0:
        return
    from .season_service import mark_participated

    mark_participated(user_id, int(scope_id))


def _ensure_point_wallet(user_id: str, scope_type: str, scope_id: str) -> UserItem:
    session = get_session()
    row = _ensure_user_item(user_id, SEASON_POINT_ITEM_ID, scope_type, scope_id)
    legacy_balance = None
    if scope_type == SEASON_SCOPE_TYPE:
        amount = get_season_starting_points(scope_id)
        seed_key = f"season_start:{scope_id}"
    elif scope_type == OFFSEASON_SCOPE_TYPE:
        from .migration import LEGACY_BRIDGE_KEY
        from .migration import get_legacy_balance_for_bridge

        legacy_balance = get_legacy_balance_for_bridge(user_id, scope_id)
        if legacy_balance is not None:
            amount = legacy_balance
            seed_key = LEGACY_BRIDGE_KEY
        else:
            amount = get_offseason_starting_points()
            seed_key = f"offseason_start:{scope_id}"
    else:
        session.commit()
        return row

    tx_key = _tx_key(
        seed_key,
        user_id,
        SEASON_POINT_ITEM_ID,
        scope_type,
        scope_id,
    )
    if tx_key and not _has_transaction(tx_key):
        if amount > 0 or legacy_balance is not None:
            row.quantity += amount
            row.updated_at = int(time.time())
            _log_transaction(
                user_id,
                SEASON_POINT_ITEM_ID,
                scope_type,
                scope_id,
                amount,
                row.quantity,
                (
                    "season_starting_points"
                    if scope_type == SEASON_SCOPE_TYPE
                    else (
                        LEGACY_BRIDGE_KEY
                        if legacy_balance is not None
                        else "offseason_starting_points"
                    )
                ),
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
    return (
        f"{idempotency_key}:user:{user_id}:item:{item_id}:scope:{scope_type}:{scope_id}"
    )


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
