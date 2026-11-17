"""Rebuild S5 transparent art from pinned Bestdori originals and draw its frames.

Uses the local gacha cache first, then the recorded public source URL. No AI
art or background removal: all original trim pixels and proportions survive.
"""

from __future__ import annotations

import json
import hashlib
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "plugins/inventory/resources/items/standing_art/winter"
FRAMES = ROOT / "plugins/inventory/resources/items/avatar_frames"
# Canonical Bestdori character IDs; project rarity is independent of game rarity.
CAST = [
    ("kasumi", "户山香澄", 1, 556, 6),
    ("tomori", "高松灯", 36, 2123, 6),
    ("aya", "丸山彩", 16, 387, 5),
    ("kokoro", "弦卷心", 11, 1397, 5),
    ("mashiro", "仓田真白", 26, 1682, 5),
    ("rokka", "朝日六花", 32, 1120, 5),
    ("ran", "美竹兰", 6, 563, 4),
    ("lisa", "今井莉莎", 23, 1691, 4),
    ("arisa", "市谷有咲", 5, 1111, 4),
    ("saaya", "山吹沙绫", 4, 2360, 4),
    ("anon", "千早爱音", 37, 2160, 4),
    ("yukina", "凑友希那", 21, 1358, 4),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build_art():
    recipes = json.loads((ART / "recipes.json").read_text())
    assets = []
    for r in recipes:
        cached = ROOT / f".data/gacha/standing/{r['card_id']}_normal.png"
        raw = (
            cached.read_bytes()
            if cached.exists()
            else urllib.request.urlopen(r["source_url"], timeout=45).read()
        )
        if digest(raw) != r["source_sha256"]:
            raise ValueError(f"Source changed: {r['card_id']}")
        from io import BytesIO

        im = Image.open(BytesIO(raw)).convert("RGBA")
        # Retain the complete transparent source canvas, add a quiet safety margin.
        out = Image.new("RGBA", (im.width + 32, im.height + 32))
        out.alpha_composite(im, (16, 16))
        target = ART / f"{r['slug']}.png"
        out.save(target, optimize=True)
        assets.append(
            dict(
                r,
                file=target.name,
                sha256=digest(target.read_bytes()),
                size=list(out.size),
            )
        )
    (ART / "manifest.json").write_text(
        json.dumps({"version": 1, "assets": assets}, ensure_ascii=False, indent=2)
        + "\n"
    )


def build_frames():
    from draw_winter_frames import main

    main()


if __name__ == "__main__":
    ART.mkdir(parents=True, exist_ok=True)
    FRAMES.mkdir(parents=True, exist_ok=True)
    build_art()
    build_frames()
