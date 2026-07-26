"""The /签到 and /排行榜 matchers: the collapsed single-card reply paths.

The old check-in flow fanned out over two content sends plus an empty finish
(the assembled text, then a separate level-up message); the old leaderboard
was one unaligned text send. These tests drive the real handler coroutines
with every service call stubbed at the plugin namespace and prove each flow
now exits through exactly one send — a card with the passive element — while
the duplicate-check-in prompt stays text.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from typing import Callable
from datetime import datetime

import pytest
from nonebot.exception import FinishedException

import plugins.daily as daily
from plugins.render.kits import MinimalKit


class RecordingMatcher:
    """Stands in for ``Matcher``: records every send, finish raises."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    async def send(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("send", message, kwargs))

    async def finish(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("finish", message, kwargs))
        raise FinishedException()


def _stub_checkin_services(monkeypatch: pytest.MonkeyPatch, user: Any) -> None:
    monkeypatch.setattr(daily, "get_user", lambda user_id: user)
    monkeypatch.setattr(daily, "add", lambda *args: None)

    async def add_xp(user_id: str, amount: int) -> None:
        return None

    monkeypatch.setattr(daily, "add_xp", add_xp)
    monkeypatch.setattr(daily, "get", lambda user_id: 1203)
    monkeypatch.setattr(daily, "is_using_offseason_points", lambda: False)
    monkeypatch.setattr(daily, "add_star_stickers", lambda *args: None)
    monkeypatch.setattr(
        daily, "get_monetary_session", lambda: SimpleNamespace(commit=lambda: None)
    )
    monkeypatch.setattr(
        daily,
        "get_today_task",
        lambda user_id: SimpleNamespace(
            name="概率学博士", description="在黑香澄中赢得一局", reward=80
        ),
    )
    monkeypatch.setattr(
        daily,
        "daily_task_service",
        SimpleNamespace(
            get_today_task=lambda user_id: SimpleNamespace(is_completed=False)
        ),
    )
    monkeypatch.setattr(
        daily, "mail_service", SimpleNamespace(get_user_mails=lambda user_id: [])
    )
    monkeypatch.setattr(
        daily, "identity_for", lambda user_id: SimpleNamespace(nickname="香澄")
    )
    monkeypatch.setattr(daily, "kit_for_user", lambda user_id: MinimalKit())


async def test_checkin_success_is_one_card_send(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    user = SimpleNamespace(
        last_daily_time=0, consecutive_checkins=5, level=23, xp=100
    )
    _stub_checkin_services(monkeypatch, user)

    matcher = RecordingMatcher()
    event = make_satori_event("/签到")
    with pytest.raises(FinishedException):
        await daily.handle_daily(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer
    # The handler committed today's streak state before replying.
    assert user.consecutive_checkins == 6


async def test_duplicate_checkin_stays_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    user = SimpleNamespace(
        last_daily_time=int(datetime.now().timestamp()),
        consecutive_checkins=5,
        level=23,
        xp=100,
    )
    _stub_checkin_services(monkeypatch, user)

    matcher = RecordingMatcher()
    event = make_satori_event("/签到")
    with pytest.raises(FinishedException):
        await daily.handle_daily(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    segment_types = [segment.type for segment in message]
    assert "img" not in segment_types
    assert "今天已经签到过了" in str(message)
    assert kwargs["referrer"] is event.referrer
    assert user.consecutive_checkins == 5


async def test_levelrank_is_one_card_send(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    top_users = [
        SimpleNamespace(user_id=f"member-{index}", level=42 - index, xp=18204 - index)
        for index in range(10)
    ]
    monkeypatch.setattr(daily, "get_top_users", lambda limit: top_users)
    monkeypatch.setattr(
        daily,
        "get_user_rank",
        lambda user_id: SimpleNamespace(rank=27, xp_gap=340),
    )
    monkeypatch.setattr(
        daily, "get_user", lambda user_id: SimpleNamespace(level=24, xp=1180)
    )
    monkeypatch.setattr(
        daily, "nickname", SimpleNamespace(get=lambda user_id: f"昵称{user_id}")
    )
    monkeypatch.setattr(daily, "kit_for_user", lambda user_id: MinimalKit())

    matcher = RecordingMatcher()
    event = make_satori_event("/排行榜")
    with pytest.raises(FinishedException):
        await daily.handle_levelrank(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer
