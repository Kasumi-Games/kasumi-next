"""Regression tests for failures observed in the 2026-07-29 production log."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from loguru import logger


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

    from nonebot_plugin_alconna.uniseg.adapters import BUILDER_MAPPING
    from nonebot_plugin_alconna.uniseg.adapters.satori.builder import (
        SatoriMessageBuilder,
    )

    from utils.alconna_compat import install_satori_file_segment_guard

    # Make the production ordering deterministic even when another test caused
    # the adapter registry to initialize before Satori was registered.
    BUILDER_MAPPING.setdefault("Satori", SatoriMessageBuilder())
    install_satori_file_segment_guard()

    # Production uses Alconna's cached builder, which may have been created
    # before the compatibility guard was installed.
    result = BUILDER_MAPPING["Satori"].generate(
        Message([File(type="file", data={"size": "39219"})])
    )

    assert len(result) == 1


async def test_guess_chart_cleans_session_when_song_info_fetch_fails(
    make_satori_event,
    monkeypatch,
):
    import plugins.guess_chart as module
    from plugins.guess_chart.store import GamersStore

    class UpstreamFailure(RuntimeError):
        pass

    class FakeSong:
        async def get_info_async(self):
            raise UpstreamFailure("502 Bad Gateway")

    class FakeChart:
        def count(self):
            return object()

    async def fake_chart(*_args, **_kwargs):
        return FakeChart()

    async def fake_image_task(*_args, **_kwargs):
        return Image.new("RGB", (1, 1))

    async def fake_finish(*_args, **_kwargs):
        raise RuntimeError("matcher-finished")

    store = GamersStore()
    monkeypatch.setattr(module, "gamers_store", store)
    monkeypatch.setattr(module, "flatten_song_data", lambda _data: [{"song_id": "1", "difficulty": "expert"}])
    monkeypatch.setattr(module, "sort_by_difficulty", lambda _data: {"expert": [1]})
    monkeypatch.setattr(module.songs, "Song", lambda _song_id: FakeSong())
    monkeypatch.setattr(module.Chart, "get_chart_async", fake_chart)
    monkeypatch.setattr(module, "run_image_task", fake_image_task)
    monkeypatch.setattr(module.game_start, "send", AsyncMock())
    monkeypatch.setattr(module.game_start, "finish", fake_finish)
    monkeypatch.setattr(module, "handle_error", lambda *_args, **_kwargs: "KSM-TEST")

    event = make_satori_event(channel_id="game-channel")
    with pytest.raises(RuntimeError, match="matcher-finished"):
        await module.handle_start(
            event=event,
            arg=module.Message(""),
            song_data={},
            band_data={},
            game_difficulty="hard",
            song_raw_data={},
        )

    assert "game-channel" not in store.get()


def test_log_error_uses_the_supplied_exception_traceback():
    from utils.error_handler import log_error

    messages: list[str] = []
    sink = logger.add(messages.append, format="{message}\n{exception}")
    try:
        error = RuntimeError("outside-except")
        log_error("KSM-TEST", error, context="test")
    finally:
        logger.remove(sink)

    rendered = "".join(messages)
    assert "RuntimeError: outside-except" in rendered
    assert "NoneType: None" not in rendered


def test_persistent_log_filter_drops_messages_and_redacts_tokens():
    from utils.error_handler import persistent_log_filter

    message_record = {
        "message": "Satori qq:bot | [message-created]: private words",
    }
    assert persistent_log_filter(message_record) is False

    secret_record = {
        "message": "token='server-secret' auth_token=reply-secret ROBOT1.0_abcdef!",
    }
    assert persistent_log_filter(secret_record) is True
    assert "server-secret" not in secret_record["message"]
    assert "reply-secret" not in secret_record["message"]
    assert "ROBOT1.0_abcdef" not in secret_record["message"]
