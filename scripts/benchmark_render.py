"""Reproducible local rendering benchmark; no bot startup or network requests.

Run: .venv/bin/python scripts/benchmark_render.py --repeats 5
Results include raw samples, CSV, and a Markdown report. Business cases reuse
the visual census fixtures; components use identical inputs for every kit.
"""

from __future__ import annotations

import csv
import sys
import json
import time
import random
import argparse
import platform
import statistics
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections.abc import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from PIL import __version__ as pillow_version

from utils import cards
from scripts import preview_kasumi_surfaces as census
from utils.images import image_bytes
from plugins.render import Grid
from plugins.render import Page
from plugins.render import Fixed
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import AutoPage
from plugins.render import RenderContext
from plugins.render.kits import KITS
from scripts.render_kits_showcase import _make_art
from scripts.render_kits_showcase import _custom_components

Render = Callable[[], Image.Image]


def component_cases(kit, ratio: int, art) -> dict[str, Render]:
    """Time factory construction, measurement, drawing, and final downsampling."""

    def draw(factory):
        return lambda: AutoPage(
            child=factory(),
            min_width=784,
            max_width=784,
        ).render(RenderContext(pixel_ratio=ratio))

    from plugins.render import PlayerIdentity
    from plugins.render import PullRevealItem

    identity = PlayerIdentity(nickname="香澄 · Benchmark", level=42, avatar=art.avatar)
    pulls = tuple(
        PullRevealItem(
            name=f"星光舞台 · {i + 1}",
            rarity=2 + i % 5,
            is_new=i % 3 == 0,
            featured=i == 9,
            image=art.standing,
        )
        for i in range(10)
    )
    factories = {
        "text": lambda: kit.text(
            "主题组件测速 / Render 12345", font_size=28, wrap=False
        ),
        "text-wrapped": lambda: kit.text(
            "这是中英文混排的自动换行测试 Render benchmark。" * 12, font_size=24
        ),
        "image-contain": lambda: kit.image(
            art.standing, width=Fixed(256), height=Fixed(320)
        ),
        "image-cover": lambda: kit.image(
            art.standing, width=Fixed(256), height=Fixed(320), fit="cover", radius=24
        ),
        "panel": lambda: kit.panel(width=Fixed(784), height=Fixed(420)),
        "separator": lambda: kit.separator(length=Fixed(720)),
        "page-title": lambda: kit.page_title("RENDER TEST"),
        "hstack": lambda: HStack(
            [kit.text(f"列 {i}", font_size=24) for i in range(8)], gap=12
        ),
        "vstack": lambda: VStack(
            [kit.text(f"第 {i} 行 / 12345", font_size=24) for i in range(10)], gap=8
        ),
        "grid": lambda: Grid(
            children=[
                kit.panel(
                    kit.text(f"格 {i}", font_size=24),
                    width=Fixed(140),
                    height=Fixed(72),
                    padding=8,
                )
                for i in range(20)
            ],
            columns=5,
            gap=12,
        ),
        "stat-row": lambda: cards.stat_row(kit, "赛季积分", "12,345 Pt", width=720),
        "meter": lambda: cards.meter(kit, value=65, total=100),
        "game-identity": lambda: cards.game_identity(
            kit, identity, width=720, detail="押注 120 Pt"
        ),
        "player-card": lambda: cards.player_card(
            kit,
            identity,
            current_pt=2350,
            description="星星在跳动，舞台上的精彩每一天。",
            standing_art=art.standing,
        ),
        "pull-single": lambda: cards.pull_reveal(kit, pulls[:1]),
        "pull-ten": lambda: cards.pull_reveal(kit, pulls),
    }
    result = {name: draw(factory) for name, factory in factories.items()}
    result["background"] = lambda: Page(
        size=(864, 1000), background=kit.background()
    ).render(RenderContext(pixel_ratio=ratio))
    # This specimen's dimensions and contents differ by kit; report separately.
    if _custom_components(kit, art, width=784) is not None:
        result["custom-components"] = draw(
            lambda: _custom_components(kit, art, width=784)
        )
    return result


