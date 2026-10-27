"""Native plugin layouts preserve data semantics and real fixture geometry."""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

import pytest
from PIL import Image
from PIL import ImageChops

from plugins.render import RenderContext
from plugins.render import PlayerIdentity
from plugins.render.kits import ManosabaKit
from plugins.render.kits.manosaba.layouts import page_for
from plugins.render.kits.manosaba.layouts.folio import FolioPage

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("pixel_ratio", [1, 2])
@pytest.mark.parametrize(
    "label,size",
    [
        ("h", 22),
        ("s", 22),
        ("d", 22),
        ("q", 22),
        ("1-4", 22),
        ("0", 22),
        ("5", 22),
        ("已完成", 23),
        ("签到成功", 26),
    ],
)
def test_stamp_glyphs_are_centered_in_the_visible_box(label, size, pixel_ratio):
    from plugins.render.kits.manosaba.components import ROSE
    from plugins.render.kits.manosaba.layouts.folio import Sheet

    ctx = RenderContext(pixel_ratio=pixel_ratio)
    sheet = Sheet(ManosabaKit(), 300, ctx, False)
    control = Sheet(ManosabaKit(), 300, ctx, False)
    width = 74 if label.isascii() else 192
    sheet.stamp(label, 40, 40, width, size=size)
    control.box(40, 40, width, 60, fill=None, border=ROSE, weight=2)
    # Subtract an otherwise identical frame to measure only visible text ink.
    ink = (
        ImageChops.difference(sheet.render(), control.render())
        .convert("RGB")
        .convert("L")
    )
    ink = ink.point(lambda value: 255 if value > 12 else 0)
    box = ink.getbbox()
    assert box is not None
    assert abs((box[0] + box[2]) / 2 - (40 + width / 2)) <= 1.5
    assert abs((box[1] + box[3]) / 2 - 70) <= 1.5


