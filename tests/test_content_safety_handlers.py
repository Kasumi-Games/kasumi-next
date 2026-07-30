from __future__ import annotations

from typing import Any
from typing import Callable

import pytest
from nonebot.adapters.satori import Message
from nonebot.exception import FinishedException

import plugins.cck as cck
import plugins.daily as daily
import plugins.help as help_plugin
import plugins.nickname as nickname
from utils.content_safety import ContentSafetyError
from utils.content_safety import SensitiveTextPolicy


class RecordingMatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    async def finish(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append((message, kwargs))
        raise FinishedException()


def _unsafe_text() -> str:
    return next(iter(SensitiveTextPolicy.default().terms))


def _assert_generic_rejection(matcher: RecordingMatcher, unsafe_text: str) -> None:
    assert len(matcher.calls) == 1
    text = str(matcher.calls[0][0])
    assert "不符合平台规范" in text
    assert unsafe_text not in text


async def test_transfer_never_echoes_an_unsafe_unknown_nickname(
    make_satori_event: Callable[..., Any],
) -> None:
    unsafe_text = _unsafe_text()
    matcher = RecordingMatcher()

    with pytest.raises(FinishedException):
        await daily.handle_transfer(  # type: ignore[arg-type]
            matcher,
            make_satori_event("/转账"),
            Message(f"{unsafe_text} 1"),
        )

    _assert_generic_rejection(matcher, unsafe_text)


async def test_help_never_echoes_an_unsafe_search_token(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event: Callable[..., Any],
) -> None:
    unsafe_text = _unsafe_text()
    matcher = RecordingMatcher()
    monkeypatch.setattr(help_plugin, "help", matcher)
    monkeypatch.setattr(help_plugin, "kit_for_user", lambda user_id: None)

    with pytest.raises(FinishedException):
        await help_plugin._(make_satori_event("/help"), Message(unsafe_text))

    _assert_generic_rejection(matcher, unsafe_text)


async def test_guess_card_never_echoes_an_unsafe_difficulty(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event: Callable[..., Any],
) -> None:
    unsafe_text = _unsafe_text()
    matcher = RecordingMatcher()
    monkeypatch.setattr(cck, "start_cck", matcher)
    event = make_satori_event("/猜卡面", message_id="unsafe-cck")

    with pytest.raises(FinishedException):
        await cck.handle_cck(event, Message(unsafe_text))

    _assert_generic_rejection(matcher, unsafe_text)


async def test_nickname_rejects_unsafe_text_before_persisting_or_echoing(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event: Callable[..., Any],
) -> None:
    unsafe_text = _unsafe_text()
    matcher = RecordingMatcher()
    monkeypatch.setattr(nickname, "set_nickname", matcher)

    with pytest.raises(FinishedException):
        await nickname.handle_set_nickname(
            make_satori_event("/设置昵称"), Message(unsafe_text)
        )

    _assert_generic_rejection(matcher, unsafe_text)


def test_cosmetic_lookup_rejects_unsafe_text_before_constructing_an_echo() -> None:
    import plugins.inventory as inventory

    with pytest.raises(ContentSafetyError):
        inventory._resolve_cosmetic_token("user", _unsafe_text())
