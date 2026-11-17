"""Authored winter stationery layouts; business data stays with its caller."""

from utils.cards import pull_reveal
from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import AutoPage

from .kit import WinterEnsembleKit
from .components import INK
from .components import LINE
from .components import MUTED
from .components import STAMP
from .components import WinterMark
from .components import WinterSeal
from .components import WinterPaper


def page(kit, title, body, width=896, *, footer=None):
    sections = [
        kit.page_title(title),
        WinterPaper(VStack(body, gap=24), padding=40, tape=True),
    ]
    if footer is not None:
        sections.append(footer)
    return AutoPage(
        Frame(VStack(sections, gap=28, align="stretch"), width=width - 112),
        padding=56,
        background=kit.background(),
    )


def section(kit, title, detail=None):
    labels = [Frame(kit.text(title, font_size=24), width=Fill(), align_x="stretch")]
    if detail:
        labels.append(kit.text(detail, font_size=22))
    return VStack(
        [HStack(labels, gap=16, align="center"), kit.separator(length=Fill())],
        gap=12,
        align="stretch",
    )


def page_for(kit, route, data):
    if not isinstance(kit, WinterEnsembleKit):
        return None
    if route == "daily.checkin":
        return checkin(kit, data)
    if route == "inventory.season_rank":
        return rank(kit, data)
    if route == "inventory.profile":
        return profile(kit, data)
    if route == "gacha.banner":
        return banner(kit, data)
    if route == "gacha.pull":
        width = 1216 if len(data.pulls) > 1 else 784
        # Each result is already a ticket; do not put another paper around it.
        rows = [kit.page_title("抽卡结果"), pull_reveal(kit, data.pulls, width=width)]
        if data.bonus_grants:
            rows.append(kit.text("附赠：" + "、".join(data.bonus_grants), font_size=24))
        rows.append(
            kit.text(f"保底计数 {data.pity_after} / {data.hard_pity}", font_size=24)
        )
        return AutoPage(
            Frame(VStack(rows, gap=28, align="stretch"), width=width),
            padding=56,
            background=kit.background(),
        )
    return None


def checkin(kit, d):
    identity = HStack(
        [
            kit.avatar(None, d.nickname, 52),
            Frame(
                VStack(
                    [
                        kit.text(d.nickname, font_size=28, max_lines=1),
                        kit.text(f"Lv.{d.new_level}", font_size=22),
                    ],
                    gap=2,
                ),
                width=Fill(),
                align_x="stretch",
            ),
            WinterSeal("签到成功"),
        ],
        gap=16,
        align="center",
    )
    reward = VStack(
        [
            kit.text("今日入账", font_size=22),
            HStack(
                [
                    kit.number(f"+{d.reward_pt}", font_size=92),
                    kit.text("Pt", font_size=32),
                ],
                gap=10,
                align="end",
            ),
            kit.text(
                f"{'休赛期临时 Pt' if d.offseason else '赛季余额'}  {d.balance:,} Pt",
                font_size=24,
            ),
        ],
        gap=4,
    )
    streak = VStack(
        [
            kit.text("连续签到", font_size=22),
            HStack(
                [
                    kit.number(f"{d.streak:02d}", font_size=72, color=STAMP),
                    kit.text("天", font_size=24),
                ],
                gap=10,
                align="end",
            ),
        ],
        gap=4,
    )
    body = [
        identity,
        kit.separator(length=Fill()),
        HStack(
            [
                Frame(reward, width=Fill(), align_x="stretch"),
                kit.separator(orientation="vertical", length=108),
                Frame(streak, width=210, padding=Insets.only(left=20)),
            ],
            gap=28,
            align="center",
        ),
    ]
    gains = []
    if d.streak_bonus or d.level_stickers:
        gains.append(
            kit.text(f"星星贴纸 +{d.streak_bonus + d.level_stickers}", font_size=24)
        )
    if d.new_level > d.old_level:
        gains.append(
            kit.text(f"等级提升  Lv.{d.old_level} → Lv.{d.new_level}", font_size=24)
        )
    if gains:
        body.append(VStack(gains, gap=8))
    body.append(section(kit, "本轮签到印记", f"{d.window_done} / {d.window_total}"))
    slots = max(1, d.window_total)
    body.append(
        Grid(
            [
                WinterMark(
                    i + 1, i < d.window_done, i == slots - 1 and bool(d.bonus_stickers)
                )
                for i in range(slots)
            ],
            columns=min(7, slots),
            column_track=Fill(),
            row_track=Fixed(100),
            gap=8,
        )
    )
    if d.bonus_stickers:
        body.append(
            kit.text(
                f"本轮 {d.bonus_stickers} 星星贴纸已到账"
                if d.window_done >= d.window_total
                else f"再签到 {max(0, d.next_bonus_day - d.streak)} 天，可获得 {d.bonus_stickers} 星星贴纸",
                font_size=24,
            )
        )
    if d.task:
        body.extend(
            [
                section(kit, "今日任务", "已完成" if d.task.done else "进行中"),
                VStack(
                    [
                        kit.text(d.task.name, font_size=28),
                        kit.text(d.task.description, font_size=24),
                        kit.text(
                            f"{'任务奖励' if d.task.done else '完成后可领取'} {d.task.reward} 星星贴纸",
                            font_size=24,
                        ),
                    ],
                    gap=8,
                    align="stretch",
                ),
            ]
        )
    notes = []
    if d.offseason:
        notes.append("休赛期临时 Pt 不计入下一赛季")
    if d.unread_mails:
        notes.append(f"{d.unread_mails} 封未读邮件 · /邮箱 查看")
    return page(
        kit,
        "今日签到",
        body,
        footer=kit.text(" · ".join(notes), font_size=22) if notes else None,
    )


