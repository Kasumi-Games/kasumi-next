import math
import random

from PIL import Image, ImageDraw, ImageFont

from .utils import FONTS_DIR, alpha_composite_paste


def scatter_images(
    canvas: Image.Image,
    image_path: str,
    density: float,
    angle_range: float,
    size_range: tuple[float, float],
) -> Image.Image:
    """
    Scatters images randomly on the canvas.
    """
    star_img = Image.open(image_path).convert("RGBA")

    width, height = canvas.size
    area = width * height
    num_images = int(area * density)

    for _ in range(num_images):
        x = random.uniform(0, width)
        y = random.uniform(0, height)
        size = random.uniform(size_range[0], size_range[1])
        angle = random.uniform(0, angle_range)
        s_img = star_img.resize((int(size), int(size)), Image.Resampling.BILINEAR)
        s_img = s_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

        paste_x = int(x - s_img.width / 2)
        paste_y = int(y - s_img.height / 2)

        alpha_composite_paste(canvas, s_img, (paste_x, paste_y))

    return canvas


def draw_text_on_canvas(
    canvas: Image.Image,
    text: str,
    font_size: int,
    angle: float,
    line_spacing: int,
    letter_spacing: int,
    stroke_width: int,
    skew_angle: float,
    opacity: float,
    scale_x: float,
) -> Image.Image:
    """
    Draws specific text pattern.
    """
    try:
        font = ImageFont.truetype(str(FONTS_DIR / "Orbitron Black.ttf"), font_size)
    except OSError:
        print("Font not found, using default.")
        font = ImageFont.load_default()

    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy_draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_width_raw = bbox[2] - bbox[0]
    text_height_raw = bbox[3] - bbox[1]

    txt_img = Image.new(
        "RGBA",
        (
            int(text_width_raw + stroke_width * 2 + 50),
            int(text_height_raw + stroke_width * 2 + 50),
        ),
        (0, 0, 0, 0),
    )
    d = ImageDraw.Draw(txt_img)

    d.text(
        (stroke_width + 10, stroke_width + 10),
        text,
        font=font,
        fill=None,
        stroke_width=stroke_width,
        stroke_fill="white",
    )

    bbox = txt_img.getbbox()
    if bbox:
        txt_img = txt_img.crop(bbox)

    w, h = txt_img.size
    new_w = int(w * scale_x)
    txt_img = txt_img.resize((new_w, h), Image.Resampling.BILINEAR)

    skew_rad = math.radians(skew_angle)
    tan_skew = math.tan(skew_rad)
    skew_offset = abs(h * tan_skew)
    skewed_w = int(new_w + skew_offset)

    x_shift = skew_offset if tan_skew < 0 else 0

    skewed_img = txt_img.transform(
        (skewed_w, h),
        Image.Transform.AFFINE,
        (1, -tan_skew, -x_shift if tan_skew < 0 else 0, 0, 1, 0),
        resample=Image.Resampling.BILINEAR,
    )

    txt_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))

    rotated_img = skewed_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    space_x = rotated_img.width + letter_spacing
    space_y = rotated_img.height + line_spacing

    cols = int(canvas.width / space_x) + 4
    rows = int(canvas.height / space_y) + 4

    for r in range(-2, rows):
        y = r * space_y
        row_offset = (space_x / 2) if (r % 2 != 0) else 0
        for c in range(-2, cols):
            x = c * space_x + row_offset

            txt_layer.paste(rotated_img, (int(x), int(y)), rotated_img)

    if opacity < 1.0:
        r, g, b, a = txt_layer.split()
        a = a.point(lambda i: int(i * opacity))
        txt_layer.putalpha(a)

    canvas.alpha_composite(txt_layer)
    return canvas
