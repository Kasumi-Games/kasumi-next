from __future__ import annotations

import pytest


@pytest.fixture
def hold_db(sqlite_session, monkeypatch):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import database

    session = sqlite_session(database, models.Base)
    session.add(
        models.Item(
            item_id=models.SEASON_POINT_ITEM_ID,
            category="currency",
            name="赛季积分",
            stackable=True,
            visible=True,
            sort_order=0,
            metadata_json="{}",
        )
    )
    session.add(
        models.CurrencyItem(
            item_id=models.SEASON_POINT_ITEM_ID,
            currency_kind="seasonal",
            unit_name="Pt",
            rankable=True,
            reset_policy="season",
        )
    )
    session.add(
        models.Season(
            id=1,
            season_key="s1",
            season_number=1,
            name="S1",
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
    session.commit()
    monkeypatch.setattr(
        service,
        "get_point_scope",
        lambda now=None: (models.SEASON_SCOPE_TYPE, "1", None),
    )
    monkeypatch.setattr(service, "get_season_starting_points", lambda scope_id: 0)
    monkeypatch.setattr(service, "get_offseason_starting_points", lambda: 0)
    service.grant_item(
        "u1",
        models.SEASON_POINT_ITEM_ID,
        500,
        "seed",
        scope=(models.SEASON_SCOPE_TYPE, "1"),
    )
    return session


def test_point_hold_reserve_increase_settle_and_retry(hold_db):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import point_hold_service as holds

    result = holds.reserve_points("u1", 100, "blackjack:g1", "blackjack")
    assert result.amount == 100
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 400

    replay = holds.reserve_points("u1", 100, "blackjack:g1", "blackjack")
    assert replay.skipped is True
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 400

    holds.increase_point_hold(
        "blackjack:g1", "u1", 100, operation_key="blackjack:g1:split", now=150
    )
    duplicate = holds.increase_point_hold(
        "blackjack:g1", "u1", 100, operation_key="blackjack:g1:split", now=150
    )
    assert duplicate.skipped is True
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 300

    settled = holds.settle_point_hold(
        "blackjack:g1", 400, operation_key="blackjack:g1:settle", now=150
    )
    assert settled.status == holds.HOLD_SETTLED
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 700
    assert holds.settle_point_hold(
        "blackjack:g1", 400, operation_key="blackjack:g1:settle", now=150
    ).skipped


def test_point_hold_capture_and_refund_use_original_scope(hold_db):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import point_hold_service as holds

    holds.reserve_points("u1", 100, "red_envelope:e1", "red_envelope")
    holds.capture_point_hold(
        "red_envelope:e1",
        "u2",
        30,
        operation_key="red_envelope:e1:claim:u2",
        now=150,
    )
    refund = holds.refund_point_hold(
        "red_envelope:e1", operation_key="red_envelope:e1:refund"
    )

    assert refund.amount == 70
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 470
    assert service.get_quantity(
        "u2", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 30
    assert holds.refund_point_hold(
        "red_envelope:e1", operation_key="red_envelope:e1:refund"
    ).skipped


def test_operation_key_replay_rejects_different_hold_or_payload(hold_db):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import point_hold_service as holds

    holds.reserve_points("u1", 100, "red_envelope:e1", "red_envelope")
    holds.reserve_points("u1", 100, "red_envelope:e2", "red_envelope")
    holds.capture_point_hold(
        "red_envelope:e1",
        "u2",
        20,
        operation_key="red_envelope:shared-claim-key",
        now=150,
    )

    with pytest.raises(holds.PointHoldError, match="different data"):
        holds.capture_point_hold(
            "red_envelope:e2",
            "u3",
            30,
            operation_key="red_envelope:shared-claim-key",
            now=150,
        )

    assert service.get_quantity(
        "u3", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 0
    assert holds.get_point_hold("red_envelope:e2").remaining_amount == 100


def test_point_hold_rejects_settlement_after_scope_closes(hold_db):
    from plugins.inventory import models
    from plugins.inventory import point_hold_service as holds

    holds.reserve_points("u1", 100, "mines:g1", "mines")
    with pytest.raises(holds.PointHoldScopeClosed):
        holds.settle_point_hold(
            "mines:g1", 200, operation_key="mines:g1:settle", now=4_000_000_000
        )

    closed = holds.close_point_scope(
        models.SEASON_SCOPE_TYPE, "1", cutoff=4_000_000_000
    )
    assert closed == 1
    assert holds.get_point_hold("mines:g1").status == holds.HOLD_REFUNDED


def test_funded_hold_backfill_does_not_debit_wallet(hold_db):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import point_hold_service as holds

    holds.create_funded_point_hold(
        "u1",
        40,
        "red_envelope:legacy",
        "red_envelope",
        scope=(models.SEASON_SCOPE_TYPE, "1"),
    )
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 500
    assert holds.refund_point_hold("red_envelope:legacy").amount == 40
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 540


def test_game_scope_close_refunds_bets_without_recording_results(
    hold_db, sqlite_session
):
    from plugins.mines import database as mines_database
    from plugins.blackjack import database as blackjack_database
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import point_hold_service as holds
    from plugins.mines.models import Base as MinesBase
    from plugins.mines.models import MinesGame
    from plugins.mines.session import GameManager as MinesManager
    from plugins.blackjack.models import Base as BlackjackBase
    from plugins.blackjack.models import Hand
    from plugins.blackjack.session import GameManager as BlackjackManager

    sqlite_session(blackjack_database, BlackjackBase)
    mines_db = sqlite_session(mines_database, MinesBase)

    blackjack = BlackjackManager()
    assert blackjack.start_game("u1", 100)
    blackjack_session = blackjack.create_session("u1", "c", 100, Hand(), Hand())
    assert blackjack.increase_bet("u1", 100, "split")

    mines = MinesManager()
    assert mines.start_game("u1", 50)
    mines_session = mines.create_session("u1", "c", 50, 5)

    blackjack.close_scope(models.SEASON_SCOPE_TYPE, "1", 4_000_000_000)
    mines.close_scope(models.SEASON_SCOPE_TYPE, "1", 4_000_000_000)

    with pytest.raises(holds.PointHoldScopeClosed):
        blackjack.ensure_active(blackjack_session)
    with pytest.raises(holds.PointHoldScopeClosed):
        mines.ensure_active(mines_session)
    assert mines_db.query(MinesGame).count() == 0
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 500


def test_startup_refunds_abandoned_game_hold(hold_db):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import point_hold_service as holds

    holds.reserve_points("u1", 75, "mines:abandoned", "mines")
    assert holds.refund_abandoned_game_holds(("mines",)) == 1
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 500


def test_vits_charge_is_refunded_to_original_scope_when_season_closes(hold_db):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import database
    from plugins.vits import _reserve_vits_charge
    from plugins.vits import _settle_vits_charge

    hold_key = _reserve_vits_charge("u1", 100)
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 400

    season = database.get_session().query(models.Season).filter_by(id=1).one()
    season.status = "ended"
    database.get_session().commit()

    assert _settle_vits_charge(hold_key) is False
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 500


def test_vits_charge_is_consumed_after_successful_delivery(hold_db):
    from plugins.inventory import models
    from plugins.inventory import service
    from plugins.inventory import point_hold_service as holds
    from plugins.vits import _reserve_vits_charge
    from plugins.vits import _settle_vits_charge

    hold_key = _reserve_vits_charge("u1", 100)

    assert _settle_vits_charge(hold_key) is True
    assert holds.get_point_hold(hold_key).status == holds.HOLD_SETTLED
    assert service.get_quantity(
        "u1", models.SEASON_POINT_ITEM_ID, (models.SEASON_SCOPE_TYPE, "1")
    ) == 400
