"""Image-card listings for /仓库 and /装扮."""

from pathlib import Path

from plugins.inventory.render import InventoryListData
from plugins.inventory.render import InventoryListRow
from plugins.inventory.render import inventory_list_page
from plugins.inventory.render import render_inventory_list
from plugins.render.kits import KasumiKit
from plugins.render.kits import MinimalKit


ROOT = Path(__file__).resolve().parents[1]
FRAME = (
    ROOT
    / "plugins"
    / "inventory"
    / "resources"
    / "items"
    / "avatar_frames"
    / "frame_starbeat_top50.png"
)


def _data() -> InventoryListData:
    return InventoryListData(
        title="装扮",
        subtitle="我的装扮 · 第 2/3 页",
        page=2,
        total_pages=3,
        equipped_summary="当前装备 · 头像框：星之鼓动前五十头像框",
        footer="/装扮 <页码> 翻页 · /装扮 装备 <序号或名称>",
        rows=(
            InventoryListRow(
                index=11,
                name="星之鼓动前五十头像框",
                detail="第一赛季前五十限定头像框。",
                kind="头像框",
                rarity=3,
                art=FRAME,
                equipped=True,
            ),
        ),
    )


def _text(component) -> list[str]:
    values: list[str] = []

    def visit(node) -> None:
        value = getattr(node, "text", None)
        if isinstance(value, str):
            values.append(value)
        for attr in ("children", "child"):
            child = getattr(node, attr, None)
            if isinstance(child, (list, tuple)):
                for item in child:
                    visit(item)
            elif child is not None:
                visit(child)

    visit(component)
    return values


def _nodes(component) -> list[object]:
    values: list[object] = []

    def visit(node) -> None:
        values.append(node)
        for attr in ("children", "child"):
            child = getattr(node, attr, None)
            if isinstance(child, (list, tuple)):
                for item in child:
                    visit(item)
            elif child is not None:
                visit(child)

    visit(component)
    return values


def test_listing_card_contains_page_numbers_commands_and_equipped_state() -> None:
    joined = " ".join(_text(inventory_list_page(_data(), MinimalKit()).child))
    assert "第 2/3 页" in joined
    assert "11" in joined
    assert "星之鼓动前五十头像框" in joined
    assert "已装备" in joined
    assert "/装扮 装备 <序号或名称>" in joined


def test_listing_card_renders_in_plain_and_character_themes() -> None:
    assert render_inventory_list(_data(), MinimalKit()).size[0] == 864
    assert render_inventory_list(_data(), KasumiKit()).size[0] == 864


def test_mewtype_listing_uses_transparent_rows_and_separators() -> None:
    from plugins.render.kits.mewtype import MewtypeKit

    data = InventoryListData(
        title="流星堂",
        subtitle="立绘",
        page=1,
        total_pages=1,
        wordmark_title="SHOP",
        panel_footer="第 1/1 页",
        rows=(
            InventoryListRow(
                index="A01",
                name="牛込里美 守望着的应援",
                detail="500 盆栽",
                kind="立绘",
                rarity=3,
                art=FRAME,
            ),
            InventoryListRow(
                index="A02",
                name="花园多惠 你终将跑过的天空",
                detail="500 盆栽",
                kind="立绘",
                rarity=3,
                art=FRAME,
            ),
        ),
    )
    page = inventory_list_page(data, MewtypeKit())
    nodes = _nodes(page.child)

    rectangular_panels = [
        node
        for node in nodes
        if type(node).__name__ == "MewtypePanel"
        and getattr(node, "radius", None) is None
    ]
    assert len(rectangular_panels) == 1
    assert sum(type(node).__name__ == "KitSeparator" for node in nodes) == 1
    assert sum(type(node).__name__ == "KitImage" for node in nodes) == 2
