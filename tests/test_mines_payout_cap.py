from types import SimpleNamespace

import pytest

import plugins.mines as mines_plugin
from plugins.mines import _format_status
from plugins.mines import _xp_reward_for_multiplier
from plugins.mines.models import GameResult
from plugins.mines.session import MAX_PAYOUT
from plugins.mines.session import MAX_XP_REWARD
from plugins.mines.session import GameManager
from plugins.mines.session import GameSession


class _FixedField:
    def __init__(self, total_cells: int, mines: int):
        self._total_cells = total_cells
        self._mines = mines

    def total_cells(self) -> int:
        return self._total_cells

    def safe_cells(self) -> int:
        return self._total_cells - self._mines


def _peak_session(*, side: int, mines: int, bet: int) -> GameSession:
    field = _FixedField(side * side, mines)
    session = GameSession(
        user_id="user",
        channel_id="channel",
        bet_amount=bet,
        mines=mines,
        field=field,
    )
    session.revealed_indices = set(range(field.safe_cells()))
    session.update_multiplier()
    return session


def test_original_five_by_five_peak_stays_uncapped_for_normal_bet():
    session = _peak_session(side=5, mines=12, bet=100)

    assert session.is_payout_capped is False
    assert session.multiplier == pytest.approx(5_044_291)
    assert session.get_payout() == 504_429_100


def test_large_board_multiplier_and_payout_stop_at_cap():
    session = _peak_session(side=10, mines=50, bet=100)

    assert session.is_payout_capped is True
    assert session.multiplier == MAX_PAYOUT / session.bet_amount
    assert session.get_payout() == MAX_PAYOUT
    assert "已达派奖上限" in _format_status(session)


@pytest.mark.parametrize("side", range(2, 11))
def test_supported_boards_never_quote_more_than_payout_cap(side):
    total_cells = side * side
    mines = total_cells // 2
    session = GameSession(
        user_id="user",
        channel_id="channel",
        bet_amount=100,
        mines=mines,
        field=_FixedField(total_cells, mines),
    )

    for revealed_count in range(1, session.safe_cells + 1):
        session.revealed_indices = set(range(revealed_count))
        session.update_multiplier()
        assert session.get_payout() <= MAX_PAYOUT


def test_session_rejects_bet_larger_than_payout_cap():
    manager = GameManager()
    manager._pending_hold_keys["user"] = "hold"

    with pytest.raises(ValueError):
        manager.create_session(
            "user", "channel", MAX_PAYOUT + 1, 5, board_size=5
        )


def test_xp_reward_keeps_existing_multiplier_scaling_below_cap():
    assert _xp_reward_for_multiplier(2.0) == 5
    assert _xp_reward_for_multiplier(8.33) == 20


def test_xp_reward_stops_at_two_and_a_half_times_payout_cap():
    assert MAX_XP_REWARD == MAX_PAYOUT * 5 // 2
    assert _xp_reward_for_multiplier(MAX_PAYOUT * 10) == MAX_XP_REWARD


async def test_result_settlement_passes_capped_xp_to_monetary(monkeypatch):
    awarded_xp = []

    async def add_xp(user_id, amount):
        awarded_xp.append((user_id, amount))
        return None

    async def no_task(*args, **kwargs):
        return None

    class _Page:
        async def render_async(self):
            return object()

    class _Matcher:
        async def send(self, *args, **kwargs):
            return None

    async def image_segment(image):
        return ""

    monkeypatch.setattr(mines_plugin.monetary, "add_xp", add_xp)
    monkeypatch.setattr(mines_plugin.monetary, "get_level", lambda user_id: 1)
    monkeypatch.setattr(mines_plugin.monetary, "get", lambda user_id: 0)
    monkeypatch.setattr(mines_plugin, "check_progress", no_task)
    monkeypatch.setattr(mines_plugin, "result_page", lambda *args, **kwargs: _Page())
    monkeypatch.setattr(mines_plugin, "image_segment_async", image_segment)

    session = GameSession(
        user_id="user",
        channel_id="channel",
        bet_amount=1,
        mines=1,
        field=_FixedField(4, 1),
    )
    pg = SimpleNamespace(element="", event=SimpleNamespace(referrer=None))

    await mines_plugin._send_result_card(
        _Matcher(),
        session,
        GameResult.CASHOUT,
        payout=MAX_PAYOUT,
        multiplier=MAX_PAYOUT * 10,
        kit=None,
        identity=None,
        pg=pg,
    )

    assert awarded_xp == [("user", MAX_XP_REWARD)]
