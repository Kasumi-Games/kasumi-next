#!/usr/bin/env python3
"""Backfill the missing S2 first-six-star avatar frame and theme.

The command is a dry run by default. Preview the exact candidates first, then
pass both ``--apply`` and the observed ``--expect`` count to write inventory
grants. Stop the bot (or otherwise pause inventory writes) during ``--apply``.

Examples::

    python scripts/backfill_s2_gacha_bundle.py --data-dir .data
    python scripts/backfill_s2_gacha_bundle.py --data-dir .data --apply --expect 3
"""

from __future__ import annotations

import os
import sys
import sqlite3
import argparse
from typing import Any
from pathlib import Path
from datetime import UTC
from datetime import datetime
from dataclasses import dataclass
from collections.abc import Callable
from collections.abc import Sequence

ROOT = Path(__file__).resolve().parents[1]
ARALE_SEASON_KEY = "2026-s02"
ARALE_ITEM_ID = "standing_art_yumemita_nakamachi_arale"
FRAME_ITEM_ID = "frame_yumemita_character"
THEME_ITEM_ID = "theme_mewtype"
BUNDLE_ITEM_IDS = (FRAME_ITEM_ID, THEME_ITEM_ID)
LIMITED_FIVE_STAR_ITEM_IDS = (
    "standing_art_yumemita_fuji_miyako",
    "standing_art_yumemita_minetsuki_ritsu",
    "standing_art_yumemita_miyanaga_nonoka",
    "standing_art_yumemita_sengoku_yuno",
)
BACKFILL_REASON = "season_gacha_bundle_backfill"
BACKFILL_KEY_PREFIX = "backfill:2026-s02:first-six-star-bundle:v1"


@dataclass(frozen=True)
class BackfillCandidate:
    user_id: str
    arale_pull_id: int
    arale_pulled_at: int
    prior_limited_item_ids: tuple[str, ...]
    missing_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class BackfillAction:
    user_id: str
    item_id: str


def _readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _first_arale_pulls(gacha_path: Path) -> list[sqlite3.Row]:
    prior_placeholders = ", ".join("?" for _ in LIMITED_FIVE_STAR_ITEM_IDS)
    query = f"""
        WITH arale_pulls AS (
            SELECT
                id,
                user_id,
                created_at,
                row_number() OVER (
                    PARTITION BY user_id ORDER BY created_at, id
                ) AS pull_number
            FROM gacha_pulls
            WHERE item_id = ?
        )
        SELECT
            arale.id,
            arale.user_id,
            arale.created_at,
            group_concat(DISTINCT prior.item_id) AS prior_limited_item_ids
        FROM arale_pulls AS arale
        LEFT JOIN gacha_pulls AS prior
          ON prior.user_id = arale.user_id
         AND (
              prior.created_at < arale.created_at
              OR (prior.created_at = arale.created_at AND prior.id < arale.id)
         )
         AND prior.item_id IN ({prior_placeholders})
        WHERE arale.pull_number = 1
        GROUP BY arale.id, arale.user_id, arale.created_at
        ORDER BY arale.created_at, arale.id
    """
    with _readonly_connection(gacha_path) as connection:
        return list(
            connection.execute(
                query,
                (ARALE_ITEM_ID, *LIMITED_FIVE_STAR_ITEM_IDS),
            )
        )


def _owned_quantities(
    connection: sqlite3.Connection, user_id: str
) -> dict[str, int]:
    item_ids = (ARALE_ITEM_ID, *BUNDLE_ITEM_IDS)
    placeholders = ", ".join("?" for _ in item_ids)
    rows = connection.execute(
        f"""
        SELECT item_id, sum(quantity) AS quantity
        FROM user_items
        WHERE user_id = ? AND item_id IN ({placeholders})
        GROUP BY item_id
        """,
        (user_id, *item_ids),
    )
    return {str(row["item_id"]): int(row["quantity"] or 0) for row in rows}


