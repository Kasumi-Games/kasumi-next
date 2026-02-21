from pathlib import Path
from typing import Union

from PIL import Image

from .effects import create_blurred_triangle_pattern, spread
from .overlays import draw_text_on_canvas, scatter_images

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"
BG_ASSETS_DIR = RESOURCES_DIR / "BG"


def create_bg(
    image_path: Union[str, Path],
    text: str = "BanG Dream!",
    width: int = 1024,
    height: int = 1024,
    blur_radius: int = 25,
    triangle_size: int = 200,
    brightness_difference: float = 0.04,
) -> Image.Image:
    if not image_path:
        raise ValueError("Image path is required")

    img = Image.open(image_path).convert("RGBA")
    bg = spread(img, width, height, 20)
    bg = create_blurred_triangle_pattern(
        bg, blur_radius, triangle_size, brightness_difference
    )

    for s_name in ("star1.png", "star2.png"):
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
