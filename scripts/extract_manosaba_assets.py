"""Extract the curated Manosaba kit assets from a local Steam copy using UnityPy.

Run with an isolated Python containing UnityPy==1.25.3. The game is read-only;
only the named UI sprites and its Source Han Serif font are exported.
"""

from __future__ import annotations

import json
import hashlib
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = (
    Path.home() / "Library/Application Support/Steam/steamapps/common/manosaba_game"
)
SPRITES = {
    "DialogBase": "paper.png",
    "Background_1": "book.png",
    "NormalPrinter_Grass_1": "flourish_right.png",
    "NormalPrinter_Grass_2": "flourish_left.png",
    "Note_TitleUnderline": "rule.png",
    "Rule_TitleBack": "title_ornament.png",
    "InitialFrame": "diamond.png",
    "ChoiceFrame_Default": "choice.png",
    "ChoicesFrame_Highlighted": "choice_active.png",
    "ButtonBase_Default": "tab.png",
    "ButtonBase_Highlighted": "tab_active.png",
    "GaugeDecoration": "crest.png",
    "PersonFrame": "portrait_frame.png",
    "ChoicePortrait_Ema": "portrait_ema.png",
    "ChoicePortrait_Hiro": "portrait_hiro.png",
    "TopFrame": "thorns_top.png",
    "BottomFrame": "thorns_bottom.png",
}


def extract(game: Path, output: Path) -> None:
    import UnityPy

    data = game / "manosaba.app/Contents/Resources/Data"
    if not data.is_dir():
        data = next(iter(game.glob("*_Data")), game)
    bundle_root = data / "StreamingAssets/aa"
    sprites_bundle = next(bundle_root.rglob("general-sprites_assets_all.bundle"))
    font_bundle = next(
        bundle_root.rglob("general-fonts-sourcehanserifsc_assets_all.bundle")
    )
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for bundle in (sprites_bundle, font_bundle):
        bundle_hash = hashlib.sha256(bundle.read_bytes()).hexdigest()
        env = UnityPy.load(str(bundle))
        found = set()
        for obj in env.objects:
            if obj.type.name not in ("Sprite", "Font"):
                continue
            asset = obj.read()
            if obj.type.name == "Sprite" and asset.m_Name in SPRITES:
                filename = SPRITES[asset.m_Name]
                if filename in found:
                    raise ValueError(f"Ambiguous sprite: {asset.m_Name}")
                found.add(filename)
                image = asset.image.convert("RGBA")
                image.save(output / filename)
                details = {
                    "size": list(image.size),
                    "transform": "UnityPy Sprite.image (atlas crop/unpack), RGBA PNG; no resizing",
                }
            elif obj.type.name == "Font" and asset.m_Name == "SourceHanSerifSC":
                filename = "SourceHanSerifSC.otf"
                (output / filename).write_bytes(bytes(asset.m_FontData))
                details = {"transform": "Unmodified Unity Font.m_FontData"}
            else:
                continue
            records.append(
                {
                    "file": filename,
                    "asset": asset.m_Name,
                    "type": obj.type.name,
                    "path_id": obj.path_id,
                    "bundle": str(bundle.relative_to(data)),
                    "bundle_sha256": bundle_hash,
                    "sha256": hashlib.sha256(
                        (output / filename).read_bytes()
                    ).hexdigest(),
                    **details,
                }
            )
    missing = set(SPRITES.values()) | {"SourceHanSerifSC.otf"}
    missing -= {r["file"] for r in records}
    if missing:
        raise RuntimeError(f"Missing assets: {sorted(missing)}")
    manifest = {
        "game": "Magical Girl Witch Trials / 魔法少女的魔女审判",
        "steam_app_id": 3101040,
        "extractor": f"UnityPy {UnityPy.__version__}",
        "notice": "Game artwork remains owned by its original rights holders; it is not covered by the repository MIT license. Source Han Serif is an Adobe font under SIL OFL 1.1.",
        "assets": sorted(records, key=lambda r: r["file"]),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Extracted {len(records)} assets to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "plugins/render/kits/manosaba/resources",
    )
    args = parser.parse_args()
    extract(args.game_dir, args.output_dir)
