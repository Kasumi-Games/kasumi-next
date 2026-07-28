"""EnvelopeCard 测试：创建卡、结算卡、列表卡、成本纪律与账本数据。"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.render import PlayerIdentity
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.red_envelope.render import ClaimRow
from plugins.red_envelope.render import EnvelopeListItem
from plugins.red_envelope.render import EnvelopeCreateData
from plugins.red_envelope.render import EnvelopeCompletionData
from plugins.red_envelope.render import list_page
from plugins.red_envelope.render import create_page
from plugins.red_envelope.render import render_list
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


def test_completion_card_height_is_bounded_after_three_ranked_rows():
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
    assert big.size[1] == small.size[1]


def test_completion_card_marks_lucky_king_by_badge_word():
    texts = _collect_text(completion_page(_completion_data(), MinimalKit()).child)
    # 极值只在摘要出现一次，成员列表不再重复贴手气王标签。
    assert texts.count("手气王") == 1
    assert "有咲 · 38 Pt" in texts
    assert texts.count("霉运王") == 1
    assert "香澄 · 12 Pt" in texts


def test_completion_ladder_ranks_amount_descending_and_shows_top_three():
    data = _completion_data(
        claims=(
            ClaimRow(name="先领但少", amount=5),
            ClaimRow(name="欧皇", amount=50, is_lucky_king=True),
            ClaimRow(name="第二名", amount=30),
            ClaimRow(name="第三名", amount=20),
            ClaimRow(name="倒霉蛋", amount=1),
        ),
        lucky_king_name="欧皇",
        lucky_king_amount=50,
    )
    texts = _collect_text(completion_page(data, MinimalKit()).child)
    ranked = [
        text for text in texts if text in {"欧皇", "第二名", "第三名", "先领但少"}
    ]
    assert ranked == ["欧皇", "第二名", "第三名"]
    assert "……还有 2 人已领取" in texts


def test_completion_ladder_caps_rows_and_keeps_lucky_king_visible():
    from plugins.red_envelope.render.envelope import MAX_LADDER_ROWS

    assert MAX_LADDER_ROWS == 3
    claims = tuple(
        ClaimRow(
            name=f"成员{i}",
            amount=50 if i == 15 else i,
            is_lucky_king=i == 15,
        )
        for i in range(1, 16)
    )
    data = _completion_data(
        claims=claims,
        total_amount=sum(claim.amount for claim in claims),
        total_count=15,
        lucky_king_name="成员15",
        lucky_king_amount=50,
    )
    texts = _collect_text(completion_page(data, MinimalKit()).child)
    assert "……还有 12 人已领取" in texts
    assert "成员15" in texts
    assert "成员1 · 1 Pt" in texts  # summary only: 霉运王
    assert "成员14" in texts
    assert "成员13" in texts
    assert "成员12" not in texts
    # 手气王行被折叠时，stat 行仍然兜底可见
    assert "成员15 · 50 Pt" in texts
    # 最霉运者也必须留在摘要里，即使其账本行被折叠。
    assert "成员1 · 1 Pt" in texts


def _list_item(index: int = 3, **overrides) -> EnvelopeListItem:
    base = dict(
        channel_index=index,
        title="新年快乐",
        remaining_amount=90,
        total_amount=100,
        remaining_count=9,
        total_count=10,
        validity_text="剩 23 小时",
    )
    base.update(overrides)
    return EnvelopeListItem(**base)


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_list_card_renders(kit_cls):
    image = render_list([_list_item(1), _list_item(2, urgent=True)], kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_list_card_defaults_to_the_bangdream_kit():
    assert render_list([_list_item()]).size[0] == 864


def test_list_card_shows_index_remaining_and_validity():
    items = [
        _list_item(3),
        _list_item(
            1,
            title="午后加餐",
            remaining_amount=5,
            total_amount=50,
            remaining_count=1,
            total_count=5,
            validity_text="剩 40 分钟",
            urgent=True,
        ),
    ]
    texts = _collect_text(list_page(items, MinimalKit()).child)
    assert "进行中 2 个" in texts
    # 编号徽章是玩家照着输入的领取口令
    assert "3" in texts and "1" in texts
    assert "新年快乐" in texts and "午后加餐" in texts
    assert "剩 90/100 Pt · 9/10 份" in texts
    assert "剩 5/50 Pt · 1/5 份" in texts
    # 有效期两种形态：普通 muted 文本与临期徽章，文字都在
    assert "剩 23 小时" in texts
    assert "剩 40 分钟" in texts
    assert "发送「抢红包 编号」领取 · 「发红包 金额 份数」再发一个" in texts


def test_list_card_empty_state_is_a_card_not_text():
    texts = _collect_text(list_page([], MinimalKit()).child)
    assert "0 个" in texts
    assert "现在没有可以抢的红包\n发一个就会出现在这里" in texts
    image = render_list([], MinimalKit())
    assert image.size[0] == 864


def test_list_card_caps_rows_and_folds_the_tail():
    items = [_list_item(i, title=f"红包{i}") for i in range(1, 16)]
    texts = _collect_text(list_page(items, MinimalKit()).child)
    assert "进行中 15 个" in texts
    assert "红包11" in texts
    assert "红包12" not in texts
    assert "……还有 4 个红包" in texts


def test_list_card_grows_with_more_rows():
    kit = MinimalKit()
    small = render_list([_list_item(1)], kit)
    big = render_list([_list_item(i) for i in range(1, 7)], kit)
    assert big.size[1] > small.size[1]


def test_list_card_strips_emoji_from_titles():
    texts = _collect_text(
        list_page([_list_item(title="🎉新年★快乐🧧")], MinimalKit()).child
    )
    assert "新年★快乐" in texts
    for text in texts:
        assert all(ord(ch) < 0x1F000 for ch in text), text


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
    for module in ("envelope.py", "listing.py"):
        source = (ROOT / "plugins/red_envelope/render" / module).read_text(
            encoding="utf-8"
        )
        assert "get_session" not in source
        assert "sqlalchemy" not in source
        assert "monetary" not in source
        # 不允许向上引用插件内部（service/数据库/昵称都只能由 handler 传入）
        assert "from .." not in source


def test_images_only_at_create_completion_and_list():
    # 成本纪律（一致性评审 #14）：广播面只在创建与抢完各渲染一次；列表卡是
    # 玩家主动查询才渲染的按需面。单次抢红包与所有报错保持文本。
    source = (ROOT / "plugins/red_envelope/__init__.py").read_text(encoding="utf-8")
    assert source.count("image_segment(image)") == 3
    assert "Messages.CLAIM_SUCCESS" in source
    assert "Messages.CLAIM_COMPLETE" in source  # 渲染失败的文本兜底
    # 列表卡渲染失败时退化为原文本列表/空提示
    assert "Messages.LIST_ITEM" in source
    assert "Messages.LIST_HEADER" in source
    assert "Messages.LIST_EMPTY" in source


def test_create_card_wires_the_cached_avatar():
    # 身份条走缓存头像（utils/avatar.py）：拿不到时 None，退化为首字徽章
    source = (ROOT / "plugins/red_envelope/__init__.py").read_text(encoding="utf-8")
    assert "from utils.avatar import get_avatar" in source
    assert "identity_for(user_id, avatar=await get_avatar(user_id))" in source


def test_completion_info_carries_the_full_ledger(sqlite_session, monkeypatch):
    from plugins.red_envelope import service
    from plugins.red_envelope import database
    from plugins.red_envelope.models import Base

    sqlite_session(database, Base)
    monkeypatch.setattr(service.monetary, "add", lambda *args, **kwargs: None)
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
