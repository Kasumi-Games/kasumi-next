"""Seasonal gacha business logic."""

import time
import uuid
import random
from typing import Any
from dataclasses import dataclass

from .models import GachaPull
from .models import GachaState
from .database import get_session

DEFAULT_PAGE_SIZE = 10


@dataclass(frozen=True)
class GachaEntry:
    item_id: str
    character_id: str
    name: str
    rarity: int
    weight: int
    featured: bool = False
    #: A normal-pool item produced from the local Bestdori trim cache.  It is
    #: registered in inventory lazily on its first use, not baked into
    #: ``items.json`` with thousands of rows.
    bestdori_card_id: int | None = None
    bestdori_variant: str | None = None


@dataclass(frozen=True)
class GachaBanner:
    season_key: str
    season_name: str
    banner_key: str
    name: str
    single_cost: int
    ten_cost: int
    base_rates: dict[int, float]
    soft_pity_start: int
    hard_pity: int
    entries: tuple[GachaEntry, ...]


@dataclass(frozen=True)
class GrantDetail:
    """One inventory grant performed by a single pull.

    A plain pull grants exactly one item; a featured ★6 pull grants up to
    three (standing art, then the season frame and theme on the first
    featured character owned). ``granted`` is the quantity actually added —
    0 means the item was a duplicate (compensated in 盆栽) or the grant was
    replayed on the idempotency key.
    """

    item_id: str
    granted: int
    skipped: bool
    message: str


@dataclass(frozen=True)
class GachaResult:
    item_id: str
    character_id: str
    name: str
    rarity: int
    cost: int
    pity_before: int
    pity_after: int
    grant_message: str
    #: Per-item grant outcomes behind ``grant_message``. The joined message
    #: stays as-is for the DB row and history compatibility; this tuple is the
    #: exact machine-readable breakdown the render layer consumes.
    grants: tuple[GrantDetail, ...] = ()


@dataclass(frozen=True)
class HistoryPage:
    rows: list[GachaPull]
    page: int
    total_pages: int
    total: int


def get_current_banner() -> GachaBanner | None:
    from ..inventory.season_service import get_current_season

    season = get_current_season()
    if season is None:
        return None
    return _banner_from_season(season)


def get_state(user_id: str) -> GachaState:
    session = get_session()
    state = session.query(GachaState).filter(GachaState.user_id == user_id).first()
    if state is None:
        state = GachaState(
            user_id=user_id,
            pity_count=0,
            total_pulls=0,
            updated_at=int(time.time()),
        )
        session.add(state)
        session.commit()
    return state


def pull(user_id: str, count: int = 1) -> list[GachaResult]:
    if count not in (1, 10):
        raise ValueError("只能单抽或十连")

    banner = get_current_banner()
    if banner is None:
        raise ValueError("当前没有开放的限定卡池")
    _validate_banner_rewards(banner)

    total_cost = banner.single_cost if count == 1 else banner.ten_cost
    from ..inventory.models import STAR_STICKER_ITEM_ID
    from ..inventory.service import cost_item
    from ..inventory.service import grant_item
    from ..inventory.service import get_quantity

    if get_quantity(user_id, STAR_STICKER_ITEM_ID) < total_cost:
        raise ValueError(f"星星贴纸不足，需要 {total_cost} 张")

    base_cost, remainder = divmod(total_cost, count)
    pull_costs = [
        base_cost + (1 if index < remainder else 0) for index in range(count)
    ]
    batch_key = uuid.uuid4().hex
    results = []
    for index, cost in enumerate(pull_costs):
        try:
            cost_item(
                user_id,
                STAR_STICKER_ITEM_ID,
                cost,
                f"gacha:{banner.banner_key}:{count}:{batch_key}:{index}",
            )
        except ValueError:
            raise ValueError(f"星星贴纸不足，需要 {total_cost} 张") from None

        try:
            results.append(_pull_once(user_id, banner, cost, index))
        except Exception:
            # Inventory and gacha history are separate databases. Compensate
            # the currently failed draw so a partial ten-pull only pays for
            # draws whose result was successfully recorded.
            grant_item(
                user_id,
                STAR_STICKER_ITEM_ID,
                cost,
                "gacha_failed_pull_refund",
                source_type="gacha_refund",
                source_id=banner.banner_key,
                idempotency_key=f"gacha_refund:{batch_key}:{index}",
            )
            raise
    return results


