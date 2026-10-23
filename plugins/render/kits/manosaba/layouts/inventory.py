"""Dossiers, registers and season almanacs for the inventory plugin."""

from dataclasses import replace

from utils.clock import format_ts

from .folio import surface
from ..components import INK
from ..components import ROSE
from ..components import MUTED
from ..components import SERIF


@surface(1120, book=True)
def profile(f, data):
    if data.standing_art is not None:
        return _profile_with_art(f, data)
    y = f.title("人物档案", "PERSONAL DOSSIER", data.season_name or "尚未参加赛季")
    left, right = 58, 438
    identity = replace(
        data.identity, avatar_frame=data.avatar_frame or data.identity.avatar_frame
    )
    a = f.person(identity, left, y, 320)
    a = f.metric(
        "休赛期临时 Pt" if data.offseason else "赛季积分",
        f"{data.current_pt:,} Pt",
        left,
        a + 36,
        310,
    )
    a = f.metric("星星贴纸", f"{data.star_stickers:,} 张", left, a + 26, 310, size=36)
    a = f.metric("盆栽", f"{data.bonsai:,} 盆", left, a + 20, 310, size=36)
    if data.season_rank is not None:
        a = f.text(f"赛季第 {data.season_rank} 名", left, a + 24, 310, 24, ROSE)
    b = f.section("个人简介", right, y, 624)
    b = f.text(
        data.description.strip() or "尚未留下证言。",
        right,
        b,
        624,
        28,
        MUTED if not data.description.strip() else INK,
        lines=12,
    )
    b = f.section("已装备的装扮", right, max(b + 42, y + 210), 624)
    b = f.facts(data.equipped or (("装扮", "尚未装备"),), right, b, 624)
    if data.xp_level_span > 0:
        b = f.meter(
            data.xp_in_level,
            data.xp_level_span,
            right,
            b + 18,
            624,
            f"等级经验 {data.xp_in_level}/{data.xp_level_span}",
        )
    bottom = max(a, b)
    f.box(400, y, 1, bottom - y, (185, 156, 156, 255))
    f.footer("/资料 简介 <文本> 修改个人简介 · /装扮 查看已拥有的装扮", bottom + 40)


def _profile_with_art(f, data):
    """An equipped standing illustration owns a full-height facing page."""
    y = f.title("人物档案", "PERSONAL DOSSIER", data.season_name or "尚未参加赛季")
    identity = replace(
        data.identity, avatar_frame=data.avatar_frame or data.identity.avatar_frame
    )
    a = f.person(identity, 58, y, 500)
    a = f.metric(
        "休赛期临时 Pt" if data.offseason else "赛季积分",
        f"{data.current_pt:,} Pt",
        58,
        a + 30,
        500,
    )
    a = f.facts(
        (("星星贴纸", f"{data.star_stickers:,} 张"), ("盆栽", f"{data.bonsai:,} 盆")),
        58,
        a + 24,
        500,
    )
    if data.season_rank is not None:
        a = f.text(f"赛季第 {data.season_rank} 名", 58, a + 10, 500, 24, ROSE)
    a = f.section("个人简介", 58, a + 24, 500)
    a = f.text(data.description.strip() or "尚未留下证言。", 58, a, 500, 25, lines=12)
    a = f.section("已装备的装扮", 58, a + 28, 500)
    a = f.facts(
        data.equipped or (("装扮", "尚未装备"),), 58, a, 500, size=22, label_width=110
    )
    if data.xp_level_span > 0:
        a = f.meter(
            data.xp_in_level,
            data.xp_level_span,
            58,
            a + 18,
            500,
            f"等级经验 {data.xp_in_level}/{data.xp_level_span}",
        )
    b = f.section("收藏立绘", 630, y, 432)
    b = f.image(data.standing_art, 630, b + 12, 432, 780)
    f.box(596, y, 1, max(a, b) - y, (185, 156, 156, 255))
    f.footer("/资料 简介 <文本> 修改个人简介 · /装扮 查看已拥有的装扮", max(a, b) + 30)


@surface(1120)
def listing(f, data):
    if data.wordmark_title == "SHOP":
        from .shop import catalogue

        return catalogue(f, data)
    y = f.title(
        data.title,
        "COLLECTION REGISTER",
        data.subtitle or f"第 {data.page}/{data.total_pages} 页",
    )
    if data.equipped_summary:
        y = f.text(data.equipped_summary, 58, y, 1004, 23, ROSE) + 26
    for row in data.rows:
        f.text(str(row.index), 58, y + 12, 64, 26, ROSE)
        name_x = 134
        if row.show_art_slot:
            if row.art is not None:
                f.image(row.art, name_x, y, 96, 96)
            name_x += 120
        end = f.text(row.name, name_x, y + 7, 1060 - name_x - 130, 28)
        end = f.text(row.detail, name_x, end + 8, 1060 - name_x - 130, 22, MUTED)
        if row.show_trailing:
            f.text(
                f"★{row.rarity}" if row.rarity else row.kind,
                930,
                y + 8,
                130,
                23,
                ROSE,
                align="right",
            )
            if row.equipped:
                f.text("已装备", 930, y + 47, 130, 21, ROSE, align="right")
        y = max(y + 112, end + 24)
        f.line(58, y, 1004, MUTED)
        y += 22
    if not data.rows:
        y = f.text("尚未收录任何装扮。", 58, y + 50, 1004, 30, MUTED)
    if data.panel_footer:
        y = f.text(data.panel_footer, 58, y + 16, 1004, 22, MUTED)
    f.footer(
        data.footer or f"第 {data.page}/{data.total_pages} 页 · /装扮 <页码> 翻页",
        y + 20,
    )


