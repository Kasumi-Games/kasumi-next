"""The season trend card — what ``/赛季趋势`` replies with.

matplotlib still draws the line geometry (a time-series polyline is exactly
what it is good at), but nothing visual is matplotlib's own: the figure is
transparent, every line, tick, and legend entry takes its color from the
active kit's palette, chart text uses the shared CJK font, and the raster is
embedded in a themed :func:`utils.cards.card_page` with the season name, the
per-rank threshold rows, and a snapshot-window footer — a card in the
player's theme, not a naked chart.

The Agg backend is selected explicitly and the figure is driven through the
object-oriented API (``Figure`` + ``FigureCanvasAgg``) with no pyplot and no
rcParams mutation, so a render is deterministic and does not leak global
state.

Data arrives pre-assembled in :class:`SeasonTrendData`: the handler fetches
the season and its snapshot rows on the event-loop thread and maps them
through :func:`season_trend_data`; this module touches no database.

Series identity is carried by line style (solid/dashed/…) plus the legend,
never by hue alone — the kit palettes have no categorical ramp and the
monochrome kit must stay readable — so every polyline draws in
``kit.text_color`` (the one color guaranteed readable on its own panel in all
kits), with ``kit.primary`` appearing only as the endpoint marker's fill
behind a ``text_color`` edge.
"""

from __future__ import annotations

from io import BytesIO
from typing import Sequence
from dataclasses import dataclass

import matplotlib

from utils.clock import format_ts

matplotlib.use("Agg")

from PIL import Image  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402

from utils.cards import LABEL_SIZE  # noqa: E402
from utils.cards import INNER_WIDTH  # noqa: E402
from utils.cards import stat_row  # noqa: E402
from utils.cards import card_page  # noqa: E402
from utils.cards import panel_section  # noqa: E402
from plugins.render import Fill  # noqa: E402
from plugins.render import Fixed  # noqa: E402
from plugins.render import Frame  # noqa: E402
from plugins.render import VStack  # noqa: E402
from plugins.render import BaseKit  # noqa: E402
from plugins.render import AutoPage  # noqa: E402
from plugins.render import Component  # noqa: E402
from plugins.render.color import ColorLike  # noqa: E402
from plugins.render.color import normalize_color  # noqa: E402
from plugins.render.kits.fonts import CHINESE_FONT  # noqa: E402
from plugins.render.kits.bangdream import BanGDreamKit  # noqa: E402

from .models import Season  # noqa: E402
from .models import SeasonRankSnapshot  # noqa: E402

#: Logical height of the chart slot inside the panel; the width is
#: ``INNER_WIDTH``. The figure rasters at ``_CHART_SCALE`` times this so it
#: survives the page's pixel-ratio-2 supersample without going soft.
_CHART_HEIGHT = 360

#: Figure raster oversampling, matching the page's ``pixel_ratio``.
_CHART_SCALE = 2

_CHART_DPI = 200

#: Line style cycle. The style is the series encoding — it survives the
#: monochrome kit, color-vision deficiencies, and chat-client downscaling —
#: while every line shares ``kit.text_color``.
_LINE_STYLES: tuple[str | tuple[int, tuple[int, ...]], ...] = (
    "solid",
    (0, (6, 3)),
    (0, (2, 2)),
    (0, (8, 3, 2, 3)),
    (0, (1, 2)),
    (0, (10, 3, 2, 3, 2, 3)),
)

#: Legend entries per row, upper bound. Three CJK entries with their
#: line-style handles usually fit the figure width, but the rank numbers are
#: config-driven (「第 5000 名」 is wider than 「第 1 名」), so
#: :func:`_chart_image` measures the rendered legend and drops to fewer
#: columns whenever the measured width would overrun the axes.
_LEGEND_COLUMNS = 3

#: Upper bound on horizontal time ticks. The real count is measured: as many
#: evenly spread ticks as fit the axes width at the rendered label width, and
#: any tick whose label would still crowd a neighbor (snapshots cluster, so
#: even spacing in time is not even spacing in pixels) is thinned out.
_MAX_X_TICKS = 4

