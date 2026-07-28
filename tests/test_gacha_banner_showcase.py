"""The /抽卡 banner showcase: the season-themed sell card.

Live round 2: ``/抽卡``（无参数 / 卡池 / 信息）replied with a plain text
dump. It is now a showcase card rendered in the CURRENT SEASON's theme kit —
the banner sells the season's identity — while every other surface stays
player-themed. Pinned here:

1. ``banner_page_data`` assembly: featured selection, pity-adjusted rates,
   bundle-name mapping with raw-id fallback, art attachment.
2. Season-kit resolution in the handler, including every fallback link.
3. Render smoke in the season kit and the fallback kits.
4. The pity meter carries real ``GachaState`` numbers end to end.
5. Offseason keeps the text reply; errors stay text; the render module stays
   DB-free.
"""

from __future__ import annotations

import copy
import unittest
from typing import Any
from typing import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from nonebot.exception import FinishedException
from nonebot.adapters.satori import Message

import plugins.gacha as gacha
from plugins.gacha import database as gacha_database
from plugins.inventory import database as inventory_database
from plugins.inventory import season_service
from plugins.render.kits import MangaKit
from plugins.render.kits import KasumiKit
from plugins.render.kits import MinimalKit
from plugins.gacha.models import Base as GachaBase
from plugins.gacha.models import GachaState
from plugins.gacha.render import BannerPageData
from plugins.gacha.render import banner_page
from plugins.gacha.render import render_banner
from plugins.gacha.render import banner_page_data
from plugins.gacha.service import GachaEntry
from plugins.gacha.service import GachaBanner
from plugins.inventory.models import Base as InventoryBase
from plugins.inventory.models import Item
from plugins.inventory.models import CosmeticItem
from plugins.inventory.catalog import sync_catalog

ROOT = Path(__file__).resolve().parents[1]
KASUMI_ART = (
    ROOT
    / "plugins/render/kits/kasumi/resources/standing/kasumi_starry_after_training.png"
)

BUNDLE_NAMES = ("星之鼓动六星角色头像框", "星之鼓动主题")


def _banner(entries: tuple[GachaEntry, ...] | None = None) -> GachaBanner:
    if entries is None:
        entries = (
            GachaEntry(
                item_id="standing_art_kasumi_starbeat",
                character_id="kasumi",
                name="户山香澄 抬头看，星星在跳动",
                rarity=6,
                weight=1,
                featured=True,
            ),
            GachaEntry(
                item_id="standing_art_placeholder_r5_001",
                character_id="placeholder_r5_001",
                name="占位角色立绘 5-1",
                rarity=5,
                weight=1,
            ),
            GachaEntry(
                item_id="standing_art_placeholder_r3_001",
                character_id="placeholder_r3_001",
                name="占位角色立绘 3-1",
                rarity=3,
                weight=1,
            ),
        )
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
        entries=entries,
    )


def _showcase_data(**overrides: Any) -> BannerPageData:
    defaults: dict[str, Any] = dict(
        banner_name="星之鼓动 限定卡池",
        season_name="星之鼓动",
        featured_name="户山香澄 抬头看，星星在跳动",
        featured_rarity=6,
        featured_art=KASUMI_ART,
        bundle_names=BUNDLE_NAMES,
        rates=((6, 0.01), (5, 0.09), (4, 0.30), (3, 0.60)),
        single_cost=120,
        ten_cost=1200,
        pity_count=12,
        hard_pity=90,
    )
    defaults.update(overrides)
    return BannerPageData(**defaults)


# ---------------------------------------------------------------------------
# banner_page_data: pure assembly
# ---------------------------------------------------------------------------


def test_banner_page_data_maps_the_featured_entry_and_bundle():
    data = banner_page_data(
        _banner(),
        pity_count=12,
        bundle_item_ids=("frame_kasumi_starbeat", "theme_kasumi_starbeat"),
        item_names={
            "frame_kasumi_starbeat": BUNDLE_NAMES[0],
            "theme_kasumi_starbeat": BUNDLE_NAMES[1],
        },
        item_art={"standing_art_kasumi_starbeat": KASUMI_ART},
    )
    assert data.banner_name == "星之鼓动 限定卡池"
    assert data.season_name == "星之鼓动"
    assert data.featured_name == "户山香澄 抬头看，星星在跳动"
    assert data.featured_rarity == 6
    assert data.featured_art == KASUMI_ART
    assert data.bundle_names == BUNDLE_NAMES
    assert data.single_cost == 120
    assert data.ten_cost == 1200
    assert data.pity_count == 12
    assert data.hard_pity == 90