def rank(kit, d):
    previous = next(
        (r for r in (*d.rows, *d.nearby) if r.rank == d.viewer_rank - 1), None
    )
    own = [
        kit.text(d.viewer_name, font_size=26),
        kit.number(f"{d.viewer_points:,} Pt", font_size=42),
    ]
    if previous is not None:
        own.append(
            kit.text(
                f"距上一名 {max(0, previous.points - d.viewer_points):,} Pt",
                font_size=22,
            )
        )
    metric = HStack(
        [
            Frame(
                VStack(
                    [
                        kit.text("本人名次", font_size=22),
                        kit.number(f"{d.viewer_rank:02d}", font_size=88)
                        if d.viewer_rank > 0
                        else kit.text("未上榜", font_size=40),
                    ],
                    gap=2,
                ),
                width=Fill(),
                align_x="stretch",
            ),
            VStack(own, gap=6, align="end"),
        ],
        gap=24,
        align="center",
    )

    def table(items, title):
        header = HStack(
            [
                Frame(kit.text("名次", font_size=22), width=56),
                Frame(kit.text("玩家", font_size=22), width=Fill(), align_x="stretch"),
                kit.text("积分 Pt", font_size=22),
            ],
            gap=12,
        )
        rows = [section(kit, title), Frame(header, padding=Insets.xy(y=10))]
        for r in items:
            mine = r.rank == d.viewer_rank
            who = r.identity
            player = HStack(
                [
                    kit.avatar(
                        who.avatar if who else None,
                        r.name,
                        36,
                        who.avatar_frame if who else None,
                    ),
                    Frame(
                        kit.text(r.name, font_size=24, wrap=False, max_lines=1),
                        width=Fill(),
                        align_x="stretch",
                    ),
                ],
                gap=12,
                align="center",
            )
            line = HStack(
                [
                    Frame(
                        kit.number(
                            f"{r.rank:02d}", font_size=32, color=STAMP if mine else INK
                        ),
                        width=56,
                    ),
                    Frame(player, width=Fill(), align_x="stretch"),
                    Frame(
                        kit.text(
                            f"{r.points:,}", font_size=24, align="right", wrap=False
                        ),
                        width=112,
                    ),
                ],
                gap=12,
                align="center",
            )
            if mine:
                # A leading index, rather than a second outlined card.
                line = WinterPaper(
                    line,
                    height=64,
                    padding=Insets.xy(y=10),
                    fill=(247, 235, 228, 255),
                    border=(247, 235, 228, 255),
                    index=True,
                )
            else:
                line = Frame(line, height=64, padding=Insets.xy(y=10), align_y="center")
            rows.extend([line, kit.separator(length=Fill(), color=LINE)])
        if not items:
            rows.append(kit.text("本赛季还没有 Pt 记录", font_size=26))
        return VStack(rows, gap=0, align="stretch")

    if d.nearby:
        columns = HStack(
            [
                Frame(
                    table(d.rows, "赛季前列"),
                    width=Fill(),
                    align_x="stretch",
                    align_y="start",
                ),
                kit.separator(orientation="vertical", length=800),
                Frame(
                    table(d.nearby, "你的附近"),
                    width=Fill(),
                    align_x="stretch",
                    align_y="start",
                ),
            ],
            gap=32,
            align="start",
        )
        return page(kit, "赛季排行", [metric, columns], width=1360)
    return page(kit, "赛季排行", [metric, table(d.rows, "赛季积分")])


