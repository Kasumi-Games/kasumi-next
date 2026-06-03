"""Catalog synchronization for built-in inventory items."""

import json
from pathlib import Path

from .models import Item
from .models import CosmeticItem
from .models import CurrencyItem
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
        item.metadata_json = json.dumps(entry.get("metadata", {}), ensure_ascii=False)

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
            row.rarity = cosmetic.get("rarity", "N")

    session.commit()
