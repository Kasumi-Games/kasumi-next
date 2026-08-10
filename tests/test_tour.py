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
    assert [config.reward_pt for config in DIFFICULTIES.values()] == [20, 40, 60, 80]


def test_display_mode_argument_parser_supports_query_and_both_modes() -> None:
    _load_plugin()
    from plugins.tour.rules import parse_display_mode_request
    from plugins.tour.models import TourDisplayMode

    assert parse_display_mode_request("").kind == "none"
    assert parse_display_mode_request("模式").kind == "query"
    assert parse_display_mode_request("mode").kind == "query"
    assert parse_display_mode_request("模式 图片").mode is TourDisplayMode.IMAGE
    assert parse_display_mode_request("mode text").mode is TourDisplayMode.TEXT
    assert parse_display_mode_request("/巡演 模式 文本").mode is TourDisplayMode.TEXT
    assert parse_display_mode_request("/tour mode image").mode is TourDisplayMode.IMAGE
    assert parse_display_mode_request("图片模式").mode is TourDisplayMode.IMAGE
    assert parse_display_mode_request("文本模式").mode is TourDisplayMode.TEXT
    assert parse_display_mode_request("模式 语音").kind == "invalid"


def test_instrument_prompt_matches_difficulty_and_equipment_state() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.session import TourSession
    from plugins.tour.messages import Messages

    normal = TourSession("u1", DIFFICULTIES["高级"], seed=2)
    assert "0 " not in Messages.prompt(normal.snapshot())

    normal.instrument = _card(CardType.INSTRUMENT, 7, "乐器")
    normal.instrument_equipped = True
    assert "0 卸下装备" in Messages.prompt(normal.snapshot())
    assert "0 卸下装备" in Messages.compact_prompt(normal.snapshot())

    normal.instrument_equipped = False
    assert "0 穿上装备" in Messages.prompt(normal.snapshot())
    assert "0 穿上装备" in Messages.compact_prompt(normal.snapshot())

    super_session = TourSession("u2", DIFFICULTIES["超级"], seed=2)
    assert "0 丢弃乐器" in Messages.prompt(super_session.snapshot())
    assert "0 丢弃乐器" in Messages.compact_prompt(super_session.snapshot())
    assert "超级难度为丢弃" not in Messages.prompt(super_session.snapshot())


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


def test_display_mode_is_user_scoped_and_persisted(sqlite_session) -> None:
    _load_plugin()
    from plugins.tour import database
    from plugins.tour.models import Base
    from plugins.tour.models import TourPreference
    from plugins.tour.models import TourDisplayMode
    from plugins.tour.service import get_display_mode
    from plugins.tour.service import set_display_mode

    db = sqlite_session(database, Base)

    assert get_display_mode("u1") is TourDisplayMode.IMAGE
    assert get_display_mode("u2") is TourDisplayMode.IMAGE

    set_display_mode("u1", TourDisplayMode.TEXT)
    db.expire_all()

    assert get_display_mode("u1") is TourDisplayMode.TEXT
    assert get_display_mode("u2") is TourDisplayMode.IMAGE
    assert db.query(TourPreference).count() == 1

    set_display_mode("u1", TourDisplayMode.IMAGE)
    db.expire_all()

    assert get_display_mode("u1") is TourDisplayMode.IMAGE
    assert db.query(TourPreference).count() == 1


def test_display_mode_survives_database_session_restart(tmp_path, monkeypatch) -> None:
    _load_plugin()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from plugins.tour import database
    from plugins.tour.models import Base
    from plugins.tour.models import TourDisplayMode
    from plugins.tour.service import get_display_mode
    from plugins.tour.service import set_display_mode

    engine = create_engine(f"sqlite:///{tmp_path / 'tour.db'}")
    Base.metadata.create_all(engine)
    first_session = sessionmaker(bind=engine)()
    monkeypatch.setattr(database, "session", first_session)

    set_display_mode("u1", TourDisplayMode.TEXT)
    first_session.close()

    second_session = sessionmaker(bind=engine)()
    monkeypatch.setattr(database, "session", second_session)

    assert get_display_mode("u1") is TourDisplayMode.TEXT

    second_session.close()
    engine.dispose()


