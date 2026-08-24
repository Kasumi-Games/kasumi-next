from __future__ import annotations

import copy
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _seed_currency(session, models, item_id: str, name: str, kind: str = "permanent"):
    session.add(
        models.Item(
            item_id=item_id,
            category="currency",
            name=name,
            stackable=True,
            visible=True,
            sort_order=0,
            metadata_json="{}",
        )
    )
    session.add(
        models.CurrencyItem(
            item_id=item_id,
            currency_kind=kind,
            unit_name="",
            rankable=False,
            reset_policy="none",
        )
    )
    session.commit()


@pytest.fixture
def economy_db(sqlite_session, monkeypatch):
    from plugins.monetary import database as monetary_database
    from plugins.monetary import transaction_service
    from plugins.inventory import models as inventory_models
    from plugins.inventory import database as inventory_database
    from plugins.monetary.models import Base as MonetaryBase
    from plugins.monetary.models import TransactionBase
    from plugins.inventory.models import Base as InventoryBase

    monetary_session = sqlite_session(monetary_database, MonetaryBase)
    transaction_engine = create_engine("sqlite:///:memory:")
    TransactionBase.metadata.create_all(transaction_engine)
    transaction_session = sessionmaker(bind=transaction_engine)()
    monkeypatch.setattr(
        monetary_database, "transaction_session", transaction_session, raising=False
    )
    monkeypatch.setattr(transaction_service, "_transaction_manager", None)
    inventory_session = sqlite_session(inventory_database, InventoryBase)
    _seed_currency(
        inventory_session,
        inventory_models,
        inventory_models.SEASON_POINT_ITEM_ID,
        "赛季积分",
        "seasonal",
    )
    _seed_currency(
        inventory_session,
        inventory_models,
        inventory_models.STAR_STICKER_ITEM_ID,
        "星星贴纸",
    )
    _seed_currency(
        inventory_session,
        inventory_models,
        inventory_models.BONSAI_ITEM_ID,
        "盆栽",
    )
    inventory_session.add(
        inventory_models.Season(
            id=1,
            season_key="test-season",
            season_number=1,
            name="测试赛季",
            start_time=1,
            end_time=4_000_000_000,
            timezone="UTC+8",
            status="open",
            metadata_json='{"starting_points": 0}',
            config_hash="test",
            opened_at=1,
            settled_at=0,
        )
    )
    inventory_session.commit()
    monkeypatch.setattr(
        "plugins.inventory.service.get_point_scope",
        lambda now=None: (inventory_models.SEASON_SCOPE_TYPE, "1", None),
    )
    return monetary_session, inventory_session, transaction_session


def test_monetary_balance_transfer_levels_and_stickers(economy_db):
    from plugins import monetary
    from plugins.monetary.models import Transaction
    from plugins.monetary.models import StickerTransaction

    monetary.add("u1", 100, "seed")
    monetary.transfer("u1", "u2", 40, "gift")
    monetary.increase_level("u1", 2)
    monetary.add_star_stickers("u1", 120, "bonus")

    assert monetary.get("u1") == 60
    assert monetary.get("u2") == 40
    assert monetary.get_level("u1") == 3
    assert monetary.get_star_stickers("u1") == 120
    assert economy_db[2].query(Transaction).count() >= 4
    assert economy_db[2].query(StickerTransaction).one().balance_after == 120


