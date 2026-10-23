"""Build S4 standing art with the user's local manosaba-sprite-synth project.

Run using that project's Python environment, e.g.:
  ../manosaba-sprite-synth/.venv/bin/python scripts/build_manosaba_season_art.py

Poses and facial layers are composed by the source project's Prefab renderer.
The alpha bounds are trimmed, proportionally reduced to at most 2048px high,
and given a transparent margin. No source assets are modified.
"""

from __future__ import annotations

import sys
import json
import hashlib
import argparse
import importlib
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "plugins/inventory/resources/items/standing_art/manosaba"


def build(project: Path):
    project = project.expanduser().resolve()
    if not (project / "src/prefab/synthesizer.py").is_file():
        raise FileNotFoundError(f"Not a sprite synthesizer project: {project}")
    sys.path.insert(0, str(project))
    prefab_type = importlib.import_module("src.prefab.synthesizer").Prefab
    recipes = json.loads((OUTPUT / "recipes.json").read_text())
    revision = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
    )
    manifest = {
        "source_project": "manosaba-sprite-synth",
        "source_revision": revision.stdout.strip()
        if revision.returncode == 0
        else None,
        "source_modules": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((project / "src/prefab").glob("*.py"))
        },
        "transformation": "Prefab.synthesize with default layers; trim alpha bounds; proportional Lanczos downscale to 2024px content height; 12px transparent margin",
        "assets": [],
    }
    for recipe in recipes:
        prefab = prefab_type(recipe["prefab"], asset_path=project / "assets")
        unknown = set(recipe["keys"]) - set(prefab.available_keys)
        if unknown:
            raise ValueError(f"Unknown composition keys for {prefab.name}: {unknown}")
        with Image.open(BytesIO(prefab.synthesize(*recipe["keys"]))) as source:
            image = source.convert("RGBA")
        bounds = image.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"Empty standing art: {prefab.name}")
        trimmed = image.crop(bounds)
        if trimmed.height > 2024:
            trimmed = trimmed.resize(
                (round(trimmed.width * 2024 / trimmed.height), 2024),
                Image.Resampling.LANCZOS,
            )
        final = Image.new("RGBA", (trimmed.width + 24, trimmed.height + 24))
        final.alpha_composite(trimmed, (12, 12))
        target = OUTPUT / f"{recipe['prefab'].lower()}.png"
        final.save(target, optimize=True)
        manifest["assets"].append(
            {
                "file": target.name,
                "prefab": prefab.name,
                "keys": recipe["keys"],
                "size": list(final.size),
                "alpha_bounds": list(bounds),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "composition_sha256": hashlib.sha256(
                    (project / "assets" / prefab.name / "composition.json").read_bytes()
                ).hexdigest(),
                "character_sha256": hashlib.sha256(
                    (project / "assets" / prefab.name / "character.json").read_bytes()
                ).hexdigest(),
                "sprites_sha256": {
                    prefab._character_data.nodes[node].name: hashlib.sha256(
                        prefab._get_sprite_path(
                            prefab._character_data.nodes[node].name
                        ).read_bytes()
                    ).hexdigest()
                    for node in sorted(prefab.compose("Body", *recipe["keys"]))
                    if node in prefab._available_image_ids
                },
            }
        )
        print(f"{prefab.name}: {final.width}x{final.height}", flush=True)
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--synth-project",
        type=Path,
        default=Path.home() / "Projects/manosaba-sprite-synth",
    )
    build(parser.parse_args().synth_project)
