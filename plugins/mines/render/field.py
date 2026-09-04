from pathlib import Path

from PIL import Image

from utils import cards
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.kasumi import KasumiKit
from plugins.render.kits.mewtype import MewtypeKit
from plugins.render.kits.bangdream import BG_DIR
from plugins.render.kits.bangdream import BanGDreamKit

from ..models import Field
from ..models import BlockType

#: Width of the board panel, which the identity strip matches.
BOARD_WIDTH = 786
BOARD_PADDING = 50
DEFAULT_CELL_SIZE = 120
DEFAULT_CELL_GAP = 21
MIN_CELL_GAP = 8


def _cell_layout(board_size: int) -> tuple[int, int]:
    """Return a cell size and gap that fill the fixed square board panel."""

    if board_size <= 0:
        raise ValueError("board size must be positive")
    inner_size = BOARD_WIDTH - BOARD_PADDING * 2
    gap = min(
        DEFAULT_CELL_GAP,
        max(MIN_CELL_GAP, round(DEFAULT_CELL_GAP * 5 / board_size)),
    )
    cell_size = (inner_size - gap * (board_size - 1)) // board_size
    return cell_size, gap


def generate_unrevealed_field(
    index: int, kit: BaseKit, *, cell_size: int = DEFAULT_CELL_SIZE
) -> Component:
    is_mewtype = isinstance(kit, MewtypeKit)
    radius = max(8, round(16 * cell_size / DEFAULT_CELL_SIZE))
    font_size = max(24, round(80 * cell_size / DEFAULT_CELL_SIZE))
    if index >= 100:
        font_size = min(font_size, round(cell_size * 0.48))
    return kit.panel(
        Frame(
            kit.text(
                str(index),
                font_size=font_size,
                color=(
                    (169, 205, 245, 255)
                    if is_mewtype
                    else (255, 255, 255, 255)
                ),
                align="center",
                max_lines=1,
            ),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(cell_size),
        height=Fixed(cell_size),
        fill=kit.paper_fill if is_mewtype else (223, 223, 223, 255),
        radius=radius,
    )


def generate_revealed_field(
    stamp_path: Path,
    background_color: tuple[int, int, int],
    kit: BaseKit,
    *,
    cell_size: int = DEFAULT_CELL_SIZE,
) -> Component:
    frame_color = None
    if isinstance(kit, MewtypeKit):
        is_mine = background_color[2] > background_color[0]
        background_color = (255, 232, 248) if is_mine else (228, 248, 255)
        frame_color = kit.accent if is_mine else kit.primary
    panel_kwargs = {"frame_color": frame_color} if frame_color is not None else {}
    stamp_size = max(1, cell_size - round(10 * cell_size / DEFAULT_CELL_SIZE))
    radius = max(8, round(16 * cell_size / DEFAULT_CELL_SIZE))
    return kit.panel(
        Frame(
            kit.image(
                stamp_path, width=Fixed(stamp_size), height=Fixed(stamp_size)
            ),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(cell_size),
        height=Fixed(cell_size),
        fill=background_color + (255,),
        radius=radius,
        **panel_kwargs,
    )


def _background(kit: BaseKit):
    if isinstance(kit, BanGDreamKit):
        return kit.background(source=BG_DIR / "bg00039.png")
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
        return kit.compact_header(
            "EXPLORATION",
            "ARISA'S WAREHOUSE",
            width=BOARD_WIDTH,
        )
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
        return kit.board_frame(
            child,
            width=Fixed(BOARD_WIDTH),
            height=Fixed(BOARD_WIDTH),
            padding=BOARD_PADDING,
            radius=32,
        )
    if isinstance(kit, MewtypeKit):
        return kit.panel(
            Frame(
                child,
                width=Fixed(BOARD_WIDTH),
                height=Fixed(BOARD_WIDTH),
                padding=BOARD_PADDING,
                align_x="stretch",
                align_y="stretch",
                aspect_ratio=1,
            ),
            width=Fixed(BOARD_WIDTH),
            height=Fixed(BOARD_WIDTH),
        )
    return kit.panel(
        Frame(
            child,
            width=Fixed(BOARD_WIDTH),
            height=Fixed(BOARD_WIDTH),
            padding=BOARD_PADDING,
            align_x="stretch",
            align_y="stretch",
            aspect_ratio=1,
        ),
        width=Fixed(BOARD_WIDTH),
        height=Fixed(BOARD_WIDTH),
        radius=32,
    )


def render(
    field: "Field",
    kit: BaseKit | None = None,
    identity: PlayerIdentity | None = None,
    detail: str | None = None,
) -> Image.Image:
    kit = kit or BanGDreamKit()
    cells = []
    cell_size, cell_gap = _cell_layout(max(field.width, field.height))

    for i in range(field.height):
        for j in range(field.width):
            block = field.field[i][j]
            if block == BlockType.EMPTY or block == BlockType.MINE:
                cell = generate_unrevealed_field(
                    i * field.width + j + 1, kit, cell_size=cell_size
                )
            elif block == BlockType.EMPTY_SHOWN:
                cell = generate_revealed_field(
                    field.kasumi_stamps[i][j],
                    (255, 124, 85),
                    kit,
                    cell_size=cell_size,
                )
            elif block == BlockType.MINE_SHOWN:
                cell = generate_revealed_field(
                    field.arisa_stamps[i][j],
                    (184, 130, 225),
                    kit,
                    cell_size=cell_size,
                )
            cells.append(cell)

    sections: list[Component] = [
        _title_bar(kit, "探险", "Arisa的仓库", width=500, height=57)
    ]
    if identity is not None:
        sections.append(
            cards.game_identity(kit, identity, width=BOARD_WIDTH, detail=detail)
        )
    sections.append(
        _board_panel(
            kit,
            Grid(
                children=cells,
                columns=field.width,
                rows=field.height,
                column_track=Fixed(cell_size),
                row_track=Fixed(cell_size),
                gap=cell_gap,
            ),
        )
    )

    page = AutoPage(
        min_width=896,
        background=_background(kit),
        padding=56,
        child=VStack(sections, gap=32),
    )
    return page.render()