@pytest.mark.asyncio
async def test_daily_task_completes_matching_config(sqlite_session, monkeypatch):
    from plugins.daily_task import database
    from plugins.daily_task.models import Base
    from plugins.daily_task.service import DailyTaskService

    sqlite_session(database, Base)
    service = DailyTaskService()
    service._task_configs = {
        "mines": {
            "id": "mines",
            "name": "探险",
            "description": "play",
            "reward": 12,
            "type": "game",
            "conditions": [{"field": "plugin", "op": "==", "value": "mines"}],
        }
    }
    monkeypatch.setattr("plugins.daily_task.service.random.choice", lambda rows: rows[0])
    add_stickers = Mock()
    monkeypatch.setattr("plugins.daily_task.service.monetary.add_star_stickers", add_stickers)

    task = service.ensure_daily_task("u1")
    assert task.task_id == "mines"
    assert await service.check_progress("u1", "message", {"plugin": "mines"}) is None

    message = await service.check_progress("u1", "game", {"plugin": "mines"})

    assert "每日任务【探险】完成" in message
    add_stickers.assert_called_once_with("u1", 12, "daily_task_mines")
    assert service.get_today_task("u1").is_completed is True


def test_daily_task_any_condition_supports_tour_progress() -> None:
    from plugins.daily_task.service import DailyTaskService

    service = DailyTaskService()
    config = {
        "type": "tour_progress",
        "condition_mode": "any",
        "conditions": [
            {"field": "tours_completed", "op": ">=", "value": 15},
            {"field": "day", "op": ">=", "value": 10},
        ],
    }

    assert not service._match(
        config, "tour_progress", {"tours_completed": 14, "day": 9}
    )
    assert service._match(
        config, "tour_progress", {"tours_completed": 15, "day": 3}
    )
    assert service._match(
        config, "tour_progress", {"tours_completed": 4, "day": 10}
    )


def test_mailbox_send_read_cleanup_and_scheduled_processing(sqlite_session, monkeypatch):
    from plugins.mailbox import database
    from plugins.mailbox.models import Base
    from plugins.mailbox.models import Mail
    from plugins.mailbox.service import MailService
    from plugins.mailbox.scheduled_service import ScheduledMailService

    session = sqlite_session(database, Base)
    mail_service = MailService()
    mail_id = mail_service.send_mail("u1", "title", "content", star_stickers=3)

    mails = mail_service.get_user_mails("u1")
    assert [mail.id for mail in mails] == [mail_id]
    assert mails[0].attachments[0].item_id == "star_sticker"

    read = mail_service.read_mail("u1", mail_id)
    assert read.is_read is True

    session.query(Mail).filter(Mail.id == mail_id).one().created_at = 1
    session.commit()
    assert mail_service.cleanup_expired_mails() == 1

    scheduled = ScheduledMailService()
    sent = []
    monkeypatch.setattr(
        scheduled.mail_service,
        "send_mail",
        lambda **kwargs: sent.append(kwargs) or 99,
    )
    scheduled.create_scheduled_mail(
        recipients="u1,u2",
        title="scheduled",
        content="payload",
        scheduled_time=1,
        name="daily",
    )

    assert scheduled.process_due_mails() == 1
    assert [row["recipient_id"] for row in sent] == ["u1", "u2"]
    assert scheduled.get_pending_count() == 0


def test_red_envelope_claims_expiry_and_completion(
    sqlite_session, monkeypatch, economy_db
):
    from plugins import monetary
    from plugins.red_envelope import service
    from plugins.red_envelope import database
    from plugins.red_envelope.models import Base

    sqlite_session(database, Base)
    monkeypatch.setattr(service.random, "randint", lambda low, high: low)
    monetary.add("creator", 20, "seed")

    envelope = service.create_envelope("creator", "channel", "hello", 10, 2)
    assert envelope.channel_index == 1

    first_status, first_amount, completion = service.claim_envelope("u1", "channel", 1)
    assert (first_status, first_amount, completion) == ("success", 1, None)
    assert service.claim_envelope("u1", "channel", 1)[0] == "already"

    second_status, second_amount, completion = service.claim_envelope("u2", "channel", 1)
    assert (second_status, second_amount) == ("success", 9)
    assert completion.lucky_king_id == "u2"
    assert monetary.get("u1") == 1
    assert monetary.get("u2") == 9

    expired = service.create_envelope("creator", "channel", "old", 5, 1)
    expired.expires_at = 1
    database.session.commit()
    assert service.expire_overdue_envelopes() == 1
    assert monetary.get("creator") == 10


