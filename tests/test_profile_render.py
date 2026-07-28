from __future__ import annotations

import pytest

from plugins.render import PlayerIdentity
from plugins.render.kits import BanGDreamKit
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.render.kits.bangdream.components import BanGDreamPanel
from plugins.render.kits.bangdream.components import BanGDreamTitlePill
from plugins.inventory.render import ProfileData
from plugins.inventory.render import profile_page
from plugins.inventory.render import render_profile


def _data(**overrides) -> ProfileData:
    defaults = dict(
        identity=PlayerIdentity(nickname="香澄", level=24),
        current_pt=1234,
        description="要一起组乐队吗？",
        star_stickers=56,
        bonsai=7,
        season_name="2026 第一赛季",
        season_rank=3,
        equipped=(("头像框", "星之鼓动冠军头像框"), ("主题", "扬帆起航")),
    )
    defaults.update(overrides)
    return ProfileData(**defaults)


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_profile_renders_in_multiple_kits(kit_cls):
    image = render_profile(_data(), kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_profile_renders_with_empty_description_and_zero_currencies(kit_cls):
    empty = _data(
        identity=PlayerIdentity(nickname="新玩家", level=None),
        current_pt=0,
        description="",
        star_stickers=0,
        bonsai=0,
        season_name=None,
        season_rank=None,
        equipped=(),
    )
    image = render_profile(empty, kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_profile_defaults_to_the_bangdream_kit():
    image = render_profile(_data())
    assert image.size[0] == 864


def test_bangdream_profile_uses_a_player_title_pill():
    page = profile_page(_data(), BanGDreamKit())
    header = page.child.children[0]
    assert isinstance(header.child, BanGDreamTitlePill)
    assert header.child.title == "资料"
    assert header.child.subtitle == "个人资料"


def test_bangdream_profile_stats_panel_is_opaque():
    page = profile_page(_data(), BanGDreamKit())
    stats_panel = page.child.children[1].children[1]
    assert isinstance(stats_panel, BanGDreamPanel)
    assert stats_panel.fill == (255, 255, 255, 255)


def test_profile_page_exposes_async_render():
    page = profile_page(_data(), MinimalKit())
    assert hasattr(page, "render_async")
    assert page.render().size[0] == 864


def test_full_profile_is_taller_than_the_empty_one():
    kit = MinimalKit()
    full = render_profile(_data(), kit)
    empty = render_profile(
        _data(
            description="",
            season_name=None,
            season_rank=None,
            equipped=(),
        ),
        kit,
    )
    assert full.size[1] > empty.size[1]


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


def test_profile_xp_meter_row_states_the_numbers():
    page = profile_page(_data(xp_in_level=1372, xp_level_span=2500), MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "等级经验" in joined
    assert "1372/2500 XP" in joined


def test_profile_without_xp_span_has_no_meter_row():
    # Old callers that never set the XP fields keep their exact card.
    joined = " ".join(_collect_text(profile_page(_data(), MinimalKit()).child))
    assert "等级经验" not in joined
    assert "XP" not in joined


def test_profile_offseason_labels_the_pt_row_and_warns():
    data = _data(
        season_name=None,
        season_rank=None,
        offseason=True,
        xp_in_level=100,
        xp_level_span=2500,
    )
    page = profile_page(data, MinimalKit())
    joined = " ".join(_collect_text(page.child))
    assert "休赛期临时 Pt" in joined
    assert "休赛期临时 Pt 不会计入下一赛季" in joined
    assert page.render().size[0] == 864


def test_profile_in_season_carries_no_offseason_note():
    joined = " ".join(_collect_text(profile_page(_data(), MinimalKit()).child))
    assert "休赛期" not in joined
