from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit


def _mail(
    mail_id: int,
    title: str,
    *,
    attachments=(),
    is_read=False,
    days=5,
    sender_id="system",
):
    from plugins.mailbox.models import ServiceMail
    from plugins.mailbox.models import ServiceMailAttachment

    now = datetime.datetime.now()
    return ServiceMail(
        id=mail_id,
        title=title,
        content="正文" * 20,
        star_kakeras=0,
        star_stickers=0,
        attachments=[
            ServiceMailAttachment(item_id=item_id, quantity=quantity)
            for item_id, quantity in attachments
        ],
        sender_id=sender_id,
        created_at=now - datetime.timedelta(days=1),
        expire_time=now + datetime.timedelta(days=days, hours=1),
        is_broadcast=False,
        is_read=is_read,
        read_at=None,
    )


def _collect_text(component) -> list[str]:
    """Collect text nodes in document (preorder) order."""

    texts: list[str] = []

    def visit(node) -> None:
        text = getattr(node, "text", None)
        if isinstance(text, str):
            texts.append(text)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
            else:
                visit(value)

    visit(component)
    return texts


class _FakeMailService:
    def __init__(self, mails):
        self._mails = list(mails)
        self.read = []

    def get_user_mails(self, user_id):
        return list(self._mails)

    def read_mail(self, user_id, mail_id):
        self.read.append(mail_id)


def test_claim_all_only_touches_unread_mails_with_attachments(monkeypatch):
    from plugins.mailbox import service
    from plugins.inventory.models import GrantResult

    calls = []

    def fake_grant_many(user_id, items, **kwargs):
        calls.append((user_id, list(items), kwargs))
        return [
            GrantResult(item.item_id, item.quantity, item.quantity, item.quantity)
            for item in items
        ]

    monkeypatch.setattr(service, "grant_many", fake_grant_many)

    mails = [
        _mail(1, "维护补偿", attachments=[("season_point", 100)]),
        _mail(2, "赛季公告"),
        _mail(3, "旧奖励", attachments=[("season_point", 20)], is_read=True),
        _mail(4, "活动奖励", attachments=[("season_point", 5), ("star_sticker", 7)]),
    ]
    fake_service = _FakeMailService(mails)

    outcome = service.claim_all_mails(fake_service, "u1")

    assert [claimed.mail.id for claimed in outcome.claimed] == [1, 4]
    # 明细行展示的是邮箱序号（/邮件 <编号>），领取不改排序，序号仍可回看
    assert [claimed.ordinal for claimed in outcome.claimed] == [1, 4]
    assert fake_service.read == [1, 4]
    assert outcome.remaining_notices == 1
    assert outcome.total_mails == 4

    # 幂等键必须与单封领取完全一致，否则已领取的邮件会被重复发放
    assert [call[2]["idempotency_key"] for call in calls] == ["mail:1", "mail:4"]
    assert [call[2]["source_id"] for call in calls] == ["1", "4"]

    totals = {total.item_id: total for total in outcome.totals}
    assert totals["season_point"].granted == 105
    assert totals["star_sticker"].granted == 7
    # 汇总按发放量降序
    assert [total.item_id for total in outcome.totals] == [
        "season_point",
        "star_sticker",
    ]


