"""Round-exit reveal cards for cck and guess_chart (games-other batch).

Covers the two new render modules plus the handler-side helpers that feed
them. The handlers themselves collapse the old multi-message exits (answer
text + raw image + task_msg + level_msg) into one card per exit; here we pin
the card contract: house width, win/loss shapes, must-read answer text, the
reward strip, determinism, the no-DB rule, and the no-emoji rule.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from PIL import Image
from PIL import ImageDraw

from plugins.render import PlayerIdentity
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit

ROOT = Path(__file__).resolve().parents[1]

#: Emoji have no glyphs in the bundled CJK font; none may reach a card.
_FORBIDDEN_EMOJI = "🎉🎴📊💰🎰🏆"


def _load_plugin_dependencies(*module_names: str) -> None:
    for module_name in module_names:
        importlib.import_module(module_name)


def _card_art() -> Image.Image:
    image = Image.new("RGB", (1334, 1002), (86, 52, 96))
    ImageDraw.Draw(image).ellipse([467, 301, 867, 701], fill=(255, 214, 120))
    return image


def _jacket() -> Image.Image:
    image = Image.new("RGB", (640, 640), (34, 40, 74))
    ImageDraw.Draw(image).ellipse([120, 120, 520, 520], fill=(240, 90, 120))
    return image


def _cck_win_data():
    from plugins.cck.render import LevelGain
    from plugins.cck.render import CckRevealData
    from plugins.cck.render import TaskCompletion

    return CckRevealData(
        outcome="win",
        character_name="戸山 香澄",
        card_id="1327",
        card_image=_card_art(),
        card_title="はじめてのステージ！",
        rarity=4,
        card_type="limited",
        difficulty="easy",
        winner=PlayerIdentity(nickname="zhaomaoniu", level=13),
        winner_attempt=1,
        base_amount=5,
        final_amount=20,
        birthday_names=("香澄",),
        multiplier=4,
        task=TaskCompletion(name="一眼看穿", reward=80),
        level=LevelGain(old_level=12, new_level=13, stickers=120),
        owner_name="zhaomaoniu",
    )


def _cck_loss_data(outcome: str):
    from plugins.cck.render import CckRevealData

    return CckRevealData(
        outcome=outcome,
        character_name="湊 友希那",
        card_id="502",
        card_image=_card_art(),
        card_title="宣誓のエチュード",
        rarity=3,
        card_type="permanent",
        difficulty="expert++",
    )


def _guess_chart_win_data():
    from plugins.guess_chart.render import LevelGain
    from plugins.guess_chart.render import TaskCompletion
    from plugins.guess_chart.render import GuessChartRevealData

    return GuessChartRevealData(
        outcome="win",
        song_name="ときめきエクスペリエンス！",
        band_name="Poppin'Party",
        difficulty="expert",
        play_level=28,
        bpm=178,
        notes=892,
        pool_size=271,
        hints_used=2,
        jacket=_jacket(),
        winner=PlayerIdentity(nickname="zhaomaoniu", level=13),
        base_amount=12,
        final_amount=24,
        birthday_names=("香澄",),
        multiplier=2,
        task=TaskCompletion(name="太谱达人", reward=80),
        level=LevelGain(old_level=12, new_level=13, stickers=120),
        owner_name="zhaomaoniu",
    )


def _guess_chart_loss_data(outcome: str, *, jacket=None):
    from plugins.guess_chart.render import GuessChartRevealData

    return GuessChartRevealData(
        outcome=outcome,
        song_name="六兆年と一夜物語",
        band_name="Roselia",
        difficulty="hard",
        play_level=25,
        bpm=186,
        notes=671,
        pool_size=1084,
        jacket=jacket,
    )


def _collect_text(component) -> list[str]:
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
def test_cck_reveal_renders_all_outcomes_at_house_width(kit_cls):
    from plugins.cck.render import render_reveal

    kit = kit_cls()
    win = render_reveal(_cck_win_data(), kit)
    assert win.size[0] == 864
    for outcome in ("bzd", "timeout"):
        loss = render_reveal(_cck_loss_data(outcome), kit)
        assert loss.size[0] == 864
        # A loss card has no winner strip and no reward panel.
        assert win.size[1] > loss.size[1]


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_guess_chart_reveal_renders_all_outcomes_at_house_width(kit_cls):
    from plugins.guess_chart.render import render_reveal

    kit = kit_cls()
    win = render_reveal(_guess_chart_win_data(), kit)
    assert win.size[0] == 864
    for outcome in ("bzd", "timeout"):
        loss = render_reveal(_guess_chart_loss_data(outcome, jacket=_jacket()), kit)
        assert loss.size[0] == 864
        assert win.size[1] > loss.size[1]


def test_reveals_default_to_the_bangdream_kit():
    from plugins.cck.render import render_reveal as render_cck
    from plugins.guess_chart.render import render_reveal as render_chart

    assert render_cck(_cck_loss_data("timeout")).size[0] == 864
    assert render_chart(_guess_chart_loss_data("timeout")).size[0] == 864


def test_guess_chart_reveal_survives_a_missing_jacket():
    from plugins.guess_chart.render import render_reveal

    image = render_reveal(_guess_chart_loss_data("bzd", jacket=None), MinimalKit())
    assert image.size[0] == 864


def test_cck_reveal_missing_art_and_metadata_still_renders():
    from plugins.cck.render import CckRevealData
    from plugins.cck.render import render_reveal

    data = CckRevealData(
        outcome="timeout",
        character_name="湊 友希那",
        card_id="502",
        card_image=None,
    )
    assert render_reveal(data, MinimalKit()).size[0] == 864


def test_cck_win_page_carries_answer_rewards_and_no_machine_strings():
    from plugins.cck.render import reveal_page

    page = reveal_page(_cck_win_data(), MinimalKit())
    joined = " ".join(_collect_text(page.child))

    # The answer and the card identity are on the card.
    assert "戸山 香澄" in joined
    assert "はじめてのステージ！" in joined
    assert "★★★★" in joined
    assert "期间限定 · #1327" in joined
    # The reward strip replaces the three reward messages.
    assert "+20 Pt" in joined
    assert "+80 贴纸" in joined
    assert "+120 贴纸" in joined
    assert "每日任务 · 一眼看穿" in joined
    assert "等级提升！Lv.12 → Lv.13" in joined
    assert "×4" in joined
    # The winner strip names the winner and the attempt.
    assert "zhaomaoniu" in joined
    assert "第 1 次答对" in joined
    # The old raw-key concatenation never reaches the card.
    assert "card_id:" not in joined


def test_cck_loss_page_shows_the_answer_but_no_rewards():
    from plugins.cck.render import reveal_page

    page = reveal_page(_cck_loss_data("timeout"), MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "湊 友希那" in joined
    assert "时间到" in joined
    assert "Pt" not in joined
    assert "贴纸" not in joined


def test_guess_chart_win_page_carries_song_identity_and_rewards():
    from plugins.guess_chart.render import reveal_page

    page = reveal_page(_guess_chart_win_data(), MinimalKit())
    joined = " ".join(_collect_text(page.child))

    assert "ときめきエクスペリエンス！" in joined
    assert "Poppin'Party" in joined
    assert "EXPERT · LV.28" in joined
    assert "BPM 178 · 892 NOTES" in joined
    assert "候选池 271 首" in joined
    assert "用了 2 条提示" in joined
    assert "+24 Pt" in joined
    assert "每日任务 · 太谱达人" in joined
    assert "等级提升！Lv.12 → Lv.13" in joined
    assert "zhaomaoniu" in joined


def test_guess_chart_loss_page_shows_the_answer_but_no_rewards():
    from plugins.guess_chart.render import reveal_page

    page = reveal_page(_guess_chart_loss_data("bzd"), MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "六兆年と一夜物語" in joined
    assert "HARD · LV.25" in joined
    assert "+24" not in joined
    assert "贴纸" not in joined


def test_reveal_pages_contain_no_emoji():
    from plugins.cck.render import reveal_page as cck_page
    from plugins.guess_chart.render import reveal_page as chart_page

    pages = [
        cck_page(_cck_win_data(), MinimalKit()),
        cck_page(_cck_loss_data("bzd"), MinimalKit()),
        chart_page(_guess_chart_win_data(), MinimalKit()),
        chart_page(_guess_chart_loss_data("timeout"), MinimalKit()),
    ]
    for page in pages:
        for text in _collect_text(page.child):
            assert not any(char in _FORBIDDEN_EMOJI for char in text)
            # The bundled CJK font has no glyphs above the BMP at all.
            assert all(ord(char) < 0x10000 for char in text)


def test_reveal_renders_are_deterministic():
    from plugins.cck.render import render_reveal as render_cck
    from plugins.guess_chart.render import render_reveal as render_chart

    kit = MinimalKit()
    first = render_cck(_cck_win_data(), kit)
    second = render_cck(_cck_win_data(), kit)
    assert first.tobytes() == second.tobytes()

    first = render_chart(_guess_chart_win_data(), kit)
    second = render_chart(_guess_chart_win_data(), kit)
    assert first.tobytes() == second.tobytes()


def test_reveal_render_modules_never_touch_a_database():
    for module_path in (
        "plugins/cck/render/reveal.py",
        "plugins/guess_chart/render/reveal.py",
    ):
        source = (ROOT / module_path).read_text(encoding="utf-8")
        assert "inventory.service" not in source
        assert "get_item" not in source
        assert "get_session" not in source
        assert "sqlalchemy" not in source
        assert "kit_for_user" not in source
        assert "identity_for" not in source


def test_cck_localized_picks_the_first_populated_server_value():
    _load_plugin_dependencies("plugins.daily_task")
    from plugins.cck import _localized

    # jp first, then the cn/tw/en/kr fallbacks in the downloader's order.
    assert _localized(["ジャパン", None, None, "简中", None]) == "ジャパン"
    assert _localized([None, "EN", "繁中", "简中", None]) == "简中"
    assert _localized([None, "EN", "繁中", None, None]) == "繁中"
    assert _localized([None, None, None, None, None]) is None
    assert _localized(None) is None
    assert _localized("not-a-list") is None


def test_level_gain_helpers_translate_xp_levels():
    _load_plugin_dependencies("plugins.daily_task")
    from plugins.cck import _level_gain as cck_level_gain
    from plugins.guess_chart import _level_gain as chart_level_gain
    from plugins.monetary.level_service import LEVEL_UP_STICKERS

    for helper in (cck_level_gain, chart_level_gain):
        assert helper(12, 12) is None
        assert helper(13, 12) is None
        gain = helper(12, 14)
        assert gain is not None
        assert gain.old_level == 12
        assert gain.new_level == 14
        assert gain.stickers == 2 * LEVEL_UP_STICKERS


def test_guess_chart_decode_jacket_tolerates_bad_bytes():
    _load_plugin_dependencies("plugins.daily_task")
    import io

    from plugins.guess_chart import _decode_jacket

    buffer = io.BytesIO()
    _jacket().save(buffer, format="PNG")
    decoded = _decode_jacket(buffer.getvalue())
    assert decoded is not None
    assert decoded.size == (640, 640)

    assert _decode_jacket(b"not an image") is None


def test_handlers_collapse_round_exits_to_single_sends():
    """The old exit shapes (answer text + raw image + task/level messages)
    must not survive in the handlers; every exit goes through the card
    sender, with the raw sends existing only inside its render fallback."""

    cck_source = (ROOT / "plugins/cck/__init__.py").read_text(encoding="utf-8")
    # One definition plus exactly three call sites (timeout / bzd / win).
    assert cck_source.count("_send_reveal_card(") == 4
    # The legacy answer text survives only as the three fallback strings.
    assert cck_source.count("答案是———") == 3
    assert "task_msg + gens" not in cck_source
    assert "level_msg + gens" not in cck_source

    chart_source = (ROOT / "plugins/guess_chart/__init__.py").read_text(
        encoding="utf-8"
    )
    assert chart_source.count("_send_reveal_card(") == 4
    # Three fallback strings plus the pre-existing logger.debug line.
    assert chart_source.count("谱面：{song_name}") == 4
    assert "task_msg + gens" not in chart_source
    assert "level_msg + gens" not in chart_source
