"""S4's real catalog, assets, two-character bundle and live boundary behavior."""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from collections import Counter

import pytest
from PIL import Image

from plugins.gacha import service as gacha_service
from plugins.gacha import database as gacha_database
from plugins.inventory import database as inventory_database
from plugins.inventory import season_service
from plugins.gacha.models import Base as GachaBase
from plugins.inventory.models import Base as InventoryBase
from plugins.inventory.catalog import sync_catalog
from plugins.inventory.service import grant_item
from plugins.inventory.service import get_quantity

ROOT = Path(__file__).resolve().parents[1]
S3_END = int(datetime.fromisoformat("2026-10-26T00:00:00+08:00").timestamp())
S4_START = int(datetime.fromisoformat("2026-10-27T00:00:00+08:00").timestamp())
S4_END = int(datetime.fromisoformat("2026-11-24T00:00:00+08:00").timestamp())
ART = ROOT / "plugins/inventory/resources/items/standing_art/manosaba"


@pytest.fixture
def season_instance(sqlite_session, monkeypatch):
    sqlite_session(inventory_database, InventoryBase)
    sqlite_session(gacha_database, GachaBase)
    clock = [S4_START]
    monkeypatch.setattr(season_service.time, "time", lambda: clock[0])
    sync_catalog()
    season_service.sync_seasons_config()
    return clock