def test_claim_all_records_already_granted_items(monkeypatch):
    from plugins.mailbox import service
    from plugins.inventory.models import GrantResult

    def fake_grant_many(user_id, items, **kwargs):
        return [
            GrantResult(item.item_id, item.quantity, 0, item.quantity, skipped=True)
            for item in items
        ]

    monkeypatch.setattr(service, "grant_many", fake_grant_many)

    outcome = service.claim_all_mails(
        _FakeMailService([_mail(9, "补发", attachments=[("season_point", 30)])]),
        "u1",
    )

    assert outcome.claimed[0].results[0].skipped is True
    assert outcome.totals[0].granted == 0
    assert outcome.totals[0].already_owned == 30


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_mailbox_cards_render_in_multiple_kits(kit_cls):
    from plugins.mailbox.models import ClaimTotal
    from plugins.mailbox.models import ClaimedMail
    from plugins.mailbox.models import ClaimOutcome
    from plugins.mailbox.render import render_mail
    from plugins.mailbox.render import render_inbox
    from plugins.mailbox.render import render_claim_all
    from plugins.inventory.models import GrantResult

    kit = kit_cls()
    mails = [
        _mail(1, "维护补偿", attachments=[("season_point", 100)]),
        _mail(2, "赛季公告", days=1),
        _mail(3, "旧奖励", attachments=[("star_sticker", 20)], is_read=True),
    ]

    inbox = render_inbox(mails, kit)
    assert inbox.size[0] == 864
    assert inbox.size[1] > 0

    # 超过 8 封时切换到单行密集排版，页面仍然只有一页
    dense = render_inbox(mails * 4, kit)
    assert dense.size[0] == 864

    empty = render_inbox([], kit)
    assert empty.size[0] == 864

    detail = render_mail(mails[0], [GrantResult("season_point", 100, 100, 100)], kit)
    assert detail.size[0] == 864

    # 已读邮件重新打开：没有发放结果，仍然要有奖励面板
    already_read = render_mail(mails[2], [], kit)
    assert already_read.size[0] == 864

    outcome = ClaimOutcome(
        claimed=(
            ClaimedMail(
                mail=mails[0],
                results=(GrantResult("season_point", 100, 100, 100),),
            ),
        ),
        totals=(ClaimTotal("season_point", 100),),
        remaining_notices=1,
        total_mails=3,
    )
    assert render_claim_all(outcome, kit).size[0] == 864
    assert render_claim_all(ClaimOutcome(total_mails=3), kit).size[0] == 864


def test_inbox_spells_out_status_and_uses_one_index_shape():
    from plugins.mailbox.render.inbox import inbox_page
    from plugins.mailbox.render.inbox import _index_cell

    unread_reward = _mail(1, "待领", attachments=[("season_point", 100)])
    read_reward = _mail(2, "已领", attachments=[("season_point", 20)], is_read=True)
    unread_notice = _mail(3, "公告")
    texts = _collect_text(
        inbox_page([unread_reward, read_reward, unread_notice], MinimalKit()).child
    )

    assert any(text.startswith("待领取") for text in texts)
    assert "已领取" in texts
    assert "未读通知" in texts
    # The sequence number is navigation, not state. Read and unread rows must
    # therefore use the same component shape.
    assert type(
        _index_cell(MinimalKit(), 1, unread_reward, size=64, font_size=30)
    ) is type(_index_cell(MinimalKit(), 2, read_reward, size=64, font_size=30))


def test_mewtype_inbox_uses_an_action_summary_instead_of_a_subtitle():
    from plugins.render.kits.mewtype import MewtypeKit
    from plugins.mailbox.render.inbox import inbox_page

    mails = [
        _mail(1, "待领", attachments=[("season_point", 100)]),
        _mail(2, "公告"),
        _mail(3, "已读", is_read=True),
    ]
    texts = _collect_text(inbox_page(mails, MewtypeKit()).child)

    assert "未领取" in texts
    assert "未读通知" in texts
    assert "全部邮件" in texts
    assert "1 封未领取 · 1 封通知未读 · 共 3 封" not in texts


def test_empty_mewtype_inbox_does_not_announce_zero_mail_twice():
    from plugins.render.kits.mewtype import MewtypeKit
    from plugins.mailbox.render.inbox import inbox_page

    texts = _collect_text(inbox_page([], MewtypeKit()).child)

    assert "0 封" not in texts
    assert "收件箱" in texts


def test_dense_and_spacious_inbox_share_the_same_expiry_badge_path():
    source = (
        Path(__file__).resolve().parents[1]
        / "plugins"
        / "mailbox"
        / "render"
        / "inbox.py"
    ).read_text(encoding="utf-8")
    assert "_expiry_text_component" not in source


