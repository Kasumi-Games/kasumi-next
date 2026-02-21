from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from plugins.render_service import (
    load_font,
    draw_pill,
    draw_rounded_rectangle,
    generate_simple_background,
)

LeaderboardRows = list[tuple[str, float]]


def _generate_title(
    text1: str, text2: str, pill_width: int, pill_height: int
) -> Image.Image:
    pill2_height = pill_height * 85 // 62
    pill2_width = pill_width * 625 // 570
    duplicate_height = pill_height * 9 // 62

    width = pill2_width
    height = pill_height + pill2_height - duplicate_height
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

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
    canvas = draw_pill(canvas, (0, 0, pill_width, pill_height), (234, 78, 116, 255))

    text1_size = pill_height * 33 // 61
    text2_size = pill2_height * 36 // 75
    draw = ImageDraw.Draw(canvas)
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


def _truncate_name(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
) -> str:
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    trimmed = text
    while trimmed:
        candidate = f"{trimmed}..."
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            return candidate
        trimmed = trimmed[:-1]
    return "..."


def _draw_capsule_separator(
    layer: Image.Image,
    x_center: int,
    y_top: int,
    y_bottom: int,
    width: int = 2,
    color: tuple[int, int, int, int] = (170, 170, 170, 255),
    scale: int = 4,
    dash_length: int = 18,
    dash_gap: int = 12,
) -> None:
    total_height = max(2, y_bottom - y_top)
    y = y_top
    while y < y_top + total_height:
        segment_h = min(dash_length, y_top + total_height - y)
        radius = max(1, width // 2)

        temp = Image.new("RGBA", (width * scale, segment_h * scale), (255, 255, 255, 0))
        draw = ImageDraw.Draw(temp)

        r = radius * scale
        w = width * scale
        h = segment_h * scale
        draw.ellipse((0, 0, w, r * 2), fill=color)
        draw.rectangle((0, r, w, h - r), fill=color)
        draw.ellipse((0, h - r * 2, w, h), fill=color)

        aa = temp.resize((width, segment_h), Image.Resampling.BICUBIC)
        layer.paste(aa, (x_center - width // 2, y), aa.split()[3])
        y += dash_length + dash_gap


def _draw_column(
    layer: Image.Image,
    area: tuple[int, int, int, int],
    header: str,
    rows: LeaderboardRows,
) -> None:
    left, top, right, bottom = area
    draw = ImageDraw.Draw(layer)

    header_font = load_font(34, "old.ttf")
    row_font = load_font(23, "old.ttf")
    time_font = load_font(22, "old.ttf")

    header_bbox = draw.textbbox((0, 0), header, font=header_font)
    header_x = left + (right - left - (header_bbox[2] - header_bbox[0])) // 2
    header_y = top + 16
    draw.text((header_x, header_y), header, font=header_font, fill=(50, 50, 65, 255))

    body_top = top + 80
    row_height = (bottom - body_top - 16) // 10
    name_left = left + 20
    time_right = right - 20

    for idx in range(10):
        y = body_top + idx * row_height
        if idx < len(rows):
            name, elapsed = rows[idx]
            time_text = f"{elapsed:.2f}s"
            time_bbox = draw.textbbox((0, 0), time_text, font=time_font)
            time_left = time_right - (time_bbox[2] - time_bbox[0])
            draw.text(
                (time_left, y),
                time_text,
                font=time_font,
                fill=(90, 90, 105, 255),
            )

            rank_prefix = f"{idx + 1:>2}. "
            name_max_width = time_left - name_left - 50
            display_name = _truncate_name(draw, name, row_font, name_max_width)
            line_text = f"{rank_prefix}{display_name}"
            draw.text((name_left, y), line_text, font=row_font, fill=(70, 70, 85, 255))
        else:
            line_text = f"{idx + 1:>2}. --"
            draw.text(
                (name_left, y), line_text, font=row_font, fill=(130, 130, 145, 255)
            )


def render_leaderboard(
    easy_rows: LeaderboardRows,
    normal_rows: LeaderboardRows,
    hard_rows: LeaderboardRows,
) -> Image.Image:
    canvas_w, canvas_h = 1280, 1024
    canvas = generate_simple_background(canvas_w, canvas_h)

    title = _generate_title("一笔画", "竞速排行榜", 420, 57)
    title_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    margin_x = max(24, int(round(canvas_w * 0.055)))
    title_y = max(20, int(round(canvas_h * 0.035)))
    title_layer.paste(title, (margin_x, title_y))
    canvas = Image.alpha_composite(canvas, title_layer)

    board_left = margin_x
    board_right = canvas_w - margin_x
    board_top = max(
        title_y + title.height + max(18, int(round(canvas_h * 0.045))),
        int(round(canvas_h * 0.16)),
    )
    board_bottom_margin = max(24, int(round(canvas_h * 0.055)))
    board_bottom = canvas_h - board_bottom_margin
    board_w = max(300, board_right - board_left)
    board_h = max(300, board_bottom - board_top)

    canvas = draw_rounded_rectangle(
        canvas,
        (board_left, board_top, board_left + board_w, board_top + board_h),
        corner_radius=48,
        fill=(255, 255, 255, 208),
    )

    layer = Image.new("RGBA", canvas.size, (255, 255, 255, 0))

    col_w = board_w // 3
    col_areas = [
        (board_left, board_top, board_left + col_w, board_top + board_h),
        (board_left + col_w, board_top, board_left + col_w * 2, board_top + board_h),
        (board_left + col_w * 2, board_top, board_left + board_w, board_top + board_h),
    ]

    _draw_column(layer, col_areas[0], "简单", easy_rows)
    _draw_column(layer, col_areas[1], "普通", normal_rows)
    _draw_column(layer, col_areas[2], "困难", hard_rows)

    sep_padding = max(16, int(round(board_h * 0.035)))
    sep_top = board_top + sep_padding
    sep_bottom = board_top + board_h - sep_padding
    _draw_capsule_separator(
        layer,
        board_left + col_w,
        sep_top,
        sep_bottom,
        width=3,
        dash_length=9,
        dash_gap=8,
    )
    _draw_capsule_separator(
        layer,
        board_left + col_w * 2,
        sep_top,
        sep_bottom,
        width=3,
        dash_length=9,
        dash_gap=8,
    )

    result = Image.alpha_composite(canvas, layer)
    return result
