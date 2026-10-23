from datetime import datetime
from contextlib import contextmanager
from collections import Counter
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from plugins.gacha import service as gacha_service
from plugins.gacha import database as gacha_database
from plugins.inventory import database as inventory_database
from plugins.inventory import season_service
from plugins.gacha.models import Base as GachaBase
from plugins.inventory.models import SEASON_SCOPE_TYPE
from plugins.inventory.models import OFFSEASON_SCOPE_TYPE
from plugins.inventory.models import SEASON_POINT_ITEM_ID
from plugins.inventory.models import STAR_STICKER_ITEM_ID
from plugins.inventory.models import Base as InventoryBase
from plugins.inventory.models import Item
from plugins.inventory.models import SeasonRanking
from plugins.inventory.catalog import sync_catalog
from plugins.inventory.service import grant_item
from plugins.inventory.service import get_quantity

USER_ID = "season-transition-test-user"

S2_START = int(datetime.fromisoformat("2026-08-30T00:00:00+08:00").timestamp())
S2_END = int(datetime.fromisoformat("2026-09-27T00:00:00+08:00").timestamp())
S3_START = int(datetime.fromisoformat("2026-09-28T00:00:00+08:00").timestamp())
S3_END = int(datetime.fromisoformat("2026-10-26T00:00:00+08:00").timestamp())


@pytest.fixture
def isolated_season_instance(tmp_path, monkeypatch):
    """Use durable, throwaway databases instead of either developer database."""

    inventory_path = tmp_path / "season-transition-inventory.db"
    inventory_engine = create_engine(f"sqlite:///{inventory_path}")
    InventoryBase.metadata.create_all(inventory_engine)
    inventory_session = sessionmaker(bind=inventory_engine)()
    monkeypatch.setattr(inventory_database, "session", inventory_session)

    gacha_path = tmp_path / "season-transition-gacha.db"
    gacha_engine = create_engine(f"sqlite:///{gacha_path}")
    GachaBase.metadata.create_all(gacha_engine)
    gacha_session = sessionmaker(bind=gacha_engine)()
    monkeypatch.setattr(gacha_database, "session", gacha_session)

    sync_catalog()
    assert inventory_path.exists()
    assert gacha_path.exists()

    yield inventory_session, gacha_session

    gacha_session.close()
    inventory_session.close()
    gacha_engine.dispose()
    inventory_engine.dispose()


@contextmanager
def at_time(timestamp: int):
    # season_service and gacha_service both reference the standard time module,
    # so this one clock controls lifecycle checks, wallet writes and pull history.
    with patch("plugins.inventory.season_service.time.time", return_value=timestamp):
        yield


def assert_banner_shape(banner, season_key: str, banner_key: str, name: str) -> None:
    assert banner is not None
    assert banner.season_key == season_key
    assert banner.banner_key == banner_key
    assert banner.name == name
    assert banner.single_cost == 120
    assert banner.ten_cost == 1200
    assert banner.soft_pity_start == 70
    assert banner.hard_pity == 90
    assert banner.base_rates == {6: 0.01, 5: 0.09, 4: 0.30, 3: 0.60}
    assert Counter(entry.rarity for entry in banner.entries) == {
        6: 1,
        5: 15,
        4: 5,
        3: 9,
    }