def test_normalize_attachments_merges_duplicate_items():
    from plugins.mailbox.service import _normalize_attachments
    from plugins.inventory.models import ItemAmount

    # 星星字段和显式附件是同一奖励的两种写法，必须合并成一条
    merged = _normalize_attachments(
        star_stickers=60, attachments=[ItemAmount("star_sticker", 60)]
    )
    assert [(item.item_id, item.quantity) for item in merged] == [("star_sticker", 120)]

    # 不同 scope 不合并
    scoped = _normalize_attachments(
        attachments=[
            ItemAmount("season_point", 10, "season", "1"),
            ItemAmount("season_point", 5),
        ]
    )
    assert [(item.item_id, item.quantity, item.scope_type) for item in scoped] == [
        ("season_point", 10, "season"),
        ("season_point", 5, None),
    ]


def test_scheduled_star_rewards_produce_one_attachment_row(sqlite_session):
    from plugins.mailbox import database
    from plugins.mailbox.models import Base
    from plugins.mailbox.models import MailAttachment
    from plugins.mailbox.service import MailService
    from plugins.mailbox.scheduled_service import ScheduledMailService

    session = sqlite_session(database, Base)
    scheduled = ScheduledMailService()
    scheduled.create_scheduled_mail(
        recipients="all",
        title="维护补偿",
        content="抱歉！",
        scheduled_time=1,
        star_stickers=60,
        name="comp",
    )

    assert scheduled.process_due_mails() == 1

    # 线上事故的根源：-s 同时走列和附件行，发送时又追加一次 -> 两行 60。
    # 现在每种奖励必须只产生一行。
    rows = session.query(MailAttachment).all()
    assert [(row.item_id, row.quantity) for row in rows] == [("star_sticker", 60)]

    mails = MailService().get_user_mails("u1")
    assert [
        (attachment.item_id, attachment.quantity) for attachment in mails[0].attachments
    ] == [("star_sticker", 60)]


def test_editing_scheduled_star_rewards_changes_what_gets_sent(sqlite_session):
    from plugins.mailbox import database
    from plugins.mailbox.models import Base
    from plugins.mailbox.models import MailAttachment
    from plugins.mailbox.scheduled_service import ScheduledMailService

    session = sqlite_session(database, Base)
    scheduled = ScheduledMailService()
    scheduled.create_scheduled_mail(
        recipients="all",
        title="补偿",
        content="正文",
        scheduled_time=1,
        star_stickers=60,
        name="edited",
    )

    # 发送走的是附件行，编辑 -s 必须同步改行，否则会被静默忽略
    assert scheduled.update_scheduled_mail("edited", star_stickers=100) is True
    assert scheduled.process_due_mails() == 1

    rows = session.query(MailAttachment).all()
    assert [(row.item_id, row.quantity) for row in rows] == [("star_sticker", 100)]


def test_scheduled_targeted_mail_sends_once_per_recipient(sqlite_session):
    from plugins.mailbox import database
    from plugins.mailbox.models import Base
    from plugins.mailbox.models import Mail
    from plugins.mailbox.models import ScheduledMail
    from plugins.mailbox.models import MailAttachment
    from plugins.mailbox.scheduled_service import ScheduledMailService

    session = sqlite_session(database, Base)
    scheduled = ScheduledMailService()
    scheduled.create_scheduled_mail(
        recipients="a,b",
        title="补偿",
        content="正文",
        scheduled_time=1,
        star_stickers=60,
        name="targeted",
    )

    # send_mail 会 commit+close 共享 session，把 ScheduledMail 实例弄成
    # expired+detached；发送前必须快照字段，否则第二位接收者读属性直接抛
    # DetachedInstanceError——第一位每个调度周期都会再收一封（is_sent 永远
    # 置不上），第二位一封都收不到。
    assert scheduled.process_due_mails() == 1

    mails = session.query(Mail).all()
    assert sorted(mail.recipients[0].user_id for mail in mails) == ["a", "b"]
    for mail in mails:
        rows = session.query(MailAttachment).filter_by(mail_id=mail.id).all()
        assert [(row.item_id, row.quantity) for row in rows] == [("star_sticker", 60)]

    assert session.query(ScheduledMail).filter_by(name="targeted").one().is_sent is True
    # 已发送的定时邮件不能再次发送
    assert scheduled.process_due_mails() == 0
    assert session.query(Mail).count() == 2


