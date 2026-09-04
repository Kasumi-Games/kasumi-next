import pytest

from plugins.mines import _format_status
from plugins.mines.session import MAX_PAYOUT
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
