"""The /赛季排行 and /资料 matchers: card replies with text kept where promised.

The in-season Pt ladder used to be a 50-line text list; it is now one card
send (top ten plus the viewer's neighbourhood), while the off-season reply —
the settled final rankings — deliberately stays text. The /资料 flow proves
the avatar fetched by the handler reaches the profile assembly. Every service
call is stubbed at the plugin namespace; the real render pipeline runs.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from typing import Callable

import pytest
from nonebot.exception import FinishedException
from nonebot.adapters.satori import Message

import plugins.inventory as inventory
from plugins.render import PlayerIdentity
from plugins.render.kits import MinimalKit
from plugins.inventory.render import ProfileData


class RecordingMatcher:
    """Stands in for ``Matcher``: records every send, finish raises."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    async def send(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("send", message, kwargs))

    async def finish(self, message: Any = None, **kwargs: Any) -> None:
        self.calls.append(("finish", message, kwargs))
        raise FinishedException()


def _ranking_rows(count: int) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(user_id=f"member-{index}", quantity=9000 - index * 250)
        for index in range(count)
    ]


def _stub_season_rank(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows: list[SimpleNamespace],
    viewer_rank: int,
    viewer_points: int,
) -> None:
    season = SimpleNamespace(id=7, name="2026 第一赛季")
    monkeypatch.setattr(inventory, "get_current_season", lambda: season)
    monkeypatch.setattr(
        inventory,
        "get_active_ranking",
        lambda limit=50, season=None: rows[:limit],
    )
    monkeypatch.setattr(
        inventory,
        "get_user_season_rank",
        lambda user_id, season=None: (viewer_rank, viewer_points),
    )
    monkeypatch.setattr(inventory, "_display_name", lambda user_id: f"昵称{user_id}")
    monkeypatch.setattr(inventory, "kit_for_user", lambda user_id: MinimalKit())


