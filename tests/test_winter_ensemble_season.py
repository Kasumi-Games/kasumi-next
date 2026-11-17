"""Pinned S5 assets and the real adjacent-season/NY boundary in isolated DBs."""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter

import pytest
from PIL import Image

from plugins.gacha import service as gacha
from plugins.gacha import database as gacha_database
from plugins.inventory import database
from plugins.inventory import season_service as seasons
from plugins.gacha.models import Base as GachaBase
from plugins.inventory.models import Base
from plugins.inventory.models import SeasonReward
from plugins.inventory.models import SeasonRanking
from plugins.inventory.catalog import sync_catalog
from plugins.inventory.service import grant_item
from plugins.inventory.service import get_item_art
from plugins.inventory.service import get_quantity

ROOT = Path(__file__).resolve().parents[1]
START = int(datetime.fromisoformat("2026-11-24T00:00:00+08:00").timestamp())
END = int(datetime.fromisoformat("2027-01-01T00:00:00+08:00").timestamp())


@pytest.fixture
def instance(sqlite_session, monkeypatch):
    sqlite_session(database, Base)
    sqlite_session(gacha_database, GachaBase)
    clock = [START]
    monkeypatch.setattr(seasons.time, "time", lambda: clock[0])
    sync_catalog()
    seasons.sync_seasons_config()
    return clock


