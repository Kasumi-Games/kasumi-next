"""A route diagram, race register and completion certificate."""

from .folio import surface
from .folio import gain_rows
from ..components import INK
from ..components import ROSE
from ..components import MUTED


@surface(1240)
def board(f, session, *, identity=None, detail=None):
    from plugins.one_stroke.difficulty import apply_time_decay
    from plugins.one_stroke.render.graph import OneStrokeBoard

    y = f.title("一笔画", "THE UNBROKEN ROUTE", session.difficulty_name)
    side = f.person(identity, 58, y, 280)
    side = f.metric(
        "路线进度",
        f"{session.drawn_count}/{session.total_edges}",
        58,
        side + 35,
        280,
        size=46,
    )
    reward = apply_time_decay(
        base_reward=session.reward,
        elapsed_seconds=session.elapsed_seconds(),
        graph=session.graph,
    )
    side = f.metric("当前奖励", f"{reward} Pt", 58, side + 28, 280, size=42)
    side = f.text(detail or "", 58, side + 24, 280, 23, MUTED)
    f.text(
        "从起点出发\n沿着道路连续走完\n每条道路只能经过一次",
        58,
        side + 34,
        280,
        23,
        leading=38,
    )
    palette = {
        "wall": INK,
        "traversable": (218, 203, 201, 255),
        "drawn": ROSE,
        "start": (169, 117, 131, 255),
        "current": (82, 57, 67, 255),
    }
    f.component(OneStrokeBoard(session, palette), 448, y, 734, 734)
    f.footer("按游戏提示输入方向继续绘制", y + 764)


@surface(1320, book=True)
def rank(f, easy_rows, normal_rows, hard_rows):
    y = f.title("竞速名册", "ONE STROKE / SPEED REGISTER", "一笔画排行榜")
    for i, (label, rows) in enumerate(
        zip(("简单", "普通", "困难"), (easy_rows, normal_rows, hard_rows), strict=True)
    ):
        x = 58 + i * 414
        top = f.section(label, x, y, 376)
        if rows:
            f.table(
                ("玩家", "用时"),
                [
                    (f"{n + 1}. {name}", f"{elapsed:.2f}s")
                    for n, (name, elapsed) in enumerate(rows[:10])
                ],
                x,
                top,
                (258, 118),
                size=21,
            )
        else:
            f.text("尚无通关记录", x, top + 25, 376, 24, MUTED)
    f.footer("仅记录各难度的个人最快通关时间")


@surface(1160, book=True)
def result(f, data, *, identity=None):
    from plugins.one_stroke.render.result import record_text

    y = f.title("路线完成证明", "ONE STROKE / CLEAR CERTIFICATE", data.difficulty)
    a = f.person(identity, 58, y, 440)
    a = f.metric(
        "完成用时",
        f"{data.elapsed_seconds:.2f} 秒",
        58,
        max(a + 36, y + 124),
        440,
        size=66,
    )
    if data.is_new_record:
        a = f.stamp("个人新纪录", 58, a + 34, 280)
    a = f.text(record_text(data), 58, a + 24, 440, 23, ROSE)
    b = f.section("奖励核定", 570, y, 532)
    rows = [
        ("基础奖励", f"{data.base_reward} Pt"),
        ("速度系数", f"× {data.decay_factor:.2f}"),
    ]
    if data.birthday_characters:
        rows.append(("生日加成", "× 2 · " + "、".join(data.birthday_characters)))
    rows += [
        ("通关奖励", f"+{data.final_reward} Pt"),
        ("当前余额", f"{data.balance:,} Pt"),
    ]
    b = f.facts(rows, 570, b, 532)
    gains = gain_rows(data)
    if gains:
        b = f.section("任务与成长", 570, b + 20, 532)
        b = f.facts(gains, 570, b, 532)
    f.gutter(498, 570, y, max(a, b), padding=24)
    f.footer("/一笔画 开始新的挑战 · /一笔画排行榜 查看竞速名册", max(a, b) + 28)
