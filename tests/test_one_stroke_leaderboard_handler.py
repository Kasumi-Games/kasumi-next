"""Handler-level regressions for the one-stroke leaderboard."""

from types import SimpleNamespace
from typing import Any
from typing import Callable

import pytest
from nonebot.adapters.satori import MessageSegment
from nonebot.exception import FinishedException

import plugins.one_stroke as one_stroke
from plugins.render.kits.kasumi import KasumiKit


class RecordingMatcher:
    def __init__(self) -> None:
        self.finished_message: Any = None

    async def finish(self, message: Any = None, **kwargs: Any) -> None:
        self.finished_message = message
        raise FinishedException()


async def test_leaderboard_passes_requesting_users_theme_to_renderer(
    monkeypatch: pytest.MonkeyPatch,
    make_satori_event: Callable[..., Any],
) -> None:
    event = make_satori_event("/osr", user_id="kasumi-user")
    matcher = RecordingMatcher()
    selected_kit = KasumiKit()
    render_call: dict[str, Any] = {}

    async def record_render(renderer: Any, *args: Any, **kwargs: Any) -> MessageSegment:
        render_call["renderer"] = renderer
        render_call["args"] = args
        render_call["kwargs"] = kwargs
        return MessageSegment.text("leaderboard-image")

    monkeypatch.setattr(one_stroke, "leaderboard_cmd", matcher)
    monkeypatch.setattr(one_stroke, "get_current_season_bounds", lambda: (100, 200))
    monkeypatch.setattr(one_stroke, "_build_leaderboard_rows", lambda *_: [])
    monkeypatch.setattr(one_stroke, "kit_for_user", lambda user_id: selected_kit)
    monkeypatch.setattr(one_stroke, "render_image_segment", record_render)
    monkeypatch.setattr(
        one_stroke,
        "PG",
        lambda _: SimpleNamespace(
            element=MessageSegment.text("passive"),
            event=SimpleNamespace(referrer=event.referrer),
        ),
    )

    with pytest.raises(FinishedException):
        await one_stroke.handle_leaderboard(event)

    assert render_call["renderer"] is one_stroke.render_leaderboard
    assert render_call["kwargs"]["kit"] is selected_kit
