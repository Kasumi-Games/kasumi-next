import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plugins.inventory import database
from plugins.inventory.models import BONSAI_ITEM_ID
from plugins.inventory.models import SEASON_SCOPE_TYPE
from plugins.inventory.models import SEASON_POINT_ITEM_ID
from plugins.inventory.models import Base
from plugins.inventory.models import Item
from plugins.inventory.models import UserItem
from plugins.inventory.models import CosmeticItem
from plugins.inventory.models import CurrencyItem
from plugins.inventory.models import SeasonParticipation
from plugins.inventory.service import grant_item
from plugins.inventory.service import get_quantity


class InventoryCosmeticsTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        database.session = sessionmaker(bind=engine)()
        self.session = database.session
        self._add_currency(BONSAI_ITEM_ID, "盆栽", "permanent")
        self._add_currency(SEASON_POINT_ITEM_ID, "赛季积分", "seasonal")
        self._add_cosmetic("frame_test_6star", "avatar_frame", 6)

    def tearDown(self) -> None:
        self.session.close()
        database.session = None

    def test_duplicate_avatar_frame_grants_bonsai(self) -> None:
        first = grant_item("u1", "frame_test_6star", 1, "test")
        duplicate = grant_item("u1", "frame_test_6star", 1, "test")

        self.assertEqual(first.granted, 1)
        self.assertTrue(duplicate.skipped)
        self.assertEqual(duplicate.message, "already_owned_compensated:12")
        self.assertEqual(get_quantity("u1", BONSAI_ITEM_ID), 12)

    def test_season_point_delta_marks_participation(self) -> None:
        grant_item(
            "u1",
            SEASON_POINT_ITEM_ID,
            5,
            "test",
            scope=(SEASON_SCOPE_TYPE, "42"),
        )

        participation = (
            self.session.query(SeasonParticipation)
            .filter(
                SeasonParticipation.user_id == "u1",
                SeasonParticipation.season_id == 42,
            )
            .first()
        )
        points = (
            self.session.query(UserItem)
            .filter(
                UserItem.user_id == "u1",
                UserItem.item_id == SEASON_POINT_ITEM_ID,
                UserItem.scope_type == SEASON_SCOPE_TYPE,
                UserItem.scope_id == "42",
            )
            .first()
        )
        self.assertIsNotNone(participation)
        self.assertEqual(points.quantity, 5)

    def _add_currency(
        self, item_id: str, name: str, currency_kind: str
    ) -> None:
        self.session.add(
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
        self.session.add(
            CurrencyItem(
                item_id=item_id,
                currency_kind=currency_kind,
                unit_name="",
                rankable=False,
                reset_policy="none",
            )
        )
        self.session.commit()

    def _add_cosmetic(
        self, item_id: str, cosmetic_type: str, rarity: int
    ) -> None:
        self.session.add(
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
        self.session.add(
            CosmeticItem(
                item_id=item_id,
                cosmetic_type=cosmetic_type,
                rarity=rarity,
            )
        )
        self.session.commit()
