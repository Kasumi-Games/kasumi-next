from __future__ import annotations

import datetime

import pytest

from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit


def _mail(mail_id: int, title: str, *, attachments=(), is_read=False, days=5):
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
        sender_id="system",
        created_at=now - datetime.timedelta(days=1),
        expire_time=now + datetime.timedelta(days=days, hours=1),
        is_broadcast=False,
        is_read=is_read,
        read_at=None,
    )


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

    detail = render_mail(
        mails[0], [GrantResult("season_point", 100, 100, 100)], kit
    )
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
