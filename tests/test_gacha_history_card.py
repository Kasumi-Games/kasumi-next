"""The /抽卡 记录 pull-history card.

Live round 3: the history reply was a terse text list. It is now a card —
rarity chip by shape, item name, product-timezone pull time, a
「第 x/y 页 · 共 n 抽」 footer, and the requester's pity line — with ★6 rows
lifted onto a nested panel (hue-free, so it survives the manga kit). Pinned
here:

1. ``history_page_data`` assembly: name mapping with raw-id fallback, grant
   note decoding, page numbers, pity with and without an open banner.
2. Product-timezone time wording: 今天/昨天 by calendar day, then dates.
3. Render smoke across kits, fixed width, deterministic rasters.
4. The ★6 row is a panel while other rarities stay open rows.
5. The matcher reply paths: one image send, empty history still a card,
   errors (including a non-numeric page) stay text.
6. The render module stays DB-free.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any
from typing import Callable
from pathlib import Path

import pytest
from nonebot.exception import FinishedException
from nonebot.adapters.satori import Message

import plugins.gacha as gacha
from utils.clock import BOT_TZ
from plugins.render.kits import MangaKit
from plugins.render.kits import KasumiKit
from plugins.render.kits import MinimalKit
from plugins.gacha.render import HistoryRow
from plugins.gacha.render import HistoryPageData
from plugins.gacha.render import history as history_module
from plugins.gacha.render import history_page
from plugins.gacha.render import render_history
from plugins.gacha.render import history_page_data
from plugins.gacha.service import HistoryPage
from plugins.render.layout import Frame

ROOT = Path(__file__).resolve().parents[1]

PAGE_WIDTH = 864  # CONTENT_WIDTH + 2 * PAGE_PADDING


def _ts(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> float:
    return datetime.datetime(
        year, month, day, hour, minute, tzinfo=BOT_TZ
    ).timestamp()


def _pull_row(
    item_id: str = "standing_art_placeholder_r3_001",
    rarity: int = 3,
    created_at: float | None = None,
    message: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        item_id=item_id,
        rarity=rarity,
        created_at=created_at if created_at is not None else _ts(2026, 7, 20),
        message=message,
    )


def _display_data(**overrides: Any) -> HistoryPageData:
    defaults: dict[str, Any] = dict(
        rows=(
            HistoryRow(6, "户山香澄 抬头看，星星在跳动立绘", "今天 21:04", ""),
            HistoryRow(3, "美竹兰 脚尖的方向立绘", "今天 21:04", "盆栽 +6"),
            HistoryRow(5, "市谷有咲 向着大海展翅的天马立绘", "昨天 09:31", ""),
            HistoryRow(4, "山吹沙绫 无私的陪伴者立绘", "07-20 18:22", "盆栽 +12"),
        ),
        page=1,
        total_pages=3,
        total=25,
        pity_count=12,
        hard_pity=90,
    )
    defaults.update(overrides)
    return HistoryPageData(**defaults)


# ---------------------------------------------------------------------------
# history_page_data: pure assembly
# ---------------------------------------------------------------------------


def test_history_page_data_maps_rows_names_and_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        history_module, "bot_today", lambda: datetime.date(2026, 7, 27)
    )
    history = HistoryPage(
        rows=[
            _pull_row(
                "standing_art_kasumi_starbeat",
                rarity=6,
                created_at=_ts(2026, 7, 27, 21, 4),
                message="already_owned_compensated:60",
            ),
            _pull_row("item_missing_from_catalog", rarity=3),
        ],
        page=2,
        total_pages=5,
        total=42,
    )
    data = history_page_data(
        history,
        pity_count=17,
        hard_pity=90,
        item_names={"standing_art_kasumi_starbeat": "户山香澄 抬头看，星星在跳动立绘"},
    )
    assert data.page == 2
    assert data.total_pages == 5
    assert data.total == 42
    assert data.pity_count == 17
    assert data.hard_pity == 90
    first, second = data.rows
    assert first.name == "户山香澄 抬头看，星星在跳动立绘"
    assert first.rarity == 6
    assert first.time_text == "今天 21:04"
    assert first.note == "盆栽 +60"
    # Ids missing from the mapping fall back to the raw item id.
    assert second.name == "item_missing_from_catalog"
    assert second.note == ""


def test_offseason_history_keeps_a_bare_pity_count() -> None:
    history = HistoryPage(rows=[_pull_row()], page=1, total_pages=1, total=1)
    data = history_page_data(history, pity_count=3, item_names={})
    assert data.hard_pity is None
    joined = " ".join(_collect_text(history_page(data, MinimalKit()).child))
    assert "保底计数 3" in joined
    assert "3/" not in joined


def test_time_text_speaks_the_product_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        history_module, "bot_today", lambda: datetime.date(2026, 7, 27)
    )
    assert history_module._time_text(_ts(2026, 7, 27, 21, 4)) == "今天 21:04"
    # Just past product-timezone midnight is still 今天, never an hour count.
    assert history_module._time_text(_ts(2026, 7, 27, 0, 1)) == "今天 00:01"
    assert history_module._time_text(_ts(2026, 7, 26, 9, 31)) == "昨天 09:31"
    assert history_module._time_text(_ts(2026, 7, 20, 18, 22)) == "07-20 18:22"
    assert (
        history_module._time_text(_ts(2025, 12, 31, 23, 59)) == "2025-12-31 23:59"
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kit_cls", [KasumiKit, MinimalKit, MangaKit])
def test_history_page_renders(kit_cls) -> None:
    image = render_history(_display_data(), kit_cls())
    assert image.size[0] == PAGE_WIDTH
    assert image.size[1] > 0


def test_history_page_defaults_to_the_bangdream_kit() -> None:
    assert render_history(_display_data()).size[0] == PAGE_WIDTH


def test_history_render_is_deterministic() -> None:
    kit = KasumiKit()
    first = render_history(_display_data(), kit)
    second = render_history(_display_data(), kit)
    assert first.tobytes() == second.tobytes()


def test_history_texts_land_on_the_page() -> None:
    joined = " ".join(_collect_text(history_page(_display_data(), MinimalKit()).child))
    assert "抽卡记录" in joined
    assert "户山香澄 抬头看，星星在跳动立绘" in joined
    assert "★6" in joined
    assert "★3" in joined
    assert "今天 21:04" in joined
    assert "盆栽 +6" in joined
    assert "盆栽 +12" in joined
    assert "保底计数 12/90" in joined
    assert "第 1/3 页 · 共 25 抽" in joined
    assert "/抽卡 记录 <页码> 翻页" in joined


def test_single_page_history_hides_the_paging_hint() -> None:
    data = _display_data(total_pages=1, total=4)
    joined = " ".join(_collect_text(history_page(data, MinimalKit()).child))
    assert "第 1/1 页 · 共 4 抽" in joined
    assert "翻页" not in joined


def test_six_star_rows_ride_a_panel_and_others_stay_open() -> None:
    kit = MinimalKit()
    lifted = history_module._row(kit, HistoryRow(6, "六星", "今天 12:00"))
    plain = history_module._row(kit, HistoryRow(5, "五星", "今天 12:00"))
    assert isinstance(plain, Frame)
    assert not isinstance(lifted, Frame)  # the kit's own panel surface
    # The chip is a filled badge; the plain row keeps the bare numeral.
    assert "★6" in _collect_text(lifted)
    assert "★5" in _collect_text(plain)


def test_empty_history_is_an_empty_state_card() -> None:
    data = _display_data(rows=(), page=1, total_pages=1, total=0, pity_count=0)
    image = render_history(data, MinimalKit())
    assert image.size[0] == PAGE_WIDTH
    joined = " ".join(_collect_text(history_page(data, MinimalKit()).child))
    assert "暂无抽卡记录" in joined
    assert "共 0 抽" in joined


def test_history_render_module_never_touches_a_database() -> None:
    source = (ROOT / "plugins/gacha/render/history.py").read_text(encoding="utf-8")
    assert "inventory.service" not in source
    assert "season_service" not in source
    assert "get_item" not in source
    assert "get_session" not in source
    assert "sqlalchemy" not in source


# ---------------------------------------------------------------------------
# The matcher reply paths
# ---------------------------------------------------------------------------


class RecordingMatcher:
    """Stands in for ``Matcher``: records every send, finish raises."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    async def send(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("send", message, kwargs))

    async def finish(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("finish", message, kwargs))
        raise FinishedException()


