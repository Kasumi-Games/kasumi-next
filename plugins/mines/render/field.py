from pathlib import Path
from typing import Tuple, Optional, TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from ..models import BlockType
from .background import create_bg
from .utils import get_random_kasumi, get_random_arisa

if TYPE_CHECKING:
    from ..models import Field

FONT_PATH = Path(__file__).resolve().parents[2] / "resources" / "Fonts" / "old.ttf"


def draw_rounded_rectangle(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    corner_radius: int = 10,
    fill: Optional[Tuple[int, int, int, int]] = None,
    outline: Optional[Tuple[int, int, int, int]] = None,
    width: int = 1,
    scale: int = 4,
) -> Image.Image:
    """
    Draw a rounded rectangle on a existing image with anti-aliased edges

    Args:
        image: the Image object
        bbox: the border box (left, top, right, bottom)
        corner_radius: the corner radius, default is 10
        fill: the fill color (R, G, B, A), None means no fill
        outline: the outline color (R, G, B, A), None means no outline
        width: the outline width, default is 1
        scale: supersampling scale factor for anti-aliasing, default is 4

    Returns:
        The image with the rounded rectangle drawn on it.
    """
    left, top, right, bottom = bbox
    w, h = right - left, bottom - top

    # ensure the corner radius is not greater than half of the rectangle
    max_radius = min(w // 2, h // 2)
    corner_radius = min(corner_radius, max_radius)

    # if the corner radius is 0, draw a normal rectangle
    if corner_radius <= 0:
        draw = ImageDraw.Draw(image)
        draw.rectangle(bbox, fill=fill, outline=outline, width=width)
        return image

    # Scale up dimensions for supersampling
    scaled_w, scaled_h = w * scale, h * scale
    scaled_radius = corner_radius * scale
    scaled_width = width * scale

    # create a temporary image at higher resolution
    # Initialize background with fill color (but 0 alpha) to avoid dark edges during resizing
    bg_color = (0, 0, 0, 0)
    if fill:
        bg_color = (fill[0], fill[1], fill[2], 0)
    temp_img = Image.new("RGBA", (scaled_w, scaled_h), bg_color)
    temp_draw = ImageDraw.Draw(temp_img)

    # draw the fill part
    if fill:
        # draw the center rectangle (horizontal)
        temp_draw.rectangle(
            [scaled_radius, 0, scaled_w - scaled_radius, scaled_h], fill=fill
        )
        # draw the center rectangle (vertical)
        temp_draw.rectangle(
            [0, scaled_radius, scaled_w, scaled_h - scaled_radius], fill=fill
        )

        # draw the four corners
        # draw the top left corner
        temp_draw.pieslice(
            [0, 0, scaled_radius * 2, scaled_radius * 2], 180, 270, fill=fill
        )
        # draw the top right corner
        temp_draw.pieslice(
            [scaled_w - scaled_radius * 2, 0, scaled_w, scaled_radius * 2],
            270,
            360,
            fill=fill,
        )
        # draw the bottom left corner
        temp_draw.pieslice(
            [0, scaled_h - scaled_radius * 2, scaled_radius * 2, scaled_h],
            90,
            180,
            fill=fill,
        )
        # draw the bottom right corner
        temp_draw.pieslice(
            [
                scaled_w - scaled_radius * 2,
                scaled_h - scaled_radius * 2,
                scaled_w,
                scaled_h,
            ],
            0,
            90,
            fill=fill,
        )

    # draw the outline
    if outline and width > 0:
        # if there is an outline, we need to draw it multiple times to achieve the specified width
        for i in range(scaled_width):
            # draw the top outline
            temp_draw.line(
                [scaled_radius, i, scaled_w - scaled_radius, i], fill=outline
            )
            # draw the bottom outline
            temp_draw.line(
                [
                    scaled_radius,
                    scaled_h - i - 1,
                    scaled_w - scaled_radius,
                    scaled_h - i - 1,
                ],
                fill=outline,
            )
            # draw the left outline
            temp_draw.line(
                [i, scaled_radius, i, scaled_h - scaled_radius], fill=outline
            )
            # draw the right outline
            temp_draw.line(
                [
                    scaled_w - i - 1,
                    scaled_radius,
                    scaled_w - i - 1,
                    scaled_h - scaled_radius,
                ],
                fill=outline,
            )

            # draw the four corners of the outline
            # draw the top left corner
            temp_draw.arc(
                [i, i, scaled_radius * 2 - i, scaled_radius * 2 - i],
                180,
                270,
                fill=outline,
            )
            # draw the top right corner
            temp_draw.arc(
                [
                    scaled_w - scaled_radius * 2 + i,
                    i,
                    scaled_w - i,
                    scaled_radius * 2 - i,
                ],
                270,
                360,
                fill=outline,
            )
            # draw the bottom left corner
            temp_draw.arc(
                [
                    i,
                    scaled_h - scaled_radius * 2 + i,
                    scaled_radius * 2 - i,
                    scaled_h - i,
                ],
                90,
                180,
                fill=outline,
            )
            # draw the bottom right corner
            temp_draw.arc(
                [
                    scaled_w - scaled_radius * 2 + i,
                    scaled_h - scaled_radius * 2 + i,
                    scaled_w - i,
                    scaled_h - i,
                ],
                0,
                90,
                fill=outline,
            )

    # Downsample to target size for anti-aliased edges
    temp_img = temp_img.resize((w, h), Image.Resampling.LANCZOS)

    # Alpha composite the temporary image to the original image
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer.paste(temp_img, (left, top))
    return Image.alpha_composite(image, layer)


def draw_pill(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    fill: Tuple[int, int, int, int],
    scale: int = 4,
) -> Image.Image:
    """
    Draw a pill shape (stadium/discorectangle) with anti-aliased edges.

    The pill consists of: left semicircle + rectangle + right semicircle.
    The radius of the semicircles is half the height of the bounding box.

    Args:
        image: the Image object
        bbox: the border box (left, top, right, bottom)
        fill: the fill color (R, G, B, A)
        scale: supersampling scale factor for anti-aliasing, default is 4

    Returns:
        The image with the pill drawn on it.
    """
    left, top, right, bottom = bbox
    w, h = right - left, bottom - top

    # The radius is half the height
    radius = h // 2

    # Scale up dimensions for supersampling
    scaled_w, scaled_h = w * scale, h * scale
    scaled_radius = radius * scale

    # Create a temporary image at higher resolution
    # Initialize background with fill color (but 0 alpha) to avoid dark edges during resizing
    bg_color = (0, 0, 0, 0)
    # fill is guaranteed to be a tuple here as per signature
    bg_color = (fill[0], fill[1], fill[2], 0)
    temp_img = Image.new("RGBA", (scaled_w, scaled_h), bg_color)
    temp_draw = ImageDraw.Draw(temp_img)

    # Draw the center rectangle
    temp_draw.rectangle(
        [scaled_radius, 0, scaled_w - scaled_radius, scaled_h], fill=fill
    )

    # Draw the left semicircle
    temp_draw.pieslice([0, 0, scaled_radius * 2, scaled_h], 90, 270, fill=fill)

    # Draw the right semicircle
    temp_draw.pieslice(
        [scaled_w - scaled_radius * 2, 0, scaled_w, scaled_h], 270, 90, fill=fill
    )

    # Downsample to target size for anti-aliased edges
    temp_img = temp_img.resize((w, h), Image.Resampling.LANCZOS)

    # Alpha composite the temporary image to the original image
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer.paste(temp_img, (left, top))
    return Image.alpha_composite(image, layer)


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
    bbox = index_draw.textbbox(
        (0, 0), str(index), font=ImageFont.truetype(str(FONT_PATH), 80)
    )
    index_draw.text(
        (
            width // 2 - (bbox[2] + bbox[0]) // 2,
            height // 2 - (bbox[3] + bbox[1]) // 2,
        ),
        str(index),
        font=ImageFont.truetype(str(FONT_PATH), 80),
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

    font1 = ImageFont.truetype(str(FONT_PATH), text1_size)
    font2 = ImageFont.truetype(str(FONT_PATH), text2_size)

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
        Path(__file__).resolve().parents[1] / "resources" / "bg.png",
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
