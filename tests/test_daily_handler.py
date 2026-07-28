"""The /签到, /等级排行, and /info matchers: the single-card reply paths.

The old check-in flow fanned out over two content sends plus an empty finish
(the assembled text, then a separate level-up message); the old leaderboard
was one unaligned text send; the old /info was a bare text summary. These
tests drive the real handler coroutines with every service call stubbed at
the plugin namespace and prove each flow now exits through exactly one send —
a card with the passive element — while the duplicate-check-in prompt and the
render-failure fallbacks stay text.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from typing import Callable
from datetime import datetime

import pytest
from nonebot.exception import FinishedException

import plugins.daily as daily
from plugins.render import PlayerIdentity
from plugins.render.kits import MinimalKit
from plugins.inventory.render import ProfileData


async def _no_avatar(user_id: str) -> None:
    return None


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
        daily,
        "identity_for",
        lambda user_id, avatar=None: SimpleNamespace(nickname="香澄"),
    )
    monkeypatch.setattr(daily, "get_avatar", _no_avatar)
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


def _profile_data(**overrides: Any) -> ProfileData:
    defaults: dict[str, Any] = dict(
        identity=PlayerIdentity(nickname="香澄", level=24),
        current_pt=1203,
        description="",
        star_stickers=56,
        bonsai=7,
        season_name="2026 第一赛季",
        season_rank=3,
        equipped=(),
        xp_in_level=100,
        xp_level_span=2500,
        offseason=False,
    )
    defaults.update(overrides)
    return ProfileData(**defaults)


def _stub_info_services(monkeypatch: pytest.MonkeyPatch, data: ProfileData) -> None:
    recorded: dict[str, Any] = {}

    def assemble(user_id: str, *, avatar: Any = None) -> ProfileData:
        recorded["user_id"] = user_id
        recorded["avatar"] = avatar
        return data

    monkeypatch.setattr(daily, "assemble_profile", assemble)
    monkeypatch.setattr(daily, "get_avatar", _no_avatar)
    monkeypatch.setattr(daily, "kit_for_user", lambda user_id: MinimalKit())


async def test_info_is_one_profile_card_send(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    _stub_info_services(monkeypatch, _profile_data())

    matcher = RecordingMatcher()
    event = make_satori_event("/info")
    with pytest.raises(FinishedException):
        await daily.info(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer


async def test_info_render_failure_degrades_to_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    _stub_info_services(monkeypatch, _profile_data(offseason=True, season_name=None))

    def broken_page(data: Any, kit: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(daily, "profile_page", broken_page)

    matcher = RecordingMatcher()
    event = make_satori_event("/余额")
    with pytest.raises(FinishedException):
        await daily.info(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    text = str(message)
    assert "img" not in [segment.type for segment in message]
    assert "Lv.24 | XP: 100/2500 (还需 2400)" in text
    assert "休赛期临时 Pt: 1203 Pt" in text
    assert "星星贴纸: 56" in text
    assert "休赛期临时 Pt 不会计入下一赛季。" in text
    assert kwargs["referrer"] is event.referrer


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
    # 排行榜 belongs to the season Pt ladder now; the level ladder is 等级排行.
    event = make_satori_event("/等级排行")
    with pytest.raises(FinishedException):
        await daily.handle_levelrank(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer
