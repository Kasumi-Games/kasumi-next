"""Render tests for the inventory plugin's season Pt ladder card."""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.render import PlayerIdentity
from plugins.inventory.render import SeasonRankRow
from plugins.inventory.render import SeasonRankData
from plugins.inventory.render import season_rank_page
from plugins.inventory.render import render_season_rank

ROOT = Path(__file__).resolve().parents[1]


def _row(rank: int, name: str | None = None, points: int | None = None) -> SeasonRankRow:
    return SeasonRankRow(
        rank=rank,
        name=name if name is not None else f"成员{rank}",
        points=points if points is not None else 12000 - rank * 400,
    )


def _data(*, viewer_in_top: bool = False) -> SeasonRankData:
    rows = tuple(_row(rank) for rank in range(1, 11))
    if viewer_in_top:
        rows = (_row(1, name="香澄"),) + rows[1:]
        return SeasonRankData(
            season_name="2026 第一赛季",
            rows=rows,
            nearby=(),
            viewer_name="香澄",
            viewer_rank=1,
            viewer_points=11600,
        )
    nearby = tuple(
        _row(rank, name="香澄" if rank == 27 else None, points=4000 - rank * 60)
        for rank in range(22, 33)
    )
    return SeasonRankData(
        season_name="2026 第一赛季",
        rows=rows,
        nearby=nearby,
        viewer_name="香澄",
        viewer_rank=27,
        viewer_points=4000 - 27 * 60,
    )


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


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_season_rank_card_renders(kit_cls):
    image = render_season_rank(_data(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_season_rank_card_defaults_to_the_bangdream_kit():
    assert render_season_rank(_data()).size[0] == 864


def test_season_rank_rows_render_avatar_frames() -> None:
    frame = (
        ROOT
        / "plugins/inventory/resources/items/avatar_frames/frame_starbeat_top50.png"
    )
    first = _row(1)
    first = SeasonRankRow(
        rank=first.rank,
        name=first.name,
        points=first.points,
        user_id="u1",
        identity=PlayerIdentity("成员1", 42, avatar_frame=frame),
    )
    data = SeasonRankData(
        season_name="2026 第一赛季",
        rows=(first,),
        nearby=(),
        viewer_name="别人",
        viewer_rank=2,
        viewer_points=1,
    )
    stack = [season_rank_page(data, MinimalKit()).child]
    sources: list[object] = []
    while stack:
        node = stack.pop()
        source = getattr(node, "source", None)
        if source is not None:
            sources.append(source)
        for attr in ("children", "child"):
            value = getattr(node, attr, None)
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            elif value is not None:
                stack.append(value)
    assert frame in sources


def test_season_rank_card_names_the_season_and_the_ladder():
    joined = " ".join(_collect_text(season_rank_page(_data(), MinimalKit()).child))
    assert "赛季排行" in joined
    assert "2026 第一赛季 · Pt 榜" in joined


def test_season_rank_card_nearby_section_when_viewer_is_outside_top():
    page = season_rank_page(_data(), MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "你的附近" in joined
    assert "香澄" in joined
    # Viewer's row value and the footer standing.
    assert "2,380 Pt" in joined
    assert "你当前排名第 27 名 · 2,380 Pt" in joined


def test_season_rank_card_viewer_in_top_has_no_nearby_section():
    page = season_rank_page(_data(viewer_in_top=True), MinimalKit())
    texts = _collect_text(page.child)
    assert texts.count("香澄") == 1
    joined = " ".join(texts)
    assert "你的附近" not in joined
    assert "你当前排名第 1 名 · 11,600 Pt" in joined


def test_season_rank_card_empty_state():
    data = SeasonRankData(
        season_name="2026 第一赛季",
        rows=(),
        nearby=(),
        viewer_name="香澄",
        viewer_rank=1,
        viewer_points=0,
    )
    page = season_rank_page(data, MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "本赛季还没有 Pt 记录" in joined
    assert page.render().size[0] == 864


def test_season_rank_render_is_deterministic():
    kit = MinimalKit()
    data = _data()
    assert (
        render_season_rank(data, kit).tobytes()
        == render_season_rank(data, kit).tobytes()
    )


def test_season_rank_card_strings_carry_no_emoji():
    for text in _collect_text(season_rank_page(_data(), MinimalKit()).child):
        assert all(ord(char) < 0x1F000 for char in text), text


def test_season_rank_render_module_never_touches_a_database():
    # No-DB rule: the handler assembles the dataclasses; the render module
    # must not import services or open a session.
    source = (ROOT / "plugins/inventory/render/season_rank.py").read_text(
        encoding="utf-8"
    )
    assert "get_session" not in source
    assert "sqlalchemy" not in source
    assert "season_service" not in source
    assert "monetary" not in source
