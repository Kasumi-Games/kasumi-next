"""The season trend card: data mapping, themed rendering, and determinism."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from utils import PassiveGenerator
from utils.images import image_segment
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.render.kits import MidnightKit
from plugins.inventory.models import Season
from plugins.inventory.models import SeasonRankSnapshot
from plugins.inventory.season_render import season_trend_data
from plugins.inventory.season_render import season_trend_page
from plugins.inventory.season_render import render_season_trend

_BASE_TS = 1_752_000_000


def _season(name: str = "2026 第一赛季") -> Season:
    return Season(
        season_key="season-2026-1",
        season_number=1,
        name=name,
        start_time=_BASE_TS - 86_400,
        end_time=_BASE_TS + 86_400 * 30,
    )


def _snapshot(ts: int, rank: int, points: int | None) -> SeasonRankSnapshot:
    return SeasonRankSnapshot(season_id=1, captured_at=ts, rank=rank, points=points)


def _snapshots() -> list[SeasonRankSnapshot]:
    rows: list[SeasonRankSnapshot] = []
    for index in range(12):
        ts = _BASE_TS + index * 3600
        rows.append(_snapshot(ts, 10, 400 + 35 * index))
        rows.append(_snapshot(ts, 50, 120 + 12 * index))
    return rows


def _data(**overrides):
    defaults = dict(owner_name="香澄")
    defaults.update(overrides)
    return season_trend_data(_season(), _snapshots(), **defaults)


def test_no_snapshots_raise_for_the_text_empty_state() -> None:
    with pytest.raises(ValueError):
        season_trend_data(_season(), [])


def test_snapshots_without_points_raise_for_the_text_empty_state() -> None:
    empty = [_snapshot(_BASE_TS, 10, None), _snapshot(_BASE_TS, 50, None)]
    with pytest.raises(ValueError):
        season_trend_data(_season(), empty)


def test_data_groups_by_rank_sorts_by_time_and_drops_unfilled_slots() -> None:
    rows = [
        _snapshot(_BASE_TS + 7200, 50, 300),
        _snapshot(_BASE_TS, 50, 100),
        _snapshot(_BASE_TS + 3600, 50, None),
        _snapshot(_BASE_TS + 3600, 10, 900),
    ]
    data = season_trend_data(_season(), rows)

    assert [series.rank for series in data.series] == [10, 50]
    assert data.series[0].points == ((_BASE_TS + 3600, 900),)
    assert data.series[1].points == ((_BASE_TS, 100), (_BASE_TS + 7200, 300))


def test_data_falls_back_to_the_season_key_when_the_name_is_empty() -> None:
    data = season_trend_data(_season(name=""), _snapshots())
    assert data.season_name == "season-2026-1"


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit, MidnightKit])
def test_trend_renders_in_multiple_kits(kit_cls) -> None:
    image = render_season_trend(_data(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_trend_defaults_to_the_bangdream_kit() -> None:
    image = render_season_trend(_data())
    assert image.size[0] == 864


def test_trend_page_exposes_async_render() -> None:
    page = season_trend_page(_data(), MinimalKit())
    assert hasattr(page, "render_async")
    assert page.render().size[0] == 864


def test_a_single_rank_with_a_single_snapshot_still_renders() -> None:
    data = season_trend_data(_season(), [_snapshot(_BASE_TS, 10, 250)])
    image = render_season_trend(data, MinimalKit())
    assert image.size[0] == 864


def test_five_rank_series_wrap_the_legend_without_style_collisions() -> None:
    # ``snapshot_ranks`` is config-driven: five ranks wrap the legend onto a
    # second row and must each keep a distinct line style.
    from plugins.inventory.season_render import _LINE_STYLES

    assert len(set(_LINE_STYLES)) == len(_LINE_STYLES) >= 5

    rows = []
    for index in range(6):
        ts = _BASE_TS + index * 3600
        for rank in (1, 10, 20, 50, 100):
            rows.append(_snapshot(ts, rank, 2000 - rank * 10 + index * 5))
    data = season_trend_data(_season(), rows)
    image = render_season_trend(data, MinimalKit())
    assert image.size[0] == 864


def test_the_render_is_deterministic() -> None:
    kit = MinimalKit()
    first = render_season_trend(_data(), kit)
    second = render_season_trend(_data(), kit)
    assert first.tobytes() == second.tobytes()


def test_image_reply_keeps_the_passive_element(
    make_satori_event: Callable[..., object],
) -> None:
    event = make_satori_event("/赛季趋势")
    passive_generator = PassiveGenerator(event)  # type: ignore[arg-type]

    message = (
        image_segment(render_season_trend(_data(), MinimalKit()))
        + passive_generator.element
    )

    assert [segment.type for segment in message] == ["img", "qq:passive"]
    assert message[1].data["id"] == event.message.id  # type: ignore[attr-defined]
