"""A gift invitation and its distribution ledger."""

from .folio import surface
from ..components import ROSE
from ..components import MUTED


@surface(1040, book=True)
def create(f, data):
    y = f.title("一份赠礼", "GIFT INVITATION", f"红包 {data.channel_index}")
    left = f.person(data.creator, 58, y, 430)
    left = f.text(data.title, 58, max(left + 36, y + 120), 430, 44, ROSE)
    left = f.text(f"{data.total_amount:,}", 58, left + 30, 430, 86)
    left = f.text("Pt / 红包总额", 58, left + 6, 430, 23, MUTED)
    right = f.section("领取须知", 566, y, 416)
    right = f.facts(
        (("总份数", f"{data.total_count} 份"), ("有效期", data.validity_text)),
        566,
        right,
        416,
    )
    right = f.text(
        f"发送「抢红包 {data.channel_index}」领取", 566, right + 48, 416, 32, ROSE
    )
    f.footer("领取结果将在红包结算后公布", max(left, right) + 40)


@surface(1120)
def listing(f, items):
    y = f.title("待领赠礼", "OPEN GIFTS", f"进行中 {len(items)} 个")
    if items:
        y = f.table(
            ("编号", "赠礼", "剩余金额", "份数", "有效期"),
            [
                (
                    i.channel_index,
                    i.title,
                    f"{i.remaining_amount}/{i.total_amount} Pt",
                    f"{i.remaining_count}/{i.total_count}",
                    i.validity_text,
                )
                for i in items
            ],
            58,
            y,
            (76, 330, 230, 130, 238),
        )
    else:
        y = f.text(
            "现在没有可以抢的红包。\n发一个，就会出现在这里。",
            118,
            y + 55,
            884,
            31,
            MUTED,
            align="center",
        )
    f.footer("抢红包 <编号> 领取 · /发红包 <金额> <份数> 再发一个", y + 36)


@surface(1160, book=True)
def completion(f, data):
    y = f.title(
        "赠礼分配记录", "GIFT DISTRIBUTION", f"红包 {data.channel_index} · {data.title}"
    )
    a = f.metric("赠礼总额", f"{data.total_amount:,} Pt", 58, y, 390, size=58)
    a = f.facts(
        (
            ("来自", data.creator_name),
            ("份数", f"{data.total_count} 份"),
            ("用时", data.duration_text),
        ),
        58,
        a + 30,
        390,
    )
    a = f.section("手气王", 58, a + 30, 390)
    a = f.text(data.lucky_king_name, 58, a, 390, 32, ROSE)
    a = f.text(f"{data.lucky_king_amount} Pt", 58, a + 12, 390, 42)
    unlucky = min(data.claims, key=lambda c: c.amount, default=None)
    if unlucky:
        a = f.text(
            f"霉运王 · {unlucky.name} / {unlucky.amount} Pt", 58, a + 30, 390, 23, MUTED
        )
    claims = sorted(data.claims, key=lambda c: c.amount, reverse=True)
    b = f.table(
        ("名次", "领取人", "金额"),
        [(i + 1, r.name, f"{r.amount} Pt") for i, r in enumerate(claims[:10])],
        516,
        y,
        (80, 300, 226),
    )
    if len(claims) > 10:
        b = f.text(f"另有 {len(claims) - 10} 人已领取", 516, b + 14, 606, 23, MUTED)
    f.footer("本次赠礼已分配完毕 · /红包列表 查看其他红包", max(a, b) + 30)