def test_rates_are_rarity_descending_and_pity_adjusted():
    base = banner_page_data(_banner(), pity_count=0)
    assert [rarity for rarity, _ in base.rates] == [6, 5, 4, 3]
    assert base.rates[0] == (6, 0.01)

    # Pull 90 is the hard pity: the ★6 line must read 100.00%.
    capped = banner_page_data(_banner(), pity_count=89)
    assert capped.rates[0] == (6, 1.0)

    # ``current_rates`` invents 0.0 entries for rarities 2/1 near hard pity;
    # the card must not show rarities the banner never drops.
    assert [rarity for rarity, _ in capped.rates] == [6, 5, 4, 3]


def test_bundle_names_fall_back_to_raw_item_ids():
    data = banner_page_data(
        _banner(), pity_count=0, bundle_item_ids=("frame_x", "theme_y")
    )
    assert data.bundle_names == ("frame_x", "theme_y")


def test_featured_falls_back_to_the_highest_rarity_entry():
    entries = (
        GachaEntry(
            item_id="standing_art_placeholder_r3_001",
            character_id="placeholder_r3_001",
            name="占位角色立绘 3-1",
            rarity=3,
            weight=1,
        ),
        GachaEntry(
            item_id="standing_art_placeholder_r5_001",
            character_id="placeholder_r5_001",
            name="占位角色立绘 5-1",
            rarity=5,
            weight=1,
        ),
    )
    data = banner_page_data(_banner(entries=entries), pity_count=0)
    assert data.featured_name == "占位角色立绘 5-1"
    assert data.featured_rarity == 5
    assert data.featured_art is None


def test_entryless_banner_still_builds_and_renders():
    data = banner_page_data(_banner(entries=()), pity_count=0)
    assert data.featured_name == ""
    assert render_banner(data, MinimalKit()).size[0] == 864


