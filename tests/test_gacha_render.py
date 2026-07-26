from __future__ import annotations

from pathlib import Path

import pytest

from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.gacha.render import grant_note
from plugins.gacha.render import render_pull
from plugins.gacha.render import pull_page_data
from plugins.gacha.service import GachaEntry
from plugins.gacha.service import GachaBanner
from plugins.gacha.service import GachaResult
from plugins.gacha.service import GrantDetail

ROOT = Path(__file__).resolve().parents[1]
KASUMI_ART = (
    ROOT
    / "plugins/render/kits/kasumi/resources/standing/kasumi_starry_after_training.png"
)


def _banner() -> GachaBanner:
    return GachaBanner(
        season_key="2026-s01",
        season_name="2026 第一赛季",
        banner_key="2026-s01-limited",
        name="星之鼓动 限定卡池",
        single_cost=120,
        ten_cost=1200,
        base_rates={6: 0.01, 5: 0.09, 4: 0.30, 3: 0.60},
        soft_pity_start=70,
        hard_pity=90,
        entries=(
            GachaEntry(
                item_id="standing_art_kasumi_starbeat",
                character_id="kasumi",
                name="户山香澄 星之鼓动立绘",
                rarity=6,
                weight=1,
                featured=True,
            ),
            GachaEntry(
                item_id="standing_art_placeholder_r3_001",
                character_id="placeholder_r3_001",
                name="占位角色立绘 3-1",
                rarity=3,
                weight=1,
            ),
        ),
    )


def _result(
    item_id: str,
    name: str,
    rarity: int,
    *,
    pity_before: int = 0,
    pity_after: int = 1,
    message: str = "",
    grants: tuple[GrantDetail, ...] = (),
) -> GachaResult:
    return GachaResult(
        item_id=item_id,
        character_id=item_id,
        name=name,
        rarity=rarity,
        cost=120,
        pity_before=pity_before,
        pity_after=pity_after,
        grant_message=message,
        grants=grants,
    )


def _ten_results() -> list[GachaResult]:
    results = [
        _result(
            "standing_art_placeholder_r3_001",
            "占位角色立绘 3-1",
            3,
            pity_before=index,
            pity_after=index + 1,
            message="already_owned" if index % 2 else "",
        )
        for index in range(9)
    ]
    results.append(
        _result(
            "standing_art_kasumi_starbeat",
            "户山香澄 星之鼓动立绘",
            6,
            pity_before=9,
            pity_after=0,
            message="already_owned_compensated:120",
        )
    )
    return results


def test_pull_page_data_maps_results_onto_reveal_items():
    data = pull_page_data(_ten_results(), _banner())

    assert data.banner_name == "星之鼓动 限定卡池"
    assert data.pity_after == 0
    assert data.hard_pity == 90
    assert len(data.pulls) == 10

    fresh = data.pulls[0]
    assert fresh.is_new is True
    assert fresh.featured is False
    assert fresh.note == ""

    duplicate = data.pulls[1]
    assert duplicate.is_new is False
    assert duplicate.note == "重复"

    featured = data.pulls[-1]
    assert featured.featured is True
    assert featured.is_new is False
    assert featured.note == "盆栽 +120"
    assert featured.rarity == 6


def test_pull_page_data_rejects_empty_results():
    with pytest.raises(ValueError):
        pull_page_data([], _banner())


def test_grant_note_decodes_machine_messages():
    assert grant_note("") == ""
    assert grant_note("already_owned") == "重复"
    assert grant_note("already_owned_compensated:120") == "盆栽 +120"
    # 限定六星会把最多三条发放消息拼在一起，补偿要合计
    joined = "already_owned_compensated:120; already_owned_compensated:15"
    assert grant_note(joined) == "盆栽 +135"
    assert grant_note("done") == "已发放"
    # 未知消息原样透传，不静默吞掉信息
    assert grant_note("weird") == "weird"


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_single_pull_renders(kit_cls):
    data = pull_page_data(
        [_result("standing_art_placeholder_r3_001", "占位角色立绘 3-1", 3)],
        _banner(),
    )
    image = render_pull(data, kit_cls())
    assert image.size[0] == 864
    assert image.size[1] > 0


@pytest.mark.parametrize("kit_cls", [MinimalKit, MangaKit])
def test_ten_pull_renders_and_is_taller_than_a_single(kit_cls):
    kit = kit_cls()
    banner = _banner()
    single = render_pull(
        pull_page_data(
            [_result("standing_art_placeholder_r3_001", "占位角色立绘 3-1", 3)],
            banner,
        ),
        kit,
    )
    ten = render_pull(pull_page_data(_ten_results(), banner), kit)
    assert ten.size[0] == 864
    assert ten.size[1] > single.size[1]


def test_pull_defaults_to_the_bangdream_kit():
    data = pull_page_data(
        [_result("standing_art_kasumi_starbeat", "户山香澄 星之鼓动立绘", 6, pity_after=0)],
        _banner(),
    )
    assert render_pull(data).size[0] == 864