def profile(kit, d):
    who = d.identity
    identity = HStack(
        [
            kit.avatar(who.avatar, who.nickname, 88, d.avatar_frame),
            Frame(
                VStack(
                    [
                        kit.text(who.nickname, font_size=36, max_lines=2),
                        kit.text(f"Lv.{who.level}", font_size=24),
                    ],
                    gap=6,
                ),
                width=Fill(),
                align_x="stretch",
            ),
        ],
        gap=24,
        align="center",
    )
    info = [identity, kit.separator(length=Fill())]
    if d.description.strip():
        info.append(kit.text(d.description, font_size=26, max_lines=5))
    info.extend(
        [
            kit.text("休赛期临时 Pt" if d.offseason else "赛季积分", font_size=22),
            kit.number(f"{d.current_pt:,} Pt", font_size=72),
        ]
    )
    facts = [("星星贴纸", f"{d.star_stickers:,} 张"), ("盆栽", f"{d.bonsai:,} 盆")]
    if d.season_rank:
        facts.append(("赛季排名", f"第 {d.season_rank} 名"))
    if d.xp_level_span:
        facts.append(("等级经验", f"{d.xp_in_level}/{d.xp_level_span} XP"))
    facts.extend(d.equipped)
    info.append(kit.separator(length=Fill()))
    for label, value in facts:
        info.append(
            HStack(
                [
                    Frame(kit.text(label, font_size=22), width=112),
                    Frame(
                        kit.text(value, font_size=24, align="right", max_lines=2),
                        width=Fill(),
                        align_x="stretch",
                    ),
                ],
                gap=16,
            )
        )
    if d.offseason:
        info.append(kit.text("休赛期临时 Pt 不会计入下一赛季", font_size=22))
    body = VStack(info, gap=16, align="stretch")
    if d.standing_art is not None:
        body = HStack(
            [
                Frame(body, width=Fill(), align_x="stretch"),
                kit.separator(orientation="vertical", length=660),
                kit.art(d.standing_art, width=460, height=600),
            ],
            gap=32,
            align="center",
        )
    return page(
        kit, "个人资料", [body], width=1240 if d.standing_art is not None else 896
    )


def banner(kit, d):
    body = []
    if d.featured_items:
        tiles = []
        for f in d.featured_items:
            character, _, card_title = f.name.partition(" ")
            tiles.append(
                Frame(
                    VStack(
                        [
                            kit.art(f.image, width=Fill(), height=300)
                            if f.image
                            else Frame(kit.text("暂无立绘", font_size=24), height=300),
                            HStack(
                                [
                                    Frame(
                                        kit.text(character, font_size=28, max_lines=2),
                                        width=Fill(),
                                        align_x="stretch",
                                    ),
                                    kit.text(f"★{f.rarity}", font_size=26),
                                ],
                                gap=12,
                                align="center",
                            ),
                            kit.text(card_title, font_size=24, max_lines=2)
                            if card_title
                            else Frame(height=0),
                        ],
                        gap=20,
                        align="stretch",
                    ),
                    width=Fill(),
                    align_x="stretch",
                )
            )
        body.append(HStack(tiles, gap=32, align="start"))
    body.append(kit.separator(length=Fill()))
    body.append(
        HStack(
            [
                Frame(
                    VStack(
                        [
                            kit.text("单抽 / 十连", font_size=22),
                            kit.number(f"{d.single_cost} / {d.ten_cost}", font_size=46),
                            kit.text("星星贴纸", font_size=22),
                        ],
                        gap=4,
                    ),
                    width=Fill(),
                    align_x="stretch",
                ),
                VStack(
                    [
                        kit.text("当前保底计数", font_size=22),
                        kit.number(f"{d.pity_count:02d} / {d.hard_pity}", font_size=46),
                    ],
                    gap=4,
                ),
            ],
            gap=24,
            align="start",
        )
    )
    body.append(section(kit, "卡池内容"))
    for rarity in sorted({r for _, r in d.pool_entries}, reverse=True):
        body.append(
            HStack(
                [
                    Frame(
                        VStack(
                            [
                                kit.text(f"★{rarity}", font_size=26),
                                kit.text(
                                    next(
                                        (
                                            f"{rate:.2%}"
                                            for r, rate in d.rates
                                            if r == rarity
                                        ),
                                        "",
                                    ),
                                    font_size=22,
                                ),
                            ],
                            gap=4,
                        ),
                        width=112,
                    ),
                    Frame(
                        kit.text(
                            "、".join(n for n, r in d.pool_entries if r == rarity),
                            font_size=24,
                        ),
                        width=Fill(),
                        align_x="stretch",
                    ),
                ],
                gap=24,
                align="start",
            )
        )
    if d.bundle_names:
        body.extend(
            [
                kit.separator(length=Fill()),
                kit.text(
                    "首次获得任意六星附赠：" + "、".join(d.bundle_names), font_size=24
                ),
            ]
        )
    body.append(
        kit.text("第 70 抽起软保底，第 90 抽保证六星档位，角色随机。", font_size=22)
    )
    return page(
        kit,
        d.banner_name,
        body,
        width=968,
        footer=kit.text("/抽卡 单抽 或 /抽卡 十连", font_size=22),
    )