def test_complete_cast_has_transparent_reproducible_standing_art():
    recipes = json.loads((ART / "recipes.json").read_text())
    manifest = json.loads((ART / "manifest.json").read_text())
    assert len(recipes) == len(manifest["assets"]) == 13
    assert len({r["character_id"] for r in recipes}) == 13
    assert Counter(r["rarity"] for r in recipes) == {6: 2, 5: 4, 4: 7}
    for entry in manifest["assets"]:
        path = ART / entry["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        with Image.open(path) as image:
            assert image.mode == "RGBA"
            assert list(image.size) == entry["size"]
            assert image.height == 2048
            alpha = image.getchannel("A")
            assert alpha.getbbox() is not None
            assert alpha.crop((0, 0, image.width, 8)).getextrema() == (0, 0)
            assert alpha.crop(
                (0, image.height - 8, image.width, image.height)
            ).getextrema() == (0, 0)


@pytest.mark.parametrize("kind", ["champion", "podium", "top10", "top50", "character"])
def test_frames_preserve_the_face_and_remain_visible_at_chat_size(kind):
    path = (
        ROOT
        / f"plugins/inventory/resources/items/avatar_frames/frame_manosaba_{kind}.png"
    )
    with Image.open(path) as image:
        assert image.mode == "RGBA"
        assert image.size == (512, 512)
        alpha = image.getchannel("A")
        assert alpha.crop((208, 240, 304, 352)).getextrema() == (0, 0)
        assert image.getpixel((256, 256))[3] == 0
        small = image.resize((64, 64), Image.Resampling.LANCZOS).getchannel("A")
        assert sum(v >= 128 for v in small.getdata()) > 400


def test_s4_banner_is_self_contained_and_validates(season_instance):
    season_service.activate_due_seasons()
    banner = gacha_service.get_current_banner()
    assert banner.season_key == "2026-s04"
    assert Counter(e.rarity for e in banner.entries) == {6: 2, 5: 4, 4: 7}
    assert len(banner.entries) == 13
    assert all(e.bestdori_card_id is None for e in banner.entries)
    gacha_service._validate_banner_rewards(banner)
    assert {e.character_id for e in banner.entries if e.featured} == {
        "manosaba_ema",
        "manosaba_hiro",
    }
    assert banner.base_rates == {6: 0.01, 5: 0.20, 4: 0.79}
    assert (
        banner.single_cost,
        banner.ten_cost,
        banner.soft_pity_start,
        banner.hard_pity,
    ) == (120, 1200, 70, 90)


def test_character_rarity_agrees_across_pool_catalog_and_recipes(season_instance):
    from plugins.inventory.service import get_item

    season_service.activate_due_seasons()
    banner = gacha_service.get_current_banner()
    expected_five = {
        "manosaba_hanna",
        "manosaba_sherry",
        "manosaba_noah",
        "manosaba_coco",
    }
    assert {e.character_id for e in banner.entries if e.rarity == 5} == expected_five
    recipes = {
        r["character_id"]: r for r in json.loads((ART / "recipes.json").read_text())
    }
    for entry in banner.entries:
        assert (
            entry.rarity
            == recipes[entry.character_id]["rarity"]
            == get_item(entry.item_id).cosmetic.rarity
        )
    for rarity in (6, 5, 4):
        entries = [e for e in banner.entries if e.rarity == rarity]
        chances = [
            banner.base_rates[rarity] * e.weight / sum(r.weight for r in entries)
            for e in entries
        ]
        assert all(p == pytest.approx(chances[0]) for p in chances)
        assert chances[0] == pytest.approx({6: 0.005, 5: 0.05, 4: 0.79 / 7}[rarity])


def test_s4_pity_rates_remain_normalized_and_only_offer_available_rarities(
    season_instance,
):
    season_service.activate_due_seasons()
    banner = gacha_service.get_current_banner()
    for pity in range(90):
        rates = gacha_service.current_rates(banner, pity)
        assert sum(rates.values()) == pytest.approx(1), (pity, rates)
        assert all(0 <= p <= 1 for p in rates.values())
        assert all(rarity in {6, 5, 4} for rarity, rate in rates.items() if rate > 0)
    hard = gacha_service.current_rates(banner, 89)
    assert hard[6] == 1
    assert all(rate == 0 for rarity, rate in hard.items() if rarity != 6)


@pytest.mark.parametrize(
    "character, compensation",
    [("coco", 50), ("noah", 50), ("meruru", 40), ("anan", 40)],
)
def test_changed_rarity_uses_the_corresponding_duplicate_compensation(
    season_instance, character, compensation
):
    item_id = f"standing_art_manosaba_{character}"
    grant_item("rarity-test", item_id, 1, "test")
    grant_item("rarity-test", item_id, 1, "test")
    assert get_quantity("rarity-test", item_id) == 1
    assert get_quantity("rarity-test", "bonsai") == compensation


def test_two_six_stars_share_one_bundle_and_duplicates_convert_to_bonsai(
    season_instance, monkeypatch
):
    season_service.activate_due_seasons()
    banner = gacha_service.get_current_banner()
    picks = iter([banner.entries[0], banner.entries[1], banner.entries[0]])
    monkeypatch.setattr(gacha_service, "_roll_rarity", lambda *args: 6)
    monkeypatch.setattr(gacha_service, "_choose_entry", lambda *args: next(picks))
    grant_item("s4-player", "star_sticker", 360, "test")
    first = gacha_service.pull("s4-player", 1)[0]
    assert [r.item_id for r in first.grants] == [
        "standing_art_manosaba_ema",
        "frame_manosaba_character",
        "theme_manosaba",
    ]
    second = gacha_service.pull("s4-player", 1)[0]
    assert [r.item_id for r in second.grants] == ["standing_art_manosaba_hiro"]
    third = gacha_service.pull("s4-player", 1)[0]
    assert len(third.grants) == 1 and third.grants[0].granted == 0
    assert get_quantity("s4-player", "bonsai") == 60
    for item_id in (
        "standing_art_manosaba_ema",
        "standing_art_manosaba_hiro",
        "frame_manosaba_character",
        "theme_manosaba",
    ):
        assert get_quantity("s4-player", item_id) == 1
    assert get_quantity("s4-player", "star_sticker") == 0


def test_s3_offseason_s4_opening_preserves_pity_and_resets_only_season_points(
    season_instance,
):
    clock = season_instance
    clock[0] = S3_END - 1
    season_service.activate_due_seasons()
    assert gacha_service.get_current_banner().season_key == "2026-s03"
    grant_item("transition", "season_point", 73, "test")
    grant_item("transition", "star_sticker", 120, "test")
    state = gacha_service.get_state("transition")
    state.pity_count = 89
    gacha_database.get_session().commit()
    clock[0] = S3_END
    assert gacha_service.get_current_banner() is None
    assert season_service.get_point_scope()[1] == "2026-s03_to_2026-s04"
    clock[0] = S4_START - 1
    assert season_service.activate_due_seasons() == 0
    clock[0] = S4_START
    assert season_service.activate_due_seasons() == 1
    assert season_service.activate_due_seasons() == 0
    assert get_quantity("transition", "season_point") == 100
    assert gacha_service.get_state("transition").pity_count == 89
    result = gacha_service.pull("transition", 1)[0]
    assert result.rarity == 6
    assert result.pity_before == 89 and result.pity_after == 0
    assert gacha_service.get_history("transition", 1).rows[0].season_key == "2026-s04"
    clock[0] = S4_END
    assert gacha_service.get_current_banner() is None


def test_s4_showcase_exposes_both_six_star_artworks(season_instance):
    from plugins.render.kits import ManosabaKit
    from plugins.gacha.render import banner_page
    from plugins.gacha.render import banner_page_data
    from plugins.inventory.service import get_item
    from plugins.inventory.service import get_item_art

    season_service.activate_due_seasons()
    banner = gacha_service.get_current_banner()
    ids = {e.item_id for e in banner.entries} | {
        "frame_manosaba_character",
        "theme_manosaba",
    }
    data = banner_page_data(
        banner,
        pity_count=0,
        bundle_item_ids=("frame_manosaba_character", "theme_manosaba"),
        item_names={i: get_item(i).name for i in ids},
        item_art={i: get_item_art(i) for i in ids if get_item_art(i)},
    )
    assert len(data.featured_items) == 2
    assert all(item.image and item.image.is_file() for item in data.featured_items)
    sheet = banner_page(data, ManosabaKit()).compose()
    values = [r.value for r in sheet.texts]
    assert all(item.name in values for item in data.featured_items)
    boxes = sheet.glyph_boxes()
    for i, (text, rect) in enumerate(boxes):
        assert 18 <= rect.x < rect.right <= sheet.width - 18, text
        for other, other_rect in boxes[i + 1 :]:
            dx = min(rect.right, other_rect.right) - max(rect.x, other_rect.x)
            dy = min(rect.bottom, other_rect.bottom) - max(rect.y, other_rect.y)
            assert dx <= 1 or dy <= 1, (text, other)


def test_equipped_full_body_art_gets_a_facing_page(monkeypatch):
    from plugins.render import PlayerIdentity
    from plugins.render.kits import ManosabaKit
    from plugins.inventory.render.profile import ProfileData
    from plugins.inventory.render.profile import profile_page
    from plugins.render.kits.manosaba.layouts.folio import Sheet

    seen = []
    original = Sheet.image

    def capture(self, source, x, y, width, height, **kwargs):
        seen.append((source, x, width, height))
        return original(self, source, x, y, width, height, **kwargs)

    monkeypatch.setattr(Sheet, "image", capture)
    art = ART / "ema.png"
    data = ProfileData(PlayerIdentity("示例玩家", 24), 100, standing_art=art)
    sheet = profile_page(data, ManosabaKit()).compose()
    assert any(
        source == art and x > sheet.width / 2 and width >= 400 and height >= 700
        for source, x, width, height in seen
    )
