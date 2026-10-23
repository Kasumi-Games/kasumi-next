"""A limited-item exhibition, evidence spread and acquisition register."""

from math import ceil

from .folio import surface
from ..components import ROSE
from ..components import MUTED


@surface(1240, book=True)
def banner(f, data):
    y = f.title(data.banner_name, "LIMITED COLLECTION", data.season_name)
    pair = len(data.featured_items) > 1
    has_art = data.featured_art is not None or any(
        item.image is not None for item in data.featured_items
    )
    x, width = (626, 556) if has_art else (58, 1124)
    if has_art:
        if pair:
            columns = min(2, len(data.featured_items))
            cell = (510 - 24 * (columns - 1)) // columns
            rows = ceil(len(data.featured_items) / columns)
            art_height = max(160, (560 - 24 * (rows - 1)) // rows)
            for i, item in enumerate(data.featured_items):
                f.image(
                    item.image,
                    58 + i % columns * (cell + 24),
                    y + i // columns * (art_height + 24),
                    cell,
                    art_height,
                )
        else:
            f.image(data.featured_art, 58, y, 510, 560)
        f.text("本期限定", 58, y + 582, 510, 23, ROSE, align="center")
    if pair:
        b = f.text(f"本期 {len(data.featured_items)} 位六星角色", x, y, width, 36)
        for item in data.featured_items:
            b = f.text(item.name, x, b + 14, width, 28)
    else:
        b = f.text(data.featured_name or "限定卡池", x, y, width, 39)
    b = f.text("★" * data.featured_rarity, x, b + 16, width, 26, ROSE)
    if data.bundle_names:
        b = f.section("首次入手加赠", x, b + 28, width)
        if data.frame_art is not None:
            f.image(data.frame_art, x, b, 82, 82)
            end = f.text(" · ".join(data.bundle_names), x + 110, b, width - 110, 24)
            b = max(end, b + 82)
        else:
            b = f.text(" · ".join(data.bundle_names), x, b, width, 24)
    if has_art:
        rates_x, rates_w, prices_x, prices_w = x, width, x, width
        rates_y = f.section("当前出率", rates_x, b + 28, rates_w)
    else:
        rates_x, rates_w, prices_x, prices_w = 58, 520, 662, 520
        rates_y = f.section("当前出率", rates_x, b + 40, rates_w)
    for index, (rarity, rate) in enumerate(data.rates):
        col, row = index % 2, index // 2
        cell_w = (rates_w - 28) // 2
        left, top = rates_x + col * (cell_w + 28), rates_y + row * 46
        f.text(f"★{rarity}", left, top, 64, 23, ROSE)
        f.text(f"{rate:.2%}", left + 72, top, cell_w - 72, 23, align="right")
    rate_bottom = rates_y + ceil(len(data.rates) / 2) * 46
    price_y = f.section(
        "抽取费用", prices_x, rate_bottom + 28 if has_art else b + 40, prices_w
    )
    half = (prices_w - 32) // 2
    a = f.metric(
        "单抽 / 星星贴纸", str(data.single_cost), prices_x, price_y, half, size=38
    )
    c = f.metric(
        "十连 / 星星贴纸",
        str(data.ten_cost),
        prices_x + half + 32,
        price_y,
        half,
        size=38,
    )
    y = max(a, c, rate_bottom, y + (640 if has_art else 0)) + 34
    f.meter(
        data.pity_count,
        data.hard_pity,
        58,
        y,
        1124,
        f"保底计数 {data.pity_count}/{data.hard_pity}",
    )
    f.footer("/抽卡 单抽 · /抽卡 十连 · /抽卡 记录")


def _art(f, item, x, y, w, h):
    from pathlib import Path

    from ..components import RESOURCES

    if (
        isinstance(item.image, (str, Path))
        and Path(item.image).resolve().parent == RESOURCES
    ):
        return f.component(f.kit.portrait(item.image, width=w, height=h), x, y, w, h)
    return f.image(item.image, x, y, w, h)


def _item(f, item, index, x, y, width, art_height):
    f.line(x, y, width, ROSE, 2 if item.rarity >= 6 else 1)
    f.text(f"{index:02d}", x, y + 12, 50, 20, MUTED)
    f.text(f"★{item.rarity}", x + width - 68, y + 10, 68, 23, ROSE, align="right")
    _art(f, item, x + 8, y + 48, width - 16, art_height)
    bottom = f.text(
        item.name, x + 8, y + art_height + 62, width - 16, 21, align="center", lines=3
    )
    states = [
        s
        for flag, s in ((item.is_new, "初次获得"), (item.featured, "本期精选"))
        if flag
    ]
    if states:
        bottom = f.text(
            " · ".join(states), x, bottom + 12, width, 19, ROSE, align="center"
        )
    if item.note:
        bottom = f.text(item.note, x, bottom + 8, width, 19, MUTED, align="center")
    return bottom + 26


@surface(1320, book=True)
def pull(f, data):
    y = f.title("抽取记录", "EVIDENCE REVEAL", data.banner_name)
    items = data.pulls
    if len(items) == 1:
        item = items[0]
        _art(f, item, 58, y, 520, 510)
        b = f.text(f"★{item.rarity} / 抽取结果", 650, y + 24, 612, 26, ROSE)
        b = f.text(item.name, 650, b + 26, 612, 39)
        states = [
            s
            for flag, s in ((item.is_new, "初次获得"), (item.featured, "本期精选"))
            if flag
        ]
        b = f.text(" · ".join(states), 650, b + 34, 612, 25, ROSE)
        if item.note:
            b = f.text(item.note, 650, b + 24, 612, 25)
        y = max(y + 540, b)
    else:
        # A rare featured exhibit owns a full facing page; the remaining pulls
        # form a numbered register on the left, rather than ten equal boxes.
        featured = next(
            (
                i
                for i, p in reversed(list(enumerate(items)))
                if p.featured and p.rarity >= 6
            ),
            None,
        )
        if featured is not None and len(items) >= 6:
            big = items[featured]
            small = [(i, p) for i, p in enumerate(items) if i != featured]
            grid_x, grid_w, columns = 58, 774, 3
            tile_w, gap = 246, 18
            right = f.text(f"{featured + 1:02d} / ★{big.rarity}", 900, y, 362, 24, ROSE)
            _art(f, big, 886, right + 24, 376, 400)
            right = f.text(big.name, 900, right + 450, 362, 31)
            if big.is_new:
                right = f.stamp("初次获得", 900, right + 24, 240)
            right = f.text("本期精选", 900, right + 24, 362, 26, ROSE)
            if big.note:
                right = f.text(big.note, 900, right + 16, 362, 24)
        else:
            small = list(enumerate(items))
            grid_x, grid_w, columns = 58, 1204, min(4, len(items))
            columns = ceil(len(items) / ceil(len(items) / columns))
            gap = 24
            tile_w = (grid_w - gap * (columns - 1)) // columns
            right = y
        row_y = y
        for start in range(0, len(small), columns):
            ends = []
            for col, (index, item) in enumerate(small[start : start + columns]):
                ends.append(
                    _item(
                        f,
                        item,
                        index + 1,
                        grid_x + col * (tile_w + gap),
                        row_y,
                        tile_w,
                        145 if len(items) >= 6 else 230,
                    )
                )
            row_y = max(ends) + 22
        y = max(row_y, right)
    if data.bonus_grants:
        y = f.text(" · ".join(data.bonus_grants), 58, y + 18, 1204, 23, ROSE)
    f.footer(
        f"保底计数 {data.pity_after}/{data.hard_pity} · /抽卡 记录 查看历史", y + 26
    )


@surface(1160)
def history(f, data):
    y = f.title(
        "入手记录",
        "ACQUISITION REGISTER",
        f"共 {data.total} 抽 · 第 {data.page}/{data.total_pages} 页",
    )
    rows = [(f"★{r.rarity}", r.name, r.note, r.time_text) for r in data.rows]
    y = f.table(
        ("稀有度", "收录项目", "附记", "时间"), rows, 58, y, (90, 526, 220, 208)
    )
    if not rows:
        y = f.text("尚无抽取记录。", 58, y + 40, 1044, 30, MUTED)
    f.footer(
        f"保底计数 {data.pity_count}/{data.hard_pity or '—'} · /抽卡 记录 <页码> 翻页",
        y + 24,
    )
