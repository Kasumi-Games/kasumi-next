import copy
import unittest
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy import inspect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plugins.gacha.models import Base as GachaBase
from plugins.gacha.models import GachaPull
from plugins.gacha import database as gacha_database
from plugins.gacha import service as gacha_service
from plugins.inventory.models import Base as InventoryBase
from plugins.inventory.models import BONSAI_ITEM_ID
from plugins.inventory import database as inventory_database
from plugins.inventory import season_service
from plugins.inventory.catalog import sync_catalog
from plugins.inventory.service import get_quantity
from plugins.inventory.service import grant_item
from plugins.ryuseido.models import Base as ShopBase
from plugins.ryuseido import database as shop_database
from plugins.ryuseido.service import buy_offer
from plugins.ryuseido.service import buy_season_pull
from plugins.ryuseido.service import list_offers
from plugins.ryuseido.service import season_pull_status


class RyuseidoServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        inventory_engine = create_engine("sqlite:///:memory:")
        InventoryBase.metadata.create_all(inventory_engine)
        inventory_database.session = sessionmaker(bind=inventory_engine)()

        gacha_engine = create_engine("sqlite:///:memory:")
        GachaBase.metadata.create_all(gacha_engine)
        gacha_database.session = sessionmaker(bind=gacha_engine)()

        shop_engine = create_engine("sqlite:///:memory:")
        ShopBase.metadata.create_all(shop_engine)
        shop_database.session = sessionmaker(bind=shop_engine)()

        sync_catalog()
        self._original_load_seasons_config = season_service.load_seasons_config
        season_service.load_seasons_config = lambda: copy.deepcopy(
            self._season_config()
        )
        season_service.activate_due_seasons(now=100)

    def tearDown(self) -> None:
        season_service.load_seasons_config = self._original_load_seasons_config
        for database in (shop_database, gacha_database, inventory_database):
            database.session.close()
            database.session = None

    def test_catalog_sells_current_permanent_art_but_no_season_theme(self) -> None:
        offers = list_offers()
        art = [offer for offer in offers if offer.section == "standing_art"]
        frames = [offer for offer in offers if offer.section == "avatar_frame"]
        themes = [offer for offer in offers if offer.section == "theme"]

        self.assertEqual(len(art), 17)
        self.assertEqual({offer.price for offer in art}, {500, 900, 1400})
        self.assertEqual(
            [(offer.sku, offer.item_id, offer.price) for offer in frames],
            [
                ("F01", "frame_shop_stardust", 1200),
                ("F02", "frame_shop_azure_rhythm", 1800),
            ],
        )
        self.assertEqual([offer.item_id for offer in themes], ["theme_sakura"])
        from plugins.inventory.service import get_item
        from utils.theming import kit_name_for_item

        stardust = get_item("frame_shop_stardust")
        azure_rhythm = get_item("frame_shop_azure_rhythm")
        self.assertEqual(stardust.name, "星屑玻璃")
        self.assertEqual(azure_rhythm.name, "舞萌DX")
        self.assertNotIn("试制品", stardust.description)
        self.assertNotIn("试制品", azure_rhythm.description)
        self.assertEqual(kit_name_for_item(get_item("theme_sakura")), "sakura")
        self.assertNotIn(
            "theme_kasumi_starbeat",
            {offer.item_id for offer in offers},
        )
        self.assertNotIn("theme_s1_sailing", {offer.item_id for offer in offers})

    def test_purchase_is_atomic_and_owned_items_cannot_be_bought_twice(self) -> None:
        grant_item("u1", BONSAI_ITEM_ID, 500, "test")

        result = buy_offer("u1", "A01")

        self.assertEqual(result.balance_after, 0)
        self.assertEqual(
            get_quantity("u1", "standing_art_placeholder_r4_001"),
            1,
        )
        with self.assertRaisesRegex(ValueError, "已经拥有"):
            buy_offer("u1", "A01")
        self.assertEqual(get_quantity("u1", BONSAI_ITEM_ID), 0)

    def test_standing_art_offer_keeps_its_image_slot(self) -> None:
        from plugins.ryuseido import _offer_row

        offer = next(
            offer
            for offer in list_offers("standing_art")
            if offer.sku == "A01"
        )
        row = _offer_row("u1", offer)

        self.assertTrue(row.show_art_slot)

    def test_bonus_pull_costs_400_counts_pity_and_stops_at_five(self) -> None:
        grant_item("u1", BONSAI_ITEM_ID, 2000, "test")

        with patch("plugins.gacha.service.random.random", return_value=0.99):
            with patch("plugins.gacha.service.random.randint", return_value=1):
                for _ in range(5):
                    buy_season_pull("u1")

        status = season_pull_status("u1")
        self.assertEqual((status.used, status.limit, status.remaining), (5, 5, 0))
        self.assertEqual(gacha_service.get_state("u1").pity_count, 5)
        rows = gacha_database.session.query(GachaPull).all()
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row.cost == 400 for row in rows))
        self.assertTrue(all(row.payment_item_id == BONSAI_ITEM_ID for row in rows))
        # The one-entry ★3 test pool returns 30 bonsai on pulls 2-5.
        self.assertEqual(get_quantity("u1", BONSAI_ITEM_ID), 120)

        with self.assertRaisesRegex(ValueError, "5 次加抽"):
            buy_season_pull("u1")

    def test_failed_bonus_pull_refunds_bonsai_and_releases_quota(self) -> None:
        grant_item("u1", BONSAI_ITEM_ID, 400, "test")

        with patch(
            "plugins.gacha.service._pull_once",
            side_effect=RuntimeError("simulated"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                buy_season_pull("u1")

        self.assertEqual(get_quantity("u1", BONSAI_ITEM_ID), 400)
        self.assertEqual(season_pull_status("u1").used, 0)
        self.assertEqual(gacha_database.session.query(GachaPull).count(), 0)

    @staticmethod
    def _season_config() -> dict:
        return {
            "timezone": "UTC+8",
            "offseason_starting_points": 100,
            "seasons": [
                {
                    "season_key": "shop-test",
                    "number": 99,
                    "name": "流星堂测试季",
                    "start_on_deployment": True,
                    "starts_at": "1970-01-01T00:00:00+08:00",
                    "ends_at": "2099-01-01T00:00:00+08:00",
                    "starting_points": 0,
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
                        "banner_key": "shop-test-banner",
                        "name": "流星堂测试卡池",
                        "single_cost": 120,
                        "ten_cost": 1200,
                        "soft_pity_start": 70,
                        "hard_pity": 90,
                        "rates": [
                            {"rarity": 6, "rate": 0.01},
                            {"rarity": 5, "rate": 0.09},
                            {"rarity": 4, "rate": 0.3},
                            {"rarity": 3, "rate": 0.6},
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
                                "character_id": "arisa",
                                "name": "市谷有咲 向着大海展翅的天马",
                                "rarity": 5,
                                "weight": 1,
                            },
                            {
                                "item_id": "standing_art_placeholder_r5_002",
                                "character_id": "tae",
                                "name": "花园多惠 你终将跑过的天空",
                                "rarity": 4,
                                "weight": 1,
                            },
                            {
                                "item_id": "standing_art_placeholder_r4_001",
                                "character_id": "rimi",
                                "name": "牛込里美 守望着的应援",
                                "rarity": 3,
                                "weight": 1,
                            },
                        ],
                    },
                    "reward_tiers": [],
                }
            ],
        }


