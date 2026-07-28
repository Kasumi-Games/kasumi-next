"""Cache-backed fixed pool and the showcase frame preview.

The season-one normal pool is a fixed, broad character collection. Its stable
catalog ids preserve existing grants, while each item names the exact Bestdori
card/variant supplied by the full operational standing-art cache. The banner
showcase additionally shows the bundled avatar-frame ring.
Pinned here:

1. Every standing-art item names either a repository asset or a Bestdori cache
   source, and no player-facing 占位 name survives.
2. seasons.json banner entry names stay in sync with the catalog.
3. Fixed banner entries and catalog items name the same Bestdori source.
4. ``banner_page_data`` picks the frame ring art out of the bundle, and the
   showcase renders it (taller page, art-path reachable).
"""

from __future__ import annotations

import json
from pathlib import Path

from plugins.render.kits import KasumiKit
from plugins.render.kits import MinimalKit
from plugins.gacha.render import render_banner
from plugins.gacha.render import banner_page_data
from plugins.gacha.service import GachaEntry
from plugins.gacha.service import GachaBanner
from plugins.gacha.service import current_rates
from plugins.inventory.catalog import load_catalog
from plugins.inventory.catalog import sync_catalog
from plugins.inventory.service import get_item

ROOT = Path(__file__).resolve().parents[1]
FRAME_ART = (
    ROOT
    / "plugins/inventory/resources/items/avatar_frames/frame_kasumi_starbeat.png"
)

NORMAL_POOL_ITEM_IDS = (
    "standing_art_placeholder_r5_001",
    "standing_art_placeholder_r3_001",
    "standing_art_standard_aya_self_search",
    "standing_art_placeholder_r5_002",
    "standing_art_placeholder_r3_002",
    "standing_art_standard_kokoro_prayer",
    "standing_art_standard_mashiro_sea_story",
    "standing_art_standard_rokka_home_run",
    "standing_art_placeholder_r4_001",
    "standing_art_placeholder_r4_002",
    "standing_art_standard_moca_warm_moment",
    "standing_art_standard_misaki_aquarium",
    "standing_art_standard_hina_on_my_mind",
    "standing_art_standard_lisa_dont_worry",
    "standing_art_standard_tomori_little_animal",
    "standing_art_standard_anon_getting_along",
    "standing_art_standard_soyo_calm_mediator",
)


def _catalog_by_id() -> dict[str, dict]:
    return {entry["item_id"]: entry for entry in load_catalog()}


def _seasons() -> dict:
    path = ROOT / "plugins/inventory/seasons.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Catalog: the placeholders became real characters
# ---------------------------------------------------------------------------


def test_every_normal_pool_item_is_a_named_character_with_cached_art_source() -> None:
    catalog = _catalog_by_id()
    for item_id in NORMAL_POOL_ITEM_IDS:
        entry = catalog[item_id]
        assert "占位" not in entry["name"], item_id
        assert not entry["name"].endswith("立绘"), item_id
        metadata = entry.get("metadata", {})
        assert metadata["bestdori_card_id"] > 0
        assert metadata["bestdori_variant"] == "after_training"
        assert "art" not in metadata


def test_every_standing_art_item_has_a_repo_or_bestdori_art_source() -> None:
    for entry in load_catalog():
        if entry.get("cosmetic", {}).get("cosmetic_type") != "standing_art":
            continue
        metadata = entry.get("metadata", {})
        art = metadata.get("art")
        cached = metadata.get("bestdori_card_id")
        assert art or cached, f"{entry['item_id']} has no art source"
        if art:
            assert (ROOT / art).exists(), art


def test_every_avatar_frame_item_has_a_replaceable_item_asset() -> None:
    from PIL import Image

    for entry in load_catalog():
        if entry.get("cosmetic", {}).get("cosmetic_type") != "avatar_frame":
            continue
        art = entry.get("metadata", {}).get("art", "")
        assert art.startswith(
            "plugins/inventory/resources/items/avatar_frames/"
        ), entry["item_id"]
        path = ROOT / art
        assert path.name == f"{entry['item_id']}.png"
        assert path.exists()
        with Image.open(path) as image:
            assert image.size == (512, 512)
            assert image.mode == "RGBA"
            assert image.getpixel((256, 256))[3] == 0


def test_banner_entry_names_match_the_catalog() -> None:
    # The reveal tile shows the banner entry name; the history card shows the
    # catalog name. They must be the same string or the same pull would read
    # differently on the two surfaces.
    catalog = _catalog_by_id()
    for season in _seasons()["seasons"]:
        banner = season.get("gacha_banner")
        if not banner:
            continue
        for entry in banner["entries"]:
            assert entry["name"] == catalog[entry["item_id"]]["name"], entry[
                "item_id"
            ]


