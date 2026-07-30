"""Business rules for 流星堂."""

import json
import time
import uuid
from pathlib import Path
from dataclasses import dataclass

from .models import SeasonPullPurchase
from .database import get_session

SHOP_PATH = Path(__file__).with_name("shop.json")
BONSAI_ITEM_ID = "bonsai"


@dataclass(frozen=True)
class ShopOffer:
    sku: str
    section: str
    item_id: str
    price: int


@dataclass(frozen=True)
class SeasonPullOffer:
    price: int
    limit: int


@dataclass(frozen=True)
class PurchaseResult:
    offer: ShopOffer
    balance_after: int


@dataclass(frozen=True)
class SeasonPullStatus:
    used: int
    limit: int
    price: int
    season_id: int | None
    season_name: str = ""

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def load_shop_config() -> dict:
    with open(SHOP_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def list_offers(section: str | None = None) -> tuple[ShopOffer, ...]:
    rows = (
        ShopOffer(
            sku=str(row["sku"]).upper(),
            section=str(row["section"]),
            item_id=str(row["item_id"]),
            price=int(row["price"]),
        )
        for row in load_shop_config().get("items", [])
    )
    offers = tuple(row for row in rows if section is None or row.section == section)
    _validate_offers(offers)
    return offers


def get_offer(sku: str) -> ShopOffer | None:
    token = sku.strip().upper()
    return next((offer for offer in list_offers() if offer.sku == token), None)


def get_season_pull_offer() -> SeasonPullOffer:
    row = load_shop_config().get("season_pull") or {}
    offer = SeasonPullOffer(price=int(row.get("price", 0)), limit=int(row.get("limit", 0)))
    if offer.price <= 0 or offer.limit <= 0:
        raise ValueError("流星堂本季加抽配置无效")
    return offer


def buy_offer(user_id: str, sku: str) -> PurchaseResult:
    offer = get_offer(sku)
    if offer is None:
        raise ValueError("没有这个商品编号")

    from ..inventory.service import exchange_for_nonstackable

    try:
        result = exchange_for_nonstackable(
            user_id,
            BONSAI_ITEM_ID,
            offer.price,
            offer.item_id,
            "ryuseido_purchase",
            source_type="shop",
            source_id=offer.sku,
            idempotency_key=f"ryuseido:{user_id}:{offer.sku}:{uuid.uuid4().hex}",
        )
    except ValueError as error:
        if str(error) == "item already owned":
            raise ValueError("已经拥有这件商品") from None
        if str(error) == "insufficient quantity":
            raise ValueError(f"盆栽不足，需要 {offer.price} 盆") from None
        raise

    from ..inventory.service import get_quantity

    return PurchaseResult(
        offer=offer,
        balance_after=get_quantity(user_id, BONSAI_ITEM_ID),
    )


def season_pull_status(user_id: str) -> SeasonPullStatus:
    offer = get_season_pull_offer()
    from ..inventory.season_service import get_current_season

    season = get_current_season()
    if season is None:
        return SeasonPullStatus(0, offer.limit, offer.price, None)
    used = (
        get_session()
        .query(SeasonPullPurchase)
        .filter(
            SeasonPullPurchase.user_id == user_id,
            SeasonPullPurchase.season_id == season.id,
            SeasonPullPurchase.status.in_(("pending", "completed")),
        )
        .count()
    )
    return SeasonPullStatus(
        used=used,
        limit=offer.limit,
        price=offer.price,
        season_id=season.id,
        season_name=season.name,
    )


def buy_season_pull(user_id: str):
    status = season_pull_status(user_id)
    if status.season_id is None:
        raise ValueError("当前没有开放的限定卡池")
    if status.remaining <= 0:
        raise ValueError("本赛季的 5 次加抽已经全部用完")

    from ..inventory.service import get_quantity

    if get_quantity(user_id, BONSAI_ITEM_ID) < status.price:
        raise ValueError(f"盆栽不足，需要 {status.price} 盆")

    session = get_session()
    purchase = SeasonPullPurchase(
        user_id=user_id,
        season_id=status.season_id,
        sequence=status.used + 1,
        price=status.price,
        status="pending",
        created_at=int(time.time()),
    )
    session.add(purchase)
    session.commit()

    from ..gacha.service import pull_with_currency

    try:
        result = pull_with_currency(
            user_id,
            BONSAI_ITEM_ID,
            status.price,
            idempotency_key=f"ryuseido:season-pull:{purchase.id}",
        )
    except Exception:
        session.delete(purchase)
        session.commit()
        raise

    purchase.status = "completed"
    purchase.completed_at = int(time.time())
    session.commit()
    return result


def _validate_offers(offers: tuple[ShopOffer, ...]) -> None:
    seen: set[str] = set()
    from ..inventory.service import get_item

    for offer in offers:
        if offer.sku in seen:
            raise ValueError(f"流星堂商品编号重复：{offer.sku}")
        seen.add(offer.sku)
        if offer.price <= 0:
            raise ValueError(f"流星堂商品价格无效：{offer.sku}")
        item = get_item(offer.item_id)
        if item is None:
            raise ValueError(f"流星堂商品不存在：{offer.item_id}")
        if item.stackable:
            raise ValueError(f"流星堂商品必须是非堆叠物品：{offer.item_id}")
