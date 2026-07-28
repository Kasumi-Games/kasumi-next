"""Bestdori transparent-CG cache contracts.

These tests deliberately use a tiny synthetic ``cards/all.5`` response: the
real response is network data and has thousands of rows, but its parsing and
file-cache invariants must remain stable without a live Bestdori request.
"""

from pathlib import Path

from plugins.gacha.standing_art import StandingArtCache
from plugins.gacha.standing_art import _cards_from_summary


def _summary() -> dict:
    return {
        "42": {
            "characterId": 1,
            "rarity": 2,
            "resourceSetName": "res001042",
            "prefix": ["日本語", "English", "繁中", "简中标题", "한국어"],
            "stat": {"training": True},
            "type": "permanent",
        },
        "43": {
            "characterId": 2,
            "rarity": 1,
            "resourceSetName": "res002043",
            "prefix": ["一星", "", "", "", ""],
            "stat": {},
            "type": "initial",
        },
        "45": {
            "characterId": 3,
            "rarity": 4,
            "resourceSetName": "res003045",
            "prefix": ["生日", "", "", "", ""],
            "stat": {},
            "type": "birthday",
        },
        "44": {
            "characterId": 0,
            "rarity": 4,
            "resourceSetName": "res000044",
            "prefix": ["other", "", "", "", ""],
            "stat": {"training": True},
            "type": "others",
        },
    }


def test_summary_keeps_both_transparent_variants_and_localizes_title() -> None:
    cards = _cards_from_summary(_summary())

    assert [(card.card_id, card.variant) for card in cards] == [
        (42, "after_training"),
        (42, "normal"),
        (43, "normal"),
        (45, "after_training"),
    ]
    trained = cards[0]
    assert trained.title == "简中标题"
    assert trained.item_id == "bestdori_standing_art_42_after_training"


def test_pool_only_exposes_downloaded_two_to_four_star_cards(tmp_path: Path) -> None:
    cache = StandingArtCache(tmp_path)
    cache.cards = _cards_from_summary(_summary())
    cache.art_dir.mkdir()
    png_signature = b"\x89PNG\r\n\x1a\n"
    (cache.art_dir / "42_normal.png").write_bytes(png_signature)
    (cache.art_dir / "43_normal.png").write_bytes(png_signature)

    cards = cache.pool_cards()

    assert [card.item_id for card in cards] == ["bestdori_standing_art_42_normal"]


def test_boot_check_rejects_a_corrupt_cached_png(tmp_path: Path) -> None:
    cache = StandingArtCache(tmp_path)
    cache.cards = _cards_from_summary(_summary())
    cache.art_dir.mkdir()
    (cache.art_dir / "42_normal.png").write_bytes(b"not a png")
    (cache.art_dir / "42_after_training.png").write_bytes(b"\x89PNG\r\n\x1a\nvalid")

    assert cache.cache_status() == (4, 1)
    assert [card.variant for card in cache.pool_cards()] == ["after_training"]