def _featured_with_owned_bundle() -> GachaResult:
    """A featured ★6 whose standing art is fresh but the bundle was owned."""

    return _result(
        "standing_art_kasumi_starbeat",
        "户山香澄 星之鼓动立绘",
        6,
        pity_after=0,
        message="already_owned_compensated:12; already_owned_compensated:120",
        grants=(
            GrantDetail("standing_art_kasumi_starbeat", 1, False, ""),
            GrantDetail(
                "frame_s1_6star_character", 0, True, "already_owned_compensated:12"
            ),
            GrantDetail("theme_s1_sailing", 0, True, "already_owned_compensated:120"),
        ),
    )


def test_new_badge_comes_from_the_pulled_items_own_grant():
    # Phase-2 deferred fix: the joined message is non-empty because the
    # bundled frame/theme were duplicates, but the standing art itself was
    # freshly granted — the tile must still read NEW.
    data = pull_page_data([_featured_with_owned_bundle()], _banner())
    tile = data.pulls[0]
    assert tile.is_new is True
    assert tile.note == "盆栽 +132"
    # Nothing extra was actually granted, so no bonus line.
    assert data.bonus_grants == ()


def test_duplicate_pulled_item_is_not_new():
    data = pull_page_data(
        [
            _result(
                "standing_art_kasumi_starbeat",
                "户山香澄 星之鼓动立绘",
                6,
                pity_after=0,
                message="already_owned_compensated:60",
                grants=(
                    GrantDetail(
                        "standing_art_kasumi_starbeat",
                        0,
                        True,
                        "already_owned_compensated:60",
                    ),
                ),
            )
        ],
        _banner(),
    )
    assert data.pulls[0].is_new is False


def test_bonus_grants_surface_bundled_items_with_player_names():
    result = _result(
        "standing_art_kasumi_starbeat",
        "户山香澄 星之鼓动立绘",
        6,
        pity_after=0,
        grants=(
            GrantDetail("standing_art_kasumi_starbeat", 1, False, ""),
            GrantDetail("frame_s1_6star_character", 1, False, ""),
            GrantDetail("theme_s1_sailing", 1, False, ""),
        ),
    )
    data = pull_page_data(
        [result],
        _banner(),
        item_names={
            "frame_s1_6star_character": "扬帆六星角色头像框",
            "theme_s1_sailing": "扬帆主题",
        },
    )
    assert data.bonus_grants == ("扬帆六星角色头像框", "扬帆主题")
    assert data.pulls[0].is_new is True


def test_bonus_grants_fall_back_to_the_item_id_without_a_name():
    result = _result(
        "standing_art_kasumi_starbeat",
        "户山香澄 星之鼓动立绘",
        6,
        pity_after=0,
        grants=(
            GrantDetail("standing_art_kasumi_starbeat", 1, False, ""),
            GrantDetail("theme_s1_sailing", 1, False, ""),
        ),
    )
    data = pull_page_data([result], _banner())
    assert data.bonus_grants == ("theme_s1_sailing",)


def test_item_art_attaches_only_to_the_pulled_tile():
    results = [
        _result("standing_art_placeholder_r3_001", "占位角色立绘 3-1", 3),
        _result("standing_art_kasumi_starbeat", "户山香澄 星之鼓动立绘", 6, pity_after=0),
    ]
    data = pull_page_data(
        results, _banner(), item_art={"standing_art_kasumi_starbeat": KASUMI_ART}
    )
    assert data.pulls[0].image is None
    assert data.pulls[1].image == KASUMI_ART


def test_pull_render_module_never_touches_a_database():
    # No-DB rule: item names and art paths are injected by the handler; the
    # render module must not import inventory services or open a session.
    source = (ROOT / "plugins/gacha/render/pull.py").read_text(encoding="utf-8")
    assert "inventory.service" not in source
    assert "get_item" not in source
    assert "get_session" not in source
    assert "sqlalchemy" not in source


def test_bonus_line_renders_above_the_pity_counter():
    from plugins.gacha.render import pull_page
    from plugins.render.kits.kasumi import KasumiKit

    result = _result(
        "standing_art_kasumi_starbeat",
        "户山香澄 星之鼓动立绘",
        6,
        pity_after=0,
        grants=(
            GrantDetail("standing_art_kasumi_starbeat", 1, False, ""),
            GrantDetail("frame_s1_6star_character", 1, False, ""),
            GrantDetail("theme_s1_sailing", 1, False, ""),
        ),
    )
    data = pull_page_data(
        [result],
        _banner(),
        item_names={
            "frame_s1_6star_character": "扬帆六星角色头像框",
            "theme_s1_sailing": "扬帆主题",
        },
        item_art={"standing_art_kasumi_starbeat": KASUMI_ART},
    )
    page = pull_page(data, KasumiKit())
    texts = _collect_text(page.child)
    joined = " ".join(texts)
    assert "同时获得：扬帆六星角色头像框 · 扬帆主题" in joined
    assert joined.index("同时获得") < joined.index("保底计数")
    # And the page actually rasterizes with the art-bearing tile.
    image = page.render()
    assert image.size[0] == 864


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