def _patch_history_flow(
    monkeypatch: pytest.MonkeyPatch, history: HistoryPage
) -> None:
    monkeypatch.setattr(gacha, "get_history", lambda user_id, page: history)
    monkeypatch.setattr(
        gacha, "get_state", lambda user_id: SimpleNamespace(pity_count=2)
    )
    monkeypatch.setattr(gacha, "get_current_banner", lambda: None)
    monkeypatch.setattr(gacha, "kit_for_user", lambda user_id: MinimalKit())
    monkeypatch.setattr(gacha, "_item_maps", lambda item_ids: ({}, {}))


async def test_history_replies_with_one_card_send(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    _patch_history_flow(
        monkeypatch,
        HistoryPage(rows=[_pull_row()], page=1, total_pages=1, total=1),
    )
    matcher = RecordingMatcher()
    event = make_satori_event("/抽卡 记录")
    with pytest.raises(FinishedException):
        await gacha.handle_gacha(matcher, event, Message("记录"))  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer


async def test_empty_history_still_replies_with_the_card(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    _patch_history_flow(
        monkeypatch, HistoryPage(rows=[], page=1, total_pages=1, total=0)
    )
    matcher = RecordingMatcher()
    event = make_satori_event("/抽卡 记录")
    with pytest.raises(FinishedException):
        await gacha.handle_gacha(matcher, event, Message("记录"))  # type: ignore[arg-type]

    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer


async def test_non_numeric_page_stays_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    matcher = RecordingMatcher()
    event = make_satori_event("/抽卡 记录 abc")
    with pytest.raises(FinishedException):
        await gacha.handle_gacha(matcher, event, Message("记录 abc"))  # type: ignore[arg-type]

    _, message, kwargs = matcher.calls[0]
    assert "img" not in [segment.type for segment in message]
    assert "页码需要是数字" in str(message)
    assert kwargs["referrer"] is event.referrer


async def test_history_failure_degrades_to_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    def boom(user_id: str, page: int) -> HistoryPage:
        raise RuntimeError("boom")

    monkeypatch.setattr(gacha, "get_history", boom)
    matcher = RecordingMatcher()
    event = make_satori_event("/抽卡 记录")
    with pytest.raises(FinishedException):
        await gacha.handle_gacha(matcher, event, Message("记录"))  # type: ignore[arg-type]

    _, message, kwargs = matcher.calls[0]
    assert "img" not in [segment.type for segment in message]
    assert "抽卡失败" in str(message)
    assert kwargs["referrer"] is event.referrer


def _collect_text(component) -> list[str]:
    """Collect text nodes in document (preorder) order."""

    texts: list[str] = []

    def visit(node) -> None:
        text = getattr(node, "text", None)
        if isinstance(text, str):
            texts.append(text)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
            else:
                visit(value)

    visit(component)
    return texts
