import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..primitives import alpha_composite_paste


def spread(
    image: Image.Image, width: int, height: int, brightness_add: int
) -> Image.Image:
    """Tile image across canvas and adjust brightness."""
    if brightness_add != 0:
        if image.mode == "RGBA":
            r, g, b, a = image.split()
            r = r.point(lambda i: i + brightness_add)
            g = g.point(lambda i: i + brightness_add)
            b = b.point(lambda i: i + brightness_add)
            image = Image.merge("RGBA", (r, g, b, a))
        else:
            image = image.point(lambda i: i + brightness_add)

    img_ratio = image.width / image.height
    canvas_ratio = width / height

    if img_ratio > canvas_ratio:
        scaled_width = width
        scaled_height = int(image.height * (width / image.width))
    else:
        scaled_height = height
        scaled_width = int(image.width * (height / image.height))

    scaled_image = image.resize((int(scaled_width), int(scaled_height)), Image.Resampling.BICUBIC)
    canvas = Image.new("RGBA", (width, height))

    for y in range(0, height, int(scaled_height)):
        for x in range(0, width, int(scaled_width)):
            alpha_composite_paste(canvas, scaled_image, (x, y))

    return canvas


def create_blurred_triangle_pattern(
    image: Image.Image,
    blur_radius: float,
    triangle_size: float,
    brightness_difference: float,
) -> Image.Image:
    """Apply a blurred triangle pattern overlay."""
    blurred_image = image.filter(ImageFilter.GaussianBlur(blur_radius))

    mask = Image.new("L", (image.width, image.height), 0)
    draw = ImageDraw.Draw(mask)

    tri_h = triangle_size * math.sqrt(3) / 2
    num_rows = math.ceil(image.height / tri_h)
    num_cols = math.ceil(image.width / triangle_size)

    for row in range(num_rows + 1):
        row_offset_y = row * tri_h
        is_offset_row = row % 2 == 1

        for col in range(-1, num_cols + 1):
            col_offset_x = col * triangle_size
            if is_offset_row:
                col_offset_x += triangle_size / 2

            p1 = (col_offset_x + triangle_size / 2, row_offset_y)
            p2 = (col_offset_x, row_offset_y + tri_h)
            p3 = (col_offset_x + triangle_size, row_offset_y + tri_h)

            draw.polygon([p1, p2, p3], fill=255)

    arr_img = np.array(blurred_image).astype(float)
    arr_mask = np.array(mask).astype(float) / 255.0

    factor = 1 + (brightness_difference * arr_mask)
    if len(arr_img.shape) == 3:
        factor = np.stack([factor] * arr_img.shape[2], axis=-1)

    arr_out = arr_img * factor
    arr_out = np.clip(arr_out, 0, 255).astype(np.uint8)

    return Image.fromarray(arr_out, mode=blurred_image.mode)
