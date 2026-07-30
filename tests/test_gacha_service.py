import copy
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plugins.gacha import service as gacha_service
from plugins.gacha import database as gacha_database
from plugins.inventory import database as inventory_database
from plugins.inventory import season_service
from plugins.gacha.models import Base as GachaBase
from plugins.gacha.models import GachaPull
from plugins.gacha.models import GachaState
from plugins.gacha.service import GachaEntry
from plugins.gacha.service import GachaBanner
from plugins.gacha.service import pull
from plugins.gacha.service import get_state
from plugins.gacha.service import get_history
from plugins.inventory.models import BONSAI_ITEM_ID
from plugins.inventory.models import STAR_STICKER_ITEM_ID
from plugins.inventory.models import Base as InventoryBase
from plugins.inventory.models import Item
from plugins.inventory.models import CosmeticItem
from plugins.inventory.models import CurrencyItem
from plugins.inventory.catalog import sync_catalog
from plugins.inventory.service import grant_item
from plugins.inventory.service import get_quantity


class GachaServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        inventory_engine = create_engine("sqlite:///:memory:")
        InventoryBase.metadata.create_all(inventory_engine)
        inventory_database.session = sessionmaker(bind=inventory_engine)()
        self.inventory_session = inventory_database.session

        gacha_engine = create_engine("sqlite:///:memory:")
        GachaBase.metadata.create_all(gacha_engine)
        gacha_database.session = sessionmaker(bind=gacha_engine)()
        self.gacha_session = gacha_database.session

        self._original_load_seasons_config = season_service.load_seasons_config
        season_service.load_seasons_config = lambda: copy.deepcopy(self._season_config())

        self._add_currency(STAR_STICKER_ITEM_ID, "星星贴纸", "permanent")
        self._add_currency(BONSAI_ITEM_ID, "盆栽", "permanent")
        self._add_cosmetic("frame_s1_6star_character", "avatar_frame", 6)
        self._add_cosmetic("theme_s1_sailing", "theme", 6)
        self._add_cosmetic("standing_art_s1_kasumi", "standing_art", 6)
        self._add_cosmetic("standing_art_s1_arisa", "standing_art", 6)
        self._add_cosmetic("standing_art_placeholder_r5_001", "standing_art", 5)
        self._add_cosmetic("standing_art_placeholder_r4_001", "standing_art", 4)
        self._add_cosmetic("standing_art_placeholder_r3_001", "standing_art", 3)
        season_service.activate_due_seasons()

    def tearDown(self) -> None:
        season_service.load_seasons_config = self._original_load_seasons_config
        self.gacha_session.close()
        self.inventory_session.close()
        gacha_database.session = None
        inventory_database.session = None

    def test_pull_requires_star_stickers(self) -> None:
        with self.assertRaisesRegex(ValueError, "星星贴纸不足"):
            pull("u1", 1)

        self.assertEqual(self.gacha_session.query(GachaPull).count(), 0)

    def test_pull_spends_stickers_records_history_and_increments_pity(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 120, "test")

        with patch("plugins.gacha.service.random.random", return_value=0.99):
            results = pull("u1", 1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rarity, 3)
        self.assertEqual(results[0].cost, 120)
        self.assertEqual(get_quantity("u1", STAR_STICKER_ITEM_ID), 0)
        self.assertEqual(get_state("u1").pity_count, 1)
        history = get_history("u1", 1)
        self.assertEqual(history.total, 1)
        self.assertEqual(history.rows[0].item_id, "standing_art_placeholder_r3_001")
        self.assertEqual(history.rows[0].payment_item_id, STAR_STICKER_ITEM_ID)

    def test_ten_pull_failure_only_charges_completed_pulls(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 1200, "test")
        original_pull_once = gacha_service._pull_once
        calls = 0

        def fail_on_eighth(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 8:
                raise RuntimeError("simulated pull failure")
            return original_pull_once(*args, **kwargs)

        with patch("plugins.gacha.service.random.random", return_value=0.99):
            with patch(
                "plugins.gacha.service._pull_once", side_effect=fail_on_eighth
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated pull failure"):
                    pull("u1", 10)

        self.assertEqual(self.gacha_session.query(GachaPull).count(), 7)
        self.assertEqual(get_quantity("u1", STAR_STICKER_ITEM_ID), 360)

    def test_hard_pity_forces_rarity_6_and_resets_pity(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 120, "test")
        self.gacha_session.add(
            GachaState(user_id="u1", pity_count=89, total_pulls=89, updated_at=1)
        )
        self.gacha_session.commit()

        with patch("plugins.gacha.service.random.randint", return_value=1):
            results = pull("u1", 1)

        self.assertEqual(results[0].rarity, 6)
        self.assertEqual(get_state("u1").pity_count, 0)
        self.assertEqual(get_quantity("u1", "standing_art_s1_kasumi"), 1)
        self.assertEqual(get_quantity("u1", "frame_s1_6star_character"), 1)
        self.assertEqual(get_quantity("u1", "theme_s1_sailing"), 1)

    def test_pity_state_carries_across_banner_keys(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 240, "test")
        first_banner = self._banner("banner-a", "season-a")
        second_banner = self._banner("banner-b", "season-b")

        with patch("plugins.gacha.service.get_current_banner", return_value=first_banner):
            with patch("plugins.gacha.service.random.random", return_value=0.99):
                pull("u1", 1)
        with patch("plugins.gacha.service.get_current_banner", return_value=second_banner):
            with patch("plugins.gacha.service.random.random", return_value=0.99):
                results = pull("u1", 1)

        self.assertEqual(results[0].pity_before, 1)
        self.assertEqual(results[0].pity_after, 2)
        self.assertEqual(get_state("u1").pity_count, 2)

    def test_first_featured_six_star_bundles_frame_and_theme(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 120, "test")

        with patch("plugins.gacha.service.random.random", return_value=0.001):
            with patch("plugins.gacha.service.random.randint", return_value=1):
                results = pull("u1", 1)

        result = results[0]
        self.assertEqual(result.rarity, 6)
        self.assertEqual(result.grant_message, "")
        self.assertEqual(
            [
                (grant.item_id, grant.granted, grant.skipped, grant.message)
                for grant in result.grants
            ],
            [
                ("standing_art_s1_kasumi", 1, False, ""),
                ("frame_s1_6star_character", 1, False, ""),
                ("theme_s1_sailing", 1, False, ""),
            ],
        )

    def test_second_pull_of_same_featured_grants_only_compensation(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 240, "test")

        with patch("plugins.gacha.service.random.random", return_value=0.001):
            with patch("plugins.gacha.service.random.randint", return_value=1):
                pull("u1", 1)
                results = pull("u1", 1)

        result = results[0]
        # 已拥有该限定角色：不再重复发放头像框/主题，立绘转为盆栽补偿
        self.assertEqual(len(result.grants), 1)
        detail = result.grants[0]
        self.assertEqual(detail.item_id, "standing_art_s1_kasumi")
        self.assertEqual(detail.granted, 0)
        self.assertTrue(detail.skipped)
        self.assertEqual(detail.message, "already_owned_compensated:60")
        self.assertEqual(result.grant_message, "already_owned_compensated:60")
        self.assertEqual(get_quantity("u1", BONSAI_ITEM_ID), 60)
        self.assertEqual(get_quantity("u1", "frame_s1_6star_character"), 1)
        self.assertEqual(get_quantity("u1", "theme_s1_sailing"), 1)

    def test_featured_pull_with_owned_bundle_reports_mixed_grants(self) -> None:
        # 从其他途径（如赛季排名）先拿到了头像框和主题，再抽中限定六星：
        # 立绘本体是全新发放，捆绑奖励走重复补偿。
        grant_item("u1", "frame_s1_6star_character", 1, "test")
        grant_item("u1", "theme_s1_sailing", 1, "test")
        grant_item("u1", STAR_STICKER_ITEM_ID, 120, "test")

        with patch("plugins.gacha.service.random.random", return_value=0.001):
            with patch("plugins.gacha.service.random.randint", return_value=1):
                results = pull("u1", 1)

        result = results[0]
        self.assertEqual(
            [
                (grant.item_id, grant.granted, grant.skipped, grant.message)
                for grant in result.grants
            ],
            [
                ("standing_art_s1_kasumi", 1, False, ""),
                ("frame_s1_6star_character", 0, True, "already_owned_compensated:12"),
                ("theme_s1_sailing", 0, True, "already_owned_compensated:120"),
            ],
        )
        self.assertEqual(
            result.grant_message,
            "already_owned_compensated:12; already_owned_compensated:120",
        )

    def test_history_is_paginated(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 1320, "test")

        with patch("plugins.gacha.service.random.random", return_value=0.99):
            pull("u1", 10)
            pull("u1", 1)

        first_page = get_history("u1", 1, page_size=5)
        third_page = get_history("u1", 3, page_size=5)
        self.assertEqual(first_page.total, 11)
        self.assertEqual(first_page.total_pages, 3)
        self.assertEqual(len(first_page.rows), 5)
        self.assertEqual(third_page.page, 3)
        self.assertEqual(len(third_page.rows), 1)

    def _banner(self, banner_key: str, season_key: str) -> GachaBanner:
        return GachaBanner(
            season_key=season_key,
            season_name=season_key,
            banner_key=banner_key,
            name=banner_key,
            single_cost=120,
            ten_cost=1200,
            base_rates={6: 0.01, 5: 0.09, 4: 0.30, 3: 0.60},
            soft_pity_start=70,
            hard_pity=90,
            entries=(
                GachaEntry(
                    item_id="standing_art_placeholder_r3_001",
                    character_id="placeholder",
                    name="占位角色立绘 3-1",
                    rarity=3,
                    weight=1,
                ),
            ),
        )

    def _season_config(self) -> dict:
        return {
            "timezone": "UTC+8",
            "seasons": [
                {
                    "season_key": "2026-s01",
                    "number": 1,
                    "name": "测试赛季",
                    "starts_at": "2000-01-01T00:00:00+08:00",
                    "ends_at": "2100-01-01T00:00:00+08:00",
                    "featured_characters": [
                        {
                            "character_id": "kasumi",
                            "name": "户山香澄",
                            "standing_art_item_id": "standing_art_s1_kasumi",
                            "rarity": 6,
                        },
                        {
                            "character_id": "arisa",
                            "name": "市谷有咲",
                            "standing_art_item_id": "standing_art_s1_arisa",
                            "rarity": 6,
                        },
                    ],
                    "gacha_character_frame_item_id": "frame_s1_6star_character",
                    "gacha_theme_item_id": "theme_s1_sailing",
                    "gacha_banner": {
                        "banner_key": "2026-s01-limited",
                        "name": "测试限定卡池",
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
                                "item_id": "standing_art_s1_kasumi",
                                "character_id": "kasumi",
                                "name": "户山香澄 扬帆立绘",
                                "rarity": 6,
                                "weight": 1,
                                "featured": True,
                            },
                            {
                                "item_id": "standing_art_s1_arisa",
                                "character_id": "arisa",
                                "name": "市谷有咲 扬帆立绘",
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

    def _add_currency(
        self, item_id: str, name: str, currency_kind: str
    ) -> None:
        self.inventory_session.add(
            Item(
                item_id=item_id,
                category="currency",
                name=name,
                stackable=True,
                visible=True,
                sort_order=0,
                metadata_json="{}",
            )
        )
        self.inventory_session.add(
            CurrencyItem(
                item_id=item_id,
                currency_kind=currency_kind,
                unit_name="",
                rankable=False,
                reset_policy="none",
            )
        )
        self.inventory_session.commit()

    def _add_cosmetic(
        self, item_id: str, cosmetic_type: str, rarity: int
    ) -> None:
        self.inventory_session.add(
            Item(
                item_id=item_id,
                category="cosmetic",
                name=item_id,
                stackable=False,
                visible=True,
                sort_order=0,
                metadata_json="{}",
            )
        )
        self.inventory_session.add(
            CosmeticItem(
                item_id=item_id,
                cosmetic_type=cosmetic_type,
                rarity=rarity,
            )
        )
        self.inventory_session.commit()


class StarbeatRealConfigTest(unittest.TestCase):
    """The shipped seasons.json + items.json must sync and validate as-is.

    No config monkeypatching here: this reads the real files, so a bad item id
    in season 2 fails in CI instead of at the first production sync.
    """

    def setUp(self) -> None:
        inventory_engine = create_engine("sqlite:///:memory:")
        InventoryBase.metadata.create_all(inventory_engine)
        inventory_database.session = sessionmaker(bind=inventory_engine)()
        self.inventory_session = inventory_database.session

    def tearDown(self) -> None:
        self.inventory_session.close()
        inventory_database.session = None

    def test_catalog_and_seasons_sync_without_errors(self) -> None:
        sync_catalog()
        seasons = season_service.sync_seasons_config()  # runs _validate_reward_items
        # 扬帆起航 was scrapped before launch; 星之鼓动 is the real season 1.
        self.assertEqual(
            [season.season_key for season in seasons], ["2026-s01"]
        )

    def test_scrapped_planned_season_is_pruned_from_the_database(self) -> None:
        from plugins.inventory.models import Season

        sync_catalog()
        session = inventory_database.get_session()
        session.add(
            Season(
                season_key="2026-scrapped",
                season_number=99,
                name="废案赛季",
                start_time=4102444800,  # far future: stays planned
                end_time=4105036800,
                status="planned",
            )
        )
        session.commit()

        season_service.sync_seasons_config()

        self.assertIsNone(season_service.get_season_by_key("2026-scrapped"))
        # The configured season is untouched.
        self.assertIsNotNone(season_service.get_season_by_key("2026-s01"))

    def test_ended_orphan_season_survives_the_prune(self) -> None:
        from plugins.inventory.models import Season

        sync_catalog()
        session = inventory_database.get_session()
        session.add(
            Season(
                season_key="2020-legacy",
                season_number=98,
                name="历史赛季",
                start_time=1577836800,
                end_time=1580515200,
                status="ended",
            )
        )
        session.commit()

        season_service.sync_seasons_config()

        self.assertIsNotNone(season_service.get_season_by_key("2020-legacy"))

    def test_starbeat_banner_builds_and_validates(self) -> None:
        sync_catalog()
        season_service.sync_seasons_config()
        season = season_service.get_season_by_key("2026-s01")
        self.assertIsNotNone(season)
        self.assertEqual(season.season_number, 1)
        self.assertEqual(season.name, "星之鼓动")

        banner = gacha_service._banner_from_season(season)
        self.assertIsNotNone(banner)
        gacha_service._validate_banner_rewards(banner)  # must not raise
        self.assertEqual(banner.banner_key, "2026-s01-limited")
        self.assertEqual(banner.name, "星之鼓动 限定卡池")
        self.assertEqual(banner.single_cost, 120)
        self.assertEqual(banner.ten_cost, 1200)
        self.assertEqual(banner.soft_pity_start, 70)
        self.assertEqual(banner.hard_pity, 90)
        self.assertEqual(
            banner.base_rates, {6: 0.01, 5: 0.09, 4: 0.30, 3: 0.60}
        )

        featured = [entry for entry in banner.entries if entry.featured]
        self.assertEqual(
            [entry.item_id for entry in featured], ["standing_art_kasumi_starbeat"]
        )
        self.assertEqual(featured[0].character_id, "kasumi")
        self.assertEqual(featured[0].rarity, 6)
        # Season 1 retains its six existing rewards while additional standard
        # standing art may be appended to the configured normal pool.
        fillers = {
            entry.item_id for entry in banner.entries if not entry.featured
        }
        self.assertTrue(
            {
                "standing_art_placeholder_r3_001",
                "standing_art_placeholder_r3_002",
                "standing_art_placeholder_r4_001",
                "standing_art_placeholder_r4_002",
                "standing_art_placeholder_r5_001",
                "standing_art_placeholder_r5_002",
            }.issubset(fillers)
        )

    def test_starbeat_rank_rewards_also_grant_the_theme(self) -> None:
        config = season_service.load_seasons_config()
        starbeat = next(
            entry
            for entry in config["seasons"]
            if entry["season_key"] == "2026-s01"
        )
        self.assertEqual(starbeat["gacha_theme_item_id"], "theme_kasumi_starbeat")
        self.assertEqual(
            starbeat["gacha_character_frame_item_id"], "frame_kasumi_starbeat"
        )
        tier_items = {
            tier["tier_key"]: {item["item_id"] for item in tier["items"]}
            for tier in starbeat["reward_tiers"]
        }
        # 设计文档：同一个主题物品可以同时来自抽卡与排名两条路径
        self.assertIn("theme_kasumi_starbeat", tier_items["rank_1"])
        self.assertIn("theme_kasumi_starbeat", tier_items["rank_2_3"])
        self.assertNotIn("theme_kasumi_starbeat", tier_items["rank_4_10"])

        tiers = {
            tier["tier_key"]: {
                item["item_id"]: item["quantity"] for item in tier["items"]
            }
            for tier in starbeat["reward_tiers"]
        }
        self.assertEqual(tiers["rank_1"]["star_sticker"], 2400)
        self.assertEqual(tiers["rank_2_3"]["star_sticker"], 1200)
        self.assertEqual(tiers["rank_4_10"]["star_sticker"], 600)
        self.assertEqual(tiers["rank_11_50"]["star_sticker"], 300)
        self.assertEqual(tiers["rank_11_50"]["frame_starbeat_top50"], 1)

    def test_theme_catalog_stays_clean(self) -> None:
        from utils.theming import validate_theme_catalog

        self.assertEqual(validate_theme_catalog(), [])

    def test_standing_art_metadata_points_at_an_existing_file(self) -> None:
        from pathlib import Path

        from plugins.inventory.catalog import load_catalog

        entry = next(
            item
            for item in load_catalog()
            if item["item_id"] == "standing_art_kasumi_starbeat"
        )
        art = entry["metadata"]["art"]
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / art).exists(), art)


class StarbeatPullTest(unittest.TestCase):
    """The starbeat shape (single featured character) through the pull flow."""

    def setUp(self) -> None:
        inventory_engine = create_engine("sqlite:///:memory:")
        InventoryBase.metadata.create_all(inventory_engine)
        inventory_database.session = sessionmaker(bind=inventory_engine)()
        self.inventory_session = inventory_database.session

        gacha_engine = create_engine("sqlite:///:memory:")
        GachaBase.metadata.create_all(gacha_engine)
        gacha_database.session = sessionmaker(bind=gacha_engine)()
        self.gacha_session = gacha_database.session

        sync_catalog()  # the real items.json: starbeat items must all exist
        self._original_load_seasons_config = season_service.load_seasons_config
        season_service.load_seasons_config = lambda: copy.deepcopy(
            self._season_config()
        )
        season_service.activate_due_seasons()

    def tearDown(self) -> None:
        season_service.load_seasons_config = self._original_load_seasons_config
        self.gacha_session.close()
        self.inventory_session.close()
        gacha_database.session = None
        inventory_database.session = None

    def test_first_featured_pull_ships_frame_and_theme(self) -> None:
        grant_item("u1", STAR_STICKER_ITEM_ID, 240, "test")

        with patch("plugins.gacha.service.random.random", return_value=0.001):
            with patch("plugins.gacha.service.random.randint", return_value=1):
                first = pull("u1", 1)[0]
                second = pull("u1", 1)[0]

        self.assertEqual(
            [
                (grant.item_id, grant.granted, grant.skipped, grant.message)
                for grant in first.grants
            ],
            [
                ("standing_art_kasumi_starbeat", 1, False, ""),
                ("frame_kasumi_starbeat", 1, False, ""),
                ("theme_kasumi_starbeat", 1, False, ""),
            ],
        )
        self.assertEqual(get_quantity("u1", "theme_kasumi_starbeat"), 1)
        self.assertEqual(get_quantity("u1", "frame_kasumi_starbeat"), 1)

        # 第二发同一限定：只有立绘补偿，捆绑奖励不重复发放
        self.assertEqual(
            [
                (grant.item_id, grant.granted, grant.skipped, grant.message)
                for grant in second.grants
            ],
            [("standing_art_kasumi_starbeat", 0, True, "already_owned_compensated:60")],
        )
        self.assertEqual(get_quantity("u1", BONSAI_ITEM_ID), 60)

    def _season_config(self) -> dict:
        return {
            "timezone": "UTC+8",
            "seasons": [
                {
                    "season_key": "2026-s01",
                    "number": 2,
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


if __name__ == "__main__":
    unittest.main()


class EarlySettlementGatingTest(unittest.TestCase):
    """A settled season is over even inside its configured time window."""

    def setUp(self) -> None:
        inventory_engine = create_engine("sqlite:///:memory:")
        InventoryBase.metadata.create_all(inventory_engine)
        inventory_database.session = sessionmaker(bind=inventory_engine)()
        self.inventory_session = inventory_database.session
        sync_catalog()
        season = season_service.sync_seasons_config()[0]
        season_service.activate_due_seasons(now=season.start_time + 1)

    def tearDown(self) -> None:
        self.inventory_session.close()
        inventory_database.session = None

    def test_settled_season_closes_scope_and_banner_mid_window(self) -> None:
        from plugins.inventory.models import OFFSEASON_SCOPE_TYPE
        from plugins.inventory.models import Season

        season = self.inventory_session.query(Season).first()
        mid_window = season.start_time + 60

        # In-window and unsettled: the season is current, the banner is open.
        self.assertIsNotNone(season_service.get_current_season(now=mid_window))
        scope_type, _, _ = season_service.get_point_scope(now=mid_window)
        self.assertNotEqual(scope_type, OFFSEASON_SCOPE_TYPE)

        # Admin settles early (what /season-admin settle does).
        season.settled_at = mid_window
        self.inventory_session.commit()

        # The very same instant: season over, Pt scope offseason, banner gone.
        self.assertIsNone(season_service.get_current_season(now=mid_window))
        scope_type, _, _ = season_service.get_point_scope(now=mid_window)
        self.assertEqual(scope_type, OFFSEASON_SCOPE_TYPE)
        self.assertIsNone(gacha_service.get_current_banner())