def test_assets_are_pinned_transparent_and_catalog_resolves(instance):
    manifest = json.loads(
        (
            ROOT / "plugins/inventory/resources/items/standing_art/winter/manifest.json"
        ).read_text()
    )
    assert len(manifest["assets"]) == 12
    for a in manifest["assets"]:
        path = get_item_art("standing_art_winter_" + a["slug"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == a["sha256"]
        with Image.open(path) as im:
            assert im.mode == "RGBA"
            assert list(im.size) == a["size"]
            assert im.getchannel("A").getextrema() == (0, 255)
            assert im.getchannel("A").crop((0, 0, im.width, 16)).getextrema() == (0, 0)
    for kind in ("character", "champion", "podium", "top10", "top50"):
        with Image.open(get_item_art("frame_winter_" + kind)) as im:
            assert im.size == (512, 512)
            assert im.getchannel("A").crop((208, 240, 304, 352)).getextrema() == (0, 0)
            for size in (64, 96):
                assert (
                    sum(
                        a >= 128
                        for a in im.resize((size, size)).getchannel("A").getdata()
                    )
                    > size * size * 0.1
                )


def test_real_adjacent_opening_preserves_pity_and_closes_old_holds(instance):
    from plugins.inventory.point_hold_service import get_point_hold
    from plugins.inventory.point_hold_service import reserve_points

    clock = instance
    clock[0] = START - 1
    seasons.activate_due_seasons()
    assert gacha.get_current_banner().season_key == "2026-s04"
    grant_item("player", "season_point", 73, "test")
    grant_item("player", "star_sticker", 120, "test")
    reserve_points("player", 40, "s4-hold", "test")
    state = gacha.get_state("player")
    state.pity_count = 89
    gacha_database.get_session().commit()
    clock[0] = START
    assert gacha.get_current_banner() is None
    assert seasons.activate_due_seasons() == 1
    assert seasons.activate_due_seasons() == 0
    assert gacha.get_current_banner().season_key == "2026-s05"
    assert get_quantity("player", "season_point") == 100
    # Settling old escrow after the opening must stay in its original wallet.
    seasons.settle_season("2026-s04")
    assert get_point_hold("s4-hold").status != "open"
    assert get_quantity("player", "season_point") == 100
    assert gacha.get_state("player").pity_count == 89
    result = gacha.pull("player", 1)[0]
    assert (result.rarity, result.pity_before, result.pity_after) == (6, 89, 0)
    assert gacha.get_history("player", 1).rows[0].season_key == "2026-s05"
    clock[0] = END
    assert gacha.get_current_banner() is None
    assert seasons.get_current_season() is None
    with pytest.raises(ValueError):
        gacha.pull("player", 1)


def test_pool_shape_and_pity(instance):
    seasons.activate_due_seasons()
    b = gacha.get_current_banner()
    assert END - START == 38 * 86400
    assert Counter(e.rarity for e in b.entries) == {6: 2, 5: 4, 4: 6}
    assert b.base_rates == {6: 0.01, 5: 0.2, 4: 0.79}
    assert (b.single_cost, b.ten_cost, b.soft_pity_start, b.hard_pity) == (
        120,
        1200,
        70,
        90,
    )
    assert all(e.weight == 1 for e in b.entries)
    gacha._validate_banner_rewards(b)
    for pity in range(90):
        rates = gacha.current_rates(b, pity)
        assert sum(rates.values()) == pytest.approx(1)
        assert all(p >= 0 for p in rates.values())
    assert gacha.current_rates(b, 89)[6] == 1


@pytest.mark.parametrize("already_has_theme", [False, True])
def test_shared_bundle_and_duplicate_compensation(
    instance, monkeypatch, already_has_theme
):
    seasons.activate_due_seasons()
    b = gacha.get_current_banner()
    if already_has_theme:
        grant_item("player", "theme_winter_ensemble", 1, "test")
    picks = iter(
        [
            b.entries[0],
            b.entries[1],
            b.entries[0],
            b.entries[2],
            b.entries[2],
            b.entries[6],
            b.entries[6],
        ]
    )
    monkeypatch.setattr(gacha, "_choose_entry", lambda *a: next(picks))
    monkeypatch.setattr(gacha, "_roll_rarity", lambda *a: 6)
    grant_item("player", "star_sticker", 840, "test")
    results = [gacha.pull("player", 1)[0] for _ in range(7)]
    assert [g.item_id for g in results[0].grants] == [
        "standing_art_winter_kasumi",
        "frame_winter_character",
        "theme_winter_ensemble",
    ]
    assert [g.item_id for g in results[1].grants] == ["standing_art_winter_tomori"]
    assert get_quantity("player", "frame_winter_character") == 1
    assert get_quantity("player", "theme_winter_ensemble") == 1
    assert get_quantity("player", "bonsai") == (270 if already_has_theme else 150)


@pytest.mark.parametrize(
    "rank,tier",
    [
        (1, "rank_1"),
        (2, "rank_2_3"),
        (3, "rank_2_3"),
        (4, "rank_4_10"),
        (10, "rank_4_10"),
        (11, "rank_11_50"),
        (50, "rank_11_50"),
        (51, None),
    ],
)
def test_reward_boundaries(instance, rank, tier):
    s = seasons.get_season_by_key("2026-s05")
    meta = seasons.get_season_metadata(s)
    assert not meta.get("participation_reward")
    reward = seasons._reward_tier_for_rank(meta["reward_tiers"], rank)
    assert (reward["tier_key"] if reward else None) == tier


def test_new_year_settlement_retry_and_asset_retention(instance, monkeypatch):
    seasons.activate_due_seasons()
    grant_item("winner", "season_point", 100, "test")
    grant_item("winner", "theme_winter_ensemble", 1, "test")
    instance[0] = END
    # A failed mail is retried by the existing durable reward outbox.
    monkeypatch.setattr(seasons, "dispatch_pending_season_rewards", lambda **kw: None)
    seasons.settle_season("2026-s05")
    count = database.get_session().query(SeasonReward).count()
    assert count == 1
    assert seasons.settle_due_seasons() == 4  # earlier seasons with no players catch up
    assert database.get_session().query(SeasonReward).count() == count
    assert database.get_session().query(SeasonRanking).count() == 1
    assert get_quantity("winner", "theme_winter_ensemble") == 1
    assert get_item_art("standing_art_winter_tomori").is_file()


def test_bonus_pull_quota_survives_december(instance, monkeypatch):
    from plugins.ryuseido.service import buy_season_pull
    from plugins.ryuseido.service import season_pull_status

    seasons.activate_due_seasons()
    monkeypatch.setattr(gacha, "_roll_rarity", lambda *args: 4)
    grant_item("shopper", "bonsai", 2000, "test")
    for _ in range(3):
        buy_season_pull("shopper")
    instance[0] = int(datetime.fromisoformat("2026-12-01T00:00:00+08:00").timestamp())
    assert season_pull_status("shopper").used == 3
    for _ in range(2):
        buy_season_pull("shopper")
    assert season_pull_status("shopper").remaining == 0
    assert gacha.get_state("shopper").pity_count == 5
    with pytest.raises(ValueError, match="5 次加抽"):
        buy_season_pull("shopper")
    history = gacha.get_history("shopper", 10).rows
    assert len(history) == 5
    assert all(row.cost == 400 and row.season_key == "2026-s05" for row in history)


def test_reward_mail_failure_retry_is_idempotent_and_theme_equips_after_end(
    instance, monkeypatch
):
    from unittest.mock import Mock

    from plugins.mailbox.service import MailService
    from plugins.inventory.service import equip_cosmetic

    seasons.activate_due_seasons()
    grant_item("winner", "season_point", 100, "test")
    grant_item("winner", "theme_winter_ensemble", 1, "test")
    instance[0] = END
    failed = Mock(side_effect=RuntimeError("mail unavailable"))
    monkeypatch.setattr(MailService, "send_mail", failed)
    seasons.settle_season("2026-s05")
    reward = database.get_session().query(SeasonReward).one()
    assert reward.mail_id == 0
    sent = Mock(return_value=123)
    monkeypatch.setattr(MailService, "send_mail", sent)
    assert seasons.dispatch_pending_season_rewards() == 1
    assert seasons.dispatch_pending_season_rewards() == 0
    assert sent.call_count == 1
    assert sent.call_args.kwargs["external_key"].endswith(":winner")
    assert (
        equip_cosmetic("winner", "theme_winter_ensemble").item_id
        == "theme_winter_ensemble"
    )