def test_fixed_pool_uses_the_same_bestdori_sources_as_the_full_cache() -> None:
    catalog = _catalog_by_id()
    season = _seasons()["seasons"][0]
    entries = {
        entry["item_id"]: entry
        for entry in season["gacha_banner"]["entries"]
        if entry["item_id"] in NORMAL_POOL_ITEM_IDS
    }
    for item_id in NORMAL_POOL_ITEM_IDS:
        metadata = catalog[item_id]["metadata"]
        assert entries[item_id]["bestdori_card_id"] == metadata["bestdori_card_id"]
        assert entries[item_id]["bestdori_variant"] == metadata["bestdori_variant"]


def test_catalog_sync_resolves_fixed_art_into_the_operational_cache() -> None:
    sync_catalog()
    item = get_item("standing_art_placeholder_r5_001")
    metadata = json.loads(item.metadata_json)
    art = Path(metadata["art"])
    assert art.name == "2242_after_training.png"
    assert art.parent.name == "standing"
    assert art.parent.parent.name == "gacha"
    assert "plugins/gacha/resources" not in art.as_posix()


def test_season_one_pool_is_fixed_and_matches_the_published_rates() -> None:
    season = _seasons()["seasons"][0]
    banner = season["gacha_banner"]

    assert {row["rarity"]: row["rate"] for row in banner["rates"]} == {
        6: 0.01,
        5: 0.09,
        4: 0.30,
        3: 0.60,
    }
    assert "bestdori_standing_art_pool" not in banner
    assert {
        rarity: sum(1 for entry in banner["entries"] if entry["rarity"] == rarity)
        for rarity in (6, 5, 4, 3)
    } == {6: 1, 5: 3, 4: 5, 3: 9}
    assert {entry["item_id"] for entry in banner["entries"] if entry["rarity"] < 6} == set(
        NORMAL_POOL_ITEM_IDS
    )
    catalog = _catalog_by_id()
    assert all(
        catalog[entry["item_id"]]["cosmetic"]["rarity"] == entry["rarity"]
        for entry in banner["entries"]
    )


def test_base_draw_rates_are_not_mutated_before_soft_pity() -> None:
    assert current_rates(_banner(), pity_count=0) == {
        6: 0.01,
        5: 0.09,
        4: 0.30,
        3: 0.60,
    }


# ---------------------------------------------------------------------------
# Showcase frame preview
# ---------------------------------------------------------------------------


def _banner() -> GachaBanner:
    return GachaBanner(
        season_key="2026-s01",
        season_name="星之鼓动",
        banner_key="2026-s01-limited",
        name="星之鼓动 限定卡池",
        single_cost=120,
        ten_cost=1200,
        base_rates={6: 0.01, 5: 0.09, 4: 0.30, 3: 0.60},
        soft_pity_start=70,
        hard_pity=90,
        entries=(
            GachaEntry(
                item_id="standing_art_kasumi_starbeat",
                character_id="kasumi",
                name="户山香澄 抬头看，星星在跳动",
                rarity=6,
                weight=1,
                featured=True,
            ),
        ),
    )


def test_banner_page_data_picks_the_frame_art_from_the_bundle() -> None:
    data = banner_page_data(
        _banner(),
        pity_count=0,
        bundle_item_ids=("frame_kasumi_starbeat", "theme_kasumi_starbeat"),
        item_art={"frame_kasumi_starbeat": FRAME_ART},
    )
    assert data.frame_art == FRAME_ART


def test_bundle_without_art_keeps_the_preview_off() -> None:
    data = banner_page_data(
        _banner(),
        pity_count=0,
        bundle_item_ids=("frame_kasumi_starbeat", "theme_kasumi_starbeat"),
    )
    assert data.frame_art is None


def test_showcase_renders_the_frame_ring() -> None:
    kit = MinimalKit()
    bundle = dict(
        bundle_item_ids=("frame_kasumi_starbeat", "theme_kasumi_starbeat"),
        item_names={
            "frame_kasumi_starbeat": "星之鼓动六星角色头像框",
            "theme_kasumi_starbeat": "星之鼓动主题",
        },
    )
    with_ring = render_banner(
        banner_page_data(
            _banner(),
            pity_count=0,
            item_art={"frame_kasumi_starbeat": FRAME_ART},
            **bundle,
        ),
        kit,
    )
    without_ring = render_banner(
        banner_page_data(_banner(), pity_count=0, **bundle), kit
    )
    # The hero has a fixed height, so the ring changes its contents rather
    # than its outer geometry.
    assert with_ring.size[0] == without_ring.size[0] == 864
    assert with_ring.size == without_ring.size
    assert with_ring.tobytes() != without_ring.tobytes()


def test_showcase_with_ring_render_is_deterministic() -> None:
    kit = KasumiKit()
    data = banner_page_data(
        _banner(),
        pity_count=12,
        bundle_item_ids=("frame_kasumi_starbeat", "theme_kasumi_starbeat"),
        item_names={"frame_kasumi_starbeat": "星之鼓动六星角色头像框"},
        item_art={
            "frame_kasumi_starbeat": FRAME_ART,
            "standing_art_kasumi_starbeat": ROOT
            / "plugins/render/kits/kasumi/resources/standing/kasumi_starry_after_training.png",
        },
    )
    assert (
        render_banner(data, kit).tobytes() == render_banner(data, kit).tobytes()
    )