@pytest.mark.asyncio
async def test_text_mode_state_skips_image_rendering(monkeypatch) -> None:
    _load_plugin()
    import plugins.tour as tour
    from plugins.tour.rules import DIFFICULTIES
    from plugins.tour.models import CardType
    from plugins.tour.models import TourDisplayMode
    from plugins.tour.session import TourSession

    session = TourSession("u1", DIFFICULTIES["高级"], seed=2)
    session.instrument = _card(CardType.INSTRUMENT, 7, "乐器")
    session.instrument_equipped = True
    sent = []

    class Matcher:
        async def send(self, message, **kwargs):
            sent.append(message)

    class Plain:
        element = ""

    async def unexpected_render(*args, **kwargs):
        raise AssertionError("text mode must not render an image")

    monkeypatch.setattr(tour, "render_image_segment", unexpected_render)

    await tour._send_state(
        Matcher(),
        session,
        pg=Plain(),
        notice="已操作",
        display_mode=TourDisplayMode.TEXT,
    )

    message = str(sent[0])
    assert "已操作" in message
    assert "体力：" in message
    assert "0 卸下装备" in message


@pytest.mark.asyncio
async def test_settlement_uses_clear_ladder_and_performance_rewards(
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
    loss.tour_played_count = 7
    loss.mark_terminal(TourOutcome.STAMINA)
    failed = await tour._settle(loss, TourOutcome.STAMINA)

    timeout = TourSession("u1", DIFFICULTIES["高级"], seed=16, run_id="timeout")
    timeout.tour_played_count = 5
    timeout.mark_terminal(TourOutcome.TIMEOUT)
    timed_out = await tour._settle(timeout, TourOutcome.TIMEOUT)

    assert result.reward_pt == 120
    assert result.base_reward_pt == 60
    assert result.birthday_names == ("香澄",)
    assert result.multiplier == 2
    assert result.task_name == "巡演开场"
    assert result.task_reward == 80
    assert duplicate.task_name is None
    assert failed.reward_pt == 7
    assert failed.base_reward_pt == 7
    assert timed_out.reward_pt == 5
    assert timed_out.base_reward_pt == 5
    assert added == [
        ("u1", 120, "tour", "tour:win:pt"),
        ("u1", 7, "tour", "tour:loss:pt"),
        ("u1", 5, "tour", "tour:timeout:pt"),
    ]
    assert xp_added == [("u1", 120)]
    assert task_events == [
        ("u1", "tour_progress", {"tours_completed": 0, "day": 1}),
        ("u1", "tour_progress", {"tours_completed": 7, "day": 1}),
        ("u1", "tour_progress", {"tours_completed": 5, "day": 1}),
    ]
    assert db.query(TourGameRecord).count() == 3
    assert db.query(TourGameRecord).filter_by(outcome="stamina").one().reward_pt == 7


def test_tour_leaderboard_keeps_fastest_season_clear_per_player(
    sqlite_session,
) -> None:
    _load_plugin()
    from plugins.tour import database
    from plugins.tour.models import Base
    from plugins.tour.models import TourGameRecord
    from plugins.tour.service import get_leaderboard

    db = sqlite_session(database, Base)
    rows = [
        ("a-older", "u1", "win", 19.0, 110),
        ("a-fast", "u1", "win", 12.0, 120),
        ("b", "u2", "win", 14.0, 130),
        ("loss", "u3", "stamina", 5.0, 140),
        ("old", "u4", "win", 1.0, 90),
        ("other", "u5", "win", 2.0, 150),
    ]
    for run_id, user_id, outcome, elapsed, timestamp in rows:
        db.add(
            TourGameRecord(
                run_id=run_id,
                user_id=user_id,
                difficulty="初级" if run_id != "other" else "中级",
                outcome=outcome,
                tours_completed=26 if outcome == "win" else 10,
                day=10,
                action_count=30,
                rest_count=0,
                stamina_remaining=1,
                elapsed_seconds=elapsed,
                reward_pt=20,
                seed=1,
                timestamp=timestamp,
            )
        )
    db.commit()

    result = get_leaderboard("初级", start_time=100, end_time=200)

    assert [(row.user_id, row.elapsed_seconds) for row in result] == [
        ("u1", 12.0),
        ("u2", 14.0),
    ]


def test_tour_leaderboard_renders_all_four_difficulties() -> None:
    _load_plugin()
    from plugins.render.kits import KITS
    from plugins.tour.render import render_leaderboard

    rows = {
        "初级": [("香澄", 12.34)],
        "中级": [("有咲", 23.45)],
        "高级": [("多惠", 34.56)],
        "超级": [("里美", 45.67)],
    }
    for factory in KITS.values():
        image = render_leaderboard(rows, factory())
        assert image.width > 0 and image.height > 0


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


def test_tour_hand_cells_and_grid_rows_fit_their_content_in_every_theme() -> None:
    _load_plugin()
    from plugins.render import Constraints
    from plugins.render import RenderContext
    from plugins.tour.rules import DIFFICULTIES
    from plugins.render.kits import KITS
    from plugins.tour.session import TourSession
    from plugins.render.spacing import as_insets
    from plugins.tour.render.state import _hand_panel

    snapshot = TourSession("u1", DIFFICULTIES["初级"], seed=13).snapshot()
    ctx = RenderContext(pixel_ratio=2).for_root_render()

    for factory in KITS.values():
        panel = _hand_panel(factory(), snapshot)
        grid = panel.child.children[1]
        cell_sizes = []
        for cell in grid.children:
            cell_size = ctx.measure(cell, Constraints())
            padding = as_insets(cell.padding)
            content_size = ctx.measure(
                cell.child.child,
                Constraints(max_width=cell_size.width - padding.horizontal),
            )
            assert cell_size.height >= content_size.height + padding.vertical
            cell_sizes.append(cell_size)

        row_gap = grid.gap[1] if isinstance(grid.gap, tuple) else grid.gap
        natural_grid_height = (
            max(size.height for size in cell_sizes[:2])
            + max(size.height for size in cell_sizes[2:])
            + row_gap
        )
        assert ctx.measure(grid, Constraints()).height >= natural_grid_height


def test_tour_status_panel_leads_with_stamina_and_keeps_progress_secondary() -> None:
    _load_plugin()
    from plugins.tour.rules import DIFFICULTIES
    from plugins.render.kits import MinimalKit
    from plugins.tour.session import TourSession
    from plugins.tour.render.state import _status_panel

    snapshot = TourSession("u1", DIFFICULTIES["初级"], seed=13).snapshot()
    texts: list[str] = []

    def collect_text(component) -> None:
        text = getattr(component, "text", None)
        if isinstance(text, str):
            texts.append(text)
        for name in ("children", "child"):
            value = getattr(component, name, None)
            if isinstance(value, (list, tuple)):
                for child in value:
                    collect_text(child)
            elif value is not None:
                collect_text(value)

    collect_text(_status_panel(MinimalKit(), snapshot))

    assert texts == [
        "体力",
        f"{snapshot.stamina}/{snapshot.max_stamina}",
        f"第 {snapshot.day} 天 · 今日行动 {snapshot.selection_count}/3",
        f"已完成 {snapshot.tour_played_count}/26 场",
    ]


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
    from plugins.tour.messages import Messages

    usage = plugin_data["巡演"]["usage"]
    assert "6" not in usage
    assert all("兼容" not in meaning for meaning in usage.values())
    assert usage["/巡演 模式 [图片|文本]"] == "查看或切换用户独立的巡演显示模式"
    assert usage["0"] == (
        "超级难度：0 丢弃乐器；其他难度：已装备时 0 卸下装备，"
        "未装备时 0 穿上装备"
    )
    assert "超级难度：0 丢弃乐器" in Messages.HELP
    assert "已装备时 0 卸下装备" in Messages.HELP
    assert "未装备时 0 穿上装备" in Messages.HELP
