from pathlib import Path
from typing import Tuple, TYPE_CHECKING

from PIL import Image, ImageDraw

from ..models import BlockType
from plugins.render_service import (
    create_bg,
    draw_pill,
    load_font,
    draw_rounded_rectangle,
)
from .utils import get_random_kasumi, get_random_arisa
from plugins.render_service.primitives import RESOURCES_DIR

if TYPE_CHECKING:
    from ..models import Field


def generate_unrevealed_field(index: int) -> Image.Image:
    width, height = 120, 120

    # Create the gradient
    gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient)

    top_color = (223, 223, 223)
    bottom_color = (213, 213, 213)

    for y in range(height):
        # Calculate color for this row
        ratio = y / height
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)

        gradient_draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Create the mask
    mask_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    # mask_draw = ImageDraw.Draw(mask)
    mask_img = draw_rounded_rectangle(
        mask_img, (0, 0, width, height), 16, fill=(255, 255, 255, 255)
    )

    # Use alpha channel of the drawn shape as mask
    mask = mask_img.split()[3]

    # Apply mask to gradient by replacing its alpha channel
    output = gradient.copy()
    output.putalpha(mask)

    # Draw the index
    index_draw = ImageDraw.Draw(output)
    bbox = index_draw.textbbox((0, 0), str(index), font=load_font(80, "old.ttf"))
    index_draw.text(
        (
            width // 2 - (bbox[2] + bbox[0]) // 2,
            height // 2 - (bbox[3] + bbox[1]) // 2,
        ),
        str(index),
        font=load_font(80, "old.ttf"),
        fill=(255, 255, 255, 255),
    )

    return output


def generate_revealed_field(
    stamp_path: Path, background_color: Tuple[int, int, int]
) -> Image.Image:
    width, height = 120, 120

    # Create a rounded rectangle with the background color
    background = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    # background_draw = ImageDraw.Draw(background)
    background = draw_rounded_rectangle(
        background, (0, 0, width, height), 16, fill=background_color + (255,)
    )

    # Create the stamp
    stamp = Image.open(stamp_path).convert("RGBA")

    # Resize the stamp to make its longest side 110 pixels
    stamp_width, stamp_height = stamp.size
    if stamp_width >= stamp_height:
        new_width = 110
        new_height = int((110 / stamp_width) * stamp_height)
    else:
        new_height = 110
        new_width = int((110 / stamp_height) * stamp_width)
    stamp = stamp.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Paste the stamp onto the background using alpha composite
    # Center the stamp
    stamp_x = (width - new_width) // 2
    stamp_y = (height - new_height) // 2

    # Create a temporary image to composite
    temp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    temp.paste(stamp, (stamp_x, stamp_y))

    # Alpha composite the stamp onto the background
    result = Image.alpha_composite(background, temp)

    return result


def generate_title(
    text1: str, text2: str, pill_width: int, pill_height: int
) -> Image.Image:
    pill2_height = pill_height * 85 // 62
    pill2_width = pill_width * 625 // 570
    duplicate_height = pill_height * 9 // 62

    width = pill2_width
    height = pill_height + pill2_height - duplicate_height

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    # draw = ImageDraw.Draw(canvas)

    canvas = draw_pill(
        canvas,
        (
            0,
            pill_height - duplicate_height,
            pill2_width,
            pill_height - duplicate_height + pill2_height,
        ),
        (255, 255, 255, 255),
    )
    canvas = draw_pill(
        canvas,
        (0, 0, pill_width, pill_height),
        (234, 78, 116, 255),
    )

    text1_size = pill_height * 33 // 61
    text2_size = pill2_height * 40 // 75

    draw = ImageDraw.Draw(
        canvas
    )  # Create draw object after pills are drawn because they return new images

    font1 = load_font(text1_size, "old.ttf")
    font2 = load_font(text2_size, "old.ttf")

    text1_bbox = draw.textbbox((0, 0), text1, font=font1)
    text2_bbox = draw.textbbox((0, 0), text2, font=font2)

    draw.text(
        (
            pill_height // 2,
            (pill_height - (text1_bbox[3] - text1_bbox[1])) // 2 - text1_bbox[1],
        ),
        text1,
        font=font1,
        fill=(255, 255, 255, 255),
    )
    draw.text(
        (
            pill2_height // 2,
            pill_height
            - duplicate_height
            + (pill2_height - (text2_bbox[3] - text2_bbox[1])) // 2
            - text2_bbox[1],
        ),
        text2,
        font=font2,
        fill=(80, 80, 80, 255),
    )

    return canvas


def render(field: "Field") -> Image.Image:
    canvas = create_bg(
        RESOURCES_DIR / "BG" / "bg00039.png",
        width=896,
        height=1024,
    )
    title = generate_title("探险", "Arisa的仓库", 500, 57)

    title_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    title_layer.paste(title, (56, 36))
    canvas = Image.alpha_composite(canvas, title_layer)

    # draw = ImageDraw.Draw(canvas)
    canvas = draw_rounded_rectangle(
        canvas,
        (56, 182, 56 + 786, 182 + 786),
        corner_radius=48,
        fill=(255, 255, 255, 200),
    )

    field_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))

    for i in range(field.height):
        for j in range(field.width):
            block = field.field[i][j]
            if block == BlockType.EMPTY or block == BlockType.MINE:
                image = generate_unrevealed_field(i * field.width + j + 1)
                field_layer.paste(
                    image,
                    (56 + 50 + j * 120 + j * 21, 182 + 50 + i * 120 + i * 21),
                )
            elif block == BlockType.EMPTY_SHOWN:
                image = generate_revealed_field(
                    get_random_kasumi(),
                    (255, 124, 85),
                )
                field_layer.paste(
                    image,
                    (56 + 50 + j * 120 + j * 21, 182 + 50 + i * 120 + i * 21),
                )
            elif block == BlockType.MINE_SHOWN:
                image = generate_revealed_field(
                    get_random_arisa(),
                    (184, 130, 225),
                )
                field_layer.paste(
                    image,
                    (56 + 50 + j * 120 + j * 21, 182 + 50 + i * 120 + i * 21),
                )

    canvas = Image.alpha_composite(canvas, field_layer)
    return canvas
