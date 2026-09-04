from types import SimpleNamespace

import pytest

from plugins.mines.models import BlockType
from plugins.mines.session import MAX_BOARD_SIZE
from plugins.mines.session import MIN_BOARD_SIZE
from plugins.mines.session import GameManager
from plugins.mines.session import parse_start_args
from plugins.mines.session import parse_reveal_indices
from plugins.mines.render.field import BOARD_WIDTH
from plugins.mines.render.field import BOARD_PADDING
from plugins.mines.render.field import render
from plugins.mines.render.field import _cell_layout


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ("100 4", (100, 4, 5)),
        ("100 2 3", (100, 2, 3)),
        ("100 12 8", (100, 12, 8)),
        ("100 20 10", (100, 20, 10)),
    ],
)
def test_parse_start_args_uses_numeric_third_argument(args, expected):
    assert parse_start_args(args) == expected


def test_dimension_form_is_rejected():
    with pytest.raises(ValueError):
        parse_start_args("100 2 3x3")


@pytest.mark.parametrize("board_size", [MIN_BOARD_SIZE, 5, MAX_BOARD_SIZE])
def test_game_manager_creates_requested_board_size(board_size):
    manager = GameManager()
    manager._pending_hold_keys["user"] = "hold"

    session = manager.create_session("user", "channel", 100, 2, board_size=board_size)

    total_cells = board_size * board_size
    assert session.field.width == board_size
    assert session.field.height == board_size
    assert session.field.total_cells() == total_cells
    assert parse_reveal_indices(str(total_cells), total_cells) == (total_cells - 1,)
    assert parse_reveal_indices(str(total_cells + 1), total_cells) is None


@pytest.mark.parametrize("board_size", [MIN_BOARD_SIZE - 1, MAX_BOARD_SIZE + 1])
def test_game_manager_rejects_board_sizes_outside_range(board_size):
    manager = GameManager()
    manager._pending_hold_keys["user"] = "hold"

    with pytest.raises(ValueError):
        manager.create_session("user", "channel", 100, 2, board_size=board_size)


@pytest.mark.parametrize("board_size", range(MIN_BOARD_SIZE, MAX_BOARD_SIZE + 1))
def test_each_board_size_fits_the_fixed_panel(board_size):
    cell_size, gap = _cell_layout(board_size)
    occupied = board_size * cell_size + (board_size - 1) * gap

    assert occupied <= BOARD_WIDTH - BOARD_PADDING * 2
    assert occupied >= BOARD_WIDTH - BOARD_PADDING * 2 - board_size


@pytest.mark.parametrize("board_size", [MIN_BOARD_SIZE, MAX_BOARD_SIZE])
def test_supported_board_size_bounds_render(board_size):
    field = SimpleNamespace(
        width=board_size,
        height=board_size,
        field=[
            [BlockType.EMPTY for _ in range(board_size)]
            for _ in range(board_size)
        ],
    )

    image = render(field)

    assert image.mode == "RGBA"
    assert image.width > 0
    assert image.height > 0
