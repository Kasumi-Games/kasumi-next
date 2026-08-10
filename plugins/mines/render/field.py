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
from plugins.render.kits.bangdream import BG_DIR
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.kasumi import KasumiKit
from plugins.render.kits.mewtype import MewtypeKit

from ..models import Field
from ..models import BlockType

#: Width of the board panel, which the identity strip matches.
BOARD_WIDTH = 786


def generate_unrevealed_field(index: int, kit: BaseKit) -> Component:
    is_mewtype = isinstance(kit, MewtypeKit)
    return kit.panel(
        Frame(
            kit.text(
                str(index),
                font_size=80,
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
        width=Fixed(120),
        height=Fixed(120),
        fill=kit.paper_fill if is_mewtype else (223, 223, 223, 255),
        radius=16,
    )


def generate_revealed_field(
    stamp_path: Path, background_color: tuple[int, int, int], kit: BaseKit
) -> Component:
    frame_color = None
    if isinstance(kit, MewtypeKit):
        is_mine = background_color[2] > background_color[0]
        background_color = (255, 232, 248) if is_mine else (228, 248, 255)
        frame_color = kit.accent if is_mine else kit.primary
    panel_kwargs = {"frame_color": frame_color} if frame_color is not None else {}
    return kit.panel(
        Frame(
            kit.image(stamp_path, width=Fixed(110), height=Fixed(110)),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(120),
        height=Fixed(120),
        fill=background_color + (255,),
        radius=16,
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
            width=Fixed(786),
            height=Fixed(786),
            padding=50,
            radius=32,
        )
    if isinstance(kit, MewtypeKit):
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

    for i in range(field.height):
        for j in range(field.width):
            block = field.field[i][j]
            if block == BlockType.EMPTY or block == BlockType.MINE:
                cell = generate_unrevealed_field(i * field.width + j + 1, kit)
            elif block == BlockType.EMPTY_SHOWN:
                cell = generate_revealed_field(
                    field.kasumi_stamps[i][j],
                    (255, 124, 85),
                    kit,
                )
            elif block == BlockType.MINE_SHOWN:
                cell = generate_revealed_field(
                    field.arisa_stamps[i][j],
                    (184, 130, 225),
                    kit,
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
                column_track=Fixed(120),
                row_track=Fixed(120),
                gap=21,
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
