import sys
import time
import types
import random
import argparse
import subprocess
import importlib.util
from typing import Iterable
from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / ".cache" / "render-previews"
PREVIEW_DATA_DIR = ROOT / ".cache" / "render-preview-data"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.render import PlayerIdentity


def _ensure_package(name: str, path: Path) -> None:
    package = sys.modules.get(name)
    if package is not None:
        return
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules[name] = package


def _load_module(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_plugin_module(name: str, relative_path: str):
    sys.modules.setdefault(
        "nonebot_plugin_localstore",
        types.SimpleNamespace(get_data_dir=lambda _name: PREVIEW_DATA_DIR),
    )
    parts = name.split(".")
    for index in range(2, len(parts)):
        package_name = ".".join(parts[:index])
        package_path = ROOT / Path(*parts[:index])
        _ensure_package(package_name, package_path)
    return _load_module(name, ROOT / relative_path)


def _kit(name: str):
    from plugins.render.kits import KITS

    if name not in KITS:
        raise ValueError(f"unknown kit: {name}")
    return KITS[name]()


def _kit_names() -> list[str]:
    from plugins.render.kits import KITS

    return list(KITS)


def _preview_card(label: str, fill: tuple[int, int, int, int]) -> Image.Image:
    width, height = 640, 896
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=36, fill=fill)
    draw.rounded_rectangle(
        (18, 18, width - 19, height - 19),
        radius=28,
        outline=(255, 255, 255, 230),
        width=8,
    )
    try:
        font = ImageFont.truetype(
            str(ROOT / "plugins" / "blackjack" / "recourses" / "old.ttf"), 120
        )
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (
            (width - (bbox[2] - bbox[0])) // 2,
            (height - (bbox[3] - bbox[1])) // 2 - bbox[1],
        ),
        label,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return image


def preview_blackjack(kit_name: str, output_dir: Path) -> list[Path]:
    render_module = _load_plugin_module(
        "plugins.blackjack.render", "plugins/blackjack/render.py"
    )
    models_module = _load_plugin_module(
        "plugins.blackjack.models", "plugins/blackjack/models.py"
    )

    renderer = object.__new__(render_module.BlackjackRenderer)
    renderer.kit = _kit(kit_name)
    renderer.card_back = _preview_card("?", (55, 55, 65, 255))
    renderer.get_font = lambda size: ImageFont.truetype(
        str(ROOT / "plugins" / "blackjack" / "recourses" / "old.ttf"), size
    )
    identity = PlayerIdentity(nickname="香澄", level=42)

    def card(rank: str, suit: str, fill: tuple[int, int, int, int]):
        item = models_module.Card(suit, rank)
        item._get_image = lambda ace_value=None: _preview_card(rank, fill)
        return item

    dealer = models_module.Hand()
    dealer.add_card(card("A", "cool", (234, 78, 116, 255)))
    dealer.add_card(card("10", "happy", (66, 133, 244, 255)))
    dealer.add_card(card("K", "pure", (76, 175, 80, 255)))

    player = models_module.Hand()
    player.add_card(card("8", "powerful", (255, 124, 85, 255)))
    player.add_card(card("7", "cool", (184, 130, 225, 255)))

    outputs = [
        output_dir / f"blackjack-hand-{kit_name}.png",
        output_dir / f"blackjack-table-{kit_name}.png",
    ]
    renderer.generate_hand(
        dealer,
        second_card_back=True,
        identity=identity,
        detail="庄家回合 · 押注 120 Pt",
    ).save(outputs[0])
    renderer.generate_table(
        dealer,
        player,
        dealer_card_back=True,
        identity=identity,
        detail="押注 120 Pt · 玩家 15 点",
    ).save(outputs[1])
    return outputs


def preview_mines(kit_name: str, output_dir: Path) -> list[Path]:
    random.seed(7)
    models_module = _load_plugin_module(
        "plugins.mines.models", "plugins/mines/models.py"
    )
    field_module = _load_plugin_module(
        "plugins.mines.render.field", "plugins/mines/render/field.py"
    )

    field = models_module.Field(width=5, height=5, mines=4)
    for index in (0, 3, 6, 12, 18):
        field.reveal_block(index)
    field.reveal_all_mines()

    output = output_dir / f"mines-{kit_name}.png"
    identity = PlayerIdentity(nickname="香澄", level=42)
    field_module.render(
        field,
        kit=_kit(kit_name),
        identity=identity,
        detail="押注 120 Pt · 剩 4 雷",
    ).save(output)
    return [output]