def find_candidates(
    gacha_path: Path, inventory_path: Path
) -> list[BackfillCandidate]:
    """Return players with an Arale pull who still lack a bundle entitlement."""

    arale_pulls = _first_arale_pulls(gacha_path)
    candidates: list[BackfillCandidate] = []
    with _readonly_connection(inventory_path) as inventory:
        for row in arale_pulls:
            quantities = _owned_quantities(inventory, str(row["user_id"]))
            if quantities.get(ARALE_ITEM_ID, 0) <= 0:
                continue
            missing = tuple(
                item_id
                for item_id in BUNDLE_ITEM_IDS
                if quantities.get(item_id, 0) <= 0
            )
            if not missing:
                continue
            raw_prior = str(row["prior_limited_item_ids"] or "")
            prior = tuple(sorted(filter(None, raw_prior.split(","))))
            candidates.append(
                BackfillCandidate(
                    user_id=str(row["user_id"]),
                    arale_pull_id=int(row["id"]),
                    arale_pulled_at=int(row["created_at"]),
                    prior_limited_item_ids=prior,
                    missing_item_ids=missing,
                )
            )
    return candidates


def apply_candidates(
    candidates: Sequence[BackfillCandidate],
    *,
    get_quantity: Callable[[str, str], int],
    grant_item: Callable[..., Any],
) -> list[BackfillAction]:
    """Grant only still-missing items, with stable per-pull idempotency keys."""

    actions: list[BackfillAction] = []
    for candidate in candidates:
        if get_quantity(candidate.user_id, ARALE_ITEM_ID) <= 0:
            raise RuntimeError(
                f"{candidate.user_id}: Arale ownership disappeared after preview"
            )
        idempotency_key = f"{BACKFILL_KEY_PREFIX}:{candidate.arale_pull_id}"
        for item_id in candidate.missing_item_ids:
            if get_quantity(candidate.user_id, item_id) > 0:
                continue
            result = grant_item(
                candidate.user_id,
                item_id,
                1,
                BACKFILL_REASON,
                source_type="season_gacha_backfill",
                source_id=f"{ARALE_SEASON_KEY}:{candidate.arale_pull_id}",
                idempotency_key=idempotency_key,
            )
            if result.granted != 1:
                raise RuntimeError(
                    f"{candidate.user_id}: failed to grant {item_id}: "
                    f"{result.message or 'unknown result'}"
                )
            actions.append(BackfillAction(candidate.user_id, item_id))
    return actions


def apply_to_inventory(
    candidates: Sequence[BackfillCandidate], inventory_path: Path
) -> list[BackfillAction]:
    """Open the selected inventory DB and apply grants through its service API."""

    data_dir = inventory_path.expanduser().resolve().parent.parent
    os.environ["LOCALSTORE_DATA_DIR"] = str(data_dir)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import nonebot
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()

    from plugins.inventory import database as inventory_database
    from plugins.inventory.service import grant_item
    from plugins.inventory.service import get_quantity

    engine = create_engine(f"sqlite:///{inventory_path.expanduser().resolve()}")
    previous_session = inventory_database.session
    session = sessionmaker(bind=engine)()
    inventory_database.session = session
    try:
        return apply_candidates(
            candidates,
            get_quantity=get_quantity,
            grant_item=grant_item,
        )
    finally:
        session.close()
        inventory_database.session = previous_session
        engine.dispose()


def _print_candidates(candidates: Sequence[BackfillCandidate]) -> None:
    for candidate in candidates:
        pulled_at = datetime.fromtimestamp(candidate.arale_pulled_at, tz=UTC)
        prior = ",".join(candidate.prior_limited_item_ids) or "none"
        missing = ",".join(candidate.missing_item_ids)
        print(
            f"user_id={candidate.user_id} "
            f"arale_pull_id={candidate.arale_pull_id} "
            f"pulled_at={pulled_at.isoformat()} "
            f"prior_limited_five_stars={prior} missing={missing}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".data")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the missing grants; omission performs a read-only preview",
    )
    parser.add_argument(
        "--expect",
        type=int,
        help="required with --apply; abort unless exactly this many users qualify",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    candidates = find_candidates(
        data_dir / "gacha/gacha.db",
        data_dir / "inventory/inventory.db",
    )
    _print_candidates(candidates)
    print(f"eligible_users={len(candidates)}")

    if not args.apply:
        print("dry_run=true; no inventory changes made")
        return
    if args.expect is None:
        parser.error("--expect is required with --apply")
    if args.expect != len(candidates):
        parser.error(
            f"expected {args.expect} eligible users, found {len(candidates)}; aborting"
        )

    actions = apply_to_inventory(candidates, data_dir / "inventory/inventory.db")
    for action in actions:
        print(f"granted user_id={action.user_id} item_id={action.item_id}")
    print(f"applied_users={len(candidates)} granted_items={len(actions)}")


if __name__ == "__main__":
    main()
