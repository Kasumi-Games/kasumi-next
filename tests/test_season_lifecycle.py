"""Season opening, settlement, recovery, and configuration invariants."""

from __future__ import annotations

import copy
import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import plugins.inventory as inventory_plugin
from plugins.inventory import database
from plugins.inventory import migration
from plugins.inventory import season_service
from plugins.inventory.models import SEASON_SCOPE_TYPE
from plugins.inventory.models import PERMANENT_SCOPE_ID
from plugins.inventory.models import PERMANENT_SCOPE_TYPE
from plugins.inventory.models import SEASON_POINT_ITEM_ID
from plugins.inventory.models import STAR_STICKER_ITEM_ID
from plugins.inventory.models import Base
from plugins.inventory.models import Item
from plugins.inventory.models import MigrationState
from plugins.inventory.models import UserItem
from plugins.inventory.models import CurrencyItem
from plugins.inventory.models import SeasonReward
from plugins.inventory.models import SeasonRanking
from plugins.inventory.service import grant_item
from plugins.inventory.service import get_quantity

START = int(datetime.fromisoformat("2030-01-01T00:00:00+08:00").timestamp())
END = int(datetime.fromisoformat("2030-01-29T00:00:00+08:00").timestamp())


def _season_entry(
    *,
    key: str = "s1",
    number: int = 1,
    starts_at: str = "2030-01-01T00:00:00+08:00",
    ends_at: str = "2030-01-29T00:00:00+08:00",
    starting_points: int = 25,
) -> dict:
    return {
        "season_key": key,
        "number": number,
        "name": key.upper(),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "starting_points": starting_points,
        "snapshot_interval_minutes": 60,
        "snapshot_ranks": [1, 3],
        "reward_tiers": [
            {
                "tier_key": "rank_1",
                "from_rank": 1,
                "to_rank": 1,
                "title": "冠军",
                "items": [{"item_id": "reward_token", "quantity": 1}],
            }
        ],
        "participation_reward": {
            "tier_key": "participation",
            "title": "参与",
            "items": [{"item_id": "participation_token", "quantity": 1}],
        },
    }


@pytest.fixture
def lifecycle_db(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(database, "session", session)
    session.add_all(
        [
            Item(
                item_id=SEASON_POINT_ITEM_ID,
                category="currency",
                name="Pt",
                stackable=True,
                visible=True,
                sort_order=0,
                metadata_json="{}",
            ),
            CurrencyItem(
                item_id=SEASON_POINT_ITEM_ID,
                currency_kind="seasonal",
                unit_name="Pt",
                rankable=True,
                reset_policy="season",
            ),
            Item(
                item_id="reward_token",
                category="item",
                name="冠军奖励",
                stackable=True,
                visible=True,
                sort_order=0,
                metadata_json="{}",
            ),
            Item(
                item_id="participation_token",
                category="item",
                name="参与奖励",
                stackable=True,
                visible=True,
                sort_order=0,
                metadata_json="{}",
            ),
        ]
    )
    session.commit()
    config = {
        "timezone": "UTC+8",
        "offseason_starting_points": 100,
        "seasons": [_season_entry()],
    }
    monkeypatch.setattr(
        season_service,
        "load_seasons_config",
        lambda: copy.deepcopy(config),
    )
    yield session, config
    session.close()


def _sync_and_grant(session, user_id: str = "u1", quantity: int = 100):
    season = season_service.sync_seasons_config()[0]
    session.refresh(season)
    grant_item(
        user_id,
        SEASON_POINT_ITEM_ID,
        quantity,
        "test",
        scope=(SEASON_SCOPE_TYPE, str(season.id)),
    )
    return season


def test_real_first_season_uses_the_committed_28_day_window():
    config = season_service.load_seasons_config()
    first = config["seasons"][0]
    starts_at = datetime.fromisoformat(first["starts_at"])
    ends_at = datetime.fromisoformat(first["ends_at"])
    assert first["starts_at"] == "2026-08-01T00:00:00+08:00"
    assert (ends_at - starts_at).days == 28


def test_inventory_migration_adds_opened_at_and_unique_season_key(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE seasons ("
            "id INTEGER PRIMARY KEY, "
            "season_number INTEGER NOT NULL UNIQUE, "
            "name VARCHAR NOT NULL, "
            "start_time INTEGER NOT NULL, "
            "end_time INTEGER NOT NULL, "
            "status VARCHAR NOT NULL"
            ")"
        )
        connection.exec_driver_sql(
            "INSERT INTO seasons "
            "(id, season_number, name, start_time, end_time, status) "
            "VALUES (1, 1, '旧赛季', 1, 2, 'planned')"
        )
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(database, "session", session)

    migration.migrate_inventory_schema()

    with engine.connect() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(seasons)"
            ).fetchall()
        }
        indexes = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA index_list(seasons)"
            ).fetchall()
        }
    assert "opened_at" in columns
    assert "uq_seasons_season_key" in indexes


