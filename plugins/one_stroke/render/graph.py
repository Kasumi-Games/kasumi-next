from __future__ import annotations

from typing import Literal
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from plugins.render_service import (
    create_bg,
    draw_pill,
    load_font,
    draw_rounded_rectangle,
)

from ..session import GameSession
from ..difficulty import apply_time_decay


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return load_font(size)


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
    font1 = _font(text1_size)
    font2 = _font(text2_size)
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


def _cell_params(rows: int, cols: int) -> tuple[int, int, int, int]:
    visual_rows = rows * 2 - 1
    visual_cols = cols * 2 - 1
    board_left, board_top = 56 + 50, 182 + 50
    board_size = 786 - 100

    gap = (
        8
        if max(visual_rows, visual_cols) <= 5
        else (6 if max(visual_rows, visual_cols) <= 7 else 5)
    )
    cell_w = (board_size - gap * (visual_cols - 1)) // visual_cols
    cell_h = (board_size - gap * (visual_rows - 1)) // visual_rows
    cell_size = min(cell_w, cell_h)

    grid_w = visual_cols * cell_size + (visual_cols - 1) * gap
    grid_h = visual_rows * cell_size + (visual_rows - 1) * gap
    offset_x = board_left + (board_size - grid_w) // 2
    offset_y = board_top + (board_size - grid_h) // 2
    return cell_size, gap, offset_x, offset_y