def test_scheduled_targeted_mail_retry_does_not_duplicate_earlier_recipients(
    sqlite_session, monkeypatch
):
    from plugins.mailbox import database
    from plugins.mailbox.models import Base
    from plugins.mailbox.models import Mail
    from plugins.mailbox.scheduled_service import ScheduledMailService

    session = sqlite_session(database, Base)
    scheduled = ScheduledMailService()
    scheduled.create_scheduled_mail(
        recipients="a,b",
        title="补偿",
        content="正文",
        scheduled_time=1,
        name="retry-targeted",
    )
    real_send = scheduled.mail_service.send_mail
    failed_once = False

    def flaky_send(**kwargs):
        nonlocal failed_once
        if kwargs["recipient_id"] == "b" and not failed_once:
            failed_once = True
            raise RuntimeError("mailbox unavailable")
        return real_send(**kwargs)

    monkeypatch.setattr(scheduled.mail_service, "send_mail", flaky_send)

    assert scheduled.process_due_mails() == 0
    assert scheduled.process_due_mails() == 1
    mails = session.query(Mail).order_by(Mail.id).all()
    assert [mail.recipients[0].user_id for mail in mails] == ["a", "b"]
    assert len({mail.external_key for mail in mails}) == 2


def test_editing_star_reward_to_zero_removes_the_row(sqlite_session):
    from plugins.mailbox import database
    from plugins.mailbox.models import Base
    from plugins.mailbox.models import ScheduledMailAttachment
    from plugins.mailbox.scheduled_service import ScheduledMailService

    session = sqlite_session(database, Base)
    scheduled = ScheduledMailService()
    scheduled.create_scheduled_mail(
        recipients="all",
        title="补偿",
        content="正文",
        scheduled_time=9_999_999_999,
        star_kakeras=10,
        star_stickers=60,
        name="zeroed",
    )

    # -s 0 表示清掉这项奖励：列归零之外，附件行也必须删掉（发送走附件行）
    assert scheduled.update_scheduled_mail("zeroed", star_stickers=0) is True
    rows = session.query(ScheduledMailAttachment).all()
    assert [(row.item_id, row.quantity) for row in rows] == [("season_point", 10)]


def test_legacy_duplicate_rows_display_and_claim_as_one(sqlite_session, monkeypatch):
    from plugins.mailbox import service as service_module
    from plugins.mailbox import database
    from plugins.mailbox.models import Base
    from plugins.mailbox.models import MailAttachment
    from plugins.mailbox.service import MailService
    from plugins.mailbox.service import claim_all_mails
    from plugins.inventory.models import GrantResult

    session = sqlite_session(database, Base)
    mail_service = MailService()
    mail_id = mail_service.send_mail("u1", "旧补偿", "正文", star_stickers=60)

    # 复刻线上已经存在的坏数据：同一奖励两行
    session.add(
        MailAttachment(
            mail_id=mail_id,
            item_id="star_sticker",
            quantity=60,
            scope_type="",
            scope_id="",
        )
    )
    session.commit()
    assert session.query(MailAttachment).filter_by(mail_id=mail_id).count() == 2

    # 展示层：坏数据也只读出一条 60——领取幂等键按物品去重，第二行
    # 从来没有发放过，显示两行（或 120）都是在骗玩家
    mails = mail_service.get_user_mails("u1")
    assert [
        (attachment.item_id, attachment.quantity) for attachment in mails[0].attachments
    ] == [("star_sticker", 60)]

    granted = []

    def fake_grant_many(user_id, items, **kwargs):
        granted.extend(items)
        return [
            GrantResult(item.item_id, item.quantity, item.quantity, item.quantity)
            for item in items
        ]

    monkeypatch.setattr(service_module, "grant_many", fake_grant_many)

    outcome = claim_all_mails(mail_service, "u1")
    assert [(item.item_id, item.quantity) for item in granted] == [("star_sticker", 60)]
    assert outcome.totals[0].granted == 60