def test_red_envelope_retries_an_uncredited_claim(
    sqlite_session, monkeypatch, economy_db
):
    from plugins import monetary
    from plugins.red_envelope import service
    from plugins.red_envelope import database
    from plugins.red_envelope.models import Base
    from plugins.red_envelope.models import ClaimRecord

    session = sqlite_session(database, Base)
    attempts = 0

    original_capture = service.point_holds.capture_point_hold

    def flaky_credit(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("inventory unavailable")
        return original_capture(*args, **kwargs)

    monkeypatch.setattr(service.point_holds, "capture_point_hold", flaky_credit)
    monkeypatch.setattr(service.random, "randint", lambda low, high: low)
    monetary.add("creator", 10, "seed")
    envelope = service.create_envelope("creator", "channel", "hello", 10, 2)

    assert service.claim_envelope("u1", "channel", 1)[0] == "error"
    claim = session.query(ClaimRecord).one()
    assert claim.credited_at == 0
    assert (envelope.remaining_amount, envelope.remaining_count) == (9, 1)

    status, amount, completion = service.claim_envelope("u1", "channel", 1)
    assert (status, amount, completion) == ("success", 1, None)
    session.refresh(claim)
    assert claim.credited_at > 0
    assert attempts == 2
    assert service.claim_envelope("u1", "channel", 1)[0] == "already"


def test_red_envelope_scope_close_honors_pending_claim_then_refunds(
    sqlite_session, monkeypatch, economy_db
):
    import time

    from plugins import monetary
    from plugins.inventory import point_hold_service as holds
    from plugins.inventory.models import SEASON_SCOPE_TYPE
    from plugins.red_envelope import database
    from plugins.red_envelope import service
    from plugins.red_envelope.models import Base

    sqlite_session(database, Base)
    monetary.add("creator", 100, "seed")
    monkeypatch.setattr(service.random, "randint", lambda low, high: low)
    envelope = service.create_envelope("creator", "channel", "hello", 50, 2)

    original_capture = service.point_holds.capture_point_hold
    attempts = 0

    def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("inventory unavailable")
        return original_capture(*args, **kwargs)

    monkeypatch.setattr(service.point_holds, "capture_point_hold", fail_once)
    assert service.claim_envelope("u1", "channel", 1)[0] == "error"

    service.close_scope_envelopes(
        SEASON_SCOPE_TYPE, "1", cutoff=int(time.time()) + 1
    )
    service.close_scope_envelopes(
        SEASON_SCOPE_TYPE, "1", cutoff=int(time.time()) + 1
    )

    assert monetary.get("creator") == 99
    assert monetary.get("u1") == 1
    assert envelope.is_expired is True
    assert envelope.closed_reason == "season_end"
    assert holds.get_point_hold(envelope.hold_key).status == holds.HOLD_REFUNDED


def test_red_envelope_scope_close_honors_claim_at_exact_cutoff(
    sqlite_session, monkeypatch, economy_db
):
    from plugins import monetary
    from plugins.inventory import point_hold_service as holds
    from plugins.inventory.models import SEASON_SCOPE_TYPE
    from plugins.red_envelope import database
    from plugins.red_envelope import service
    from plugins.red_envelope.models import Base
    from plugins.red_envelope.models import ClaimRecord

    session = sqlite_session(database, Base)
    monetary.add("creator", 100, "seed")
    monkeypatch.setattr(service.random, "randint", lambda low, high: low)
    envelope = service.create_envelope("creator", "channel", "hello", 50, 2)

    original_capture = service.point_holds.capture_point_hold
    attempts = 0

    def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("inventory unavailable")
        return original_capture(*args, **kwargs)

    monkeypatch.setattr(service.point_holds, "capture_point_hold", fail_once)
    assert service.claim_envelope("u1", "channel", 1)[0] == "error"
    claim = session.query(ClaimRecord).one()

    service.close_scope_envelopes(
        SEASON_SCOPE_TYPE, "1", cutoff=claim.claimed_at
    )

    session.refresh(claim)
    assert claim.credited_at > 0
    assert monetary.get("creator") == 99
    assert monetary.get("u1") == 1
    assert envelope.is_expired is True
    assert holds.get_point_hold(envelope.hold_key).status == holds.HOLD_REFUNDED


def test_red_envelope_reconciliation_refunds_unreferenced_open_hold(
    sqlite_session, economy_db
):
    from plugins import monetary
    from plugins.inventory import point_hold_service as holds
    from plugins.red_envelope import database
    from plugins.red_envelope import service
    from plugins.red_envelope.models import Base

    sqlite_session(database, Base)
    monetary.add("creator", 100, "seed")
    active = service.create_envelope("creator", "channel", "active", 20, 2)
    holds.reserve_points(
        "creator",
        40,
        "red_envelope:crashed-create",
        "red_envelope",
    )

    assert monetary.get("creator") == 40
    assert service.refund_orphaned_envelope_holds() == 1
    assert monetary.get("creator") == 80
    assert holds.get_point_hold(active.hold_key).status == holds.HOLD_OPEN
    assert (
        holds.get_point_hold("red_envelope:crashed-create").status
        == holds.HOLD_REFUNDED
    )


def test_red_envelope_close_finishes_business_state_after_hold_was_refunded(
    sqlite_session, economy_db
):
    from plugins import monetary
    from plugins.inventory import point_hold_service as holds
    from plugins.inventory.models import SEASON_SCOPE_TYPE
    from plugins.red_envelope import database
    from plugins.red_envelope import service
    from plugins.red_envelope.models import Base

    session = sqlite_session(database, Base)
    monetary.add("creator", 100, "seed")
    envelope = service.create_envelope("creator", "channel", "hello", 40, 2)

    # Simulate a process disappearing after the inventory refund committed but
    # before the red-envelope database saved its closed state.
    holds.refund_point_hold(
        envelope.hold_key,
        operation_key=f"{envelope.hold_key}:close:season_end",
    )
    assert envelope.is_expired is False

    service.close_scope_envelopes(SEASON_SCOPE_TYPE, "1", cutoff=envelope.created_at)

    session.refresh(envelope)
    assert envelope.is_expired is True
    assert envelope.remaining_amount == 0
    assert envelope.remaining_count == 0
    assert envelope.closed_reason == "season_end"


def test_legacy_active_envelope_backfills_funded_hold_without_second_debit(
    sqlite_session, monkeypatch, economy_db
):
    import time

    from plugins import monetary
    from plugins.inventory.models import SEASON_SCOPE_TYPE
    from plugins.red_envelope import database
    from plugins.red_envelope import service
    from plugins.red_envelope.models import Base
    from plugins.red_envelope.models import ClaimRecord
    from plugins.red_envelope.models import RedEnvelope

    session = sqlite_session(database, Base)
    now = int(time.time())
    monetary.add("creator", 70, "legacy_balance_after_envelope_debit")
    envelope = RedEnvelope(
        creator_id="creator",
        channel_id="channel",
        channel_index=1,
        title="legacy",
        total_amount=30,
        remaining_amount=25,
        total_count=2,
        remaining_count=1,
        created_at=now - 10,
        expires_at=now + 100,
        is_expired=False,
        hold_key=None,
        scope_type="",
        scope_id="",
        closed_reason="",
    )
    session.add(envelope)
    session.flush()
    session.add(
        ClaimRecord(
            envelope_id=envelope.id,
            user_id="u1",
            amount=5,
            claimed_at=now - 5,
            credited_at=0,
        )
    )
    session.commit()
    monetary.add(
        "u1",
        5,
        "legacy_red_envelope_claim",
        idempotency_key=f"red_envelope_claim:{envelope.id}:u1",
    )
    monkeypatch.setattr(
        service,
        "get_point_scope_at",
        lambda timestamp: (SEASON_SCOPE_TYPE, "1", None),
    )

    assert service.reconcile_legacy_envelope_holds(now=now) == 1
    assert monetary.get("creator") == 70
    assert session.query(ClaimRecord).one().credited_at > 0
    service.close_scope_envelopes(SEASON_SCOPE_TYPE, "1", cutoff=now + 1)
    assert monetary.get("creator") == 95
    assert monetary.get("u1") == 5


def test_red_envelope_migration_marks_historical_claims_as_credited(
    tmp_path, monkeypatch
):
    import sqlite3

    from plugins.red_envelope import migration

    path = tmp_path / "red-envelope.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE red_envelopes ("
            "id INTEGER PRIMARY KEY, "
            "pending_amounts VARCHAR"
            ")"
        )
        connection.execute(
            "CREATE TABLE claim_records ("
            "id INTEGER PRIMARY KEY, "
            "envelope_id INTEGER NOT NULL, "
            "user_id VARCHAR NOT NULL, "
            "amount INTEGER NOT NULL, "
            "claimed_at INTEGER NOT NULL"
            ")"
        )
        connection.execute(
            "INSERT INTO claim_records "
            "(id, envelope_id, user_id, amount, claimed_at) "
            "VALUES (1, 2, 'u1', 3, 123)"
        )

    monkeypatch.setattr(migration.store, "get_data_file", lambda *args: path)
    migration.migrate_red_envelope_schema()

    with sqlite3.connect(path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(claim_records)").fetchall()
        }
        credited_at = connection.execute(
            "SELECT credited_at FROM claim_records WHERE id = 1"
        ).fetchone()[0]
        envelope_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(red_envelopes)"
            ).fetchall()
        }
    assert "credited_at" in columns
    assert credited_at == 123
    assert "pending_amounts" not in envelope_columns
    assert {"hold_key", "scope_type", "scope_id", "closed_reason"}.issubset(
        envelope_columns
    )