@lru_cache(maxsize=64)
def _generate_cell(
    size: int, fill: tuple[int, int, int, int], corner_radius: int, label: str = ""
) -> Image.Image:
    cell = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cell = draw_rounded_rectangle(
        cell,
        (0, 0, size, size),
        corner_radius=corner_radius,
        fill=fill,
    )
    if label:
        draw = ImageDraw.Draw(cell)
        font = _font(max(12, size // 3))
        bbox = draw.textbbox((0, 0), label, font=font)
        draw.text(
            (
                (size - (bbox[2] - bbox[0])) // 2,
                (size - (bbox[3] - bbox[1])) // 2 - bbox[1],
            ),
            label,
            font=font,
            fill=(255, 255, 255, 255),
        )
    return cell


@lru_cache(maxsize=64)
def _generate_node_circle(
    size: int, fill: tuple[int, int, int, int], label: str = ""
) -> Image.Image:
    node = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(node)
    draw.ellipse((0, 0, size - 1, size - 1), fill=fill)
    if label:
        font = _font(max(12, size // 3))
        bbox = draw.textbbox((0, 0), label, font=font)
        draw.text(
            (
                (size - (bbox[2] - bbox[0])) // 2,
                (size - (bbox[3] - bbox[1])) // 2 - bbox[1],
            ),
            label,
            font=font,
            fill=(255, 255, 255, 255),
        )
    return node


@lru_cache(maxsize=64)
def _generate_pipe(
    length: int,
    thickness: int,
    fill: tuple[int, int, int, int],
    horizontal: bool,
) -> Image.Image:
    if horizontal:
        w, h = length, thickness
    else:
        w, h = thickness, length
    pipe = Image.new("RGBA", (w, h), fill)
    return pipe


def _node_from_visual(vr: int, vc: int) -> tuple[int, int]:
    return vr // 2, vc // 2


def _edge_from_visual(
    vr: int, vc: int
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    if vr % 2 == 0 and vc % 2 == 1:
        return (vr // 2, vc // 2), (vr // 2, vc // 2 + 1)
    if vr % 2 == 1 and vc % 2 == 0:
        return (vr // 2, vc // 2), (vr // 2 + 1, vc // 2)
    return None


def _cell_type(
    session: GameSession, vr: int, vc: int
) -> Literal["wall", "traversable", "drawn", "start", "current"]:
    graph = session.graph

    if vr % 2 == 1 and vc % 2 == 1:
        return "wall"

    if vr % 2 == 0 and vc % 2 == 0:
        node = _node_from_visual(vr, vc)
        if node == session.current_pos:
            return "current"
        if node == graph.start_node:
            return "start"
        if node in session.visited_nodes:
            return "drawn"
        if graph.has_node(node):
            return "traversable"
        return "wall"

    edge_nodes = _edge_from_visual(vr, vc)
    if edge_nodes is None:
        return "wall"
    edge = frozenset(edge_nodes)
    if edge in session.drawn_edges:
        return "drawn"
    if edge in graph.edges:
        return "traversable"
    return "wall"


def render(session: GameSession) -> Image.Image:
    live_reward = apply_time_decay(
        base_reward=session.reward,
        elapsed_seconds=session.elapsed_seconds(),
        graph=session.graph,
    )
    canvas = create_bg(
        session.bg_path,
        width=896,
        height=1024,
        text="BanG Dream!",
        blur_radius=40,
        triangle_size=200,
        brightness_difference=0.06,
    )
    title = _generate_title(
        "一笔画",
        f"{session.difficulty_name} | {session.drawn_count}/{session.total_edges} | 奖励 {live_reward}/{session.reward}",
        560,
        57,
    )
    title_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    title_layer.paste(title, (56, 36))
    canvas = Image.alpha_composite(canvas, title_layer)

    canvas = draw_rounded_rectangle(
        canvas,
        (56, 182, 56 + 786, 182 + 786),
        corner_radius=48,
        fill=(255, 255, 255, 208),
    )

    visual_rows = session.graph.rows * 2 - 1
    visual_cols = session.graph.cols * 2 - 1
    cell_size, gap, offset_x, offset_y = _cell_params(
        session.graph.rows, session.graph.cols
    )
    corner_radius = max(6, cell_size // 7)

    palette = {
        "wall": (90, 85, 110, 255),
        "traversable": (215, 215, 225, 255),
        "drawn": (234, 78, 116, 255),
        "start": (76, 175, 80, 255),
        "current": (66, 133, 244, 255),
    }

    pipe_thickness = cell_size
    node_overlap = cell_size // 2

    wall_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    traversable_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    drawn_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    special_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    for vr in range(visual_rows):
        for vc in range(visual_cols):
            ctype = _cell_type(session, vr, vc)
            x = offset_x + vc * (cell_size + gap)
            y = offset_y + vr * (cell_size + gap)

            is_node = vr % 2 == 0 and vc % 2 == 0
            is_h_edge = vr % 2 == 0 and vc % 2 == 1
            is_v_edge = vr % 2 == 1 and vc % 2 == 0

            if is_node:
                if ctype == "wall":
                    cell = _generate_cell(
                        cell_size,
                        palette["wall"],
                        corner_radius=corner_radius,
                        label="",
                    )
                    wall_layer.paste(cell, (x, y), cell)
                else:
                    label = "S" if ctype == "start" else ""
                    node = _generate_node_circle(
                        cell_size,
                        palette[ctype],
                        label=label,
                    )
                    if ctype == "traversable":
                        traversable_layer.paste(node, (x, y), node)
                    elif ctype == "drawn":
                        drawn_layer.paste(node, (x, y), node)
                    else:
                        special_layer.paste(node, (x, y), node)

                if ctype == "current":
                    glow = Image.new(
                        "RGBA", (cell_size + 8, cell_size + 8), (0, 0, 0, 0)
                    )
                    glow_draw = ImageDraw.Draw(glow)
                    glow_draw.ellipse(
                        (0, 0, cell_size + 7, cell_size + 7),
                        outline=(66, 133, 244, 150),
                        width=4,
                    )
                    special_layer.paste(glow, (x - 4, y - 4), glow)

            elif is_h_edge:
                if ctype == "wall":
                    cell = _generate_cell(
                        cell_size,
                        palette["wall"],
                        corner_radius=corner_radius,
                        label="",
                    )
                    wall_layer.paste(cell, (x, y), cell)
                else:
                    pipe_len = cell_size + 2 * gap + 2 * node_overlap
                    pipe = _generate_pipe(
                        pipe_len,
                        pipe_thickness,
                        palette[ctype],
                        horizontal=True,
                    )
                    px = x - gap - node_overlap
                    py = y + (cell_size - pipe_thickness) // 2
                    if ctype == "drawn":
                        drawn_layer.paste(pipe, (px, py), pipe)
                    else:
                        traversable_layer.paste(pipe, (px, py), pipe)

            elif is_v_edge:
                if ctype == "wall":
                    cell = _generate_cell(
                        cell_size,
                        palette["wall"],
                        corner_radius=corner_radius,
                        label="",
                    )
                    wall_layer.paste(cell, (x, y), cell)
                else:
                    pipe_len = cell_size + 2 * gap + 2 * node_overlap
                    pipe = _generate_pipe(
                        pipe_len,
                        pipe_thickness,
                        palette[ctype],
                        horizontal=False,
                    )
                    px = x + (cell_size - pipe_thickness) // 2
                    py = y - gap - node_overlap
                    if ctype == "drawn":
                        drawn_layer.paste(pipe, (px, py), pipe)
                    else:
                        traversable_layer.paste(pipe, (px, py), pipe)

            else:
                cell = _generate_cell(
                    cell_size,
                    palette["wall"],
                    corner_radius=corner_radius,
                    label="",
                )
                wall_layer.paste(cell, (x, y), cell)

    canvas = Image.alpha_composite(canvas, wall_layer)
    canvas = Image.alpha_composite(canvas, traversable_layer)
    canvas = Image.alpha_composite(canvas, drawn_layer)
    canvas = Image.alpha_composite(canvas, special_layer)

    return canvas