def test_opening_applies_configured_starting_points(
    lifecycle_db, monkeypatch: pytest.MonkeyPatch
):
    season_service.sync_seasons_config()
    monkeypatch.setattr(season_service.time, "time", lambda: START + 1)
    season_service.activate_due_seasons(now=START + 1)
    assert get_quantity("new-user", SEASON_POINT_ITEM_ID) == 25
    assert get_quantity("new-user", SEASON_POINT_ITEM_ID) == 25


def test_zero_point_wallet_without_participation_is_not_ranked(
    lifecycle_db, monkeypatch: pytest.MonkeyPatch
):
    session, config = lifecycle_db
    config["seasons"][0]["starting_points"] = 0
    season = season_service.sync_seasons_config()[0]
    monkeypatch.setattr(season_service.time, "time", lambda: START + 1)
    season_service.activate_due_seasons(now=START + 1)

    # Reading a balance creates a wallet, but must not count as participation.
    assert get_quantity("viewer-only", SEASON_POINT_ITEM_ID) == 0
    grant_item(
        "participant",
        SEASON_POINT_ITEM_ID,
        10,
        "test",
        scope=(SEASON_SCOPE_TYPE, str(season.id)),
    )

    with patch("plugins.mailbox.service.MailService.send_mail", return_value=101):
        season_service.settle_season("s1", now=END)

    rankings = session.query(SeasonRanking).order_by(SeasonRanking.rank).all()
    assert [(row.user_id, row.final_points) for row in rankings] == [
        ("participant", 10)
    ]
    assert (
        session.query(SeasonReward)
        .filter(SeasonReward.user_id == "viewer-only")
        .count()
        == 0
    )


def test_open_transition_is_recorded_once(lifecycle_db):
    session, _ = lifecycle_db
    season = season_service.sync_seasons_config()[0]
    assert season_service.activate_due_seasons(now=START - 1) == 0
    assert season_service.get_current_season(now=START) is None
    assert season_service.activate_due_seasons(now=START) == 1
    assert season_service.get_current_season(now=START) is not None
    assert season_service.activate_due_seasons(now=START + 60) == 0
    session.refresh(season)
    assert season.opened_at == START
    assert season.status == "open"


def test_start_on_deployment_opens_early_and_freezes_the_actual_start(
    lifecycle_db,
):
    session, config = lifecycle_db
    config["seasons"][0]["start_on_deployment"] = True
    deployment_time = START - 86_400

    due = season_service.get_due_seasons(now=deployment_time)
    assert [row.season_key for row in due] == ["s1"]
    assert season_service.get_current_season(now=deployment_time) is None

    assert season_service.activate_due_seasons(now=deployment_time) == 1
    season = season_service.get_current_season(now=deployment_time)
    assert season is not None
    assert season.start_time == deployment_time
    assert season.opened_at == deployment_time

    # Later config syncs must not restore the authored placeholder start.
    season_service.sync_seasons_config(now=deployment_time + 60)
    session.refresh(season)
    assert season.start_time == deployment_time


def test_regular_season_does_not_open_before_its_authored_start(lifecycle_db):
    assert season_service.get_due_seasons(now=START - 86_400) == []