def test_inventory_profile_equipment_and_season_status(sqlite_session, monkeypatch):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import database
    from plugins.inventory import season_service

    session = sqlite_session(database, models.Base)
    _seed_currency(session, models, models.SEASON_POINT_ITEM_ID, "赛季积分", "seasonal")
    session.add(
        models.Item(
            item_id="frame",
            category="cosmetic",
            name="frame",
            stackable=False,
            visible=True,
            sort_order=0,
            metadata_json="{}",
        )
    )
    session.add(models.CosmeticItem(item_id="frame", cosmetic_type="avatar_frame", rarity=4))
    session.commit()

    service.grant_item("u1", "frame", 1, "test")
    assert service.equip_cosmetic("u1", "frame").slot == "avatar_frame"
    assert service.get_equipped("u1") == {"avatar_frame": "frame"}
    assert service.unequip_cosmetic("u1", "avatar_frame") is True
    assert (
        service.set_profile_description("u1", "hello").profile_description == "hello"
    )
    with pytest.raises(ValueError):
        service.validate_profile_description(
            "x" * (service.PROFILE_DESCRIPTION_MAX_LENGTH + 1)
        )

    season_config = {
        "seasons": [
            {
                "season_key": "s1",
                "number": 1,
                "name": "S1",
                "starts_at": "2000-01-01T00:00:00+00:00",
                "ends_at": "2100-01-01T00:00:00+00:00",
                "reward_tiers": [],
            }
        ]
    }
    monkeypatch.setattr(season_service, "load_seasons_config", lambda: copy.deepcopy(season_config))
    synced = season_service.sync_seasons_config()
    season_service.activate_due_seasons(now=2_000_000_000)
    assert synced[0].season_key == "s1"
    assert season_service.get_current_season(now=2_000_000_000).name == "S1"
