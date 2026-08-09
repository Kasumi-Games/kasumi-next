"""Rule, persistence and themed-surface coverage for the tour plugin."""

from __future__ import annotations

import importlib

import pytest


def _load_plugin() -> None:
    # ``plugins.tour`` calls ``require("daily_task")`` while importing.
    importlib.import_module("plugins.daily_task")
    importlib.import_module("plugins.tour")


def _card(card_type, value: int, name: str = "测试牌"):
    from plugins.tour.models import TourCard

    return TourCard(card_type, value, name)


def test_seeded_deck_is_deterministic_and_has_the_expected_counts() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession

    first = TourSession("u1", DIFFICULTIES["初级"], seed=12345)
    second = TourSession("u1", DIFFICULTIES["初级"], seed=12345)

    assert first.hand == second.hand
    assert first.deck == second.deck
    assert len(first.hand) == 4
    assert len(first.deck) == 40
    assert sum(card.type is CardType.TOUR for card in first.hand + first.deck) == 26
    assert sum(card.type is CardType.INSTRUMENT for card in first.hand + first.deck) == 9
    assert sum(card.type is CardType.STAMINA for card in first.hand + first.deck) == 9


def test_command_aliases_and_action_parser_match_the_public_contract() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.rules import parse_action
    from plugins.tour.rules import difficulty_for_command

    assert difficulty_for_command("/巡演", "").key == "初级"
    assert difficulty_for_command("/tour", "高级").key == "高级"
    assert difficulty_for_command("/xyex", "").key == "超级"
    assert difficulty_for_command("/中级巡演", "").key == "中级"
    assert difficulty_for_command("/巡演", "未知") is None
    assert parse_action("  012340  ").digits == "012340"
    assert parse_action("0123407").kind == "invalid"
    assert parse_action("5").kind == "rest"
    assert parse_action("6").kind == "invalid"
    assert parse_action("q").kind == "quit"
    assert set(DIFFICULTIES) == {"初级", "中级", "高级", "超级"}


def test_food_is_consumed_but_only_the_first_food_restores_each_day() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession

    session = TourSession("u1", DIFFICULTIES["中级"], seed=1)
    session.stamina = 10
    session.hand = [
        _card(CardType.STAMINA, 2, "第一份食物"),
        _card(CardType.STAMINA, 9, "第二份食物"),
        None,
        None,
    ]

    result = session.apply("12")

    assert [action.amount for action in result.performed] == [2, 0]
    assert session.stamina == 12
    assert session.stamina_used_today is True
    assert session.hand[:2] == [None, None]
    assert session.action_count == 2
    assert session.selection_count == 2


def test_zero_does_not_count_and_super_zero_discards() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession

    normal = TourSession("u1", DIFFICULTIES["高级"], seed=2)
    normal.hand = [_card(CardType.INSTRUMENT, 7, "乐器"), None, None, None]
    normal.apply("1")
    before = (normal.selection_count, normal.action_count)
    toggle = normal.apply("0")
    assert toggle.changed is True
    assert (normal.selection_count, normal.action_count) == before
    assert normal.instrument_equipped is False

    super_session = TourSession("u2", DIFFICULTIES["超级"], seed=2)
    super_session.hand = [_card(CardType.INSTRUMENT, 7, "乐器"), None, None, None]
    super_session.apply("1")
    before = (super_session.selection_count, super_session.action_count)
    super_session.apply("0")
    assert super_session.instrument is None
    assert (super_session.selection_count, super_session.action_count) == before


def test_unequipped_instrument_stays_unequipped_across_day_and_rest() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession

    session = TourSession("u1", DIFFICULTIES["高级"], seed=21)
    session.instrument = _card(CardType.INSTRUMENT, 7, "乐器")
    session.instrument_equipped = False
    session.hand = [
        _card(CardType.STAMINA, 2, "一"),
        _card(CardType.STAMINA, 2, "二"),
        _card(CardType.STAMINA, 2, "三"),
        None,
    ]

    session.apply("123")

    assert session.day == 2
    assert session.instrument_equipped is False

    resting = TourSession("u2", DIFFICULTIES["高级"], seed=22)
    resting.instrument = _card(CardType.INSTRUMENT, 7, "乐器")
    resting.instrument_equipped = False
    resting.apply("5")

    assert resting.instrument_equipped is False


def test_low_compatibility_message_matches_the_difficulty_rule() -> None:
    _load_plugin()
    from plugins.tour.messages import Messages

    assert "先卸下当前乐器" in Messages.invalid_reason("low_compatibility")
    assert "先丢弃当前乐器" in Messages.invalid_reason(
        "low_compatibility", can_discard=True
    )


