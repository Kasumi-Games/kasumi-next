from zlib import crc32
from typing import Literal
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from utils import cards
from plugins.render import Rect
from plugins.render import Size
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import Constraints
from plugins.render import RenderContext
from plugins.render import PlayerIdentity
from plugins.render.primitives import load_font
from plugins.render.primitives import draw_rounded_rectangle
from plugins.render.kits.bangdream import BG_DIR
from plugins.render.kits.bangdream import CHINESE_FONT
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.kasumi import KasumiKit
from plugins.render.kits.mewtype import MewtypeKit

from ..session import GameSession
from ..difficulty import apply_time_decay

#: Width of the board panel, which the identity strip matches.
BOARD_WIDTH = 786


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return load_font(size, CHINESE_FONT)


def _cell_params(
    rows: int, cols: int, rect: Rect, ctx: RenderContext
) -> tuple[int, int, int, int]:
    visual_rows = rows * 2 - 1
    visual_cols = cols * 2 - 1
    board_size = min(rect.width, rect.height)

    logical_gap = (
        8
        if max(visual_rows, visual_cols) <= 5
        else (6 if max(visual_rows, visual_cols) <= 7 else 5)
    )
    gap = ctx.scale_px(logical_gap)
    cell_w = (board_size - gap * (visual_cols - 1)) // visual_cols
    cell_h = (board_size - gap * (visual_rows - 1)) // visual_rows
    cell_size = min(cell_w, cell_h)

    grid_w = visual_cols * cell_size + (visual_cols - 1) * gap
    grid_h = visual_rows * cell_size + (visual_rows - 1) * gap
    offset_x = rect.x + (rect.width - grid_w) // 2
    offset_y = rect.y + (rect.height - grid_h) // 2
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


@dataclass(frozen=True)
class OneStrokeBoard:
    session: GameSession
    palette: dict[str, tuple[int, int, int, int]] | None = None

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(686, 686))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        session = self.session
        visual_rows = session.graph.rows * 2 - 1
        visual_cols = session.graph.cols * 2 - 1
        cell_size, gap, offset_x, offset_y = _cell_params(
            session.graph.rows, session.graph.cols, rect, ctx
        )
        _render_board_cells(
            session,
            canvas,
            visual_rows,
            visual_cols,
            cell_size,
            gap,
            offset_x,
            offset_y,
            ctx,
            self.palette,
        )


def _render_board_cells(
    session: GameSession,
    canvas: Image.Image,
    visual_rows: int,
    visual_cols: int,
    cell_size: int,
    gap: int,
    offset_x: int,
    offset_y: int,
    ctx: RenderContext,
    palette_override: dict[str, tuple[int, int, int, int]] | None = None,
) -> None:
    corner_radius = max(6, cell_size // 7)

    palette = palette_override or {
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
                        "RGBA",
                        (cell_size + ctx.scale_px(8), cell_size + ctx.scale_px(8)),
                        (0, 0, 0, 0),
                    )
                    glow_draw = ImageDraw.Draw(glow)
                    glow_draw.ellipse(
                        (
                            0,
                            0,
                            cell_size + ctx.scale_px(7),
                            cell_size + ctx.scale_px(7),
                        ),
                        outline=(*palette["current"][:3], 150),
                        width=ctx.scale_px(4),
                    )
                    special_layer.paste(
                        glow, (x - ctx.scale_px(4), y - ctx.scale_px(4)), glow
                    )

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

    for layer in (wall_layer, traversable_layer, drawn_layer, special_layer):
        canvas.paste(Image.alpha_composite(canvas, layer), (0, 0))


def _background_index(session: GameSession, count: int) -> int:
    """Deterministic background pick for one game.

    Keyed on the session's stable identity (player, channel, creation stamp):
    a new game may land on a different background, but every move of the same
    game re-renders over the same one. ``started_at`` is deliberately not part
    of the key — ``restart_timer()`` resets it after the first board send,
    which would shift the background between move 0 and move 1.
    """

    key = f"{session.user_id}:{session.channel_id}:{session.created_at}"
    return crc32(key.encode("utf-8")) % count


def _background(kit: BaseKit, session: GameSession) -> Image.Image:
    if isinstance(kit, BanGDreamKit):
        # Sorted, because glob order is filesystem-dependent and the index
        # below must always land on the same file.
        choices = sorted(Path(BG_DIR).glob("bg[0-9][0-9][0-9][0-9][0-9].png"))
        if choices:
            return kit.background(
                source=choices[_background_index(session, len(choices))]
            )
    return kit.background()


def _title_bar(
    kit: BaseKit,
    title: str,
    subtitle: str,
    *,
    width: int,
    height: int,
):
    if isinstance(kit, MewtypeKit):
        return kit.compact_header("ONE STROKE", subtitle, width=BOARD_WIDTH)
    if isinstance(kit, KasumiKit):
        return kit.game_title(title, subtitle, width=width, height=height)
    if isinstance(kit, BanGDreamKit):
        return kit.title_pill(
            title,
            subtitle,
            pill_width=width,
            pill_height=height,
        )
    return kit.panel(
        Frame(
            kit.text(
                f"{title} - {subtitle}",
                font_size=24,
                align="center",
                max_lines=1,
            ),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(width),
        height=Fixed(height),
        radius=height // 2,
    )


def _board_panel(kit: BaseKit, child):
    if isinstance(kit, BanGDreamKit):
        return kit.panel(
            child,
            radius=64,
            padding=50,
            width=Fixed(786),
            height=Fixed(786),
        )
    return kit.panel(
        Frame(
            child,
            width=Fixed(786),
            height=Fixed(786),
            padding=50,
            align_x="stretch",
            align_y="stretch",
            aspect_ratio=1,
        ),
        width=Fixed(786),
        height=Fixed(786),
    )


def render(
    session: GameSession,
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
    detail: str | None = None,
) -> Image.Image:
    live_reward = apply_time_decay(
        base_reward=session.reward,
        elapsed_seconds=session.elapsed_seconds(),
        graph=session.graph,
    )
    kit = kit or BanGDreamKit()
    title = (
        f"{session.difficulty_name} | {session.drawn_count}/{session.total_edges} | "
        f"奖励 {live_reward}/{session.reward}"
    )
    sections: list[Component] = [
        _title_bar(kit, "一笔画", title, width=560, height=57)
    ]
    if identity is not None:
        sections.append(
            cards.game_identity(kit, identity, width=BOARD_WIDTH, detail=detail)
        )
    palette = None
    if isinstance(kit, MewtypeKit):
        palette = {
            "wall": (32, 47, 109, 255),
            "traversable": (232, 225, 242, 255),
            "drawn": (255, 115, 213, 255),
            "start": (201, 131, 232, 255),
            "current": (29, 211, 243, 255),
        }
    sections.append(_board_panel(kit, OneStrokeBoard(session, palette)))

    page = AutoPage(
        min_width=896,
        background=_background(kit, session),
        padding=56,
        child=VStack(sections, gap=24),
    )
    return page.render()
