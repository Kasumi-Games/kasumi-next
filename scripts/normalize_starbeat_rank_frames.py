"""Normalize the four Starbeat ranking-frame rails to one shared geometry.

The avatar-frame contract uses a centered 416px avatar disc on a 512px RGBA
canvas. The original Starbeat exports had smaller, vertically shifted rails,
which exposed a crescent of the avatar at the bottom in compact surfaces.
This script enlarges and recenters each complete frame without changing its
design, then writes it back to the inventory asset path.
"""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FRAME_DIR = ROOT / "plugins/inventory/resources/items/avatar_frames"
FRAME_PATHS = tuple(
    FRAME_DIR / f"frame_starbeat_{rank}.png"
    for rank in ("champion", "podium", "top10", "top50")
)

CANVAS = 512
ALPHA_THRESHOLD = 128
TARGET_CENTER = 255.5
TARGET_DIAMETER = 449


def _opaque_runs(values: list[int]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if value >= ALPHA_THRESHOLD and start is None:
            start = index
        elif value < ALPHA_THRESHOLD and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(values) - 1))
    return runs


def ring_geometry(image: Image.Image) -> tuple[float, float, int, int]:
    """Measure the rail on the undecorated horizontal and vertical axes."""

    alpha = image.getchannel("A")
    row = _opaque_runs([alpha.getpixel((x, CANVAS // 2)) for x in range(CANVAS)])
    column = _opaque_runs(
        [alpha.getpixel((CANVAS // 2, y)) for y in range(CANVAS)]
    )
    if len(row) < 2 or len(column) < 2:
        raise ValueError("frame does not contain a complete circular rail")
    left, right = row[0][0], row[-1][1]
    top, bottom = column[0][0], column[-1][1]
    return (
        (left + right) / 2,
        (top + bottom) / 2,
        right - left,
        bottom - top,
    )


def _already_normalized(geometry: tuple[float, float, int, int]) -> bool:
    center_x, center_y, width, height = geometry
    return (
        abs(center_x - TARGET_CENTER) <= 0.5
        and abs(center_y - TARGET_CENTER) <= 0.5
        and abs(width - TARGET_DIAMETER) <= 1
        and abs(height - TARGET_DIAMETER) <= 1
    )


def normalize(source: Image.Image) -> Image.Image:
    source = source.convert("RGBA")
    center_x, center_y, width, height = ring_geometry(source)
    scale_x = TARGET_DIAMETER / width
    scale_y = TARGET_DIAMETER / height

    # PIL's affine tuple maps output coordinates back into source coordinates.
    transform = (
        1 / scale_x,
        0,
        center_x - TARGET_CENTER / scale_x,
        0,
        1 / scale_y,
        center_y - TARGET_CENTER / scale_y,
    )
    return source.transform(
        (CANVAS, CANVAS),
        Image.Transform.AFFINE,
        transform,
        Image.Resampling.BICUBIC,
    )


def main() -> None:
    for path in FRAME_PATHS:
        with Image.open(path) as opened:
            source = opened.convert("RGBA")
        before = ring_geometry(source)
        if _already_normalized(before):
            print(f"unchanged {path.name}: geometry={before}")
            continue

        result = normalize(source)
        after = ring_geometry(result)
        if not _already_normalized(after):
            raise RuntimeError(f"{path.name}: normalization missed target: {after}")
        if result.getchannel("A").getbbox() in (None, (0, 0, CANVAS, CANVAS)):
            raise RuntimeError(f"{path.name}: invalid or edge-clipped alpha bounds")
        result.save(path)
        print(f"normalized {path.name}: {before} -> {after}")


if __name__ == "__main__":
    main()
