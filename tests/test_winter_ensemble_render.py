"""Winter Tier A keeps every result and renders deterministically at real scales."""

import pytest

from utils import cards
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import AutoPage
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.kit import BaseKit
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits import KITS
from plugins.render.kits import WinterEnsembleKit


def render(component, width):
    return AutoPage(
        Frame(component, width=Fixed(width)),
        background=WinterEnsembleKit().background(),
    ).render()


def test_three_surfaces_are_authored_and_registered():
    assert KITS["winter_ensemble"] is WinterEnsembleKit
    for name in ("game_identity", "player_card", "pull_reveal"):
        assert getattr(WinterEnsembleKit, name) is not getattr(BaseKit, name)


@pytest.mark.parametrize("width", [200, 784])
def test_missing_identity_assets_and_long_name_fit_strip(width):
    kit = WinterEnsembleKit()
    component = cards.game_identity(
        kit,
        PlayerIdentity("很长的中文昵称" * 10, 24),
        width=width,
        detail="当前下注 120 Pt",
    )
    size = component.measure(RenderContext(), Constraints(max_width=width))
    assert 64 <= size.height <= 88
    a = render(component, width)
    b = render(component, width)
    assert a.size == (width, 80)
    assert a.tobytes() == b.tobytes()


@pytest.mark.parametrize("count", range(1, 11))
@pytest.mark.parametrize("width", [200, 784, 1216])
def test_pulls_keep_all_results_without_art(count, width):
    kit = WinterEnsembleKit()
    pulls = tuple(
        PullRevealItem(
            "很长的角色名 冬日", 4 + i % 3, i % 2 == 0, i % 3 == 0, note="盆栽 +60"
        )
        for i in range(count)
    )
    component = cards.pull_reveal(kit, pulls, width=width)
    image = render(component, width)
    assert image.width == width
    if count > 1 or width < 540:
        assert len(component.children) == count
        assert all(tile.height == 500 for tile in component.children)
    assert image.tobytes() == render(component, width).tobytes()


def test_profile_missing_slots_stay_stable():
    kit = WinterEnsembleKit()
    component = cards.player_card(
        kit,
        PlayerIdentity("示例玩家", 24),
        current_pt=100,
        description="",
        width=784,
        height=420,
    )
    assert render(component, 784).size == (784, 420)
