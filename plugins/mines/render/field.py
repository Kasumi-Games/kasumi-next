from pathlib import Path

from PIL import Image

from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BG_DIR
from plugins.render.kits.bangdream import BanGDreamKit

from ..models import Field
from ..models import BlockType


def generate_unrevealed_field(index: int, kit: BaseKit) -> Component:
    return kit.panel(
        Frame(
            kit.text(
                str(index),
                font_size=80,
                color=(255, 255, 255, 255),
                align="center",
                max_lines=1,
            ),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(120),
        height=Fixed(120),
        fill=(223, 223, 223, 255),
        radius=16,
    )


def generate_revealed_field(
    stamp_path: Path, background_color: tuple[int, int, int], kit: BaseKit
) -> Component:
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
                color=(255, 255, 255, 255),
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
        fill=(255, 255, 255, 200),
        radius=32,
    )


def render(field: "Field", kit: BaseKit | None = None) -> Image.Image:
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

    page = AutoPage(
        min_width=896,
        background=_background(kit),
        padding=56,
        child=VStack(
            [
                _title_bar(kit, "探险", "Arisa的仓库", width=500, height=57),
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
                ),
            ],
            gap=32,
        ),
    )
    return page.render()
