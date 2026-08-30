from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from scripts.backfill_s2_gacha_bundle import ARALE_ITEM_ID
from scripts.backfill_s2_gacha_bundle import FRAME_ITEM_ID
from scripts.backfill_s2_gacha_bundle import THEME_ITEM_ID
from scripts.backfill_s2_gacha_bundle import find_candidates
from scripts.backfill_s2_gacha_bundle import apply_candidates


def _create_gacha_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE gacha_pulls (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO gacha_pulls VALUES (?, ?, ?, ?)",
            [
                (1, "affected", "standing_art_yumemita_fuji_miyako", 100),
                (2, "affected", ARALE_ITEM_ID, 110),
                (3, "affected", ARALE_ITEM_ID, 120),
                (4, "complete", ARALE_ITEM_ID, 130),
                (5, "partial", ARALE_ITEM_ID, 140),
                (6, "inconsistent", ARALE_ITEM_ID, 150),
            ],
        )


def _create_inventory_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE user_items (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO user_items (user_id, item_id, quantity) VALUES (?, ?, ?)",
            [
                ("affected", ARALE_ITEM_ID, 1),
                ("complete", ARALE_ITEM_ID, 1),
                ("complete", FRAME_ITEM_ID, 1),
                ("complete", THEME_ITEM_ID, 1),
                ("partial", ARALE_ITEM_ID, 1),
                ("partial", FRAME_ITEM_ID, 1),
            ],
        )


def test_find_candidates_reports_only_missing_entitlements(tmp_path) -> None:
    gacha_path = tmp_path / "gacha.db"
    inventory_path = tmp_path / "inventory.db"
    _create_gacha_database(gacha_path)
    _create_inventory_database(inventory_path)

    candidates = find_candidates(gacha_path, inventory_path)

    assert [candidate.user_id for candidate in candidates] == [
        "affected",
        "partial",
    ]
    assert candidates[0].arale_pull_id == 2
    assert candidates[0].prior_limited_item_ids == (
        "standing_art_yumemita_fuji_miyako",
    )
    assert candidates[0].missing_item_ids == (FRAME_ITEM_ID, THEME_ITEM_ID)
    assert candidates[1].prior_limited_item_ids == ()
    assert candidates[1].missing_item_ids == (THEME_ITEM_ID,)


def test_apply_candidates_is_repeatable_and_uses_stable_keys(tmp_path) -> None:
    gacha_path = tmp_path / "gacha.db"
    inventory_path = tmp_path / "inventory.db"
    _create_gacha_database(gacha_path)
    _create_inventory_database(inventory_path)
    candidates = find_candidates(gacha_path, inventory_path)
    quantities = {
        ("affected", ARALE_ITEM_ID): 1,
        ("partial", ARALE_ITEM_ID): 1,
        ("partial", FRAME_ITEM_ID): 1,
    }
    calls = []

    def get_quantity(user_id: str, item_id: str) -> int:
        return quantities.get((user_id, item_id), 0)

    def grant_item(
        user_id: str,
        item_id: str,
        quantity: int,
        reason: str,
        **kwargs,
    ):
        calls.append((user_id, item_id, quantity, reason, kwargs))
        quantities[(user_id, item_id)] = 1
        return SimpleNamespace(granted=1, skipped=False, message="")

    first = apply_candidates(
        candidates,
        get_quantity=get_quantity,
        grant_item=grant_item,
    )
    second = apply_candidates(
        candidates,
        get_quantity=get_quantity,
        grant_item=grant_item,
    )

    assert [(action.user_id, action.item_id) for action in first] == [
        ("affected", FRAME_ITEM_ID),
        ("affected", THEME_ITEM_ID),
        ("partial", THEME_ITEM_ID),
    ]
    assert second == []
    assert [call[4]["idempotency_key"] for call in calls] == [
        "backfill:2026-s02:first-six-star-bundle:v1:2",
        "backfill:2026-s02:first-six-star-bundle:v1:2",
        "backfill:2026-s02:first-six-star-bundle:v1:5",
    ]
    assert all(call[3] == "season_gacha_bundle_backfill" for call in calls)
