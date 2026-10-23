"""Correspondence index, stationery and a claim receipt for the mailbox."""

from .folio import surface
from ..components import ROSE
from ..components import MUTED


def prepare(name, data, results=(), **kwargs):
    """Resolve catalog-backed captions before handing raster work to a worker."""
    from plugins.mailbox.render.rewards import item_facts
    from plugins.mailbox.render.rewards import item_display
    from plugins.mailbox.render.rewards import receipt_lines
    from plugins.mailbox.render.rewards import attachment_summary

    if name == "inbox":
        return {
            "summaries": tuple(
                attachment_summary(m.attachments) or "通知" for m in data
            )
        }
    if name == "mail":
        from plugins.mailbox.render.mail import _band_caption

        results = tuple(results)
        return {
            "caption": _band_caption(data, results),
            "receipts": tuple(receipt_lines(data.attachments, results)),
        }
    return {
        "totals": tuple(
            item_display(t.item_id, t.granted)
            if t.granted > 0
            else f"{item_facts(t.item_id)[0]} · 已拥有"
            for t in data.totals
        ),
        "rows": tuple(
            (
                str(m.ordinal) if m.ordinal else "—",
                f"{m.mail.title}\n{' · '.join(receipt_lines(m.mail.attachments, m.results))}",
            )
            for m in data.claimed
        ),
    }


@surface(1140)
def inbox(f, mails, *, prepared):
    from plugins.mailbox.render.inbox import expiry_state

    pending = sum(not m.is_read and bool(m.attachments) for m in mails)
    notices = sum(not m.is_read and not m.attachments for m in mails)
    y = f.title(
        "往来信件",
        "CORRESPONDENCE INDEX",
        f"{pending} 封待领取 · {notices} 封通知未读 · 共 {len(mails)} 封",
    )
    if mails:
        rows = []
        for i, mail in enumerate(mails, 1):
            status = (
                "已领取"
                if mail.is_read and mail.attachments
                else "已读"
                if mail.is_read
                else "待领取"
                if mail.attachments
                else "未读通知"
            )
            rows.append(
                (
                    f"{i:02d}",
                    f"{mail.title}\n{status}",
                    prepared["summaries"][i - 1],
                    expiry_state(mail.expire_time)[0],
                )
            )
        y = f.table(
            ("编号", "信件", "附件", "有效期"),
            rows,
            58,
            y,
            (74, 386, 390, 174),
            size=22,
        )
    else:
        f.box(124, y + 45, 190, 120, fill=None, border=MUTED)
        f.line(124, y + 45, 190, ROSE)
        f.text("未收到新的信件", 380, y + 54, 660, 36)
        y = (
            f.text("有新邮件时，这里会列出信件与附件。", 380, y + 116, 660, 24, MUTED)
            + 55
        )
    f.footer("/邮件 <编号> 查看信件 · /邮件 领取 一键领取", y + 24)


@surface(1020, book=True)
def mail(f, mail, results=(), *, ordinal=None, prepared):
    from plugins.mailbox.render.mail import _meta_line
    from plugins.mailbox.render.inbox import expiry_state

    y = f.title(
        "信件",
        "A LETTER TO YOU",
        f"第 {ordinal} 封 · {expiry_state(mail.expire_time)[0]}"
        if ordinal
        else expiry_state(mail.expire_time)[0],
    )
    y = f.text(mail.title, 108, y + 12, 804, 42)
    y = f.text(_meta_line(mail), 108, y + 14, 804, 19, MUTED)
    f.line(108, y + 25, 804, MUTED)
    y = f.text(mail.content, 108, y + 55, 804, 25, lines=24, leading=39)
    if mail.attachments:
        y = f.section(prepared["caption"], 108, y + 48, 804)
        for caption in prepared["receipts"]:
            y = f.text(caption, 108, y, 804, 30, ROSE) + 20
    f.footer("/邮箱 返回信件目录 · /邮件 领取 一键领取", y + 36)


@surface(1120)
def claim(f, outcome, *, prepared):
    from plugins.mailbox.render.claim import _nothing_message

    y = f.title("领取回执", "DELIVERY RECEIPT", f"本次领取 {len(outcome.claimed)} 封")
    if not outcome.claimed:
        y = f.text(_nothing_message(outcome), 150, y + 50, 820, 30, align="center")
    else:
        left = y
        if outcome.totals:
            left = f.section(
                "合计获得"
                if any(t.granted > 0 for t in outcome.totals)
                else "之前已发放",
                58,
                y,
                340,
            )
        for total, caption in zip(outcome.totals, prepared["totals"], strict=True):
            left = f.text(caption, 58, left, 340, 34, ROSE) + 28
            if total.already_owned:
                left = (
                    f.text(
                        f"已有 {total.already_owned}，未重复发放",
                        58,
                        left,
                        340,
                        21,
                        MUTED,
                    )
                    + 18
                )
        right_x = 460 if outcome.totals else 58
        right_w = 602 if outcome.totals else 1004
        right = f.section("领取明细", right_x, y, right_w)
        right = f.table(
            ("编号", "邮件及奖励"),
            prepared["rows"],
            right_x,
            right,
            (80, right_w - 80),
        )
        y = max(left, right)
    if outcome.remaining_notices:
        y = f.text(
            f"还有 {outcome.remaining_notices} 封通知未读 · /邮箱 查看",
            58,
            y + 30,
            1004,
            24,
            ROSE,
        )
    f.footer("/邮箱 查看邮箱 · /邮件 <编号> 查看正文", y + 30)