#: Clear raster pixels kept between neighboring time labels.
_X_TICK_GAP = 48

#: Raster pixels of breathing room between any chart ink and the figure edge.
#: The regression tests assert a 4 px clean band, so this must stay above it.
_EDGE_PAD = 8

#: Raster gap between the axes top and the legend block.
_LEGEND_GAP = 24


@dataclass(frozen=True)
class TrendSeries:
    """One rank-threshold polyline.

    Attributes:
        rank: Ladder rank this series tracks (第 N 名的 Pt).
        points: ``(captured_at, points)`` pairs in capture order. Snapshots
            where nobody held the rank are already dropped; never empty.
    """

    rank: int
    points: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class SeasonTrendData:
    """Everything the trend card shows, assembled by :func:`season_trend_data`.

    Attributes:
        season_name: Player-facing season name (the page title).
        series: Rank series sorted by rank ascending; never empty.
        owner_name: Requester's nickname for the theme signature on this
            shared surface, or ``None`` to omit.
    """

    season_name: str
    series: tuple[TrendSeries, ...]
    owner_name: str | None = None


def season_trend_data(
    season: Season,
    snapshots: Sequence[SeasonRankSnapshot],
    *,
    owner_name: str | None = None,
) -> SeasonTrendData:
    """Map season snapshot rows onto the trend card's data.

    Pure: the handler fetches ``snapshots`` (``season_service.list_snapshots``)
    on the event-loop thread and passes them in.

    Args:
        season: The season the snapshots belong to.
        snapshots: Snapshot rows in any order.
        owner_name: Requester's nickname for the theme signature.

    Returns:
        Data ready for :func:`season_trend_page`.

    Raises:
        ValueError: When there are no snapshots, or none carries a plottable
            point value. The handler answers these with text, per the
            empty-state rule.
    """

    if not snapshots:
        raise ValueError("no snapshots")

    by_rank: dict[int, list[tuple[int, int]]] = {}
    for snapshot in snapshots:
        if snapshot.points is None:
            continue
        by_rank.setdefault(snapshot.rank, []).append(
            (snapshot.captured_at, snapshot.points)
        )
    if not by_rank:
        raise ValueError("no plottable snapshots")

    series = tuple(
        TrendSeries(rank=rank, points=tuple(sorted(points)))
        for rank, points in sorted(by_rank.items())
    )
    return SeasonTrendData(
        season_name=season.name or season.season_key,
        series=series,
        owner_name=owner_name,
    )


def render_season_trend(
    data: SeasonTrendData, kit: BaseKit | None = None
) -> Image.Image:
    """Render the season trend card.

    Args:
        data: Pre-assembled trend data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return season_trend_page(data, kit).render()


def season_trend_page(
    data: SeasonTrendData, kit: BaseKit | None = None
) -> AutoPage:
    """Build the season trend page without rendering it.

    The handler uses this so the raster is offloaded to
    ``await page.render_async()``.

    Args:
        data: Pre-assembled trend data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    rows: list[Component] = [
        kit.image(
            _chart_image(data, kit),
            width=Fixed(INNER_WIDTH),
            height=Fixed(_CHART_HEIGHT),
        ),
        kit.separator(length=Fill()),
    ]
    # The numbers the player actually reads: the latest threshold per rank, in
    # full text color. The chart above them is the shape of how they got there.
    rows.extend(
        stat_row(kit, f"第 {series.rank} 名门槛", f"{series.points[-1][1]} Pt")
        for series in data.series
    )

    return card_page(
        kit,
        title=data.season_name,
        subtitle="赛季趋势 · Pt 门槛",
        body=panel_section(kit, VStack(rows, gap=18, align="stretch")),
        footer=_footer(kit, data),
        owner_name=data.owner_name,
    )


