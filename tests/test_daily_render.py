"""Render tests for the daily plugin's CheckinCard and RankCard."""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.daily.render import RankRow
from plugins.daily.render import RankData
from plugins.daily.render import CheckinData
from plugins.daily.render import CheckinTask
from plugins.daily.render import rank_page
from plugins.daily.render import render_rank
from plugins.daily.render import checkin_page
from plugins.daily.render import render_checkin

ROOT = Path(__file__).resolve().parents[1]


def _checkin(
    *,
    streak: int = 24,
    streak_bonus: int = 0,
    old_level: int = 23,
    new_level: int = 23,
    level_stickers: int = 0,
    offseason: bool = False,
    unread_mails: int = 0,
    task_done: bool = False,
) -> CheckinData:
    return CheckinData(
        nickname="香澄",
        reward_pt=7,
        balance=1203,
        offseason=offseason,
        streak=streak,
        window_done=(streak - 1) % 7 + 1,
        window_total=7,
        next_bonus_day=((streak - 1) // 7 + 1) * 7,
        bonus_stickers=120,
        streak_bonus=streak_bonus,
        old_level=old_level,
        new_level=new_level,
        level_stickers=level_stickers,
        task=CheckinTask(
            name="概率学博士",
            description="在黑香澄中赢得一局",
            reward=80,
            done=task_done,
        ),
        unread_mails=unread_mails,
    )


def _rank(*, viewer_in_top: bool = False) -> RankData:
    rows = tuple(
        RankRow(rank=index + 1, name=f"成员{index + 1}", level=40 - index, xp=18204 - index * 900)
        for index in range(10)
    )
    if viewer_in_top:
        rows = (RankRow(rank=1, name="香澄", level=42, xp=18204),) + rows[1:]
        return RankData(
            rows=rows, viewer=None, viewer_name="香澄", viewer_rank=1, xp_gap=0
        )
    return RankData(
        rows=rows,
        viewer=RankRow(rank=27, name="香澄", level=24, xp=1180),
        viewer_name="香澄",
        viewer_rank=27,
        xp_gap=340,
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


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_checkin_card_renders(kit_cls):
    image = render_checkin(_checkin(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_checkin_card_defaults_to_the_bangdream_kit():
    assert render_checkin(_checkin()).size[0] == 864


def test_checkin_card_carries_the_reward_streak_and_task():
    page = checkin_page(_checkin(), MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "签到成功" in joined
    assert "+7 Pt" in joined
    assert "签到奖励" in joined
    assert "连续签到" in joined
    assert "24 天" in joined
    # Streak meter counts toward the next 7-day milestone from the real logic.
    assert "3/7" in joined
    assert "第 28 天奖励 120 星星贴纸" in joined
    assert "概率学博士" in joined
    assert "在黑香澄中赢得一局" in joined
    assert "奖励 80 星星贴纸" in joined
    assert "赛季 Pt" in joined
    assert "1203 Pt" in joined


def test_checkin_card_without_level_change_has_no_level_up_row():
    page = checkin_page(_checkin(), MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "等级提升" not in joined
    assert "升级奖励" not in joined


def test_checkin_card_level_up_row_appears_only_on_change():
    data = _checkin(old_level=23, new_level=24, level_stickers=120)
    page = checkin_page(data, MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "等级提升！Lv.23 → Lv.24" in joined
    assert "+120 星星贴纸" in joined
    assert "升级奖励" in joined
    assert page.render().size[0] == 864


def test_checkin_card_day7_bonus_row():
    data = _checkin(streak=28, streak_bonus=120)
    page = checkin_page(data, MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "+120 星星贴纸" in joined
    assert "连续签到 28 天奖励" in joined
    # The window is complete, so the meter states the payout, not a countdown.
    assert "7/7" in joined
    assert "本轮 120 星星贴纸已到账" in joined


def test_checkin_card_conditional_notices():
    quiet = " ".join(_collect_text(checkin_page(_checkin(), MinimalKit()).child))
    assert "未读邮件" not in quiet
    assert "休赛期" not in quiet

    noisy = " ".join(
        _collect_text(
            checkin_page(
                _checkin(offseason=True, unread_mails=3), MinimalKit()
            ).child
        )
    )
    assert "你有 3 封未读邮件 · 发送 /邮箱 查看" in noisy
    assert "休赛期临时 Pt" in noisy


def test_checkin_card_strings_carry_no_emoji():
    data = _checkin(
        streak=28,
        streak_bonus=120,
        old_level=23,
        new_level=24,
        level_stickers=120,
        offseason=True,
        unread_mails=2,
        task_done=True,
    )
    for text in _collect_text(checkin_page(data, MinimalKit()).child):
        assert all(ord(char) < 0x1F000 for char in text), text


def test_checkin_render_is_deterministic():
    kit = MinimalKit()
    data = _checkin(streak=7, streak_bonus=120)
    assert render_checkin(data, kit).tobytes() == render_checkin(data, kit).tobytes()


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_rank_card_renders(kit_cls):
    image = render_rank(_rank(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_rank_card_appends_the_viewer_row_outside_top_10():
    page = rank_page(_rank(), MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "27" in joined
    assert "香澄" in joined
    assert "Lv.24 · 1,180 XP" in joined
    assert "你当前排名第 27 名 · 距上一名 340 XP" in joined


def test_rank_card_viewer_in_top_10_gets_no_extra_row():
    page = rank_page(_rank(viewer_in_top=True), MinimalKit())
    texts = _collect_text(page.child)
    assert texts.count("香澄") == 1
    joined = " ".join(texts)
    assert "你当前排名第 1 名" in joined
    # Rank 1 has nobody above: no gap sentence at all.
    assert "距上一名" not in joined
    assert "与上一名相同" not in joined


def test_rank_card_tie_reads_as_equal():
    data = RankData(
        rows=_rank().rows,
        viewer=RankRow(rank=11, name="有咲", level=30, xp=8470),
        viewer_name="有咲",
        viewer_rank=11,
        xp_gap=0,
    )
    joined = " ".join(_collect_text(rank_page(data, MinimalKit()).child))
    assert "你当前排名第 11 名 · 与上一名相同" in joined


def test_rank_card_names_the_ladder_in_the_subtitle():
    joined = " ".join(_collect_text(rank_page(_rank(), MinimalKit()).child))
    assert "等级榜 · Top 10" in joined


def test_rank_card_empty_state():
    data = RankData(rows=(), viewer=None, viewer_name="香澄", viewer_rank=1, xp_gap=0)
    page = rank_page(data, MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "还没有人上榜" in joined
    assert page.render().size[0] == 864


def test_daily_render_module_never_touches_a_database():
    # No-DB rule: the handler assembles the dataclasses; the render module
    # must not import services or open a session.
    for name in ("checkin.py", "rank.py"):
        source = (ROOT / "plugins/daily/render" / name).read_text(encoding="utf-8")
        assert "get_session" not in source
        assert "sqlalchemy" not in source
        assert "monetary" not in source
        assert "daily_task" not in source
        assert "mail_service" not in source


def test_daily_plugin_source_carries_no_emoji():
    # The 🎉 that used to sit in the check-in text must not come back: any
    # string the handler routes into a card would render as an empty box.
    for path in (
        ROOT / "plugins/daily/__init__.py",
        ROOT / "plugins/daily/render/checkin.py",
        ROOT / "plugins/daily/render/rank.py",
    ):
        source = path.read_text(encoding="utf-8")
        emoji = [char for char in source if ord(char) >= 0x1F000]
        assert emoji == [], f"{path.name}: {emoji}"
