from plugins.mines.models import Field
from plugins.mines.models import BlockType
from plugins.mines.session import GameSession
from plugins.mines.session import parse_reveal_indices


def _session_with_mine_at(mine_index: int) -> GameSession:
    field = Field(width=5, height=1, mines=1)
    field.field = [[BlockType.EMPTY for _ in range(5)]]
    field.field[0][mine_index] = BlockType.MINE
    return GameSession(
        user_id="user",
        channel_id="channel",
        bet_amount=100,
        mines=1,
        field=field,
    )


def test_parse_reveal_indices_accepts_whitespace_separated_positions():
    assert parse_reveal_indices("1  3\n5", total_cells=5) == (0, 2, 4)


def test_parse_reveal_indices_rejects_the_entire_invalid_batch():
    assert parse_reveal_indices("1 nope 3", total_cells=5) is None
    assert parse_reveal_indices("1 6 3", total_cells=5) is None
    assert parse_reveal_indices("", total_cells=5) is None


def test_batch_reveal_stops_at_mine_and_leaves_later_cells_closed():
    session = _session_with_mine_at(2)

    result = session.reveal_blocks((0, 2, 4))

    assert result.opened_indices == (0, 2)
    assert result.hit_mine is True
    assert result.won is False
    assert session.revealed_indices == {0}
    assert session.field.get_block(4) == BlockType.EMPTY


def test_batch_reveal_skips_duplicates_and_continues_in_order():
    session = _session_with_mine_at(4)
    session.reveal_blocks((0,))

    result = session.reveal_blocks((0, 1, 1, 2))

    assert result.opened_indices == (1, 2)
    assert result.already_revealed_indices == (0, 1)
    assert session.revealed_indices == {0, 1, 2}


def test_batch_reveal_stops_after_final_safe_cell():
    session = _session_with_mine_at(4)

    result = session.reveal_blocks((0, 1, 2, 3, 4))

    assert result.opened_indices == (0, 1, 2, 3)
    assert result.won is True
    assert result.hit_mine is False
    assert session.field.get_block(4) == BlockType.MINE