def test_shop_sku_renders_in_inventory_listing() -> None:
    from plugins.inventory.render import InventoryListData
    from plugins.inventory.render import InventoryListRow
    from plugins.inventory.render import inventory_list_page
    from plugins.render.kits.minimal import MinimalKit

    page = inventory_list_page(
        InventoryListData(
            title="流星堂",
            page=1,
            total_pages=1,
            rows=(
                InventoryListRow(
                    index="A01",
                    name="立绘",
                    detail="500 盆栽",
                    kind="立绘",
                    rarity=3,
                ),
            ),
            subtitle="立绘",
            panel_footer="第 1/1 页",
        ),
        MinimalKit(),
    )
    image = page.render()

    assert image.width > 0
    assert image.height > 0
    text = " ".join(_component_text(page.child))
    assert "流星堂" in text
    assert "立绘" in text
    assert "第 1/1 页" in text
    assert "余额" not in text


def test_mewtype_shop_listing_uses_shop_wordmark() -> None:
    from plugins.inventory.render import InventoryListData
    from plugins.inventory.render import InventoryListRow
    from plugins.inventory.render import inventory_list_page
    from plugins.render.kits.mewtype import MewtypeKit

    page = inventory_list_page(
        InventoryListData(
            title="流星堂",
            subtitle="立绘",
            page=1,
            total_pages=1,
            rows=(
                InventoryListRow(
                    index="A01",
                    name="角色立绘",
                    detail="500 盆栽",
                    kind="立绘",
                    rarity=3,
                ),
            ),
            panel_footer="第 1/1 页",
            wordmark_title="SHOP",
        ),
        MewtypeKit(),
    )

    texts = _component_text(page.child)
    assert "SHOP" in texts
    assert "INVENTORY" not in texts
    assert page.render().width == 864


def test_theme_preview_is_rendered_by_the_theme_it_sells() -> None:
    from plugins.render.kits.sakura import SakuraKit
    from plugins.ryuseido.render import ThemePreviewData
    from plugins.ryuseido.render import theme_preview_page

    page = theme_preview_page(
        ThemePreviewData(
            sku="T01",
            name="樱色",
            description="奶油底色、樱粉点缀与飘落花瓣。",
            price=3000,
        ),
        SakuraKit(),
    )
    image = page.render()

    assert image.width == 864
    assert image.height > 0
    text = " ".join(_component_text(page.child))
    assert "樱色" in text
    assert "本主题" in text
    assert "个人资料" in text
    assert "游戏结果" in text
    assert "排行榜" in text
    assert "3000 盆栽" in text
    assert "/流星堂 购买 T01" in text
    assert "余额" not in text


def _component_text(component) -> list[str]:
    values: list[str] = []
    value = getattr(component, "text", None)
    if isinstance(value, str):
        values.append(value)
    for attribute in ("children", "child"):
        child = getattr(component, attribute, None)
        if isinstance(child, (list, tuple)):
            for item in child:
                values.extend(_component_text(item))
        elif child is not None:
            values.extend(_component_text(child))
    return values


def test_gacha_schema_migration_marks_legacy_pulls_as_sticker_paid() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE gacha_pulls ("
                "id INTEGER PRIMARY KEY, user_id VARCHAR, banner_key VARCHAR, "
                "season_key VARCHAR, item_id VARCHAR, character_id VARCHAR, "
                "rarity INTEGER, cost INTEGER, pity_before INTEGER, "
                "pity_after INTEGER, message VARCHAR, created_at INTEGER)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO gacha_pulls VALUES "
                "(1, 'u1', 'b', 's', 'i', 'c', 3, 120, 0, 1, '', 1)"
            )
        )

    gacha_database.migrate_gacha_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("gacha_pulls")}
    self_row = None
    with engine.connect() as connection:
        self_row = connection.execute(
            text("SELECT payment_item_id FROM gacha_pulls WHERE id = 1")
        ).scalar_one()
    assert "payment_item_id" in columns
    assert self_row == "star_sticker"
