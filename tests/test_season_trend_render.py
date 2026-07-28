"""The season trend card: data mapping, themed rendering, and determinism."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PIL import Image

from utils import PassiveGenerator
from utils.images import image_segment
from plugins.render.kits import MangaKit
from plugins.render.kits import KasumiKit
from plugins.render.kits import MinimalKit
from plugins.render.kits import MidnightKit
from plugins.render.kits import BanGDreamKit
from plugins.inventory.models import Season
from plugins.inventory.models import SeasonRankSnapshot
from plugins.inventory.season_render import _chart_image
from plugins.inventory.season_render import _label_spans
from plugins.inventory.season_render import _thin_label_spans
from plugins.inventory.season_render import season_trend_data
from plugins.inventory.season_render import season_trend_page
from plugins.inventory.season_render import render_season_trend
from plugins.inventory.season_render import _spread_tick_indices

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


# ---------------------------------------------------------------------------
# Clipping and collision regressions, from live reports: y labels ran off the
# left edge with big Pt values, wide config-driven legend entries ran off the
# right edge, and clustered snapshot times overlapped their x labels.
#
# The detector runs on the chart raster (transparent background), where
# "non-background within N px of an edge" is a plain alpha check; the themed
# card paints decoration to its edges, so it cannot host this assertion.
# ---------------------------------------------------------------------------

_EDGE_BAND = 4


def _assert_edge_band_clean(chart: Image.Image, band: int = _EDGE_BAND) -> None:
    rgba = chart.convert("RGBA")
    width, height = rgba.size
    edges = {
        "left": (0, 0, band, height),
        "right": (width - band, 0, width, height),
        "top": (0, 0, width, band),
        "bottom": (0, height - band, width, height),
    }
    for side, box in edges.items():
        alpha_max = rgba.crop(box).getextrema()[3][1]
        assert alpha_max <= 8, f"chart ink within {band}px of the {side} edge"


def _six_digit_snapshots() -> list[SeasonRankSnapshot]:
    rows: list[SeasonRankSnapshot] = []
    for index in range(4 * 48):
        ts = _BASE_TS + index * 1800
        rows.append(_snapshot(ts, 10, 480_000 + 4_000 * index))
        rows.append(_snapshot(ts, 100, 120_000 + 900 * index))
    return rows


def _wide_legend_snapshots() -> list[SeasonRankSnapshot]:
    rows: list[SeasonRankSnapshot] = []
    for index in range(24):
        ts = _BASE_TS + index * 7200
        for rank in (100, 500, 1000, 2000, 5000):
            rows.append(_snapshot(ts, rank, 90_000 - rank * 10 + index * 260))
    return rows


def _clustered_snapshots() -> list[SeasonRankSnapshot]:
    times = [_BASE_TS + index * 600 for index in range(13)]
    times.append(_BASE_TS + 86_400 * 5)
    rows: list[SeasonRankSnapshot] = []
    for index, ts in enumerate(times):
        rows.append(_snapshot(ts, 10, 500 + 40 * index))
        rows.append(_snapshot(ts, 50, 200 + 15 * index))
    return rows


@pytest.mark.parametrize("kit_cls", [BanGDreamKit, KasumiKit])
@pytest.mark.parametrize(
    "snapshots",
    [_six_digit_snapshots, _wide_legend_snapshots, _clustered_snapshots],
    ids=["six-digit-values", "wide-legend-ranks", "clustered-times"],
)
def test_worst_case_charts_keep_ink_off_every_canvas_edge(
    kit_cls, snapshots
) -> None:
    data = season_trend_data(_season(), snapshots(), owner_name="香澄")
    chart = _chart_image(data, kit_cls())
    assert chart.size == (1440, 720)
    _assert_edge_band_clean(chart)
    # The full card must also still assemble around the measured chart.
    assert render_season_trend(data, kit_cls()).size[0] == 864


@pytest.mark.parametrize("kit_cls", [BanGDreamKit, KasumiKit])
def test_a_single_snapshot_chart_keeps_ink_off_every_canvas_edge(
    kit_cls,
) -> None:
    data = season_trend_data(_season(), [_snapshot(_BASE_TS, 10, 12345)])
    _assert_edge_band_clean(_chart_image(data, kit_cls()))


# The edge-band raster check cannot pin two of the live defects on its own:
# the pre-fix right-edge legend truncation happened to cut in a glyph gap
# (verified: the old code passes the band check on the wide-legend case), and
# the clustered-label overlap is mid-canvas where no edge band looks. These
# spies pin the fix behavior itself: the legend measurably refits to fewer
# columns, and crowded middle ticks are measurably thinned.


def test_wide_legend_case_measurably_refits_to_fewer_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plugins.inventory import season_render

    columns_used: list[int] = []
    real_build = season_render._build_legend

    def spy(ax, columns, tick_font, text_color):
        columns_used.append(columns)
        return real_build(ax, columns, tick_font, text_color)

    monkeypatch.setattr(season_render, "_build_legend", spy)
    data = season_trend_data(_season(), _wide_legend_snapshots())
    chart = _chart_image(data, BanGDreamKit())

    assert chart.size == (1440, 720)
    assert columns_used[0] == season_render._LEGEND_COLUMNS
    # 「第 5000 名」 entries at three columns measure wider than the axes; the
    # refit must have engaged, not just been present.
    assert columns_used[-1] < season_render._LEGEND_COLUMNS


@pytest.mark.parametrize(
    ("snapshots", "expected"),
    [(_clustered_snapshots, 2), (_six_digit_snapshots, 3)],
    ids=["clustered-thins-to-endpoints", "even-cadence-keeps-a-middle"],
)
def test_final_time_ticks_are_thinned_but_not_overthinned(
    monkeypatch: pytest.MonkeyPatch, snapshots, expected
) -> None:
    from plugins.inventory import season_render

    tick_sets: list[list[int]] = []
    real_ticks = season_render._set_time_ticks

    def spy(ax, ticks, tick_font, text_color):
        tick_sets.append(list(ticks))
        return real_ticks(ax, ticks, tick_font, text_color)

    monkeypatch.setattr(season_render, "_set_time_ticks", spy)
    data = season_trend_data(_season(), snapshots())
    _chart_image(data, BanGDreamKit())

    times = sorted({ts for series in data.series for ts, _ in series.points})
    final = tick_sets[-1]
    assert len(final) == expected
    assert final[0] == times[0]
    assert final[-1] == times[-1]


def test_worst_case_render_is_deterministic() -> None:
    kit = KasumiKit()
    data = season_trend_data(_season(), _wide_legend_snapshots())
    first = render_season_trend(data, kit)
    second = render_season_trend(data, kit)
    assert first.tobytes() == second.tobytes()


def test_spread_tick_indices_spread_by_value_not_by_index() -> None:
    # 13 clustered values then one far away: the index-based middle pick used
    # to land the middle tick in the same pixel column as the first one.
    values = [index * 600 for index in range(13)] + [86_400 * 5]

    indices = _spread_tick_indices(values, 3)

    assert indices[0] == 0
    assert indices[-1] == len(values) - 1
    assert len(indices) <= 3
    # The middle pick is the value nearest the range midpoint, not index 7.
    midpoint = values[-1] / 2
    for index in indices[1:-1]:
        assert abs(values[index] - midpoint) == min(
            abs(value - midpoint) for value in values
        )


def test_spread_tick_indices_keep_small_sets_verbatim() -> None:
    assert _spread_tick_indices([5], 4) == [0]
    assert _spread_tick_indices([5, 9, 12], 4) == [0, 1, 2]


def test_label_spans_follow_the_edge_alignment_rule() -> None:
    spans = _label_spans([100.0, 500.0, 900.0], 200.0)
    assert spans[0] == (100.0, 300.0)  # first extends right
    assert spans[1] == (400.0, 600.0)  # middle is centered
    assert spans[2] == (700.0, 900.0)  # last extends left


def test_thin_label_spans_drop_a_middle_that_crowds_the_first() -> None:
    spans = [(0.0, 200.0), (150.0, 350.0), (800.0, 1000.0)]
    assert _thin_label_spans(spans, 48.0) == [0, 2]


def test_thin_label_spans_keep_middles_with_room() -> None:
    spans = [(0.0, 200.0), (400.0, 600.0), (800.0, 1000.0)]
    assert _thin_label_spans(spans, 48.0) == [0, 1, 2]


def test_thin_label_spans_always_pin_first_and_last() -> None:
    assert _thin_label_spans([(0.0, 10.0)], 48.0) == [0]
    assert _thin_label_spans([(0.0, 10.0), (5.0, 15.0)], 48.0) == [0, 1]


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
