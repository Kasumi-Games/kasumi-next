from pathlib import Path

from PIL import Image

ASSETS_DIR = Path(__file__).resolve().parents[2] / "resources"
BG_ASSETS_DIR = ASSETS_DIR / "BG"
FONTS_DIR = ASSETS_DIR / "Fonts"


def alpha_composite_paste(dest: Image.Image, source: Image.Image, pos: tuple[int, int]):
    """
    Pastes source onto dest using alpha compositing at position pos.
    Handles boundaries and cropping.
    """
    x, y = pos
    w, h = source.size
    dest_w, dest_h = dest.size

    # Calculate intersection limits
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(dest_w, x + w)
    y2 = min(dest_h, y + h)

    if x1 >= x2 or y1 >= y2:
        return

    # Source crop coordinates
    sx1 = x1 - x
    sy1 = y1 - y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)

    target_width = x2 - x1
    target_height = y2 - y1

    # Verify dimensions match (bounds check above should ensure this, but safety first)
    if target_width <= 0 or target_height <= 0:
        return

    source_crop = source.crop((sx1, sy1, sx2, sy2))
    dest_crop = dest.crop((x1, y1, x2, y2))

    # Ensure RGBA
    if dest_crop.mode != "RGBA":
        dest_crop = dest_crop.convert("RGBA")
    if source_crop.mode != "RGBA":
        source_crop = source_crop.convert("RGBA")

    comp = Image.alpha_composite(dest_crop, source_crop)

    dest.paste(comp, (x1, y1))