def _footer(kit: BaseKit, data: SeasonTrendData) -> Component:
    """The snapshot window. Content the player reads, so full text color."""

    times = sorted({ts for series in data.series for ts, _ in series.points})
    first = _format_time(times[0])
    last = _format_time(times[-1])
    window = first if first == last else f"{first} 至 {last}"
    return Frame(
        kit.text(
            f"{window} · 共 {len(times)} 次快照",
            font_size=LABEL_SIZE,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )


def _chart_image(data: SeasonTrendData, kit: BaseKit) -> Image.Image:
    """Rasterize the threshold polylines with the kit's palette.

    The figure is fully transparent so the kit's panel fill shows through;
    everything drawn on it uses palette colors, and all chart text is at least
    ``LABEL_SIZE`` logical pixels once the page downsamples.

    Layout is measured, not guessed: the figure margins come from the rendered
    extents of the tick labels and the legend (a draw pass on the Agg canvas,
    then :meth:`~matplotlib.text.Text.get_window_extent`), so six-digit Pt
    values widen the left margin instead of clipping, a config-driven
    「第 5000 名」 legend refits to fewer columns instead of running off the
    right edge, and time ticks are spread by value and thinned by rendered
    label width so clustered snapshots cannot overlap their labels. Every
    measurement draw is a deterministic function of ``data`` and the kit
    palette, so renders stay byte-identical.
    """

    text = _mpl_color(kit.text_color)
    muted = _mpl_color(kit.muted_text_color)
    accent = _mpl_color(getattr(kit, "primary", None) or kit.text_color)
    tick_font = _font_properties(_pt(LABEL_SIZE))

    figure_width = INNER_WIDTH * _CHART_SCALE
    figure_height = _CHART_HEIGHT * _CHART_SCALE
    fig = Figure(
        figsize=(figure_width / _CHART_DPI, figure_height / _CHART_DPI),
        dpi=_CHART_DPI,
    )
    canvas = FigureCanvasAgg(fig)
    fig.patch.set_alpha(0.0)

    ax = fig.add_subplot()
    # Provisional margins for the measurement pass; the real ones are computed
    # from rendered extents below.
    fig.subplots_adjust(left=0.11, right=0.98, bottom=0.15, top=0.85)
    ax.set_facecolor((0.0, 0.0, 0.0, 0.0))

    for index, series in enumerate(data.series):
        xs = [ts for ts, _ in series.points]
        ys = [points for _, points in series.points]
        ax.plot(
            xs,
            ys,
            color=text,
            linewidth=1.8,
            linestyle=_LINE_STYLES[index % len(_LINE_STYLES)],
            solid_capstyle="round",
            label=f"第 {series.rank} 名",
        )
        # Endpoint marker: the "now" of each line. Primary is only a fill
        # accent — the text-color edge keeps it visible in kits whose primary
        # sits close to the panel fill. The axes margins below keep the
        # marker's full radius inside the axes box, so the default clipping
        # never cuts it.
        ax.plot(
            [xs[-1]],
            [ys[-1]],
            linestyle="none",
            marker="o",
            markersize=6,
            markerfacecolor=accent,
            markeredgecolor=text,
            markeredgewidth=1.1,
        )

    ax.margins(x=0.04, y=0.16)
    ax.grid(True, axis="y", color=muted, alpha=0.45, linewidth=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(muted)
        ax.spines[side].set_linewidth(0.9)
    ax.tick_params(color=muted, width=0.9)

    ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    ylim = ax.get_ylim()
    yticks = [tick for tick in ax.get_yticks() if ylim[0] <= tick <= ylim[1]]
    ax.set_yticks(yticks)
    y_labels = ax.set_yticklabels(
        [str(int(tick)) for tick in yticks],
        fontproperties=tick_font,
        color=text,
    )
    ax.set_ylim(ylim)

    # Candidate time ticks at the upper bound; the final set is cut down to
    # what the measured label width says fits.
    times = sorted({ts for series in data.series for ts, _ in series.points})
    candidates = [
        times[index]
        for index in _spread_tick_indices(times, _MAX_X_TICKS)
    ]
    x_labels = _set_time_ticks(ax, candidates, tick_font, text)

    legend = None
    if len(data.series) > 1:
        legend = _build_legend(
            ax, min(len(data.series), _LEGEND_COLUMNS), tick_font, text
        )

    # Measurement pass: rendered extents of everything that lives in the
    # figure margins. Overhangs are measured *positionally* against the axes
    # box — label offset from the spine is tick length plus pad plus font
    # metrics, and measuring the rendered geometry beats re-deriving that
    # stack of rcParam defaults. An overhang is margin-invariant, so extents
    # taken at the provisional margins stay exact after the final adjust.
    canvas.draw()
    renderer = canvas.get_renderer()
    axes_box = ax.get_window_extent(renderer)
    left_overhang = max(
        (
            axes_box.x0 - label.get_window_extent(renderer).x0
            for label in y_labels
        ),
        default=0.0,
    )
    y_label_height = max(
        (label.get_window_extent(renderer).height for label in y_labels),
        default=0.0,
    )
    x_label_width = max(
        (label.get_window_extent(renderer).width for label in x_labels),
        default=0.0,
    )
    bottom_overhang = max(
        (
            axes_box.y0 - label.get_window_extent(renderer).y0
            for label in x_labels
        ),
        default=0.0,
    )

    left = min((left_overhang + _EDGE_PAD) / figure_width, 0.35)
    right = 1.0 - (2 * _EDGE_PAD) / figure_width
    bottom = min((bottom_overhang + _EDGE_PAD) / figure_height, 0.30)

    if legend is not None:
        # Refit the legend to the measured axes width: fewer columns instead
        # of clipping when the config-driven rank numbers run wide.
        available = (right - left) * figure_width
        columns = min(len(data.series), _LEGEND_COLUMNS)
        while (
            columns > 1
            and legend.get_window_extent(renderer).width > available
        ):
            columns -= 1
            legend = _build_legend(ax, columns, tick_font, text)
            canvas.draw()
        legend_height = legend.get_window_extent(renderer).height
        top_reserve = legend_height + _LEGEND_GAP + _EDGE_PAD
    else:
        # No legend: only the topmost y label can poke above the axes box,
        # by at most half its height.
        top_reserve = y_label_height / 2.0 + _EDGE_PAD
    top = max(1.0 - top_reserve / figure_height, 0.50)

    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top)
    if legend is not None:
        # Anchor the legend a fixed gap above the (now final) axes top.
        axes_height = (top - bottom) * figure_height
        legend.set_bbox_to_anchor(
            (0.0, 1.0 + _LEGEND_GAP / axes_height, 1.0, 0.0)
        )

    # Final time ticks at the final geometry: the largest evenly spread set
    # whose rendered labels all clear each other, backing off one tick at a
    # time. Even spacing in time is not even spacing in pixels — clustered
    # snapshots put two ticks in almost the same pixel column — so each count
    # is checked against the measured label spans, and two ticks (first and
    # last, edge-aligned) always fit at this figure width.
    axes_left = left * figure_width
    axes_width = (right - left) * figure_width
    xlim = ax.get_xlim()
    time_span = xlim[1] - xlim[0]
    ticks = [times[0]]
    for count in range(min(_MAX_X_TICKS, len(times)), 1, -1):
        candidate = [
            times[index] for index in _spread_tick_indices(times, count)
        ]
        positions = [
            axes_left + (tick - xlim[0]) / time_span * axes_width
            for tick in candidate
        ]
        spans = _label_spans(positions, x_label_width)
        kept = _thin_label_spans(spans, _X_TICK_GAP)
        ticks = [candidate[index] for index in kept]
        if len(kept) == len(candidate):
            break
    _set_time_ticks(ax, ticks, tick_font, text)

    buffer = BytesIO()
    fig.savefig(buffer, format="png", transparent=True)
    buffer.seek(0)
    chart = Image.open(buffer)
    chart.load()
    return chart


def _build_legend(ax, columns: int, tick_font, text_color):
    """(Re)create the above-the-axes legend at ``columns`` columns."""

    legend = ax.legend(
        loc="lower left",
        bbox_to_anchor=(0.0, 1.0, 1.0, 0.0),
        ncols=columns,
        frameon=False,
        borderaxespad=0.0,
        handlelength=2.8,
        prop=tick_font,
    )
    for label in legend.get_texts():
        label.set_color(text_color)
    return legend


def _set_time_ticks(ax, ticks: Sequence[int], tick_font, text_color):
    """Apply time ticks with edge-aligned first/last labels.

    The first label extends right from its tick and the last extends left, so
    neither can clip at the figure edge regardless of the margin math.
    """

    ax.set_xticks(list(ticks))
    labels = ax.set_xticklabels(
        [_format_time(tick) for tick in ticks],
        fontproperties=tick_font,
        color=text_color,
    )
    if len(labels) >= 2:
        labels[0].set_ha("left")
        labels[-1].set_ha("right")
        for label in labels[1:-1]:
            label.set_ha("center")
    return labels


def _spread_tick_indices(values: Sequence[int], limit: int) -> list[int]:
    """Indices of up to ``limit`` values evenly spread across the value range.

    Spread by *value*, not by index: snapshots cluster in time, and the old
    index-based middle pick landed a tick (and its label) in the same pixel
    column as the first one whenever the capture cadence was uneven.

    Args:
        values: Sorted, deduplicated values.
        limit: Maximum number of indices to return; at least 1.

    Returns:
        Sorted unique indices; always includes the first and last value.
    """

    count = len(values)
    if count <= limit:
        return list(range(count))
    lo, hi = values[0], values[-1]
    span = hi - lo
    if span <= 0 or limit == 1:
        return [0]
    picked = {
        min(range(count), key=lambda index: abs(values[index] - target))
        for target in (lo + span * step / (limit - 1) for step in range(limit))
    }
    picked.update((0, count - 1))
    return sorted(picked)


def _label_spans(
    positions: Sequence[float], width: float
) -> list[tuple[float, float]]:
    """Horizontal extents of tick labels under the edge-alignment rule.

    The first label is left-aligned at its tick, the last right-aligned, and
    everything between is centered — mirroring :func:`_set_time_ticks`.
    """

    last = len(positions) - 1
    spans: list[tuple[float, float]] = []
    for index, position in enumerate(positions):
        if index == 0 and last > 0:
            spans.append((position, position + width))
        elif index == last and last > 0:
            spans.append((position - width, position))
        else:
            spans.append((position - width / 2.0, position + width / 2.0))
    return spans


def _thin_label_spans(
    spans: Sequence[tuple[float, float]], gap: float
) -> list[int]:
    """Indices of labels that fit without crowding, first and last pinned.

    Greedy left-to-right: a middle label survives only when it clears the
    previously kept label *and* the pinned last label by ``gap``.
    """

    count = len(spans)
    if count <= 2:
        return list(range(count))
    kept = [0]
    for index in range(1, count - 1):
        previous = spans[kept[-1]]
        if (
            spans[index][0] >= previous[1] + gap
            and spans[index][1] + gap <= spans[count - 1][0]
        ):
            kept.append(index)
    kept.append(count - 1)
    return kept


def _pt(logical_px: int) -> float:
    """Convert final-card pixels to a matplotlib point size.

    The figure rasters at ``_CHART_SCALE`` times its logical size and the page
    downsamples by the same factor, so ``logical_px`` here is what actually
    lands in the sent image.
    """

    return logical_px * 72.0 * _CHART_SCALE / _CHART_DPI


def _mpl_color(color: ColorLike) -> tuple[float, float, float, float]:
    red, green, blue, alpha = normalize_color(color)
    return (red / 255.0, green / 255.0, blue / 255.0, alpha / 255.0)


def _font_properties(size: float) -> font_manager.FontProperties:
    """The shared CJK font at ``size`` points, degrading like ``load_font``.

    A missing bundle falls back to matplotlib's default font instead of
    raising, mirroring how the kits themselves degrade.
    """

    if CHINESE_FONT.exists():
        return font_manager.FontProperties(fname=str(CHINESE_FONT), size=size)
    return font_manager.FontProperties(size=size)


def _format_time(timestamp: int) -> str:
    return format_ts(timestamp, "%m-%d %H:%M")