def test_continuous_input_stops_at_day_boundary_and_preserves_suffix() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession

    session = TourSession("u1", DIFFICULTIES["初级"], seed=3)
    session.hand = [
        _card(CardType.STAMINA, 2, "一"),
        _card(CardType.STAMINA, 3, "二"),
        _card(CardType.STAMINA, 4, "三"),
        _card(CardType.TOUR, 2, "不应执行"),
    ]

    result = session.apply("1234")

    assert result.changed is True
    assert len(result.performed) == 3
    assert result.ignored_suffix == "4"
    assert session.day == 2
    assert session.selection_count == 0
    assert session.tour_played_count == 0


def test_invalid_middle_step_keeps_previous_actions_and_reports_position() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession

    session = TourSession("u1", DIFFICULTIES["初级"], seed=4)
    session.hand = [_card(CardType.STAMINA, 2, "食物"), None, None, None]

    result = session.apply("12")

    assert len(result.performed) == 1
    assert result.invalid_reason == "empty_slot"
    assert result.invalid_step == 2
    assert result.ignored_suffix == ""
    assert session.action_count == 1
    assert session.hand[0] is None


def test_rest_restrictions_and_strict_instrument_compatibility() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession

    rest = TourSession("u1", DIFFICULTIES["初级"], seed=5)
    assert rest.apply("5").changed is True
    assert rest.day == 2
    assert rest.apply("5").invalid_reason == "rest_consecutive"
    rest.hand[0] = _card(CardType.STAMINA, 2, "食物")
    rest.apply("1")
    assert rest.apply("5").invalid_reason == "rest_after_action"

    instrument = TourSession("u2", DIFFICULTIES["中级"], seed=6)
    instrument.stamina = 30
    instrument.hand = [
        _card(CardType.INSTRUMENT, 5, "底力五"),
        _card(CardType.TOUR, 8, "难度八"),
        None,
        None,
    ]
    equip = instrument.apply("1")
    play = instrument.apply("2")
    assert equip.performed[0].kind == "instrument"
    assert play.performed[0].amount == 3
    instrument.hand[0] = _card(CardType.TOUR, 8, "重复难度")
    blocked = instrument.apply("1")
    assert blocked.invalid_reason == "low_compatibility"


def test_stamina_zero_has_priority_over_the_26th_clear() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.models import TourOutcome
    from plugins.tour.session import TourSession

    loss = TourSession("u1", DIFFICULTIES["初级"], seed=7)
    loss.stamina = 1
    loss.hand = [_card(CardType.TOUR, 2, "最后一场"), None, None, None]
    loss_result = loss.apply("1")
    assert loss_result.outcome is TourOutcome.STAMINA
    assert loss.tour_played_count == 1

    win = TourSession("u2", DIFFICULTIES["初级"], seed=8)
    win.tour_played_count = 25
    win.stamina = 10
    win.hand = [_card(CardType.TOUR, 2, "第26场"), None, None, None]
    win_result = win.apply("1")
    assert win_result.outcome is TourOutcome.WIN
    assert win.tour_played_count == 26
    assert win.stamina > 0


def test_manager_rejects_duplicate_user_sessions() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.session import TourGameManager

    manager = TourGameManager()
    first = manager.start("u1", DIFFICULTIES["初级"], seed=10)
    assert first is not None
    assert manager.start("u1", DIFFICULTIES["超级"], seed=11) is None
    assert manager.get("u1") is first
    assert manager.end("u1") is first
    assert manager.get("u1") is None


def test_terminal_records_are_idempotent(sqlite_session) -> None:
    _load_plugin()
    from plugins.tour import database
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import Base
    from plugins.tour.models import TourOutcome
    from plugins.tour.service import record_result
    from plugins.tour.session import TourSession

    db = sqlite_session(database, Base)
    session = TourSession("u1", DIFFICULTIES["高级"], seed=12, run_id="run-1")
    session.mark_terminal(TourOutcome.WIN)

    first = record_result(session, TourOutcome.WIN, 24)
    second = record_result(session, TourOutcome.WIN, 24)

    assert first.id == second.id
    assert db.query(type(first)).count() == 1
    assert first.run_id == "run-1"
    assert first.reward_pt == 24
    assert first.outcome == "win"


