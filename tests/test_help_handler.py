"""The /help matcher: which branch renders, and what the reply is made of."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageSegment

from utils import PassiveGenerator
from plugins.help import HELP_ENTRIES
from plugins.help import escape_text
from utils.images import image_segment
from plugins.help.render import render_detail
from plugins.render.kits import KITS
from plugins.help.entries import find_entries


def test_an_image_reply_keeps_the_passive_element(
    make_satori_event: Callable[..., object],
) -> None:
    event = make_satori_event("/help 娶群友")
    passive_generator = PassiveGenerator(event)  # type: ignore[arg-type]
    entry = find_entries(HELP_ENTRIES, "娶群友")[0]

    message = (
        image_segment(render_detail(entry, KITS["minimal"]()))
        + passive_generator.element
    )

    assert isinstance(message, Message)
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert message[1].data["id"] == event.message.id  # type: ignore[attr-defined]
    assert passive_generator.event.referrer is event.referrer  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "token", ["<script>", 'a"b', "香澄&", "完全不存在的功能"]
)
def test_the_miss_reply_escapes_whatever_was_typed(token: str) -> None:
    assert find_entries(HELP_ENTRIES, token) == ()
    escaped = escape_text(f"没有叫「{token}」的功能")
    assert "<" not in escaped and ">" not in escaped and '"' not in escaped
    assert MessageSegment.text(escaped)


def test_an_ambiguous_token_resolves_to_several_entries() -> None:
    names = [entry.name for entry in find_entries(HELP_ENTRIES, "bzd")]
    assert names == ["猜卡面", "猜谱面"]
