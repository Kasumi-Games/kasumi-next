"""Season chart rendering helpers."""

from __future__ import annotations

import datetime
from io import BytesIO

import matplotlib.pyplot as plt

from .models import Season
from .season_service import list_snapshots


def render_snapshot_trend(season: Season) -> bytes:
    snapshots = list_snapshots(season)
    if not snapshots:
        raise ValueError("no snapshots")

    by_rank: dict[int, list[tuple[int, int | None]]] = {}
    for snapshot in snapshots:
        by_rank.setdefault(snapshot.rank, []).append(
            (snapshot.captured_at, snapshot.points)
        )

    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    plotted = False
    for rank, rows in sorted(by_rank.items()):
        xs = [ts for ts, points in rows if points is not None]
        ys = [points for _, points in rows if points is not None]
        if xs:
            ax.plot(xs, ys, marker="o", linewidth=2, label=f"Rank {rank}")
            plotted = True

    if not plotted:
        plt.close(fig)
        raise ValueError("no plottable snapshots")

    ax.set_title(f"{season.season_key} Pt Threshold")
    ax.set_xlabel("Snapshot")
    ax.set_ylabel("Pt")
    ax.grid(True, alpha=0.3)
    ax.legend()

    if snapshots:
        all_ts = sorted({snapshot.captured_at for snapshot in snapshots})
        if all_ts:
            step = max(1, len(all_ts) // 5)
            ticks = all_ts[::step]
            ax.set_xticks(ticks)
            ax.set_xticklabels(
                [
                    datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
                    for ts in ticks
                ],
                rotation=20,
                ha="right",
            )

    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()
