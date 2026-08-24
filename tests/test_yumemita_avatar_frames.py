"""Geometry checks for the YUMEMITA character cat-ear headwear."""

from pathlib import Path
from math import hypot

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_FRAME = (
    ROOT
    / "plugins/inventory/resources/items/avatar_frames/frame_yumemita_character.png"
)


def test_character_headwear_stays_above_the_avatar_face() -> None:
    """Only the cat-ear headwear may overlap the upper portrait edge."""

    alpha = Image.open(CHARACTER_FRAME).convert("RGBA").getchannel("A")
    bbox = alpha.getbbox()
    assert bbox is not None
    assert bbox[1] < 48  # the ears rise above the Ø416 avatar disc
    assert bbox[3] < 208  # no ring, bangs, or hair below the upper portrait band
    assert alpha.crop((0, 208, 512, 512)).getextrema() == (0, 0)
    assert alpha.crop((208, 240, 304, 352)).getextrema() == (0, 0)


def test_character_headwear_keeps_the_black_and_yellow_cat_ear_palette() -> None:
    image = Image.open(CHARACTER_FRAME).convert("RGBA")
    pixels = list(image.getdata())
    black = sum(
        alpha > 30 and max(red, green, blue) < 80
        for red, green, blue, alpha in pixels
    )
    yellow = sum(
        alpha > 30 and red > 180 and green > 120 and blue < 100
        for red, green, blue, alpha in pixels
    )
    assert black > 5_000
    assert yellow > 5_000


def test_character_headband_follows_the_round_avatar_boundary() -> None:
    """The inner band edge is concentric with the centered Ø416 avatar."""

    alpha = Image.open(CHARACTER_FRAME).convert("RGBA").getchannel("A")
    inner_radii: list[float] = []
    for x in (192, 224, 256, 288, 320):
        visible_y = [y for y in range(208) if alpha.getpixel((x, y)) >= 128]
        assert visible_y, x
        inner_y = max(visible_y)
        inner_radii.append(hypot(x - 256, inner_y - 256))

    # The redrawn 21px band straddles the r=208 avatar edge, so its inner edge
    # sits at approximately r=198 at every unobstructed sample column.
    assert all(195 <= radius <= 201 for radius in inner_radii), inner_radii
    assert max(inner_radii) - min(inner_radii) <= 3, inner_radii
