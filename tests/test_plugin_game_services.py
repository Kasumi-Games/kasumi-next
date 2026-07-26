from __future__ import annotations

import importlib
from pathlib import Path


def _load_plugin_dependencies(*module_names: str) -> None:
    for module_name in module_names:
        importlib.import_module(module_name)


def test_blackjack_hand_session_and_stats(sqlite_session, monkeypatch):
    _load_plugin_dependencies("plugins.daily_task", "plugins.cck")

    from plugins.blackjack import database
    from plugins.blackjack.models import Base
    from plugins.blackjack.models import Card
    from plugins.blackjack.models import Hand
    from plugins.blackjack.models import GameResult
    from plugins.blackjack.session import GameManager
    from plugins.blackjack.game_service import BlackjackGameService

    sqlite_session(database, Base)
    balance = {"u1": 100}
    monkeypatch.setattr("plugins.blackjack.session.monetary.get", lambda user_id: balance[user_id])
    monkeypatch.setattr(
        "plugins.blackjack.session.monetary.cost",
        lambda user_id, amount, reason: balance.__setitem__(user_id, balance[user_id] - amount),
    )
    monkeypatch.setattr(
        "plugins.blackjack.session.monetary.add",
        lambda user_id, amount, reason: balance.__setitem__(user_id, balance[user_id] + amount),
    )

    hand = Hand()
    hand.add_card(Card("happy", "A"))
    hand.add_card(Card("cool", "K"))
    hand.add_card(Card("pure", "5"))
    assert hand.value == 16

    manager = GameManager()
    assert manager.start_game("u1", 20) is True
    assert manager.start_game("u1", 20) is False
    manager.create_session("u1", "c1", 20, Hand(), Hand())
    assert manager.end_game("u1", GameResult.WIN, winnings=20) == 20
    assert balance["u1"] == 120

    stats = BlackjackGameService.get_user_stats("u1")
    assert stats["total_games"] == 1
    assert stats["wins"] == 1
    assert stats["net_profit"] == 20


def test_mines_field_session_and_stats(sqlite_session, monkeypatch):
    _load_plugin_dependencies("plugins.daily_task")

    from plugins.mines import database
    from plugins.mines.models import Base
    from plugins.mines.models import Field
    from plugins.mines.models import BlockType
    from plugins.mines.models import GameResult
    from plugins.mines.session import GameManager
    from plugins.mines.stats_service import get_mines_stats

    sqlite_session(database, Base)
    monkeypatch.setattr("plugins.mines.models.get_random_kasumi", lambda: Path("kasumi.png"))
    monkeypatch.setattr("plugins.mines.models.get_random_arisa", lambda: Path("arisa.png"))
    monkeypatch.setattr("plugins.mines.models.random.sample", lambda population, mines: [0])
    balance = {"u1": 100}
    monkeypatch.setattr("plugins.mines.session.monetary.get", lambda user_id: balance[user_id])
    monkeypatch.setattr(
        "plugins.mines.session.monetary.cost",
        lambda user_id, amount, reason: balance.__setitem__(user_id, balance[user_id] - amount),
    )
    monkeypatch.setattr(
        "plugins.mines.session.monetary.add",
        lambda user_id, amount, reason: balance.__setitem__(user_id, balance[user_id] + amount),
    )

    field = Field(width=2, height=2, mines=1)
    assert field.reveal_block(0) == BlockType.MINE
    assert field.get_block(0) == BlockType.MINE_SHOWN
    assert field.safe_cells() == 3

    manager = GameManager()
    assert manager.start_game("u1", 10) is True
    session = manager.create_session("u1", "c1", 10, 1)
    session.revealed_indices.add(1)
    session.update_multiplier()
    payout = session.get_payout()
    manager.end_game("u1", GameResult.CASHOUT, payout)

    stats = get_mines_stats("u1")
    assert stats.total_games == 1
    assert stats.total_wagered == 10
    assert stats.recent_games[0].revealed_count == 1


def test_one_stroke_movement_reward_decay_and_manager():
    _load_plugin_dependencies("plugins.daily_task")

    from plugins.one_stroke.models import Graph
    from plugins.one_stroke.models import MoveResult
    from plugins.one_stroke.session import GameManager
    from plugins.one_stroke.difficulty import apply_time_decay
    from plugins.one_stroke.difficulty import calculate_reward
    from plugins.one_stroke.graph_generator import parse_difficulty

    graph = Graph(
        rows=2,
        cols=2,
        nodes={(0, 0), (0, 1), (1, 1)},
        edges={frozenset(((0, 0), (0, 1))), frozenset(((0, 1), (1, 1)))},
        start_node=(0, 0),
    )
    manager = GameManager()
    session = manager.create_session("u1", "c1", "easy", calculate_reward(graph), graph)

    assert manager.create_session("u1", "c1", "easy", 1, graph) is None
    assert session.move("D") == MoveResult.SUCCESS
    assert session.move("A") == MoveResult.ALREADY_DRAWN
    assert session.move("S") == MoveResult.SUCCESS
    assert session.is_complete is True
    assert apply_time_decay(10, elapsed_seconds=0, graph=graph) == 10
    assert apply_time_decay(10, elapsed_seconds=999, graph=graph) < 10
    assert parse_difficulty("hd").key == "hard"

    manager.end_game("u1")
    assert manager.is_in_game("u1") is False


def test_guess_chart_helpers_and_cck_crop(monkeypatch):
    from PIL import Image

    _load_plugin_dependencies("plugins.daily_task")

    from plugins.cck.draw import random_crop_image
    from plugins.guess_chart.utils import fuzzy_match
    from plugins.guess_chart.utils import num_to_range
    from plugins.guess_chart.utils import is_valid_query
    from plugins.guess_chart.utils import build_enriched_dictionary

    monkeypatch.setattr("plugins.cck.draw.random.randint", lambda low, high: low)
    image = Image.new("RGBA", (100, 80), (1, 2, 3, 255))
    cropped = random_crop_image(
        image, cut_width=20, cut_length=10, is_black=1, cut_counts=1
    )
    assert cropped.data["src"].startswith("data:image/png;base64,")

    dictionary = {"1": ["星之鼓动", "star beat"]}
    song_raw_data = {"1": {"musicTitle": ["", "", "", "STAR BEAT", ""]}}
    enriched = build_enriched_dictionary(dictionary, song_raw_data)
    assert "star beat" in enriched["1"]
    assert fuzzy_match("star beat", enriched) == "1"
    assert is_valid_query("star") is True
    assert num_to_range(7) == (0, 100)