# ---------------------------------------------------------------------------
# Render smoke
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kit_cls", [KasumiKit, MinimalKit, MangaKit])
def test_banner_page_renders_with_art(kit_cls):
    image = render_banner(_showcase_data(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_banner_page_defaults_to_the_bangdream_kit():
    assert render_banner(_showcase_data()).size[0] == 864


def test_artless_data_renders_without_reserving_the_art_slot():
    kit = MinimalKit()
    with_art = render_banner(_showcase_data(), kit)
    without_art = render_banner(_showcase_data(featured_art=None), kit)
    assert without_art.size[1] < with_art.size[1]


def test_banner_render_is_deterministic():
    kit = KasumiKit()
    first = render_banner(_showcase_data(), kit)
    second = render_banner(_showcase_data(), kit)
    assert first.tobytes() == second.tobytes()


def test_banner_hero_and_detail_deck_fill_the_content_column():
    from plugins.gacha.render import banner as banner_module
    from plugins.render.core import Constraints
    from plugins.render.core import RenderContext
    from utils.cards import CONTENT_WIDTH

    kit = KasumiKit()
    data = _showcase_data()
    constraints = Constraints(max_width=CONTENT_WIDTH, max_height=4000)
    ctx = RenderContext()
    assert banner_module._showcase(kit, data).measure(ctx, constraints).width == CONTENT_WIDTH
    assert banner_module._details_deck(kit, data).measure(ctx, constraints).width == CONTENT_WIDTH


def test_showcase_texts_land_on_the_page_in_sell_order():
    page = banner_page(_showcase_data(), KasumiKit())
    joined = " ".join(_collect_text(page.child))
    assert "户山香澄 抬头看，星星在跳动" in joined
    assert "★6" in joined
    assert "首次入手加赠" in joined
    assert "星之鼓动六星角色头像框 · 星之鼓动主题" in joined
    assert "首次入手同时获得：" not in joined
    assert "1.00%" in joined
    assert "120" in joined
    assert "1200" in joined
    assert "张星星贴纸" in joined
    assert "12/90" in joined
    assert "/抽卡 单抽 · /抽卡 十连 · /抽卡 记录" in joined
    # The sell comes before the numbers.
    assert joined.index("首次入手加赠") < joined.index("当前出率")


def test_banner_render_module_never_touches_a_database():
    # No-DB rule: names, art, and the bundle come pre-assembled from the
    # handler; the render module must not import inventory services or open a
    # session.
    source = (ROOT / "plugins/gacha/render/banner.py").read_text(encoding="utf-8")
    assert "inventory.service" not in source
    assert "season_service" not in source
    assert "get_item" not in source
    assert "get_session" not in source
    assert "sqlalchemy" not in source


# ---------------------------------------------------------------------------
# Season-kit resolution + real GachaState numbers (handler side)
# ---------------------------------------------------------------------------


class SeasonKitResolutionTest(unittest.TestCase):
    """``_season_kit`` walks season → theme item → kit, and falls back."""

    def setUp(self) -> None:
        inventory_engine = create_engine("sqlite:///:memory:")
        InventoryBase.metadata.create_all(inventory_engine)
        inventory_database.session = sessionmaker(bind=inventory_engine)()
        self.inventory_session = inventory_database.session

        gacha_engine = create_engine("sqlite:///:memory:")
        GachaBase.metadata.create_all(gacha_engine)
        gacha_database.session = sessionmaker(bind=gacha_engine)()
        self.gacha_session = gacha_database.session

        sync_catalog()  # real items.json: the starbeat theme item exists
        self._config = self._season_config()
        self._original_load_seasons_config = season_service.load_seasons_config
        season_service.load_seasons_config = lambda: copy.deepcopy(self._config)
        season_service.activate_due_seasons()

    def tearDown(self) -> None:
        season_service.load_seasons_config = self._original_load_seasons_config
        self.gacha_session.close()
        self.inventory_session.close()
        gacha_database.session = None
        inventory_database.session = None

    def test_resolves_the_season_theme_kit(self) -> None:
        # The player's own kit must not even be consulted on the happy path.
        with patch.object(
            gacha, "kit_for_user", side_effect=AssertionError("player kit consulted")
        ):
            kit = gacha._season_kit("2026-s01", "u1")
        self.assertIsInstance(kit, KasumiKit)

    def test_unknown_season_falls_back_to_the_player_kit(self) -> None:
        sentinel = MinimalKit()
        with patch.object(gacha, "kit_for_user", return_value=sentinel) as fallback:
            kit = gacha._season_kit("2099-does-not-exist", "u1")
        self.assertIs(kit, sentinel)
        fallback.assert_called_once_with("u1")

    def test_season_without_a_theme_id_falls_back(self) -> None:
        del self._config["seasons"][0]["gacha_theme_item_id"]
        sentinel = MinimalKit()
        with patch.object(gacha, "kit_for_user", return_value=sentinel):
            kit = gacha._season_kit("2026-s01", "u1")
        self.assertIs(kit, sentinel)

    def test_theme_item_missing_from_the_catalog_falls_back(self) -> None:
        # The config sync rejects unknown reward ids, so the walk raises and
        # the except path must still land on the player's kit.
        self._config["seasons"][0]["gacha_theme_item_id"] = "theme_nonexistent"
        sentinel = MinimalKit()
        with patch.object(gacha, "kit_for_user", return_value=sentinel):
            kit = gacha._season_kit("2026-s01", "u1")
        self.assertIs(kit, sentinel)

    def test_theme_item_without_kit_metadata_falls_back(self) -> None:
        self.inventory_session.add(
            Item(
                item_id="theme_broken",
                category="cosmetic",
                name="坏掉的主题",
                stackable=False,
                visible=True,
                sort_order=0,
                metadata_json="{}",
            )
        )
        self.inventory_session.add(
            CosmeticItem(item_id="theme_broken", cosmetic_type="theme", rarity=6)
        )
        self.inventory_session.commit()
        self._config["seasons"][0]["gacha_theme_item_id"] = "theme_broken"
        sentinel = MinimalKit()
        with patch.object(gacha, "kit_for_user", return_value=sentinel):
            kit = gacha._season_kit("2026-s01", "u1")
        self.assertIs(kit, sentinel)

    def test_showcase_data_carries_real_gacha_state_numbers(self) -> None:
        self.gacha_session.add(
            GachaState(user_id="u1", pity_count=37, total_pulls=37, updated_at=1)
        )
        self.gacha_session.commit()

        banner = gacha.get_current_banner()
        self.assertIsNotNone(banner)
        data = gacha._banner_showcase_data("u1", banner)

        self.assertEqual(data.pity_count, 37)
        self.assertEqual(data.hard_pity, 90)
        self.assertEqual(data.bundle_names, BUNDLE_NAMES)
        self.assertEqual(data.featured_name, "户山香澄 抬头看，星星在跳动")
        self.assertEqual(data.featured_art, KASUMI_ART)

        joined = " ".join(_collect_text(banner_page(data, MinimalKit()).child))
        self.assertIn("37/90", joined)

    def test_fresh_player_pity_meter_starts_at_zero(self) -> None:
        banner = gacha.get_current_banner()
        data = gacha._banner_showcase_data("newbie", banner)
        self.assertEqual(data.pity_count, 0)
        joined = " ".join(_collect_text(banner_page(data, MinimalKit()).child))
        self.assertIn("0/90", joined)

    def _season_config(self) -> dict:
        return {
            "timezone": "UTC+8",
            "seasons": [
                {
                    "season_key": "2026-s01",
                    "number": 1,
                    "name": "星之鼓动",
                    "starts_at": "2000-01-01T00:00:00+08:00",
                    "ends_at": "2100-01-01T00:00:00+08:00",
                    "featured_characters": [
                        {
                            "character_id": "kasumi",
                            "name": "户山香澄",
                            "standing_art_item_id": "standing_art_kasumi_starbeat",
                            "rarity": 6,
                        }
                    ],
                    "gacha_character_frame_item_id": "frame_kasumi_starbeat",
                    "gacha_theme_item_id": "theme_kasumi_starbeat",
                    "gacha_banner": {
                        "banner_key": "2026-s01-limited",
                        "name": "星之鼓动 限定卡池",
                        "single_cost": 120,
                        "ten_cost": 1200,
                        "soft_pity_start": 70,
                        "hard_pity": 90,
                        "rates": [
                            {"rarity": 6, "rate": 0.01},
                            {"rarity": 5, "rate": 0.09},
                            {"rarity": 4, "rate": 0.30},
                            {"rarity": 3, "rate": 0.60},
                        ],
                        "entries": [
                            {
                                "item_id": "standing_art_kasumi_starbeat",
                                "character_id": "kasumi",
                                "name": "户山香澄 抬头看，星星在跳动",
                                "rarity": 6,
                                "weight": 1,
                                "featured": True,
                            },
                            {
                                "item_id": "standing_art_placeholder_r5_001",
                                "character_id": "placeholder_r5_001",
                                "name": "占位角色立绘 5-1",
                                "rarity": 5,
                                "weight": 1,
                            },
                            {
                                "item_id": "standing_art_placeholder_r4_001",
                                "character_id": "placeholder_r4_001",
                                "name": "占位角色立绘 4-1",
                                "rarity": 4,
                                "weight": 1,
                            },
                            {
                                "item_id": "standing_art_placeholder_r3_001",
                                "character_id": "placeholder_r3_001",
                                "name": "占位角色立绘 3-1",
                                "rarity": 3,
                                "weight": 1,
                            },
                        ],
                    },
                    "reward_tiers": [],
                }
            ],
        }


# ---------------------------------------------------------------------------
# The matcher reply paths
# ---------------------------------------------------------------------------


class RecordingMatcher:
    """Stands in for ``Matcher``: records every send, finish raises."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    async def send(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("send", message, kwargs))

    async def finish(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("finish", message, kwargs))
        raise FinishedException()


async def test_no_args_offseason_stays_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    monkeypatch.setattr(gacha, "get_current_banner", lambda: None)

    matcher = RecordingMatcher()
    event = make_satori_event("/抽卡")
    with pytest.raises(FinishedException):
        await gacha.handle_gacha(matcher, event, Message(""))  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert "img" not in [segment.type for segment in message]
    assert "当前没有开放的限定卡池" in str(message)
    assert kwargs["referrer"] is event.referrer


async def test_no_args_in_season_is_one_showcase_card_send(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    banner = _banner()
    recorded: dict[str, Any] = {}

    def season_kit(season_key: str, user_id: str) -> Any:
        recorded["season_key"] = season_key
        return MinimalKit()

    monkeypatch.setattr(gacha, "get_current_banner", lambda: banner)
    monkeypatch.setattr(gacha, "_season_kit", season_kit)
    monkeypatch.setattr(
        gacha,
        "_banner_showcase_data",
        lambda user_id, b: banner_page_data(b, pity_count=12),
    )

    matcher = RecordingMatcher()
    event = make_satori_event("/抽卡 卡池")
    with pytest.raises(FinishedException):
        await gacha.handle_gacha(matcher, event, Message("卡池"))  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer
    assert recorded["season_key"] == banner.season_key


async def test_showcase_failure_degrades_to_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    banner = _banner()
    monkeypatch.setattr(gacha, "get_current_banner", lambda: banner)
    monkeypatch.setattr(gacha, "_season_kit", lambda *args: MinimalKit())

    def boom(user_id: str, b: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(gacha, "_banner_showcase_data", boom)

    matcher = RecordingMatcher()
    event = make_satori_event("/抽卡")
    with pytest.raises(FinishedException):
        await gacha.handle_gacha(matcher, event, Message(""))  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert "img" not in [segment.type for segment in message]
    assert "抽卡失败" in str(message)
    assert kwargs["referrer"] is event.referrer


def _collect_text(component) -> list[str]:
    """Collect text nodes in document (preorder) order."""

    texts: list[str] = []

    def visit(node) -> None:
        text = getattr(node, "text", None)
        if isinstance(text, str):
            texts.append(text)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
            else:
                visit(value)

    visit(component)
    return texts
