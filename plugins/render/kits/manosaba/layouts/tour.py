"""A four-card tour desk, itinerary settlement and a compact race archive."""

from .folio import surface
from .folio import gain_rows
from ..components import INK
from ..components import ROSE
from ..components import MUTED
from ..components import SURFACE


@surface(1440, book=True)
def state(f, data, *, identity=None, detail=None):
    from plugins.tour.models import CardType

    s = data.snapshot
    y = f.title("巡演手记", "TOUR / THE DAY'S HAND", f"{s.difficulty} · 第 {s.day} 天")
    side = f.person(identity, 58, y, 270)
    if detail:
        side = f.text(detail, 58, side + 18, 270, 23, MUTED)
    side = f.metric("体力", f"{s.stamina}/{s.max_stamina}", 58, side + 30, 270, size=48)
    side = f.meter(s.stamina, s.max_stamina, 58, side + 12, 270)
    side = f.facts(
        (
            ("今日行动", f"{s.selection_count}/3"),
            ("已完成", f"{s.tour_played_count}/26 场"),
            ("牌库剩余", f"{s.deck_size} 张"),
        ),
        58,
        side + 32,
        270,
    )
    side = f.section("当前乐器", 58, side + 30, 270)
    if s.instrument:
        side = f.text(s.instrument.name, 58, side, 270, 27)
        side = f.text(
            f"底力 +{s.instrument.value} · {'已装备' if s.instrument_equipped else '未装备'}",
            58,
            side + 12,
            270,
            22,
            ROSE,
        )
        if s.last_performance is not None:
            side = f.text(
                f"下次演出难度须低于 {s.last_performance}",
                58,
                side + 12,
                270,
                22,
                MUTED,
            )
    else:
        side = f.text("未装备乐器\n选择乐器牌后会自动装备。", 58, side, 270, 23, MUTED)
    hand_y = f.section("今日手牌 · 输入编号选择", 386, y, 996)
    for i in range(4):
        x, width = 386 + i * 254, 234
        card = s.hand[i] if i < len(s.hand) else None
        f.box(x, hand_y, width, 370, SURFACE, MUTED)
        f.box(x, hand_y, width, 58, INK)
        f.text(f"{i + 1:02d}", x + 18, hand_y + 14, width - 36, 26, SURFACE)
        if card is None:
            f.text("空槽", x + 22, hand_y + 146, width - 44, 30, MUTED, align="center")
            continue
        kind = {
            CardType.TOUR: "巡演",
            CardType.INSTRUMENT: "乐器",
            CardType.STAMINA: "食物",
        }[card.type]
        f.text(kind, x + 22, hand_y + 88, width - 44, 22, ROSE)
        f.text(card.name, x + 22, hand_y + 132, width - 44, 29, lines=3)
        f.text(f"{card.value:02d}", x + 22, hand_y + 268, width - 44, 48, ROSE)
        f.text(
            {
                CardType.TOUR: "演出难度",
                CardType.INSTRUMENT: "乐器底力",
                CardType.STAMINA: "恢复体力",
            }[card.type],
            x + 22,
            hand_y + 334,
            width - 44,
            19,
            MUTED,
        )
    route_y = hand_y + 410
    f.text("巡演进度", 386, route_y, 996, 22, ROSE)
    for i in range(26):
        f.box(
            386 + i * 38,
            route_y + 46,
            25,
            25,
            ROSE if i < s.tour_played_count else None,
            MUTED,
        )
    f.text(f"已完成 {s.tour_played_count}/26 场", 386, route_y + 92, 996, 24)
    f.gutter(328, 386, y, max(side, route_y + 135), padding=18)
    f.footer(
        "1–4 选择手牌 · 0 操作乐器 · 5 休息 · q 退出 · 可连续输入最多 6 个 0–4",
        max(side, route_y + 135) + 28,
    )


@surface(1160, book=True)
def result(f, data, *, identity=None):
    from plugins.tour.render.result import _headline

    y = f.title("巡演归档", "TOUR / FINAL ITINERARY", _headline(data))
    s = data.snapshot
    a = f.person(identity, 58, y, 420)
    a = f.metric("巡演奖励", f"{data.reward_pt:+,} Pt", 58, a + 40, 420, size=60)
    a = f.metric("完成演出", f"{s.tour_played_count}/26", 58, a + 34, 420, size=48)
    b = f.section("巡演行程", 564, y, 538)
    b = f.facts(
        (
            ("难度", s.difficulty),
            ("耗时", f"{data.elapsed_seconds:.0f} 秒"),
            ("剩余体力", f"{s.stamina}/{s.max_stamina}"),
            ("当前余额", f"{data.balance:,} Pt"),
        ),
        564,
        b,
        538,
    )
    if data.base_reward_pt is not None:
        b = f.facts((("基础奖励", f"{data.base_reward_pt} Pt"),), 564, b, 538)
    if data.multiplier > 1 and data.birthday_names:
        b = f.text(
            f"生日加成 × {data.multiplier} · {'、'.join(data.birthday_names)}",
            564,
            b + 12,
            538,
            23,
            ROSE,
        )
    gains = gain_rows(data)
    if gains:
        b = f.section("任务与成长", 564, b + 24, 538)
        b = f.facts(gains, 564, b, 538)
    f.gutter(478, 564, y, max(a, b))
    f.footer("/巡演 开始新的行程 · /巡演排行榜 查看竞速记录", max(a, b) + 30)


@surface(1240, book=True)
def rank(f, rows_by_difficulty):
    y = f.title("巡演竞速档案", "TOUR / SPEED ARCHIVE", "当前赛季最快通关记录")
    top = y
    for start in range(0, 4, 2):
        ends = []
        for col, difficulty in enumerate(
            ("初级", "中级", "高级", "超级")[start : start + 2]
        ):
            x = 58 + col * 600
            end = f.section(difficulty, x, top, 524)
            rows = rows_by_difficulty.get(difficulty, [])
            if rows:
                end = f.table(
                    ("玩家", "用时"),
                    [
                        (f"{i + 1}. {name}", f"{elapsed:.2f}s")
                        for i, (name, elapsed) in enumerate(rows[:10])
                    ],
                    x,
                    end,
                    (380, 144),
                )
            else:
                end = f.text("尚无通关记录", x, end + 20, 524, 24, MUTED) + 45
            ends.append(end)
        top = max(ends) + 36
    f.gutter(582, 658, y, top - 36)
    f.footer("按难度分别记录个人最快通关时间", top)


@surface(1240, book=True)
def help_page(f):
    from plugins.tour.help_content import RULE_SECTIONS

    from .help import rulebook

    rulebook(f, "巡演", "TOUR / RULE BOOK", RULE_SECTIONS)