def preview_one_stroke(kit_name: str, output_dir: Path) -> list[Path]:
    models_module = _load_plugin_module(
        "plugins.one_stroke.models", "plugins/one_stroke/models.py"
    )
    session_module = _load_plugin_module(
        "plugins.one_stroke.session", "plugins/one_stroke/session.py"
    )
    graph_module = _load_plugin_module(
        "plugins.one_stroke.render.graph", "plugins/one_stroke/render/graph.py"
    )
    leaderboard_module = _load_plugin_module(
        "plugins.one_stroke.render.leaderboard",
        "plugins/one_stroke/render/leaderboard.py",
    )

    nodes = {(r, c) for r in range(4) for c in range(4)}
    path = [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 3),
        (1, 2),
        (1, 1),
        (1, 0),
        (2, 0),
        (2, 1),
        (2, 2),
        (2, 3),
        (3, 3),
    ]
    edges = {frozenset((a, b)) for a, b in zip(path, path[1:])}
    graph = models_module.Graph(
        rows=4, cols=4, nodes=nodes, edges=edges, start_node=path[0]
    )
    session = session_module.GameSession(
        user_id="preview",
        channel_id="preview",
        difficulty_name="普通",
        reward=120,
        graph=graph,
    )
    for next_node in path[1:7]:
        edge = frozenset((session.current_pos, next_node))
        session.drawn_edges.add(edge)
        session.current_pos = next_node
        session.visited_nodes.add(next_node)

    board_output = output_dir / f"one-stroke-{kit_name}.png"
    leaderboard_output = output_dir / f"one-stroke-leaderboard-{kit_name}.png"
    identity = PlayerIdentity(nickname="香澄", level=42)
    graph_module.render(
        session,
        kit=_kit(kit_name),
        identity=identity,
        detail="难度 普通 · 奖励 120 Pt",
    ).save(board_output)
    leaderboard_module.render_leaderboard(
        [("kasumi", 12.34), ("arisa", 16.78), ("tae", 20.12)],
        [("a very very long player name", 23.45), ("rimi", 25.67)],
        [("saaya", 31.23)],
        kit=_kit(kit_name),
    ).save(leaderboard_output)
    return [board_output, leaderboard_output]


def render_targets(
    targets: Iterable[str], kits: Iterable[str], output_dir: Path
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for kit_name in kits:
        for target in targets:
            if target == "blackjack":
                outputs.extend(preview_blackjack(kit_name, output_dir))
            elif target == "mines":
                outputs.extend(preview_mines(kit_name, output_dir))
            elif target == "one-stroke":
                outputs.extend(preview_one_stroke(kit_name, output_dir))
            else:
                raise ValueError(f"unknown target: {target}")
    return outputs


def _expand_targets(target: str) -> list[str]:
    if target == "all":
        return ["blackjack", "mines", "one-stroke"]
    return [target]


def _expand_kits(kit: str) -> list[str]:
    if kit == "all":
        return _kit_names()
    if kit == "both":
        return ["bangdream", "minimal"]
    return [kit]


def _watch_files() -> list[Path]:
    return [
        Path(__file__),
        ROOT / "plugins" / "blackjack" / "render.py",
        ROOT / "plugins" / "mines" / "render" / "field.py",
        ROOT / "plugins" / "one_stroke" / "render" / "graph.py",
        ROOT / "plugins" / "one_stroke" / "render" / "leaderboard.py",
    ]


def _snapshot(paths: Iterable[Path]) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in paths if path.exists()}


def _open_paths(paths: Iterable[Path]) -> None:
    for path in paths:
        subprocess.run(["open", str(path)], check=False)


def run_once(args: argparse.Namespace) -> list[Path]:
    targets = _expand_targets(args.target)
    kits = _expand_kits(args.kit)
    outputs = render_targets(targets, kits, args.output_dir)
    for path in outputs:
        print(path)
    if args.open:
        _open_paths(outputs)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render local game previews without loading NoneBot plugins."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["all", "blackjack", "mines", "one-stroke"],
    )
    parser.add_argument(
        "--kit",
        default="bangdream",
        choices=[*_kit_names(), "both", "all"],
        help="Render with one kit, 'both' for bangdream+minimal, or 'all' kits.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated preview PNGs.",
    )
    parser.add_argument("--open", action="store_true", help="Open generated PNGs.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Regenerate when previewed render files change.",
    )
    args = parser.parse_args()

    if not args.watch:
        run_once(args)
        return

    watched = _watch_files()
    previous = _snapshot(watched)
    run_once(args)
    print("Watching render files. Press Ctrl+C to stop.")
    while True:
        time.sleep(0.5)
        current = _snapshot(watched)
        if current == previous:
            continue
        previous = current
        for name in list(sys.modules):
            if name.startswith(
                ("plugins.blackjack", "plugins.mines", "plugins.one_stroke")
            ):
                sys.modules.pop(name, None)
        print("Change detected. Regenerating...")
        run_once(args)


if __name__ == "__main__":
    main()