async def test_season_rank_in_season_is_one_card_send(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    rows = _ranking_rows(30)
    rows[26] = SimpleNamespace(user_id="user", quantity=rows[26].quantity)
    _stub_season_rank(
        monkeypatch, rows=rows, viewer_rank=27, viewer_points=rows[26].quantity
    )

    matcher = RecordingMatcher()
    event = make_satori_event("/赛季排行")
    with pytest.raises(FinishedException):
        await inventory.handle_season_rank(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer


async def test_season_rank_offseason_stays_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    monkeypatch.setattr(inventory, "get_current_season", lambda: None)
    monkeypatch.setattr(
        inventory,
        "get_latest_season",
        lambda: SimpleNamespace(id=6, name="2025 第四赛季"),
    )
    monkeypatch.setattr(
        inventory,
        "list_settled_rankings",
        lambda season, limit=50: [
            SimpleNamespace(rank=1, user_id="member-0", final_points=9000)
        ],
    )
    monkeypatch.setattr(inventory, "_display_name", lambda user_id: f"昵称{user_id}")

    matcher = RecordingMatcher()
    event = make_satori_event("/赛季排行")
    with pytest.raises(FinishedException):
        await inventory.handle_season_rank(matcher, event)  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, _ = matcher.calls[0]
    assert "img" not in [segment.type for segment in message]
    text = str(message)
    assert "2025 第四赛季 最终排行榜" in text
    assert "1. 昵称member-0: 9000 Pt" in text
    # Off-season, the live ladder is the level one — the reply must say so.
    assert "等级排行" in text


def test_assemble_season_rank_slices_the_viewer_neighbourhood(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _ranking_rows(30)
    rows[26] = SimpleNamespace(user_id="user", quantity=rows[26].quantity)
    _stub_season_rank(
        monkeypatch, rows=rows, viewer_rank=27, viewer_points=rows[26].quantity
    )

    data = inventory._assemble_season_rank("user", SimpleNamespace(id=7, name="S1"))
    assert [row.rank for row in data.rows] == list(range(1, 11))
    # Viewer ±5: ranks 22 through 32, capped at the ladder's 30 entries.
    assert [row.rank for row in data.nearby] == list(range(22, 31))
    assert data.viewer_rank == 27
    assert data.viewer_name == "昵称user"
    assert any(row.name == "昵称user" for row in data.nearby)


def test_assemble_season_rank_pins_a_viewer_without_a_pt_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _ranking_rows(30)
    _stub_season_rank(monkeypatch, rows=rows, viewer_rank=31, viewer_points=0)

    data = inventory._assemble_season_rank("user", SimpleNamespace(id=7, name="S1"))
    assert data.nearby[-1].rank == 31
    assert data.nearby[-1].name == "昵称user"
    assert data.nearby[-1].points == 0
    # The window before the pinned row is real ladder tail: ranks 26-30.
    assert [row.rank for row in data.nearby[:-1]] == list(range(26, 31))


def test_assemble_season_rank_never_repeats_top_rows_in_the_neighbourhood(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A rank-11 viewer's ±5 window reaches into the top ten; the section must
    # start below the rows the top section already shows instead of showing
    # ranks 6-10 twice on one card.
    rows = _ranking_rows(30)
    rows[10] = SimpleNamespace(user_id="user", quantity=rows[10].quantity)
    _stub_season_rank(
        monkeypatch, rows=rows, viewer_rank=11, viewer_points=rows[10].quantity
    )

    data = inventory._assemble_season_rank("user", SimpleNamespace(id=7, name="S1"))
    assert [row.rank for row in data.rows] == list(range(1, 11))
    assert [row.rank for row in data.nearby] == list(range(11, 17))
    top_ranks = {row.rank for row in data.rows}
    assert not top_ranks & {row.rank for row in data.nearby}


def test_assemble_season_rank_short_ladder_pins_only_the_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Early-season shape: three Pt rows, viewer unranked. The top section
    # already shows the whole ladder, so 「你的附近」 is just the pinned
    # zero-Pt viewer row — never a second copy of the ladder.
    rows = _ranking_rows(3)
    _stub_season_rank(monkeypatch, rows=rows, viewer_rank=4, viewer_points=0)

    data = inventory._assemble_season_rank("user", SimpleNamespace(id=7, name="S1"))
    assert [row.rank for row in data.rows] == [1, 2, 3]
    assert [(row.rank, row.name, row.points) for row in data.nearby] == [
        (4, "昵称user", 0)
    ]


def test_assemble_season_rank_viewer_in_top_has_no_nearby(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _ranking_rows(30)
    rows[2] = SimpleNamespace(user_id="user", quantity=rows[2].quantity)
    _stub_season_rank(
        monkeypatch, rows=rows, viewer_rank=3, viewer_points=rows[2].quantity
    )

    data = inventory._assemble_season_rank("user", SimpleNamespace(id=7, name="S1"))
    assert data.nearby == ()


async def test_season_overview_in_season_is_one_card_send(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    now = 1_700_000_000
    season = SimpleNamespace(
        id=7,
        name="星之鼓动",
        start_time=now - 3600,
        end_time=now + 7 * 24 * 3600,
    )
    monkeypatch.setattr(inventory.time, "time", lambda: now)
    monkeypatch.setattr(
        inventory, "get_current_season", lambda now=None: season
    )
    monkeypatch.setattr(inventory, "get_next_season", lambda now=None: None)
    monkeypatch.setattr(
        inventory,
        "get_season_metadata",
        lambda season: {
            "reward_tiers": [],
            "gacha_banner": {"name": "星之鼓动 限定卡池"},
            "featured_characters": [{"name": "户山香澄"}],
        },
    )
    monkeypatch.setattr(
        inventory,
        "get_user_season_rank",
        lambda user_id, season=None: (7, 2480),
    )
    monkeypatch.setattr(inventory, "kit_for_user", lambda user_id: MinimalKit())

    matcher = RecordingMatcher()
    event = make_satori_event("/赛季")
    with pytest.raises(FinishedException):
        await inventory.handle_season(matcher, event, Message(""))  # type: ignore[arg-type]

    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer


async def test_season_overview_before_open_is_an_upcoming_card(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    now = 1_700_000_000
    season = SimpleNamespace(
        id=7,
        name="星之鼓动",
        start_time=now + 2 * 3600,
        end_time=now + 10 * 24 * 3600,
    )
    monkeypatch.setattr(inventory.time, "time", lambda: now)
    monkeypatch.setattr(
        inventory, "get_current_season", lambda now=None: None
    )
    monkeypatch.setattr(
        inventory, "get_next_season", lambda now=None: season
    )
    monkeypatch.setattr(
        inventory,
        "get_season_metadata",
        lambda season: {
            "reward_tiers": [],
            "gacha_banner": {"name": "星之鼓动 限定卡池"},
            "featured_characters": [{"name": "户山香澄"}],
        },
    )
    monkeypatch.setattr(
        inventory,
        "get_user_season_rank",
        lambda *args, **kwargs: pytest.fail("upcoming card queried a live rank"),
    )
    monkeypatch.setattr(inventory, "kit_for_user", lambda user_id: MinimalKit())

    matcher = RecordingMatcher()
    event = make_satori_event("/赛季")
    with pytest.raises(FinishedException):
        await inventory.handle_season(matcher, event, Message(""))  # type: ignore[arg-type]

    _, message, _ = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]


async def test_profile_passes_the_fetched_avatar_into_assembly(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    marker = object()
    recorded: dict[str, Any] = {}

    async def fake_avatar(user_id: str) -> Any:
        return marker

    def assemble(user_id: str, *, avatar: Any = None) -> ProfileData:
        recorded["user_id"] = user_id
        recorded["avatar"] = avatar
        return ProfileData(
            identity=PlayerIdentity(nickname="香澄", level=24),
            current_pt=1203,
        )

    monkeypatch.setattr(inventory, "get_avatar", fake_avatar)
    monkeypatch.setattr(inventory, "assemble_profile", assemble)
    monkeypatch.setattr(inventory, "kit_for_user", lambda user_id: MinimalKit())

    matcher = RecordingMatcher()
    event = make_satori_event("/资料")
    with pytest.raises(FinishedException):
        await inventory.handle_profile(matcher, event, Message(""))  # type: ignore[arg-type]

    assert recorded == {"user_id": "user", "avatar": marker}
    assert [kind for kind, _, _ in matcher.calls] == ["finish"]
    _, message, kwargs = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert kwargs["referrer"] is event.referrer


async def test_profile_description_subcommand_updates_long_text(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    description = "这是一段长文本" * 11
    recorded: dict[str, str] = {}
    monkeypatch.setattr(
        inventory,
        "set_profile_description",
        lambda user_id, value: recorded.update(user_id=user_id, value=value),
    )

    matcher = RecordingMatcher()
    event = make_satori_event(f"#资料 简介 {description}")
    with pytest.raises(FinishedException):
        await inventory.handle_profile(
            matcher, event, Message(f"简介 {description}")
        )  # type: ignore[arg-type]

    assert recorded == {"user_id": "user", "value": description}
    assert "已更新个人简介" in str(matcher.calls[0][1])


async def test_inventory_listing_has_stable_numbered_pages(
    monkeypatch: pytest.MonkeyPatch, make_satori_event: Callable[..., Any]
) -> None:
    rows = [
        SimpleNamespace(
            item_id=f"item-{index}",
            quantity=1,
            scope_type="permanent",
            scope_id="",
        )
        for index in range(12)
    ]
    monkeypatch.setattr(inventory, "list_inventory", lambda *args, **kwargs: rows)
    monkeypatch.setattr(
        inventory,
        "display_item_amount",
        lambda item_id, quantity: item_id,
    )
    monkeypatch.setattr(inventory, "display_scope", lambda *args: "")

    matcher = RecordingMatcher()
    event = make_satori_event("#仓库 2")
    with pytest.raises(FinishedException):
        await inventory.handle_inventory(
            matcher, event, Message("2")
        )  # type: ignore[arg-type]

    _, message, _ = matcher.calls[0]
    assert [segment.type for segment in message] == ["img", "qq:passive"]
    data = inventory._inventory_list_data(
        rows[10:],
        page=2,
        total_pages=2,
        offset=10,
        category="全部",
    )
    assert data.subtitle == "全部 · 第 2/2 页"
    assert [(row.index, row.name) for row in data.rows] == [
        (11, "item-10"),
        (12, "item-11"),
    ]
