"""A shop catalogue: category index, illustrated product plates and theme spread."""

from .folio import surface
from ..components import ROSE
from ..components import MUTED
from ..components import RESOURCES


def catalogue(f, data):
    y = f.title("流星堂", "THE COLLECTION SHOP", data.subtitle)
    if data.equipped_summary:
        y = f.text(data.equipped_summary, 58, y, 1004, 23, ROSE) + 28
    category_index = bool(data.rows) and all(
        not r.show_art_slot and not r.show_trailing for r in data.rows
    )
    if category_index:
        for start in range(0, len(data.rows), 2):
            ends = []
            for col, row in enumerate(data.rows[start : start + 2]):
                x = 58 + col * 526
                f.text(str(row.index), x, y, 88, 64, ROSE)
                bottom = f.text(row.name, x + 118, y + 8, 356, 35)
                bottom = f.text(row.detail, x + 118, bottom + 14, 356, 23, MUTED)
                f.line(x, max(bottom + 28, y + 150), 474, MUTED)
                ends.append(max(bottom + 54, y + 186))
            y = max(ends)
    else:
        for start in range(0, len(data.rows), 2):
            ends = []
            for col, row in enumerate(data.rows[start : start + 2]):
                x = 58 + col * 526
                f.text(str(row.index), x, y, 120, 25, ROSE)
                f.text(f"★{row.rarity}", x + 374, y, 100, 24, ROSE, align="right")
                if row.art is not None:
                    f.image(row.art, x + 30, y + 58, 414, 250)
                    bottom = y + 330
                else:
                    # Theme products use a paper-and-ink specimen, not a fake
                    # missing-art thumbnail or an empty standing-art slot.
                    f.image(
                        RESOURCES / "book.png", x + 30, y + 58, 414, 160, opacity=0.35
                    )
                    f.component(
                        f.kit.page_title(row.kind, font_size=30),
                        x + 60,
                        y + 92,
                        354,
                        90,
                    )
                    bottom = y + 240
                bottom = f.text(row.name, x, bottom, 474, 28)
                bottom = f.text(row.detail, x, bottom + 12, 474, 24, ROSE)
                if row.equipped:
                    bottom = f.text("已拥有 / 已装备", x, bottom + 12, 474, 22, MUTED)
                f.line(x, bottom + 24, 474, MUTED)
                ends.append(bottom + 58)
            y = max(ends)
    if not data.rows:
        y = f.text("本页暂无在售商品。", 58, y + 40, 1004, 30, MUTED)
    if data.panel_footer:
        y = f.text(data.panel_footer, 58, y + 12, 1004, 22, MUTED)
    f.footer(
        data.footer or f"第 {data.page}/{data.total_pages} 页 · /流星堂 购买 <编号>",
        y + 26,
    )


@surface(1240, book=True)
def preview(f, data):
    y = f.title(data.name, "THEME SPECIMEN", f"流星堂 / {data.sku}")
    # A real dossier miniature demonstrates the theme's type, artwork and
    # composition together; the offer owns the facing page.
    f.component(
        f.kit.portrait(RESOURCES / "portrait_ema.png", width=300, height=340),
        130,
        y + 26,
        300,
        340,
    )
    left = f.text("人物档案", 58, y + 390, 500, 22, ROSE)
    left = f.text("樱羽艾玛", 58, left + 12, 500, 38)
    left = f.text("旧纸记下证言，墨迹划出边界。", 58, left + 20, 500, 25)
    left = f.facts((("赛季积分", "2,350 Pt"), ("等级", "Lv.24")), 58, left + 30, 500)
    right = f.section("主题图鉴", 658, y, 524)
    right = f.text(data.description, 658, right, 524, 28)
    right = f.text(
        "资料档案 · 证物展示 · 往来信件\n棋盘对局 · 成绩记录 · 流星堂目录",
        658,
        right + 30,
        524,
        24,
        MUTED,
    )
    right = f.metric(
        "已购入" if data.owned else "售价",
        "已拥有" if data.owned else f"{data.price:,} 盆栽",
        658,
        right + 48,
        524,
        size=46,
    )
    if data.notice:
        right = f.text(data.notice, 658, right + 24, 524, 23, ROSE)
    action = f"/装扮 装备 {data.name}" if data.owned else f"/流星堂 购买 {data.sku}"
    f.footer(data.footer or action, max(left, right) + 30)