def test_every_business_fixture_has_a_native_layout_without_text_overlaps(tmp_path):
    report = tmp_path / "audit.json"
    result = subprocess.run(
        [sys.executable, "scripts/audit_manosaba_layouts.py", "--output", str(report)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(report.read_text())
    # The shared census includes the full tour leaderboard; the audit also
    # exercises the existing partially filled leaderboard fixture below it.
    assert len(data["pages"]) == 55
    assert sum(page["layout"] == "tour.rank" for page in data["pages"]) == 2
    assert not data["missing"]
    assert not data["failures"]
    assert all(not page["errors"] for page in data["pages"])


def test_unfinished_checkin_task_is_not_shown_as_a_granted_reward():
    from plugins.daily.render import CheckinData
    from plugins.daily.render import CheckinTask
    from plugins.daily.render import checkin_page

    data = CheckinData(
        "香澄",
        7,
        1203,
        False,
        24,
        3,
        7,
        28,
        120,
        0,
        23,
        23,
        0,
        CheckinTask("概率学博士", "在黑香澄中赢得一局", 80, False),
    )
    page = checkin_page(data, ManosabaKit())
    assert isinstance(page, FolioPage)
    values = [run.value for run in page.compose().texts]
    assert "进行中" in values
    assert any("奖励 80" in value for value in values)
    assert not any("+80" in value for value in values)


def test_mail_receipt_pairs_grants_before_scope_aware_deduplication():
    from plugins.mailbox.models import ServiceMail
    from plugins.mailbox.models import ServiceMailAttachment
    from plugins.mailbox.render import mail_page
    from plugins.inventory.models import GrantResult

    a = ServiceMailAttachment(
        item_id="season_point", quantity=100, scope_type="season", scope_id="one"
    )
    b = ServiceMailAttachment(
        item_id="season_point", quantity=200, scope_type="season", scope_id="two"
    )
    mail = ServiceMail(
        id=982341,
        title="回执测试",
        content="正文",
        star_kakeras=0,
        attachments=[a, a, b],
        sender_id="opaque_sender_secret",
        created_at=datetime(2026, 10, 1),
        expire_time=datetime(2099, 1, 1),
        is_broadcast=False,
        is_read=False,
        read_at=None,
    )
    results = (
        GrantResult("season_point", 100, 12, 12),
        GrantResult("season_point", 100, 0, 12, skipped=True),
        GrantResult("season_point", 200, 34, 34),
    )
    values = [
        run.value
        for run in mail_page(mail, results, ManosabaKit(), ordinal=4).compose().texts
    ]
    receipts = [v for v in values if "赛季积分" in v]
    assert len(receipts) == 2
    assert any("12" in v for v in receipts) and any("34" in v for v in receipts)
    assert not any("100" in v or "200" in v for v in receipts)
    assert not any("opaque_sender_secret" in v or "982341" in v for v in values)


def test_hidden_mines_do_not_change_the_board_image():
    from plugins.mines.models import Field
    from plugins.mines.models import BlockType

    first, second = object.__new__(Field), object.__new__(Field)
    for field in (first, second):
        field.width = field.height = 2
        field.mines = 1
    first.field = [
        [BlockType.MINE, BlockType.EMPTY],
        [BlockType.EMPTY, BlockType.EMPTY],
    ]
    second.field = [
        [BlockType.EMPTY, BlockType.EMPTY],
        [BlockType.EMPTY, BlockType.MINE],
    ]
    kit = ManosabaKit()
    a = page_for(kit, "mines.board", first).render(RenderContext(pixel_ratio=1))
    b = page_for(kit, "mines.board", second).render(RenderContext(pixel_ratio=1))
    assert a.tobytes() == b.tobytes()


def test_hidden_blackjack_card_and_score_do_not_reveal_the_card():
    from plugins.blackjack.models import Card
    from plugins.blackjack.models import Hand
    from plugins.blackjack.render import BlackjackRenderer

    renderer = object.__new__(BlackjackRenderer)
    renderer.kit = ManosabaKit()

    def card_image(card, hidden):
        color = (40, 40, 40, 255) if hidden else (card.get_value() * 20, 80, 80, 255)
        return Image.new("RGBA", (160, 224), color)

    renderer._render_card_with_text = card_image

    def hand(*ranks):
        cards = Hand()
        for rank in ranks:
            cards.add_card(Card("cool", rank))
        return cards

    player = hand("8", "7")
    a = renderer.generate_table(hand("5", "2"), player, dealer_card_back=True)
    b = renderer.generate_table(hand("5", "K"), player, dealer_card_back=True)
    assert a.mode == b.mode == "RGB"
    assert a.tobytes() == b.tobytes()


@pytest.mark.asyncio
async def test_native_profile_retains_cosmetics_and_the_async_page_contract(
    monkeypatch,
):
    from plugins.inventory.render import ProfileData
    from plugins.inventory.render import profile_page

    frame = Image.new("RGBA", (512, 512), (100, 40, 70, 120))
    kit = ManosabaKit()
    seen = []
    original = kit._avatar

    def avatar(image, nickname, size, cosmetic=None):
        seen.append(cosmetic)
        return original(image, nickname, size, cosmetic)

    monkeypatch.setattr(kit, "_avatar", avatar)
    data = ProfileData(
        PlayerIdentity("很长的昵称用于检查档案布局", 24),
        1234,
        description="个人简介。",
        avatar_frame=frame,
    )
    page = profile_page(data, kit)
    a = page.render(RenderContext(pixel_ratio=1))
    b = await page.render_async(RenderContext(pixel_ratio=1))
    assert a.tobytes() == b.tobytes()
    assert seen and all(cosmetic is frame for cosmetic in seen)


@pytest.mark.asyncio
async def test_mail_catalog_is_resolved_before_worker_rendering(monkeypatch):
    from plugins.mailbox.models import ServiceMail
    from plugins.mailbox.models import ServiceMailAttachment
    from plugins.mailbox.render import rewards
    from plugins.mailbox.render import mail_page

    mail = ServiceMail(
        id=1,
        title="通知",
        content="信件正文",
        star_kakeras=0,
        attachments=[ServiceMailAttachment(item_id="season_point", quantity=12)],
        sender_id="admin",
        created_at=datetime(2026, 10, 1),
        expire_time=datetime(2099, 1, 1),
        is_broadcast=False,
        is_read=True,
        read_at=None,
    )
    page = mail_page(mail, (), ManosabaKit())

    def forbidden(*args, **kwargs):
        raise AssertionError("Catalog access must happen before render_async")

    monkeypatch.setattr(rewards, "item_display", forbidden)
    monkeypatch.setattr(rewards, "item_facts", forbidden)
    image = await page.render_async(RenderContext(pixel_ratio=1))
    assert image.width == 1020


def test_rankings_retain_equipped_avatar_frames(monkeypatch):
    from plugins.daily.render.rank import RankRow
    from plugins.daily.render.rank import RankData
    from plugins.daily.render.rank import rank_page
    from plugins.inventory.render.season_rank import SeasonRankRow
    from plugins.inventory.render.season_rank import SeasonRankData
    from plugins.inventory.render.season_rank import season_rank_page

    frame = Image.new("RGBA", (512, 512), (100, 40, 70, 120))
    identity = PlayerIdentity("测试玩家", 12, avatar_frame=frame)
    kit = ManosabaKit()
    seen = []
    original = kit._avatar

    def avatar(image, nickname, size, cosmetic=None):
        seen.append(cosmetic)
        return original(image, nickname, size, cosmetic)

    monkeypatch.setattr(kit, "_avatar", avatar)
    daily = RankData(
        (RankRow(1, "测试玩家", 12, 300, identity=identity),), None, "测试玩家", 1, 0
    )
    season = SeasonRankData(
        "测试赛季",
        (SeasonRankRow(1, "测试玩家", 300, identity=identity),),
        (),
        "测试玩家",
        1,
        300,
    )
    for page in (rank_page(daily, kit), season_rank_page(season, kit)):
        sheet = page.compose(RenderContext(pixel_ratio=1))
        assert "测试玩家" in [run.value for run in sheet.texts]
        assert not any("距上一名" in run.value for run in sheet.texts)
        assert not any("你附近" in run.value for run in sheet.texts)
    assert seen and all(value is frame for value in seen)
