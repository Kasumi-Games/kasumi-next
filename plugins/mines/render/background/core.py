from pathlib import Path
from typing import Union

from PIL import Image

from .utils import BG_ASSETS_DIR
from .overlays import draw_text_on_canvas, scatter_images
from .effects import create_blurred_triangle_pattern, spread


def create_bg(
    image_path: Union[str, Path],
    text: str = "BanG Dream!",
    width: int = 1024,
    height: int = 1024,
):
    if not image_path:
        raise ValueError("Image path is required")

    img = Image.open(image_path).convert("RGBA")

    bg = spread(img, width, height, 20)

    bg = create_blurred_triangle_pattern(bg, 25, 200, 0.04)

    stars = ["star1.png", "star2.png"]
    for s_name in stars:
        s_path = BG_ASSETS_DIR / s_name
        if s_path.exists():
            bg = scatter_images(
                bg,
                str(s_path),
                density=0.00001,
                angle_range=72,
                size_range=(25, 75),
            )

    bg = draw_text_on_canvas(
        bg,
        text,
        font_size=150,
        angle=15,
        line_spacing=50,
        letter_spacing=100,
        stroke_width=3,
        skew_angle=-12,
        opacity=0.5,
        scale_x=0.8,
    )

    return bg