def test_mail_detail_shows_ordinal_and_never_sender_or_mail_code():
    import re

    from plugins.mailbox.render import mail_page

    mail = _mail(
        6,
        "维护补偿",
        attachments=[("star_sticker", 60)],
        is_read=True,
        sender_id="3f9c1a77e0b24d68",
    )
    texts = _collect_text(mail_page(mail, [], MinimalKit(), ordinal=1).child)
    joined = " ".join(texts)

    # 玩家输入的序号，而不是与之相反的数据库编号
    assert "第 1 封" in joined
    assert "#M" not in joined
    assert not any(re.fullmatch(r"#?M\d+", text) for text in texts)

    # 发件人 id 是平台散列，绝不能出现在可分享的图片里
    assert "3f9c1a77e0b24d68" not in joined
    assert "送达" in joined
    assert "过期" in joined


def test_mail_detail_without_ordinal_still_renders():
    from plugins.mailbox.render import mail_page

    mail = _mail(6, "维护补偿", attachments=[("star_sticker", 60)], is_read=True)
    page = mail_page(mail, [], MinimalKit())
    joined = " ".join(_collect_text(page.child))
    # 没有序号时不显示「第 n 封」，其余照常
    assert "封" not in joined
    assert page.render().size[0] == 864


def test_mail_detail_collapses_duplicate_rows_into_one_tile(monkeypatch):
    from plugins.mailbox.render import rewards
    from plugins.mailbox.render import mail_page

    monkeypatch.setattr(rewards, "item_facts", lambda item_id: ("星星贴纸", "张", True))

    # 线上真实存在的双行邮件必须渲染成一条 60（与实际发放一致）
    mail = _mail(
        6,
        "旧补偿",
        attachments=[("star_sticker", 60), ("star_sticker", 60)],
        is_read=True,
    )
    texts = _collect_text(mail_page(mail, [], MinimalKit(), ordinal=2).child)

    assert texts.count("星星贴纸") == 1
    assert "1 项" in texts


def test_reward_tile_keeps_unit_with_amount(monkeypatch):
    from plugins.mailbox.render import rewards
    from plugins.mailbox.render import mail_page
    from plugins.inventory.models import GrantResult

    monkeypatch.setattr(rewards, "item_facts", lambda item_id: ("星星贴纸", "张", True))

    mail = _mail(3, "补偿", attachments=[("star_sticker", 60)])
    texts = _collect_text(
        mail_page(
            mail,
            [GrantResult("star_sticker", 60, 60, 60)],
            MinimalKit(),
            ordinal=1,
        ).child
    )

    # 单位跟数量走（+60 张），标签只写名字（星星贴纸）
    assert "+60" in texts
    assert "张" in texts
    assert "星星贴纸" in texts
    assert "星星贴纸 张" not in texts


def test_claim_receipt_shows_ordinals_not_mail_codes():
    import re

    from plugins.mailbox.models import ClaimTotal
    from plugins.mailbox.models import ClaimedMail
    from plugins.mailbox.models import ClaimOutcome
    from plugins.inventory.models import GrantResult
    from plugins.mailbox.render.claim import claim_all_page

    outcome = ClaimOutcome(
        claimed=(
            ClaimedMail(
                mail=_mail(41, "维护补偿", attachments=[("season_point", 100)]),
                results=(GrantResult("season_point", 100, 100, 100),),
                ordinal=2,
            ),
        ),
        totals=(ClaimTotal("season_point", 100),),
        total_mails=3,
    )
    texts = _collect_text(claim_all_page(outcome, MinimalKit()).child)

    assert "2" in texts
    assert not any(re.fullmatch(r"#?M\d+", text) for text in texts)


def test_select_mail_accepts_index_and_code():
    from plugins.mailbox import select_mail
    from plugins.mailbox import select_error_text

    mails = [_mail(42, "一"), _mail(41, "二")]

    assert select_mail(mails, "1").id == 42
    assert select_mail(mails, "2").id == 41
    assert select_mail(mails, "M41").id == 41
    assert select_mail(mails, "#m41").id == 41
    assert select_mail(mails, "3") is None
    assert select_mail(mails, "0") is None
    assert select_mail(mails, "M99") is None
    assert select_mail(mails, "abc") is None

    assert "1-2" in select_error_text("3", len(mails))
    assert "1-2" in select_error_text("abc", len(mails))
    assert select_error_text("1", 0) == "你的邮箱是空的呢~"
