"""EnvelopeCard 测试：创建卡、结算卡、成本纪律与账本数据。"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.render import PlayerIdentity
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.red_envelope.render import ClaimRow
from plugins.red_envelope.render import EnvelopeCreateData
from plugins.red_envelope.render import EnvelopeCompletionData
from plugins.red_envelope.render import create_page
from plugins.red_envelope.render import render_create
from plugins.red_envelope.render import completion_page
from plugins.red_envelope.render import render_completion

ROOT = Path(__file__).resolve().parents[1]


def _identity(nickname: str = "香澄") -> PlayerIdentity:
    return PlayerIdentity(nickname=nickname, level=12, avatar=None)


def _create_data(**overrides) -> EnvelopeCreateData:
    base = dict(
        channel_index=3,
        title="新年快乐",
        total_amount=100,
        total_count=10,
        creator=_identity(),
    )
    base.update(overrides)
    return EnvelopeCreateData(**base)


def _default_claims() -> tuple[ClaimRow, ...]:
    return (
        ClaimRow(name="有咲", amount=38, is_lucky_king=True),
        ClaimRow(name="彩", amount=24),
        ClaimRow(name="沙绫", amount=16),
        ClaimRow(name="香澄", amount=12),
    )


def _completion_data(**overrides) -> EnvelopeCompletionData:
    base = dict(
        channel_index=3,
        title="新年快乐",
        total_amount=90,
        total_count=4,
        creator_name="香澄",
        duration_text="2 分 14 秒",
        lucky_king_name="有咲",
        lucky_king_amount=38,
        claims=_default_claims(),
    )
    base.update(overrides)
    return EnvelopeCompletionData(**base)


def _collect_text(component) -> list[str]:
    """按文档序收集组件树里的文本节点。"""

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


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_create_card_renders(kit_cls):
    image = render_create(_create_data(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_create_card_defaults_to_the_bangdream_kit():
    assert render_create(_create_data()).size[0] == 864


def test_create_card_shows_command_amount_and_creator():
    texts = _collect_text(create_page(_create_data(), MinimalKit()).child)
    joined = " ".join(texts)
    assert "发送「抢红包 3」领取" in texts
    assert "100 Pt" in texts
    assert "共 10 份" in texts
    assert "新年快乐" in texts
    # 创建者身份条（Tier A 面）带昵称与等级
    assert "香澄" in texts
    assert "Lv.12" in joined
    # 有效期由 handler 从 service 常量推得，这里走默认值
    assert "24 小时" in texts


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_completion_card_renders(kit_cls):
    image = render_completion(_completion_data(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_completion_card_grows_with_more_claims():
    kit = MinimalKit()
    small = render_completion(_completion_data(), kit)
    claims = tuple(
        ClaimRow(name=f"成员{i}", amount=9, is_lucky_king=i == 1)
        for i in range(1, 11)
    )
    big = render_completion(
        _completion_data(
            claims=claims,
            total_amount=90,
            total_count=10,
            lucky_king_name="成员1",
            lucky_king_amount=9,
        ),
        kit,
    )
    assert big.size[1] > small.size[1]


def test_completion_card_marks_lucky_king_by_badge_word():
    texts = _collect_text(completion_page(_completion_data(), MinimalKit()).child)
    # 恰好两处：stat 行标签 + 榜单行徽章（形状标记，不靠色相）
    assert texts.count("手气王") == 2
    assert "有咲 · 38 Pt" in texts


def test_completion_ladder_keeps_claim_order():
    texts = _collect_text(completion_page(_completion_data(), MinimalKit()).child)
    names = [t for t in texts if t in {"彩", "沙绫"} or t == "有咲"]
    assert names == ["有咲", "彩", "沙绫"]
    # 领取顺序编号逐行排布
    orders = [t for t in texts if t in {"1", "2", "3", "4"}]
    assert orders == ["1", "2", "3", "4"]


def test_completion_ladder_caps_rows_and_keeps_lucky_king_visible():
    claims = tuple(
        ClaimRow(name=f"成员{i}", amount=50 if i == 15 else 1, is_lucky_king=i == 15)
        for i in range(1, 16)
    )
    data = _completion_data(
        claims=claims,
        total_amount=64,
        total_count=15,
        lucky_king_name="成员15",
        lucky_king_amount=50,
    )
    texts = _collect_text(completion_page(data, MinimalKit()).child)
    assert "……还有 5 人已领取" in texts
    assert "成员10" in texts
    assert "成员11" not in texts
    # 手气王行被折叠时，stat 行仍然兜底可见
    assert "成员15 · 50 Pt" in texts


def test_emoji_is_stripped_but_star_glyphs_survive():
    create_texts = _collect_text(
        create_page(
            _create_data(title="🎉新年★快乐🧧", creator=_identity("香澄🎀")),
            MinimalKit(),
        ).child
    )
    assert "新年★快乐" in create_texts
    assert "香澄" in create_texts

    completion_texts = _collect_text(
        completion_page(
            _completion_data(
                title="🎉新年★快乐🧧",
                creator_name="香澄🎀",
                lucky_king_name="有咲✨",
                claims=(
                    ClaimRow(name="有咲✨", amount=38, is_lucky_king=True),
                    ClaimRow(name="彩", amount=52),
                ),
            ),
            MinimalKit(),
        ).child
    )
    for text in create_texts + completion_texts:
        assert all(ord(ch) < 0x1F000 for ch in text), text
        assert all(not (0x2700 <= ord(ch) <= 0x27BF) for ch in text), text
    assert "有咲" in completion_texts
    assert "#3 · 新年★快乐" in completion_texts


def test_absent_bmp_glyphs_are_stripped_too():
    # 字体 cmap 实测：U+2600 块只有 ★☆☉♀♂，U+2300 块只有 ⌒，U+2B00 块全无。
    # ♥♪⭐⏰‼™ 等字体没有字形的字符必须剥掉，否则渲染成空框（豆腐块）。
    texts = _collect_text(
        create_page(
            _create_data(title="新年♪⭐快乐⏰来抢‼", creator=_identity("香澄♥™(⌒▽⌒)")),
            MinimalKit(),
        ).child
    )
    assert "新年快乐来抢" in texts
    # ⌒（颜文字弧线）与几何形状 ▽ 字体里有字形，必须存活
    assert "香澄(⌒▽⌒)" in texts
    banned = {0x2B50, 0x23F0, 0x203C, 0x2122, 0x2665, 0x266A, 0x2764}
    for text in texts:
        assert all(ord(ch) not in banned for ch in text), text


def test_strip_ranges_match_the_bundled_font_cmap():
    # 剥离表是对照字体 cmap 实测的；字体一旦换掉，这里立刻报警。
    ttLib = pytest.importorskip("fontTools.ttLib")
    from plugins.red_envelope.render.envelope import _is_unrenderable

    font_path = ROOT / "plugins/render/kits/bangdream/resources/Fonts/old.ttf"
    cmap = ttLib.TTFont(font_path).getBestCmap()
    for code in (0x2312, 0x2605, 0x2606, 0x2609, 0x2640, 0x2642):
        assert not _is_unrenderable(chr(code))
        assert code in cmap
    for code in (
        0x203C,
        0x2122,
        0x231A,
        0x23F0,
        0x2600,
        0x2665,
        0x266A,
        0x26A1,
        0x2713,
        0x2B50,
        0x2B55,
    ):
        assert _is_unrenderable(chr(code))
        assert code not in cmap


def test_render_module_never_touches_a_database():
    # 渲染层无 DB 规则：昵称/身份/主题都由 handler 在事件循环线程解析后传入
    source = (ROOT / "plugins/red_envelope/render/envelope.py").read_text(
        encoding="utf-8"
    )
    assert "get_session" not in source
    assert "sqlalchemy" not in source
    assert "monetary" not in source
    # 不允许向上引用插件内部（service/数据库/昵称都只能由 handler 传入）
    assert "from .." not in source


def test_only_create_and_completion_reply_with_images():
    # 成本纪律（一致性评审 #14）：图片只在创建与抢完两个节点各发一次，
    # 单次抢红包、列表、报错全部保持文本。
    source = (ROOT / "plugins/red_envelope/__init__.py").read_text(encoding="utf-8")
    assert source.count("image_segment(image)") == 2
    assert "Messages.CLAIM_SUCCESS" in source
    assert "Messages.LIST_ITEM" in source
    assert "Messages.CLAIM_COMPLETE" in source  # 渲染失败的文本兜底


def test_completion_info_carries_the_full_ledger(sqlite_session, monkeypatch):
    from plugins.red_envelope import service
    from plugins.red_envelope import database
    from plugins.red_envelope.models import Base

    sqlite_session(database, Base)
    monkeypatch.setattr(service.monetary, "add", lambda *args: None)
    monkeypatch.setattr(service.random, "randint", lambda low, high: high)

    service.create_envelope("creator", "channel", "hello", 10, 3)
    assert service.claim_envelope("u1", "channel", 1)[0] == "success"
    assert service.claim_envelope("u2", "channel", 1)[2] is None

    status, _amount, completion = service.claim_envelope("u3", "channel", 1)
    assert status == "success"
    assert completion is not None
    assert completion.channel_index == 1
    assert completion.title == "hello"
    assert completion.total_amount == 10
    assert completion.total_count == 3
    # 账本按领取顺序排列，金额合计等于总额
    assert [claim.user_id for claim in completion.claims] == ["u1", "u2", "u3"]
    assert sum(claim.amount for claim in completion.claims) == 10
    lucky = max(completion.claims, key=lambda claim: claim.amount)
    assert completion.lucky_king_id == lucky.user_id
    assert completion.lucky_king_amount == lucky.amount