def get_history(user_id: str, page: int, page_size: int = DEFAULT_PAGE_SIZE) -> HistoryPage:
    page = max(1, page)
    session = get_session()
    query = session.query(GachaPull).filter(GachaPull.user_id == user_id)
    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    rows = (
        query.order_by(GachaPull.created_at.desc(), GachaPull.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return HistoryPage(rows=rows, page=page, total_pages=total_pages, total=total)


def current_rates(banner: GachaBanner, pity_count: int) -> dict[int, float]:
    rates = dict(banner.base_rates)
    rarity6 = _rarity6_rate(banner, pity_count)
    extra = max(0.0, rarity6 - rates.get(6, 0.0))
    rates[6] = rarity6
    for rarity in (4, 3, 2, 1):
        if extra <= 0:
            break
        available = rates.get(rarity, 0.0)
        reduction = min(available, extra)
        rates[rarity] = available - reduction
        extra -= reduction
    return rates


def _pull_once(
    user_id: str, banner: GachaBanner, cost: int, batch_index: int
) -> GachaResult:
    session = get_session()
    state = get_state(user_id)
    pity_before = state.pity_count
    rarity = _roll_rarity(banner, pity_before)
    entry = _choose_entry(banner, rarity)

    if entry.bestdori_card_id is not None:
        _register_bestdori_entry(entry)

    if entry.rarity == 6 and entry.featured:
        from ..inventory.season_service import grant_featured_character_reward

        grant_results = grant_featured_character_reward(
            user_id,
            banner.season_key,
            entry.character_id,
            idempotency_key=(
                f"gacha:{banner.banner_key}:{user_id}:{state.total_pulls + 1}:{batch_index}"
            ),
        )
        grant_message = "; ".join(
            result.message for result in grant_results if result.message
        )
        grant_details = tuple(
            GrantDetail(
                item_id=result.item_id,
                granted=result.granted,
                skipped=result.skipped,
                message=result.message,
            )
            for result in grant_results
        )
    else:
        from ..inventory.service import grant_item

        grant_result = grant_item(
            user_id,
            entry.item_id,
            1,
            "season_gacha_pull",
            source_type="gacha",
            source_id=banner.banner_key,
            idempotency_key=(
                f"gacha:{banner.banner_key}:{user_id}:{state.total_pulls + 1}:{batch_index}"
            ),
        )
        grant_message = grant_result.message
        grant_details = (
            GrantDetail(
                item_id=grant_result.item_id,
                granted=grant_result.granted,
                skipped=grant_result.skipped,
                message=grant_result.message,
            ),
        )

    pity_after = 0 if rarity == 6 else pity_before + 1
    state.pity_count = pity_after
    state.total_pulls += 1
    state.updated_at = int(time.time())
    pull_row = GachaPull(
        user_id=user_id,
        banner_key=banner.banner_key,
        season_key=banner.season_key,
        item_id=entry.item_id,
        character_id=entry.character_id,
        rarity=rarity,
        cost=cost,
        pity_before=pity_before,
        pity_after=pity_after,
        message=grant_message,
        created_at=int(time.time()),
    )
    session.add(pull_row)
    session.commit()
    return GachaResult(
        item_id=entry.item_id,
        character_id=entry.character_id,
        name=entry.name,
        rarity=rarity,
        cost=cost,
        pity_before=pity_before,
        pity_after=pity_after,
        grant_message=grant_message,
        grants=grant_details,
    )


def _roll_rarity(banner: GachaBanner, pity_count: int) -> int:
    rates = current_rates(banner, pity_count)
    roll = random.random()
    cumulative = 0.0
    for rarity in sorted(rates.keys(), reverse=True):
        cumulative += rates[rarity]
        if roll <= cumulative:
            return rarity
    return min(rates.keys())


def _rarity6_rate(banner: GachaBanner, pity_count: int) -> float:
    pull_number = pity_count + 1
    if pull_number >= banner.hard_pity:
        return 1.0
    base = banner.base_rates.get(6, 0.0)
    if pull_number < banner.soft_pity_start:
        return base
    span = max(1, banner.hard_pity - banner.soft_pity_start)
    progress = (pull_number - banner.soft_pity_start + 1) / span
    return min(1.0, base + (1.0 - base) * progress)


def _choose_entry(banner: GachaBanner, rarity: int) -> GachaEntry:
    entries = [entry for entry in banner.entries if entry.rarity == rarity]
    if not entries:
        raise ValueError(f"卡池缺少稀有度 {rarity} 的奖励")
    total_weight = sum(max(0, entry.weight) for entry in entries)
    if total_weight <= 0:
        raise ValueError(f"卡池稀有度 {rarity} 权重无效")
    roll = random.randint(1, total_weight)
    current = 0
    for entry in entries:
        current += max(0, entry.weight)
        if roll <= current:
            return entry
    return entries[-1]


def _validate_banner_rewards(banner: GachaBanner) -> None:
    from ..inventory.service import get_item
    from ..inventory.season_service import get_season_by_key
    from ..inventory.season_service import get_season_metadata

    cache_registered = [
        entry
        for entry in banner.entries
        if entry.bestdori_card_id is not None and get_item(entry.item_id) is None
    ]
    if cache_registered:
        from .standing_art import standing_art_cache

        if standing_art_cache is None:
            raise ValueError("Bestdori 立绘缓存尚未初始化")
        cards = {
            (card.card_id, card.variant)
            for card in standing_art_cache.pool_cards(min_rarity=1, max_rarity=5)
        }
        unavailable = sorted(
            entry.item_id
            for entry in cache_registered
            if (entry.bestdori_card_id, entry.bestdori_variant) not in cards
        )
        if unavailable:
            raise ValueError("Bestdori 立绘缓存不完整")

    missing = sorted(
        {
            entry.item_id
            for entry in banner.entries
            if entry.bestdori_card_id is None and get_item(entry.item_id) is None
        }
    )
    if missing:
        raise ValueError(f"卡池奖励配置缺失：{', '.join(missing)}")

    featured_entries = [entry for entry in banner.entries if entry.featured]
    if not featured_entries:
        return

    season = get_season_by_key(banner.season_key)
    if season is None:
        raise ValueError(f"卡池赛季配置缺失：{banner.season_key}")
    metadata = get_season_metadata(season)
    featured_character_ids = {
        str(character.get("character_id"))
        for character in metadata.get("featured_characters", [])
    }
    unknown = sorted(
        {
            entry.character_id
            for entry in featured_entries
            if entry.character_id not in featured_character_ids
        }
    )
    if unknown:
        raise ValueError(f"卡池限定角色配置缺失：{', '.join(unknown)}")


def _banner_from_season(season) -> GachaBanner | None:
    from ..inventory.season_service import get_season_metadata

    metadata = get_season_metadata(season)
    config = metadata.get("gacha_banner")
    if not config:
        return None
    rates = {int(row["rarity"]): float(row["rate"]) for row in config["rates"]}
    entries = list(_entry_from_config(row) for row in config["entries"])
    pool_config = config.get("bestdori_standing_art_pool")
    if pool_config:
        dynamic_entries = _bestdori_pool_entries(pool_config)
        # The six checked-in cards keep the banner playable during the first
        # crawl.  As soon as a given rarity has real cached Bestdori cards,
        # that rarity no longer includes its old fixed fallback entries.
        dynamic_rarities = {entry.rarity for entry in dynamic_entries}
        entries = [
            entry
            for entry in entries
            if entry.featured or entry.rarity not in dynamic_rarities
        ]
        entries.extend(dynamic_entries)
    return GachaBanner(
        season_key=season.season_key,
        season_name=season.name,
        banner_key=config["banner_key"],
        name=config["name"],
        single_cost=int(config.get("single_cost", 120)),
        ten_cost=int(config.get("ten_cost", 1200)),
        base_rates=rates,
        soft_pity_start=int(config.get("soft_pity_start", 70)),
        hard_pity=int(config.get("hard_pity", 90)),
        entries=tuple(entries),
    )


def _entry_from_config(row: dict[str, Any]) -> GachaEntry:
    return GachaEntry(
        item_id=row["item_id"],
        character_id=row.get("character_id", ""),
        name=row["name"],
        rarity=int(row["rarity"]),
        weight=int(row.get("weight", 1)),
        featured=bool(row.get("featured", False)),
        bestdori_card_id=(
            int(row["bestdori_card_id"]) if row.get("bestdori_card_id") else None
        ),
        bestdori_variant=row.get("bestdori_variant"),
    )


def _bestdori_pool_entries(config: dict[str, Any]) -> list[GachaEntry]:
    """Expose every already-cached Bestdori 2–4★ trim as a normal-pool item."""

    from .standing_art import standing_art_cache

    if standing_art_cache is None:
        return []
    minimum = int(config.get("min_rarity", 2))
    maximum = int(config.get("max_rarity", 4))
    return [
        GachaEntry(
            item_id=card.item_id,
            character_id=str(card.character_id),
            name=card.name,
            rarity=card.rarity,
            weight=1,
            bestdori_card_id=card.card_id,
            bestdori_variant=card.variant,
        )
        for card in standing_art_cache.pool_cards(
            min_rarity=minimum, max_rarity=maximum
        )
    ]


def _register_bestdori_standing_art(card) -> None:
    """Create the inventory record for a cached card the first time it drops."""

    import json

    from ..inventory.database import get_session
    from ..inventory.models import CosmeticItem
    from ..inventory.models import Item
    from .standing_art import standing_art_cache

    if standing_art_cache is None:
        raise RuntimeError("Bestdori 立绘缓存尚未初始化")

    session = get_session()
    item = session.query(Item).filter(Item.item_id == card.item_id).first()
    if item is None:
        item = Item(item_id=card.item_id)
        session.add(item)
    item.category = "cosmetic"
    item.name = card.name
    item.description = f"Bestdori 卡面 #{card.card_id} 的透明人物 CG。"
    item.stackable = False
    item.visible = True
    item.sort_order = 1_000_000 + card.card_id
    item.metadata_json = json.dumps(
        {
            "art": str(standing_art_cache.art_path(card)),
            "bestdori_card_id": card.card_id,
            "bestdori_resource_set": card.resource_set,
            "bestdori_variant": card.variant,
        },
        ensure_ascii=False,
    )
    cosmetic = (
        session.query(CosmeticItem)
        .filter(CosmeticItem.item_id == card.item_id)
        .first()
    )
    if cosmetic is None:
        cosmetic = CosmeticItem(item_id=card.item_id)
        session.add(cosmetic)
    cosmetic.cosmetic_type = "standing_art"
    cosmetic.rarity = card.rarity
    session.commit()


def _register_bestdori_entry(entry: GachaEntry) -> None:
    """Register only the selected dynamic reward, not the whole catalogue."""

    from .standing_art import standing_art_cache

    from ..inventory.service import get_item

    # Curated fixed-pool rewards already have stable catalog ids and resolve
    # their art to the deterministic cache path. They remain drawable while a
    # first full crawl is still filling that path; rendering adds the art as
    # soon as the PNG arrives.
    if get_item(entry.item_id) is not None:
        return
    if standing_art_cache is None:
        raise RuntimeError("Bestdori 立绘缓存尚未初始化")
    card = next(
        (
            card
            for card in standing_art_cache.pool_cards(min_rarity=1, max_rarity=5)
            if card.card_id == entry.bestdori_card_id
            and card.variant == entry.bestdori_variant
        ),
        None,
    )
    if card is None:
        raise ValueError(f"Bestdori 立绘缓存缺失：{entry.item_id}")
    if entry.item_id != card.item_id:
        raise ValueError(f"Bestdori 立绘奖品配置缺失：{entry.item_id}")
    _register_bestdori_standing_art(card)
