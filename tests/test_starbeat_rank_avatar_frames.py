"""Shared geometry contract for the four Starbeat season-ranking frames."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FRAME_DIR = ROOT / "plugins/inventory/resources/items/avatar_frames"
RANK_FRAMES = tuple(
    FRAME_DIR / f"frame_starbeat_{rank}.png"
    for rank in ("champion", "podium", "top10", "top50")
)

# A 416px avatar disc occupies x/y 48..464 on the 512px frame canvas. The
# ranking rail is deliberately a little larger, matching the established
# inventory-frame standard, so it overlaps the avatar edge instead of exposing
# a crescent of portrait at the bottom.
AVATAR_BOUNDARY_POINTS = ((256, 48), (464, 256), (256, 464), (48, 256))
TARGET_RING_CENTER = 255.5
TARGET_RING_DIAMETER = 449


def _opaque_runs(values: list[int], threshold: int = 128) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if value >= threshold and start is None:
            start = index
        elif value < threshold and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(values) - 1))
    return runs


def _ring_geometry(alpha: Image.Image) -> tuple[float, float, int, int]:
    row = _opaque_runs([alpha.getpixel((x, 256)) for x in range(512)])
    column = _opaque_runs([alpha.getpixel((256, y)) for y in range(512)])
    assert len(row) >= 2
    assert len(column) >= 2
    left, right = row[0][0], row[-1][1]
    top, bottom = column[0][0], column[-1][1]
    return (
        (left + right) / 2,
        (top + bottom) / 2,
        right - left,
        bottom - top,
    )


def test_rank_frames_share_one_center_and_outer_diameter() -> None:
    for path in RANK_FRAMES:
        alpha = Image.open(path).convert("RGBA").getchannel("A")
        center_x, center_y, width, height = _ring_geometry(alpha)
        assert abs(center_x - TARGET_RING_CENTER) <= 0.5, path.name
        assert abs(center_y - TARGET_RING_CENTER) <= 0.5, path.name
        assert abs(width - TARGET_RING_DIAMETER) <= 1, path.name
        assert abs(height - TARGET_RING_DIAMETER) <= 1, path.name


def test_rank_frames_cover_the_avatar_boundary_on_all_four_axes() -> None:
    for path in RANK_FRAMES:
        alpha = Image.open(path).convert("RGBA").getchannel("A")
        uncovered = [point for point in AVATAR_BOUNDARY_POINTS if alpha.getpixel(point) < 128]
        assert not uncovered, f"{path.name} exposes the avatar at {uncovered}"
