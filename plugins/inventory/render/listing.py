"""Paginated image cards for ``/仓库`` and ``/装扮``."""

from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import badge
from utils.cards import card_page
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.types import ImageSource
from plugins.render.kits.bangdream import BanGDreamKit


@dataclass(frozen=True)
class InventoryListRow:
    index: int | str
    name: str
    detail: str
    kind: str
    rarity: int = 0
    art: ImageSource | None = None
    equipped: bool = False
    show_art_slot: bool = True
    show_trailing: bool = True


@dataclass(frozen=True)
class InventoryListData:
    title: str
    page: int
    total_pages: int
    rows: tuple[InventoryListRow, ...]
    subtitle: str = ""
    equipped_summary: str = ""
    footer: str = ""


def render_inventory_list(
    data: InventoryListData, kit: BaseKit | None = None
) -> Image.Image:
    return inventory_list_page(data, kit).render()


def inventory_list_page(
    data: InventoryListData, kit: BaseKit | None = None
) -> AutoPage:
    kit = kit or BanGDreamKit()
    children: list[Component] = []
    if data.equipped_summary:
        children.append(
            kit.text(
                data.equipped_summary,
                font_size=LABEL_SIZE,
                max_lines=2,
                overflow="ellipsis",
            )
        )
        children.append(kit.separator(length=Fill()))
    children.extend(_row(kit, row) for row in data.rows)
    body = panel_section(
        kit,
        VStack(children, gap=14, align="stretch"),
    )
    return card_page(
        kit,
        title=data.title,
        subtitle=data.subtitle or f"第 {data.page}/{data.total_pages} 页",
        body=body,
        footer=(
            kit.text(data.footer, font_size=LABEL_SIZE, wrap=False, max_lines=1)
            if data.footer
            else None
        ),
    )


def _row(kit: BaseKit, row: InventoryListRow) -> Component:
    art_slot: Component
    if row.art is not None:
        art_slot = kit.image(
            row.art,
            width=Fixed(64),
            height=Fixed(64),
            fit="contain",
        )
    else:
        art_slot = badge(
            kit,
            row.kind[:2] or "物品",
            width=64,
            height=40,
            font_size=18,
        )

    rarity = f"★{row.rarity}" if row.rarity else row.kind
    right_rows: list[Component] = [
        kit.text(
            rarity,
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            align="right",
            wrap=False,
            max_lines=1,
        )
    ]
    if row.equipped:
        right_rows.append(
            kit.text("已装备", font_size=LABEL_SIZE, align="right", wrap=False)
        )

    row_children: list[Component] = [
        badge(kit, str(row.index), width=48, height=40, font_size=20)
    ]
    if row.show_art_slot:
        row_children.append(
            Frame(
                art_slot,
                width=Fixed(64),
                height=Fixed(64),
                align_x="center",
                align_y="center",
            )
        )
    row_children.append(
        Frame(
            VStack(
                [
                    kit.text(
                        row.name,
                        font_size=BODY_SIZE,
                        wrap=False,
                        max_lines=1,
                        overflow="shrink",
                    ),
                    kit.text(
                        row.detail,
                        font_size=LABEL_SIZE,
                        color=kit.muted_text_color,
                        wrap=False,
                        max_lines=1,
                        overflow="ellipsis",
                    ),
                ],
                gap=5,
                align="stretch",
            ),
            width=Fill(),
            align_x="stretch",
            align_y="center",
        )
    )
    if row.show_trailing:
        row_children.append(VStack(right_rows, gap=4, align="end"))

    return kit.panel(
        HStack(row_children, gap=16, align="center"),
        width=Fixed(INNER_WIDTH),
        height=Fixed(92),
        padding=Insets.only(left=12, top=10, right=16, bottom=10),
    )


__all__ = [
    "InventoryListData",
    "InventoryListRow",
    "inventory_list_page",
    "render_inventory_list",
]