def test_deferred_migration_does_not_open_legacy_database(
    lifecycle_db, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(season_service.time, "time", lambda: START - 1)

    def fail_if_called():
        raise AssertionError("legacy database should stay untouched before a season")

    monkeypatch.setattr(
        "plugins.monetary.database.init_database",
        fail_if_called,
    )

    migration.migrate_legacy_monetary_balances()


def test_opening_adds_legacy_balances_without_losing_preseason_inventory(
    lifecycle_db,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    session, config = lifecycle_db
    config["seasons"][0]["starting_points"] = 0
    season = season_service.sync_seasons_config()[0]

    legacy_db = tmp_path / "monetary.db"
    with sqlite3.connect(legacy_db) as connection:
        connection.execute(
            "CREATE TABLE users ("
            "user_id TEXT PRIMARY KEY, balance INTEGER NOT NULL, "
            "star_stickers INTEGER NOT NULL)"
        )
        connection.execute(
            "INSERT INTO users (user_id, balance, star_stickers) "
            "VALUES ('legacy-user', 12345, 6900)"
        )
    monkeypatch.setattr(migration.store, "get_data_file", lambda *_args: legacy_db)
    monkeypatch.setattr(
        "plugins.monetary.database.init_database",
        lambda: None,
    )

    # A deployment before opening creates a separate off-season Pt wallet and
    # may receive permanent sticker rewards before the deferred migration runs.
    monkeypatch.setattr(season_service.time, "time", lambda: START - 1)
    assert get_quantity("legacy-user", SEASON_POINT_ITEM_ID) == 12345
    grant_item(
        "legacy-user",
        SEASON_POINT_ITEM_ID,
        55,
        "preseason_game_reward",
    )
    assert get_quantity("legacy-user", SEASON_POINT_ITEM_ID) == 12400
    assert get_quantity("new-user", SEASON_POINT_ITEM_ID) == 0
    grant_item(
        "new-user",
        SEASON_POINT_ITEM_ID,
        77,
        "preseason_new_user_reward",
    )
    session.add(
        UserItem(
            user_id="legacy-user",
            item_id=STAR_STICKER_ITEM_ID,
            scope_type=PERMANENT_SCOPE_TYPE,
            scope_id=PERMANENT_SCOPE_ID,
            quantity=80,
            updated_at=START - 1,
        )
    )
    session.commit()
    migration.migrate_legacy_monetary_balances()
    assert session.query(MigrationState).count() == 0

    monkeypatch.setattr(season_service.time, "time", lambda: START + 1)
    # If migration is slow or fails, crossing the configured timestamp keeps
    # the same bridge wallet visible instead of creating a fresh 100-Pt scope.
    assert get_quantity("legacy-user", SEASON_POINT_ITEM_ID) == 12400
    due = season_service.get_due_seasons(now=START + 1)
    migration.migrate_legacy_monetary_balances(season=due[0])
    season_service.activate_due_seasons(now=START + 1)

    season_points = (
        session.query(UserItem)
        .filter(
            UserItem.user_id == "legacy-user",
            UserItem.item_id == SEASON_POINT_ITEM_ID,
            UserItem.scope_type == SEASON_SCOPE_TYPE,
            UserItem.scope_id == str(season.id),
        )
        .one()
    )
    stickers = (
        session.query(UserItem)
        .filter(
            UserItem.user_id == "legacy-user",
            UserItem.item_id == STAR_STICKER_ITEM_ID,
            UserItem.scope_type == PERMANENT_SCOPE_TYPE,
            UserItem.scope_id == PERMANENT_SCOPE_ID,
        )
        .one()
    )
    assert season_points.quantity == 12400
    new_user_points = (
        session.query(UserItem)
        .filter(
            UserItem.user_id == "new-user",
            UserItem.item_id == SEASON_POINT_ITEM_ID,
            UserItem.scope_type == SEASON_SCOPE_TYPE,
            UserItem.scope_id == str(season.id),
        )
        .one()
    )
    assert new_user_points.quantity == 77
    assert stickers.quantity == 6980

    # The old off-season wallet remains archived rather than being deleted,
    # and the migration marker makes every later lifecycle retry a no-op.
    offseason_points = (
        session.query(UserItem)
        .filter(
            UserItem.user_id == "legacy-user",
            UserItem.item_id == SEASON_POINT_ITEM_ID,
            UserItem.scope_type != SEASON_SCOPE_TYPE,
        )
        .one()
    )
    assert offseason_points.quantity == 12400
    migration.migrate_legacy_monetary_balances()
    assert season_points.quantity == 12400
    assert stickers.quantity == 6980


async def test_lifecycle_retries_deferred_legacy_migration(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []
    due_season = object()
    monkeypatch.setattr(
        inventory_plugin,
        "get_due_seasons",
        lambda *, now=None: [due_season],
    )
    monkeypatch.setattr(
        inventory_plugin,
        "activate_due_seasons",
        lambda *, now=None: calls.append("open") or 1,
    )
    monkeypatch.setattr(inventory_plugin, "settle_due_seasons", lambda: 0)
    monkeypatch.setattr(
        inventory_plugin,
        "dispatch_pending_season_rewards",
        lambda: 0,
    )
    monkeypatch.setattr(
        migration,
        "migrate_legacy_monetary_balances",
        lambda *, season=None: calls.append(
            "migration:due" if season is due_season else "migration:wrong"
        ),
    )

    await inventory_plugin.process_season_lifecycle()

    assert calls == ["migration:due", "open"]


async def test_lifecycle_does_not_open_when_legacy_migration_fails(
    lifecycle_db,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []
    monkeypatch.setattr(
        inventory_plugin, "get_due_seasons", lambda *, now=None: [object()]
    )
    monkeypatch.setattr(
        inventory_plugin,
        "activate_due_seasons",
        lambda *, now=None: calls.append("open"),
    )
    monkeypatch.setattr(
        migration,
        "migrate_legacy_monetary_balances",
        lambda *, season=None: (_ for _ in ()).throw(RuntimeError("migration failed")),
    )

    await inventory_plugin.process_season_lifecycle()

    assert calls == []


def test_planned_season_cannot_be_settled(lifecycle_db):
    with pytest.raises(ValueError, match="尚未开始"):
        season_service.settle_season("s1", now=START - 1, force=True)


def test_early_settlement_requires_force(lifecycle_db):
    with pytest.raises(ValueError, match="force"):
        season_service.settle_season("s1", now=START + 1)


def test_second_settlement_cannot_rewrite_final_ranking(lifecycle_db):
    session, _ = lifecycle_db
    season = _sync_and_grant(session)
    with patch(
        "plugins.mailbox.service.MailService.send_mail", return_value=101
    ):
        season_service.settle_season("s1", now=END)

    wallet = (
        session.query(UserItem)
        .filter(
            UserItem.user_id == "u1",
            UserItem.scope_type == SEASON_SCOPE_TYPE,
            UserItem.scope_id == str(season.id),
        )
        .one()
    )
    wallet.quantity = 999
    session.commit()

    with pytest.raises(ValueError, match="已经结算"):
        season_service.settle_season("s1", now=END + 60)
    session.expire_all()
    ranking = (
        session.query(SeasonRanking)
        .filter(
            SeasonRanking.season_id == season.id,
            SeasonRanking.user_id == "u1",
        )
        .one()
    )
    assert ranking.final_points == 125


def test_settled_season_config_is_frozen(lifecycle_db):
    session, config = lifecycle_db
    season = _sync_and_grant(session)
    with patch(
        "plugins.mailbox.service.MailService.send_mail", return_value=101
    ):
        season_service.settle_season("s1", now=END)
    original_start = season.start_time
    original_metadata = season.metadata_json

    config["seasons"][0]["starts_at"] = "2031-01-01T00:00:00+08:00"
    config["seasons"][0]["ends_at"] = "2031-01-29T00:00:00+08:00"
    season_service.sync_seasons_config(now=END + 60)
    session.refresh(season)

    assert season.start_time == original_start
    assert season.metadata_json == original_metadata


def test_settlement_preview_is_read_only(lifecycle_db):
    session, _ = lifecycle_db
    season = _sync_and_grant(session)
    before = session.query(SeasonReward).count()
    preview = season_service.settlement_preview("s1")
    after = session.query(SeasonReward).count()
    assert preview == {
        "season_key": "s1",
        "status": "planned",
        "rankings": 1,
        "participants": 1,
        "reward_mails": 1,
        "pending_mails": 0,
    }
    assert before == after == 0
    assert season.settled_at == 0


def test_failed_mail_stays_pending_and_can_be_retried(lifecycle_db):
    session, _ = lifecycle_db
    season = _sync_and_grant(session)
    with patch(
        "plugins.mailbox.service.MailService.send_mail",
        side_effect=RuntimeError("mail db unavailable"),
    ):
        season_service.settle_season("s1", now=END)

    session.expire_all()
    reward = (
        session.query(SeasonReward)
        .filter(
            SeasonReward.season_id == season.id,
            SeasonReward.user_id == "u1",
        )
        .one()
    )
    assert reward.mail_id == 0

    with patch(
        "plugins.mailbox.service.MailService.send_mail", return_value=321
    ) as send:
        assert season_service.dispatch_pending_season_rewards() == 1
    session.expire_all()
    assert send.call_count == 1
    assert (
        send.call_args.kwargs["external_key"]
        == f"season_reward:{season.id}:u1"
    )
    assert reward.mail_id == 321


def test_early_settlement_keeps_one_stable_offseason_scope(lifecycle_db):
    session, _ = lifecycle_db
    season = season_service.sync_seasons_config()[0]
    session.refresh(season)
    season.settled_at = START + 60
    season.status = "settled"
    session.commit()
    during_window = season_service.get_offseason_scope_id(now=START + 60)
    after_window = season_service.get_offseason_scope_id(now=END)
    assert during_window == after_window == "s1_to_after-last-season"


@pytest.mark.parametrize(
    "seasons",
    [
        [
            _season_entry(
                starts_at="2030-01-29T00:00:00+08:00",
                ends_at="2030-01-01T00:00:00+08:00",
            )
        ],
        [
            _season_entry(),
            _season_entry(
                key="s2",
                number=2,
                starts_at="2030-01-15T00:00:00+08:00",
                ends_at="2030-02-12T00:00:00+08:00",
            ),
        ],
    ],
    ids=["end-before-start", "overlap"],
)
def test_invalid_timeline_is_rejected(lifecycle_db, seasons):
    _, config = lifecycle_db
    config["seasons"] = seasons
    with pytest.raises(ValueError):
        season_service.sync_seasons_config()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda entry: entry["reward_tiers"][0]["items"][0].update(quantity=-1),
        lambda entry: entry["reward_tiers"].append(
            {
                "tier_key": "overlap",
                "from_rank": 1,
                "to_rank": 10,
                "title": "重叠",
                "items": [{"item_id": "reward_token", "quantity": 1}],
            }
        ),
        lambda entry: entry.update(snapshot_interval_minutes=-5),
    ],
    ids=["negative-reward", "overlapping-tier", "negative-snapshot-interval"],
)
def test_invalid_rules_are_rejected(lifecycle_db, mutate):
    _, config = lifecycle_db
    mutate(config["seasons"][0])
    with pytest.raises(ValueError):
        season_service.sync_seasons_config()


def test_normal_due_settlement_remains_idempotent(lifecycle_db):
    session, _ = lifecycle_db
    season = _sync_and_grant(session)
    with patch(
        "plugins.mailbox.service.MailService.send_mail", return_value=123
    ) as send:
        assert season_service.settle_due_seasons(now=END) == 1
        assert season_service.settle_due_seasons(now=END + 60) == 0
    assert send.call_count == 1
    assert (
        session.query(SeasonReward)
        .filter(SeasonReward.season_id == season.id)
        .count()
        == 1
    )
