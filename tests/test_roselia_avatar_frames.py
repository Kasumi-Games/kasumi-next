"""Geometry checks for the Roselia character wig avatar cosmetic."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHARACTER_FRAME = (
    ROOT / "plugins/inventory/resources/items/avatar_frames/frame_roselia_character.png"
)


def test_character_wig_covers_the_top_and_side_avatar_boundary() -> None:
    """Hair, rather than a circular rail, must hide the avatar-disc edge."""

    alpha = Image.open(CHARACTER_FRAME).convert("RGBA").getchannel("A")
    boundary_points = (
        (256, 48),
        (109, 109),
        (48, 256),
        (464, 256),
        (403, 109),
    )
    uncovered = [point for point in boundary_points if alpha.getpixel(point) < 128]
    assert not uncovered, f"avatar edge is exposed at {uncovered}"


def test_character_wig_keeps_the_face_and_bottom_center_open() -> None:
    """The wig may surround the portrait but must not become a closed ring."""

    alpha = Image.open(CHARACTER_FRAME).convert("RGBA").getchannel("A")
    assert alpha.getpixel((256, 256)) == 0
    assert alpha.getpixel((256, 464)) == 0