@surface(1240, book=True)
def season_rank(f, data):
    y = f.title("赛季名册", "SEASON RANKING", data.season_name)
    left = f.section("前列记录", 58, y, 650)
    left = f.table(
        ("名次", "玩家", "赛季积分"),
        [(r.rank, r.identity or r.name, f"{r.points:,} Pt") for r in data.rows],
        58,
        left,
        (80, 330, 240),
        highlight=tuple(
            i for i, r in enumerate(data.rows) if r.rank == data.viewer_rank
        ),
    )
    if not data.rows:
        left = f.text(
            "本赛季还没有 Pt 记录\n玩一局游戏赚取第一份 Pt",
            58,
            left + 24,
            650,
            26,
            MUTED,
        )
    right = f.metric("你的排名", f"第 {data.viewer_rank} 名", 770, y, 410, size=48)
    right = f.text(
        f"{data.viewer_name} · {data.viewer_points:,} Pt", 770, right + 8, 410, 24, ROSE
    )
    if data.nearby:
        right = f.section("你附近的记录", 770, right + 38, 410)
        right = f.table(
            (),
            [(r.rank, r.identity or r.name, f"{r.points:,}") for r in data.nearby],
            770,
            right,
            (62, 204, 144),
            size=21,
            highlight=tuple(
                i for i, r in enumerate(data.nearby) if r.rank == data.viewer_rank
            ),
        )
    f.footer("/赛季趋势 查看积分门槛的变化 · /赛季 查看本期奖励", max(left, right) + 24)


@surface(1160, book=True)
def season_info(f, data):
    from plugins.inventory.render.season_info import _countdown

    y = f.title("赛季纪事", "SEASON ALMANAC", data.season_name)
    f.stamp("进行中" if data.state == "active" else "即将开始", 58, y, 190)
    target = data.ends_at if data.state == "active" else data.starts_at
    left = f.metric(
        "距结束" if data.state == "active" else "距开始",
        _countdown(target - data.now),
        58,
        y + 100,
        440,
        size=42,
    )
    left = f.facts(
        (
            ("开始", format_ts(data.starts_at, "%m-%d %H:%M")),
            ("结束", format_ts(data.ends_at, "%m-%d %H:%M")),
        ),
        58,
        left + 30,
        440,
    )
    if data.state == "active":
        left = f.facts(
            (
                ("我的积分", f"{data.points or 0:,} Pt"),
                ("当前排名", f"第 {data.rank} 名" if data.rank else "暂未上榜"),
            ),
            58,
            left + 12,
            440,
        )
    right = f.section("排名奖励", 562, y, 540)
    for reward in data.reward_rows:
        right = f.text(reward.placement, 562, right, 540, 29, ROSE)
        right = f.text("\n".join(reward.rewards), 590, right + 7, 512, 24) + 28
    if data.banner_name or data.featured_names:
        right = f.section("本期限定卡池", 562, right + 16, 540)
        right = f.text(data.banner_name or "", 562, right, 540, 28)
        right = f.text(" · ".join(data.featured_names), 562, right + 12, 540, 24, MUTED)
    f.footer("/赛季排行 · /赛季趋势 · /抽卡", max(left, right) + 30)


@surface(1240)
def trend(f, data):
    from plugins.inventory.season_render import _chart_image

    y = f.title("积分观测记录", "SEASON OBSERVATORY", data.season_name)
    f.image(_chart_image(data, f.kit, font_path=SERIF), 58, y, 820, 410)
    side = f.section("最新门槛", 924, y, 258)
    for series in data.series:
        side = (
            f.metric(
                f"第 {series.rank} 名",
                f"{series.points[-1][1]:,} Pt",
                924,
                side,
                258,
                size=32,
            )
            + 24
        )
    times = sorted({ts for s in data.series for ts, _ in s.points})
    f.footer(
        f"{format_ts(times[0], '%m-%d %H:%M')} 至 {format_ts(times[-1], '%m-%d %H:%M')} · 共 {len(times)} 次快照",
        max(side, y + 410) + 28,
    )
