"""Regression tests for failures observed in the 2026-07-29 production log."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image


def test_passive_generator_survives_an_evicted_sequence_counter(
    make_satori_event,
    monkeypatch,
):
    from utils import passive_generator as module

    counters = module.ExpiringDict(expiration_minutes=5)
    monkeypatch.setattr(module, "_seq_counters", counters)

    event = make_satori_event(message_id="old-message")
    generator = module.PassiveGenerator(event)
    del counters[event.message.id]

    segment = generator.element

    assert segment.type == "qq:passive"
    assert segment.data == {"id": "old-message", "seq": 1}


def test_game_membership_removal_is_idempotent():
    from plugins.cck.store import GamersStore as CckGamersStore
    from plugins.guess_chart.store import GamersStore as GuessChartGamersStore

    for store_type in (CckGamersStore, GuessChartGamersStore):
        store = store_type()
        store.add("channel")
        store.remove("channel")
        store.remove("channel")
        assert "channel" not in store.get()


def test_long_running_games_keep_the_current_passive_reply_locally():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "plugins/cck/__init__.py",
        "plugins/guess_chart/__init__.py",
        "plugins/one_stroke/__init__.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert not re.search(r"gens\[[^\]\n]+\]\.(?:element|event)", source), relative


async def test_interactive_game_waiters_ignore_other_channels(
    make_satori_event,
):
    from utils.waiter_rules import same_channel

    rule = same_channel("game-channel")

    assert await rule(make_satori_event(channel_id="game-channel"))
    assert not await rule(make_satori_event(channel_id="other-channel"))


def test_force_stop_commands_are_not_consumed_as_game_guesses():
    from utils.waiter_rules import is_force_stop_message

    assert is_force_stop_message("/猜卡面   -f", {"猜卡面", "cck"})
    assert is_force_stop_message("/cpm -f", {"猜谱面", "cpm"})
    assert not is_force_stop_message("/猜卡面 hard", {"猜卡面", "cck"})


def test_guess_chart_waiter_force_stop_clears_active_game(monkeypatch):
    import importlib

    importlib.import_module("plugins.daily_task")
    guess_chart = importlib.import_module("plugins.guess_chart")
    from plugins.guess_chart.store import GamersStore

    store = GamersStore()
    store.add("game-channel")
    monkeypatch.setattr(guess_chart, "gamers_store", store)

    assert guess_chart._stop_if_force_stop("/cpm -f", "game-channel") is True
    assert "game-channel" not in store.get()


def test_guess_chart_force_stop_invalidates_the_previous_waiter_session():
    from plugins.guess_chart.store import GamersStore

    store = GamersStore()
    old_session = store.add("game-channel")
    store.remove("game-channel")
    new_session = store.add("game-channel")

    assert store.is_current("game-channel", old_session) is False
    assert store.is_current("game-channel", new_session) is True


def test_blackjack_chooses_from_cards_that_have_local_art(monkeypatch):
    from plugins.blackjack.render import BlackjackRenderer

    renderer = BlackjackRenderer.__new__(BlackjackRenderer)
    transparent = Image.new("RGBA", (640, 896), (0, 0, 0, 0))
    renderer.frames = {"5": transparent}
    renderer.attrs = {"happy": Image.new("RGBA", (1, 1), (0, 0, 0, 0))}
    renderer.star = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    renderer.star_trained = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    renderer.bands = {"1": transparent}
    renderer.filter_cards = lambda *_args: [
        {"resource_set_name": "missing", "band_id": 1},
        {"resource_set_name": "available", "band_id": 1},
    ]
    renderer.get_card_images = lambda resource: (
        ["available.png"] if resource == "available" else []
    )
    renderer.cut_card = lambda _path: Image.new("RGB", (594, 850), "white")
    monkeypatch.setattr("plugins.blackjack.render.random.choice", lambda items: items[0])

    image, _regenerate = renderer.generate_card(
        "A",
        "happy",
        ace_value=11,
    )

    assert image.size == (640, 896)


def test_alconna_ignores_satori_file_segments_without_src():
    import nonebot
    from nonebot.adapters.satori import Message
    from nonebot.adapters.satori.message import File

    if nonebot.get_plugin("nonebot_plugin_alconna") is None:
        nonebot.require("nonebot_plugin_alconna")
    assert nonebot.get_plugin("nonebot_plugin_alconna") is not None

    from nonebot_plugin_alconna.uniseg.adapters.satori.builder import (
        SatoriMessageBuilder,
    )

    from utils.alconna_compat import install_satori_file_segment_guard

    install_satori_file_segment_guard()

    result = SatoriMessageBuilder().generate(
        Message([File(type="file", data={"size": "39219"})])
    )

    assert len(result) == 1
