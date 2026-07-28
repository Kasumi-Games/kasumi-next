"""Catalog synchronization for built-in inventory items."""

import json
from pathlib import Path

from nonebot.log import logger
import nonebot_plugin_localstore as store

from .models import Item
from .models import CosmeticItem
from .models import CurrencyItem
from .models import EquippedItem
from .models import ItemTransaction
from .models import UserItem
from .database import get_session

CATALOG_PATH = Path(__file__).with_name("items.json")


def load_catalog() -> list[dict]:
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("items", [])


def sync_catalog() -> None:
    session = get_session()

    for entry in load_catalog():
        item = session.query(Item).filter(Item.item_id == entry["item_id"]).first()
        if item is None:
            item = Item(item_id=entry["item_id"])
            session.add(item)

        item.category = entry["category"]
        item.name = entry["name"]
        item.description = entry.get("description", "")
        item.stackable = bool(entry.get("stackable", True))
        item.visible = bool(entry.get("visible", True))
        item.sort_order = int(entry.get("sort_order", 0))
        metadata = dict(entry.get("metadata", {}))
        if card_id := metadata.get("bestdori_card_id"):
            variant = metadata.get("bestdori_variant", "after_training")
            metadata["art"] = str(
                store.get_data_dir("gacha")
                / "standing"
                / f"{int(card_id)}_{variant}.png"
            )
        item.metadata_json = json.dumps(metadata, ensure_ascii=False)

        if currency := entry.get("currency"):
            row = (
                session.query(CurrencyItem)
                .filter(CurrencyItem.item_id == item.item_id)
                .first()
            )
            if row is None:
                row = CurrencyItem(item_id=item.item_id)
                session.add(row)
            row.currency_kind = currency["currency_kind"]
            row.unit_name = currency.get("unit_name", "")
            row.rankable = bool(currency.get("rankable", False))
            row.reset_policy = currency.get("reset_policy", "none")

        if cosmetic := entry.get("cosmetic"):
            row = (
                session.query(CosmeticItem)
                .filter(CosmeticItem.item_id == item.item_id)
                .first()
            )
            if row is None:
                row = CosmeticItem(item_id=item.item_id)
                session.add(row)
            row.cosmetic_type = cosmetic["cosmetic_type"]
            row.rarity = int(cosmetic.get("rarity", 1))

    _purge_title_cosmetics()
    session.commit()
    _invalidate_theme_cache()


def _purge_title_cosmetics() -> None:
    """Remove the retired title cosmetic type and every development record.

    Titles were removed before launch, so there is no live-data migration to
    preserve.  Keeping this in catalog sync also cleans pre-existing local
    SQLite databases when the bot next starts.
    """

    session = get_session()
    title_item_ids = [
        item_id
        for (item_id,) in session.query(CosmeticItem.item_id)
        .filter(CosmeticItem.cosmetic_type == "title")
        .all()
    ]
    if not title_item_ids:
        return

    session.query(EquippedItem).filter(
        EquippedItem.item_id.in_(title_item_ids)
    ).delete(synchronize_session=False)
    session.query(UserItem).filter(UserItem.item_id.in_(title_item_ids)).delete(
        synchronize_session=False
    )
    session.query(ItemTransaction).filter(
        ItemTransaction.item_id.in_(title_item_ids)
    ).delete(synchronize_session=False)
    session.query(CosmeticItem).filter(
        CosmeticItem.item_id.in_(title_item_ids)
    ).delete(synchronize_session=False)
    session.query(Item).filter(Item.item_id.in_(title_item_ids)).delete(
        synchronize_session=False
    )
    session.expire_all()


def _invalidate_theme_cache() -> None:
    """Drop cached theme metadata so a catalog edit takes effect immediately."""

    try:
        from utils.theming import invalidate_catalog

        invalidate_catalog()
    except Exception:
        logger.opt(exception=True).debug("theme catalog cache invalidation skipped")