@pytest.mark.asyncio
async def test_settlement_rewards_only_wins_and_completes_the_daily_task(
    sqlite_session, monkeypatch
) -> None:
    _load_plugin()
    import plugins.tour as tour
    from plugins.tour import database
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import Base
    from plugins.tour.models import TourOutcome
    from plugins.tour.models import TourGameRecord
    from plugins.tour.session import TourSession

    db = sqlite_session(database, Base)
    added: list[tuple] = []
    xp_added: list[tuple] = []
    task_events: list[tuple] = []

    def add(user_id, amount, description, *, idempotency_key=None):
        added.append((user_id, amount, description, idempotency_key))

    async def add_xp(user_id, amount):
        xp_added.append((user_id, amount))

    async def check_progress(user_id, event_type, data):
        task_events.append((user_id, event_type, data))
        return "done"

    monkeypatch.setattr(tour.monetary, "add", add)
    monkeypatch.setattr(tour.monetary, "add_xp", add_xp)
    monkeypatch.setattr(tour.monetary, "get_level", lambda user_id: 1)
    monkeypatch.setattr(tour.monetary, "get", lambda user_id: 100)
    monkeypatch.setattr(tour, "get_today_birthday", lambda: ["香澄"])
    monkeypatch.setattr(tour, "check_progress", check_progress)
    monkeypatch.setattr(
        tour,
        "get_today_task",
        lambda user_id: type("Task", (), {"name": "巡演开场", "reward": 80})(),
    )

    win = TourSession("u1", DIFFICULTIES["高级"], seed=14, run_id="win")
    win.mark_terminal(TourOutcome.WIN)
    result = await tour._settle(win, TourOutcome.WIN)
    duplicate = await tour._settle(win, TourOutcome.WIN)

    loss = TourSession("u1", DIFFICULTIES["高级"], seed=15, run_id="loss")
    loss.mark_terminal(TourOutcome.STAMINA)
    failed = await tour._settle(loss, TourOutcome.STAMINA)

    assert result.reward_pt == 48
    assert result.base_reward_pt == 24
    assert result.birthday_names == ("香澄",)
    assert result.multiplier == 2
    assert result.task_name == "巡演开场"
    assert result.task_reward == 80
    assert duplicate.task_name is None
    assert failed.reward_pt == 0
    assert added == [("u1", 48, "tour", "tour:win:pt")]
    assert xp_added == [("u1", 48)]
    assert task_events == [("u1", "tour_clear", {})]
    assert db.query(TourGameRecord).count() == 2
    assert db.query(TourGameRecord).filter_by(outcome="stamina").one().reward_pt == 0


def test_tour_surfaces_render_without_identity_in_every_theme() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.render.kits import KITS
    from plugins.tour.models import TourOutcome
    from plugins.tour.render import render_help
    from plugins.tour.render import render_state
    from plugins.tour.render import render_result
    from plugins.tour.session import TourSession
    from plugins.tour.render.state import TourRenderData
    from plugins.tour.render.result import TourResultData

    session = TourSession("u1", DIFFICULTIES["初级"], seed=13)
    snapshot = session.snapshot()
    result_data = TourResultData(
        snapshot=snapshot,
        outcome=TourOutcome.WIN,
        reward_pt=24,
        balance=100,
        elapsed_seconds=42,
        base_reward_pt=12,
        birthday_names=("香澄",),
        multiplier=2,
        task_name="巡演开场",
        task_reward=80,
    )
    for factory in KITS.values():
        kit = factory()
        state = render_state(TourRenderData(snapshot), kit)
        result = render_result(result_data, kit)
        help_image = render_help(kit)
        assert state.width > 0 and state.height > 0
        assert result.width > 0 and result.height > 0
        assert help_image.width > 0 and help_image.height > 0


def test_state_card_handles_long_instrument_names_in_every_theme() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.render.kits import KITS
    from plugins.tour.models import CardType
    from plugins.tour.models import TourCard
    from plugins.tour.render import render_state
    from plugins.tour.session import TourSession
    from plugins.tour.render.state import TourRenderData

    session = TourSession("u1", DIFFICULTIES["超级"], seed=16)
    session.instrument = TourCard(
        CardType.INSTRUMENT,
        5,
        "这是一个特别特别特别长的乐器名称测试",
    )
    session.instrument_equipped = True
    session.last_performance = {5: 12}
    snapshot = session.snapshot()

    for factory in KITS.values():
        image = render_state(TourRenderData(snapshot), factory())
        assert image.width > 0 and image.height > 0


def test_tour_help_omits_legacy_compatibility_notes_and_removed_action() -> None:
    _load_plugin()
    from plugins.help import plugin_data

    usage = plugin_data["巡演"]["usage"]
    assert "6" not in usage
    assert all("兼容" not in meaning for meaning in usage.values())
