"""Attendance seals and an experience register, with no generic result panels."""

from .folio import surface
from ..components import INK
from ..components import ROSE
from ..components import MUTED
from ..components import SURFACE


@surface(1080, book=True)
def checkin(f, data):
    y = f.title("今日的记录", "DAILY ATTENDANCE", data.nickname)
    f.text(f"{data.streak:02d}", 58, y, 230, 100, ROSE)
    f.text("连续签到 / 天", 58, y + 148, 230, 21, MUTED)
    f.stamp("签到成功", 58, y + 208, 230)
    right = f.section("今日入账", 354, y, 668)
    right = f.metric("签到奖励", f"+{data.reward_pt} Pt", 354, right, 668, size=58)
    gains = []
    if data.new_level > data.old_level:
        gains.append(("等级提升", f"Lv.{data.old_level} → Lv.{data.new_level}"))
        if data.level_stickers:
            gains.append(("升级奖励", f"+{data.level_stickers} 星星贴纸"))
    if data.streak_bonus:
        gains.insert(0, ("连续签到奖励", f"+{data.streak_bonus} 星星贴纸"))
    right = f.facts(gains, 354, right + 20, 668)
    right = f.facts(
        (("休赛期临时 Pt" if data.offseason else "赛季余额", f"{data.balance:,} Pt"),),
        354,
        right + 8,
        668,
    )
    y = max(y + 310, right) + 34
    y = f.section("本轮签到印记", 58, y, 964)
    slots = max(1, data.window_total)
    step = min(120, 964 // slots)
    for i in range(slots):
        f.box(
            58 + i * step, y, step - 14, 58, INK if i < data.window_done else None, ROSE
        )
        f.text(
            str(i + 1),
            58 + i * step,
            y + 13,
            step - 14,
            23,
            SURFACE if i < data.window_done else MUTED,
            align="center",
        )
    y = f.text(
        f"{data.window_done}/{data.window_total} · 第 {data.next_bonus_day} 天奖励 {data.bonus_stickers} 星星贴纸",
        58,
        y + 78,
        964,
        22,
        MUTED,
    )
    if data.task:
        y = f.section("今日任务", 58, y + 34, 964)
        f.stamp("已完成" if data.task.done else "进行中", 830, y, 192, size=23)
        end = f.text(data.task.name, 58, y, 730, 30)
        y = f.text(
            f"{data.task.description} · 奖励 {data.task.reward} 星星贴纸",
            58,
            end + 12,
            730,
            23,
        )
    notes = []
    if data.offseason:
        notes.append("本次获得休赛期临时 Pt，不计入下一赛季")
    if data.unread_mails:
        notes.append(f"{data.unread_mails} 封未读邮件 · /邮箱 查看")
    f.footer(" · ".join(notes) or "/每日任务 查看任务进度 · /资料 查看个人档案", y + 34)


@surface(1140)
def rank(f, data):
    y = f.title("成长名册", "EXPERIENCE REGISTER", "等级排行榜")
    left = f.metric("你的排名", f"第 {data.viewer_rank} 名", 58, y, 260, size=43)
    if data.viewer and data.viewer.identity:
        left = f.person(data.viewer.identity, 58, left + 10, 260)
    else:
        left = f.text(data.viewer_name, 58, left + 10, 260, 29)
    if data.viewer:
        left = f.facts(
            (("等级", f"Lv.{data.viewer.level}"), ("经验", f"{data.viewer.xp:,} XP")),
            58,
            left + 30,
            260,
        )
    if data.viewer_rank != 1:
        f.text(
            f"距上一名\n{data.xp_gap:,} XP" if data.xp_gap > 0 else "与上一名相同",
            58,
            left + 28,
            260,
            24,
            MUTED,
        )
    rows = [
        (r.rank, r.identity or r.name, f"Lv.{r.level}", f"{r.xp:,} XP")
        for r in data.rows
    ]
    bottom = f.table(
        ("名次", "玩家", "等级", "经验"),
        rows,
        376,
        y,
        (76, 260, 138, 232),
        highlight=tuple(
            i for i, r in enumerate(data.rows) if r.rank == data.viewer_rank
        ),
    )
    if not rows:
        bottom = f.text(
            "还没有人上榜\n发送 /签到 赚取第一份 XP", 376, bottom + 30, 706, 26, MUTED
        )
    f.footer("/签到 和游戏奖励可获得经验 · /资料 查看个人档案", bottom + 20)