def test_real_s2_offseason_s3_transition_and_gacha_state(
    isolated_season_instance,
) -> None:
    inventory_session, gacha_session = isolated_season_instance

    # A fresh instance catches up the already-ended S1, then exposes the real
    # one-day S1 -> S2 offseason. No banner is available before activation.
    with at_time(S2_START - 1):
        season_service.sync_seasons_config(now=S2_START - 1)
        assert season_service.settle_due_seasons(now=S2_START - 1) == 1
        assert season_service.get_current_season() is None
        assert gacha_service.get_current_banner() is None
        assert season_service.get_point_scope()[:2] == (
            OFFSEASON_SCOPE_TYPE,
            "2026-s01_to_2026-s02",
        )
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID) == 100

    # Exact S2 opening: activation is required once, its Pt wallet is fresh,
    # and a real normal-pool draw creates the pity/history state to carry on.
    with at_time(S2_START):
        assert gacha_service.get_current_banner() is None
        assert season_service.activate_due_seasons(now=S2_START) == 1
        assert season_service.activate_due_seasons(now=S2_START) == 0

        s2 = season_service.get_current_season()
        assert s2 is not None
        assert s2.season_key == "2026-s02"
        assert s2.status == "open"
        assert season_service.get_point_scope()[:2] == (
            SEASON_SCOPE_TYPE,
            str(s2.id),
        )
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID) == 100
        grant_item(USER_ID, SEASON_POINT_ITEM_ID, 50, "transition_test")
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID) == 150

        s2_banner = gacha_service.get_current_banner()
        assert_banner_shape(
            s2_banner,
            "2026-s02",
            "2026-s02-limited",
            "夢見∞無限 限定卡池",
        )
        gacha_service._validate_banner_rewards(s2_banner)
        assert {
            entry.character_id for entry in s2_banner.entries if entry.featured
        } == {
            "nakamachi_arale",
            "fuji_miyako",
            "minetsuki_ritsu",
            "miyanaga_nonoka",
            "sengoku_yuno",
        }

        grant_item(USER_ID, STAR_STICKER_ITEM_ID, 240, "transition_test")
        with patch("plugins.gacha.service.random.random", return_value=0.99):
            with patch("plugins.gacha.service.random.randint", return_value=1):
                s2_pull = gacha_service.pull(USER_ID, 1)[0]
        assert s2_pull.rarity == 3
        assert s2_pull.pity_before == 0
        assert s2_pull.pity_after == 1
        assert get_quantity(USER_ID, STAR_STICKER_ITEM_ID) == 120
        assert gacha_service.get_state(USER_ID).pity_count == 1

    s2_scope = (SEASON_SCOPE_TYPE, str(s2.id))

    # The configured end instant closes the banner even before settlement.
    # Settlement freezes the ranking, while the one-day S2 -> S3 offseason
    # gets an independent 100 Pt wallet and rejects all pulls.
    with at_time(S2_END):
        assert gacha_service.get_current_banner() is None
        with patch(
            "plugins.mailbox.service.MailService.send_mail", return_value=2002
        ) as send_mail:
            assert season_service.settle_due_seasons(now=S2_END) == 1
        send_mail.assert_called_once()
        assert season_service.settle_due_seasons(now=S2_END) == 0

        settled_s2 = season_service.get_season_by_key("2026-s02")
        assert settled_s2 is not None
        assert settled_s2.status == "settled"
        ranking = (
            inventory_session.query(SeasonRanking)
            .filter(
                SeasonRanking.season_id == settled_s2.id,
                SeasonRanking.user_id == USER_ID,
            )
            .one()
        )
        assert (ranking.rank, ranking.final_points) == (1, 150)
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID, s2_scope) == 150

        assert season_service.get_point_scope()[:2] == (
            OFFSEASON_SCOPE_TYPE,
            "2026-s02_to_2026-s03",
        )
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID) == 100
        grant_item(USER_ID, SEASON_POINT_ITEM_ID, 25, "transition_test")
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID) == 125

        with pytest.raises(ValueError, match="当前没有开放的限定卡池"):
            gacha_service.pull(USER_ID, 1)
        assert gacha_service.get_state(USER_ID).pity_count == 1
        assert gacha_service.get_history(USER_ID, 1).total == 1

    # The entire gap remains closed; the S3 start boundary is also closed
    # until its one-time activation runs.
    with at_time(S2_END + 12 * 60 * 60):
        assert season_service.activate_due_seasons(now=S2_END + 12 * 60 * 60) == 0
        assert season_service.get_current_season() is None
        assert gacha_service.get_current_banner() is None

    with at_time(S3_START):
        assert season_service.get_current_season() is None
        assert gacha_service.get_current_banner() is None
        assert season_service.activate_due_seasons(now=S3_START) == 1
        assert season_service.activate_due_seasons(now=S3_START) == 0

        s3 = season_service.get_current_season()
        assert s3 is not None
        assert s3.season_key == "2026-s03"
        assert s3.name == "Roselia · 蔷薇穹庭"
        assert s3.status == "open"

        # S2/offseason balances are archived; S3 starts from its own 100 Pt.
        assert season_service.get_point_scope()[:2] == (
            SEASON_SCOPE_TYPE,
            str(s3.id),
        )
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID) == 100
        assert (
            get_quantity(
                USER_ID,
                SEASON_POINT_ITEM_ID,
                (OFFSEASON_SCOPE_TYPE, "2026-s02_to_2026-s03"),
            )
            == 125
        )
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID, s2_scope) == 150

        s3_banner = gacha_service.get_current_banner()
        assert_banner_shape(
            s3_banner,
            "2026-s03",
            "2026-s03-limited",
            "蔷薇穹庭 限定卡池",
        )
        gacha_service._validate_banner_rewards(s3_banner)
        featured = {
            entry.character_id: (
                entry.rarity,
                entry.bestdori_card_id,
                entry.bestdori_variant,
            )
            for entry in s3_banner.entries
            if entry.featured
        }
        assert featured == {
            "yukina": (6, 90021, "normal"),
            "sayo": (5, 90022, "normal"),
            "lisa": (5, 90023, "normal"),
            "ako": (5, 90024, "normal"),
            "rinko": (5, 90025, "normal"),
        }
        catalog_ids = {
            item_id for (item_id,) in inventory_session.query(Item.item_id).all()
        }
        assert {entry.item_id for entry in s3_banner.entries} <= catalog_ids

        # Pity is account-wide by design: it survives the closed-banner gap and
        # continues on S3. The history row must point to the new season/banner.
        assert gacha_service.get_state(USER_ID).pity_count == 1
        with patch("plugins.gacha.service.random.random", return_value=0.99):
            with patch("plugins.gacha.service.random.randint", return_value=2):
                s3_pull = gacha_service.pull(USER_ID, 1)[0]
        assert s3_pull.rarity == 3
        assert s3_pull.pity_before == 1
        assert s3_pull.pity_after == 2
        assert get_quantity(USER_ID, STAR_STICKER_ITEM_ID) == 0

        history = gacha_service.get_history(USER_ID, 1)
        assert history.total == 2
        assert [row.season_key for row in history.rows] == [
            "2026-s03",
            "2026-s02",
        ]
        assert [row.banner_key for row in history.rows] == [
            "2026-s03-limited",
            "2026-s02-limited",
        ]
        assert gacha_service.get_state(USER_ID).pity_count == 2
        grant_item(USER_ID, SEASON_POINT_ITEM_ID, 10, "transition_test")

    # Also close the loop: the S3 end removes its banner, settles once, and
    # creates the S3 -> S4 offseason wallet without mutating any prior scope.
    with at_time(S3_END):
        assert gacha_service.get_current_banner() is None
        with patch(
            "plugins.mailbox.service.MailService.send_mail", return_value=2003
        ) as send_mail:
            assert season_service.settle_due_seasons(now=S3_END) == 1
        send_mail.assert_called_once()
        assert season_service.settle_due_seasons(now=S3_END) == 0
        assert season_service.get_current_season() is None
        assert season_service.get_point_scope()[:2] == (
            OFFSEASON_SCOPE_TYPE,
            "2026-s03_to_2026-s04",
        )
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID) == 100
        assert get_quantity(USER_ID, SEASON_POINT_ITEM_ID, s2_scope) == 150
        assert gacha_service.get_state(USER_ID).pity_count == 2
        assert gacha_session.query(gacha_service.GachaPull).count() == 2