def measure(render: Render, repeats: int, warmup: int) -> dict:
    def once():
        start = time.perf_counter_ns()
        image = render()
        drawn = time.perf_counter_ns()
        try:
            encoded = image_bytes(image)
            finished = time.perf_counter_ns()
            return {
                "render_ms": (drawn - start) / 1e6,
                "png_ms": (finished - drawn) / 1e6,
                "total_ms": (finished - start) / 1e6,
                "width": image.width,
                "height": image.height,
                "png_bytes": len(encoded),
            }
        finally:
            image.close()

    first = once()
    for _ in range(warmup):
        once()
    samples = [once() for _ in range(repeats)]
    result = {key: samples[-1][key] for key in ("width", "height", "png_bytes")}
    for stage in ("render", "png", "total"):
        values = [sample[f"{stage}_ms"] for sample in samples]
        result[f"{stage}_median_ms"] = statistics.median(values)
        result[f"{stage}_min_ms"] = min(values)
        result[f"{stage}_max_ms"] = max(values)
    result.update(first=first, samples=samples)
    return result


def report(data: dict) -> str:
    rows = data["results"]
    business = [r for r in rows if r["group"] == "business"]
    lines = [
        "# Render benchmark",
        "",
        f"Date: {data['environment']['date']}",
        f"Machine: {data['environment']['cpu']}; {data['environment']['platform']}; Python {data['environment']['python'].split()[0]}; Pillow {data['environment']['pillow']}",
        "",
        f"{len(rows)} successful cases; {len(data['errors'])} errors. {data['repeats']} measured repetitions after the first invocation and {data['warmup']} additional warmup(s).",
        "",
        "## Method",
        "",
        "Single process, sequential execution, fixed shuffled case order (seed 617). Timings are wall clock. Each timed call constructs fresh components and a fresh render context. Global font/art caches remain warm. First invocation is recorded separately and is not a process/OS cold start. GC remains enabled. Fixture builders called inside business render lambdas are included.",
        "Component image inputs use the deterministic showcase art. Business fixtures include real bundled art where available; blackjack uses generated stand-in playing-card art, whose generation is included in the timed calls.",
        "",
        "Components compare 1x/2x supersampling on identical inputs. Business pages use their production defaults (2x for the shared page pipeline). PNG encoding uses utils.images.image_bytes, the outgoing-message PNG settings. No network, database queries, queue wait, bot startup, message transport, or disk output is timed. Theme page dimensions and bespoke content can differ, so business medians describe this equal-weight scenario mix, not production traffic.",
        "",
        "With this small sample count, min/max describe observed variation; they are not production tail-latency estimates. custom-components is a variable-content showcase and is excluded from equal-case component theme comparisons.",
        "",
        "## Business pages by theme",
        "",
        "| Theme | Cases | Median draw ms | Median PNG ms | Median total ms | Slowest page (total ms) |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    summaries = []
    for kit in data["kits"]:
        subset = [r for r in business if r["kit"] == kit]
        if subset:
            slow = max(subset, key=lambda r: r["total_median_ms"])
            summaries.append(
                (
                    statistics.median(r["total_median_ms"] for r in subset),
                    kit,
                    subset,
                    slow,
                )
            )
    for total, kit, subset, slow in sorted(summaries):
        lines.append(
            f"| {kit} | {len(subset)} | {statistics.median(r['render_median_ms'] for r in subset):.2f} | {statistics.median(r['png_median_ms'] for r in subset):.2f} | {total:.2f} | {slow['case']} ({slow['total_median_ms']:.2f}) |"
        )
    for group, title in (
        ("component", "Component draw medians (ms)"),
        ("business", "Business draw + PNG medians (ms)"),
    ):
        lines.extend(["", f"## {title}", ""])
        kits = data["kits"]
        lines.extend(
            [
                "| Case | " + " | ".join(kits) + " |",
                "| --- | " + " | ".join("---:" for _ in kits) + " |",
            ]
        )
        keys = sorted({(r["case"], r["ratio"]) for r in rows if r["group"] == group})
        lookup = {
            (r["kit"], r["case"], r["ratio"]): r for r in rows if r["group"] == group
        }
        for case, ratio in keys:
            values = []
            for kit in kits:
                row = lookup.get((kit, case, ratio))
                key = "render_median_ms" if group == "component" else "total_median_ms"
                values.append(f"{row[key]:.2f}" if row else "—")
            lines.append(f"| {case} ({ratio}x) | " + " | ".join(values) + " |")
    lines.extend(
        [
            "",
            "## Slowest business combinations",
            "",
            "| Theme | Page | Size | Draw ms | PNG ms | Total median ms | Total min–max ms |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in sorted(business, key=lambda r: r["total_median_ms"], reverse=True)[:25]:
        lines.append(
            f"| {row['kit']} | {row['case']} | {row['width']}×{row['height']} | {row['render_median_ms']:.2f} | {row['png_median_ms']:.2f} | {row['total_median_ms']:.2f} | {row['total_min_ms']:.2f}–{row['total_max_ms']:.2f} |"
        )
    if data["errors"]:
        lines.extend(
            [
                "",
                "## Errors",
                "",
                "```json",
                json.dumps(data["errors"], ensure_ascii=False, indent=2),
                "```",
            ]
        )
    return "\n".join(lines) + "\n"


def save(data, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    (output / "report.md").write_text(report(data))
    rows = [
        {k: v for k, v in r.items() if k not in ("first", "samples")}
        for r in data["results"]
    ]
    if rows:
        with (output / "results.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kits", nargs="+", choices=list(KITS), default=list(KITS))
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=["component", "business"],
        default=["component", "business"],
    )
    parser.add_argument("--ratios", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--case", help="Only case names containing this substring")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / ".cache" / "render-benchmark"
    )
    args = parser.parse_args()
    if args.repeats < 1 or args.warmup < 0 or any(r < 1 for r in args.ratios):
        parser.error("repeats/ratios must be positive; warmup must be nonnegative")
    cpu = (
        subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
        if sys.platform == "darwin"
        else platform.processor()
    )
    data = {
        "environment": {
            "date": datetime.now(ZoneInfo("Pacific/Auckland")).isoformat(),
            "cpu": cpu,
            "platform": platform.platform(),
            "python": sys.version,
            "pillow": pillow_version,
            "git_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
            ).stdout.strip(),
            "git_status": subprocess.run(
                ["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True
            ).stdout,
        },
        "kits": args.kits,
        "repeats": args.repeats,
        "warmup": args.warmup,
        "results": [],
        "errors": [],
    }
    art = _make_art()
    started = time.perf_counter()
    kits = list(args.kits)
    random.Random(617).shuffle(kits)
    for kit_name in kits:
        cases = []
        if "component" in args.groups:
            for ratio in args.ratios:
                cases.extend(
                    ("component", name, ratio, render)
                    for name, render in component_cases(
                        KITS[kit_name](), ratio, art
                    ).items()
                )
        if "business" in args.groups:
            census._render_gallery(
                args.output_dir / "fixtures",
                kit_name,
                consumer=lambda name, render: cases.append(
                    ("business", name, 2, render)
                ),
            )
        random.Random(617).shuffle(cases)
        for group, name, ratio, render in cases:
            if args.case and args.case not in name:
                continue
            try:
                result = measure(render, args.repeats, args.warmup)
                data["results"].append(
                    dict(kit=kit_name, group=group, case=name, ratio=ratio, **result)
                )
                print(
                    f"{kit_name:10} {group:9} {name:32} {ratio}x draw={result['render_median_ms']:8.2f} png={result['png_median_ms']:7.2f} ms",
                    flush=True,
                )
            except Exception as error:
                data["errors"].append(
                    dict(
                        kit=kit_name,
                        group=group,
                        case=name,
                        ratio=ratio,
                        error=f"{type(error).__name__}: {error}",
                    )
                )
                print(f"ERROR {kit_name} {name}: {error}", flush=True)
        data["elapsed_seconds"] = time.perf_counter() - started
        save(data, args.output_dir)
    print(f"Report: {args.output_dir / 'report.md'} ({data['elapsed_seconds']:.1f}s)")
    return bool(data["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
