from __future__ import annotations

import pytest

from plugins.render import PlayerIdentity
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
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
        equipped=(("称号", "扬帆之星"), ("主题", "扬帆起航")),
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
