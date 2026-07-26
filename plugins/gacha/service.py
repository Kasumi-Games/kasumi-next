"""Seasonal gacha business logic."""

import time
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

    try:
        cost_item(
            user_id,
            STAR_STICKER_ITEM_ID,
            total_cost,
            f"gacha:{banner.banner_key}:{count}",
        )
    except ValueError:
        raise ValueError(f"星星贴纸不足，需要 {total_cost} 张")

    results = []
    for index in range(count):
        cost = banner.single_cost if count == 1 else total_cost // count
        results.append(_pull_once(user_id, banner, cost, index))
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

    missing = sorted(
        {entry.item_id for entry in banner.entries if get_item(entry.item_id) is None}
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
    entries = tuple(_entry_from_config(row) for row in config["entries"])
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
        entries=entries,
    )


def _entry_from_config(row: dict[str, Any]) -> GachaEntry:
    return GachaEntry(
        item_id=row["item_id"],
        character_id=row.get("character_id", ""),
        name=row["name"],
        rarity=int(row["rarity"]),
        weight=int(row.get("weight", 1)),
        featured=bool(row.get("featured", False)),
    )
