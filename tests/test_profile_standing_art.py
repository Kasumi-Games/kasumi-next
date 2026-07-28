"""Equipped standing art (立绘) on the profile card.

Pulled 立绘 are now displayable: when a player equips a ``standing_art``
cosmetic whose item carries ``metadata.art``, the profile page renders that
art in a sibling Frame beside the identity panel. The dispatcher still
supports explicit art for other player-card callers, while ``None`` keeps
the identity card art-free. The Kasumi theme's built-in default is selected
at the profile-page layer.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from utils import cards
from plugins.render import BaseKit
from plugins.render import PlayerIdentity
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits import MangaKit
from plugins.render.kits import MinimalKit
from plugins.inventory.render import ProfileData
from plugins.inventory.render import profile_page
from plugins.render.kits.kasumi import KasumiKit
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.kasumi.components import STANDING_ART

ROOT = Path(__file__).resolve().parents[1]

#: A real, existing art asset that is NOT the kasumi kit's built-in default.
CUSTOM_ART = (
    ROOT
    / "plugins"
    / "render"
    / "kits"
    / "kasumi"
    / "resources"
    / "standing"
    / "kasumi_starry_normal.png"
)
FRAME_ART = (
    ROOT
    / "plugins"
    / "inventory"
    / "resources"
    / "items"
    / "avatar_frames"
    / "frame_kasumi_starbeat.png"
)

IDENTITY = PlayerIdentity(nickname="香澄", level=24)


def _image_sources(component) -> list:
    """Collect every image ``source`` in a component tree."""

    sources = []
    stack = [component]
    while stack:
        node = stack.pop()
        source = getattr(node, "source", None)
        if source is not None:
            sources.append(source)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                stack.append(value)
    return sources


def _data(**overrides) -> ProfileData:
    defaults = dict(
        identity=IDENTITY,
        current_pt=1234,
        description="要一起组乐队吗？",
        star_stickers=56,
        bonsai=7,
        season_name="2026 第一赛季",
        season_rank=3,
        equipped=(("立绘", "户山香澄 抬头看，星星在跳动"),),
    )
    defaults.update(overrides)
    return ProfileData(**defaults)


def test_custom_art_asset_exists() -> None:
    assert CUSTOM_ART.exists()
    assert CUSTOM_ART != STANDING_ART


# ---------------------------------------------------------------------------
# Kasumi bespoke: the identity card is art-free unless explicitly supplied
# ---------------------------------------------------------------------------


def test_kasumi_identity_card_is_art_free_by_default() -> None:
    card = cards.player_card(KasumiKit(), IDENTITY, current_pt=100)
    sources = _image_sources(card)
    assert STANDING_ART not in sources
    assert CUSTOM_ART not in sources


def test_kasumi_explicit_standing_art_wins_over_the_default() -> None:
    card = cards.player_card(
        KasumiKit(), IDENTITY, current_pt=100, standing_art=CUSTOM_ART
    )
    sources = _image_sources(card)
    assert CUSTOM_ART in sources
    assert STANDING_ART not in sources


# ---------------------------------------------------------------------------
# BanG Dream! bespoke: conditional right column, no reflow
# ---------------------------------------------------------------------------


def test_bangdream_has_no_art_column_without_standing_art() -> None:
    card = cards.player_card(BanGDreamKit(), IDENTITY, current_pt=100)
    assert CUSTOM_ART not in _image_sources(card)


def test_bangdream_gains_the_art_column_with_standing_art() -> None:
    card = cards.player_card(
        BanGDreamKit(), IDENTITY, current_pt=100, standing_art=CUSTOM_ART
    )
    assert CUSTOM_ART in _image_sources(card)


def test_bangdream_card_canvas_is_identical_with_and_without_art() -> None:
    # The card designs against a fixed canvas; the art column must never
    # change the card's outer size (no reflow at the page level).
    ctx = RenderContext()
    constraints = Constraints(max_width=cards.CONTENT_WIDTH, max_height=4000)
    kit = BanGDreamKit()
    plain = cards.player_card(kit, IDENTITY, current_pt=100)
    with_art = cards.player_card(
        kit, IDENTITY, current_pt=100, standing_art=CUSTOM_ART
    )
    assert plain.measure(ctx, constraints) == with_art.measure(ctx, constraints)


# ---------------------------------------------------------------------------
# Generic fallback: same conditional column
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kit_cls", [MangaKit, MinimalKit])
def test_generic_fallback_adds_art_only_when_provided(kit_cls) -> None:
    kit = kit_cls()
    plain = cards.player_card(kit, IDENTITY, current_pt=100)
    with_art = cards.player_card(
        kit, IDENTITY, current_pt=100, standing_art=CUSTOM_ART
    )
    assert CUSTOM_ART not in _image_sources(plain)
    assert CUSTOM_ART in _image_sources(with_art)


# ---------------------------------------------------------------------------
# The profile page end to end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kit_cls", [BanGDreamKit, KasumiKit, MangaKit])
def test_profile_page_renders_the_equipped_art(kit_cls) -> None:
    page = profile_page(_data(standing_art=CUSTOM_ART), kit_cls())
    assert CUSTOM_ART in _image_sources(page.child)
    image = page.render()
    assert image.size[0] == 864
    assert image.size[1] > 0


def test_profile_page_without_art_keeps_the_art_less_card() -> None:
    page = profile_page(_data(), MangaKit())
    assert CUSTOM_ART not in _image_sources(page.child)
    assert page.render().size[0] == 864


def test_kasumi_profile_uses_default_art_in_a_separate_frame() -> None:
    from plugins.inventory.render.profile import _profile_showcase
    from plugins.render import Frame
    from plugins.render import HStack

    showcase = _profile_showcase(KasumiKit(), _data())
    assert isinstance(showcase, HStack)
    assert len(showcase.children) == 2
    assert isinstance(showcase.children[1], Frame)
    assert STANDING_ART in _image_sources(showcase.children[1])
    assert STANDING_ART not in _image_sources(showcase.children[0])


@pytest.mark.parametrize("kit_cls", [BanGDreamKit, KasumiKit])
def test_profile_page_renders_the_equipped_avatar_frame(kit_cls) -> None:
    page = profile_page(_data(avatar_frame=FRAME_ART), kit_cls())
    assert FRAME_ART in _image_sources(page.child)
    assert page.render().size[0] == 864


def test_profile_page_with_art_renders_deterministically() -> None:
    def render():
        return profile_page(
            _data(standing_art=CUSTOM_ART), BanGDreamKit()
        ).render()

    assert render().tobytes() == render().tobytes()


# ---------------------------------------------------------------------------
# Assembly degradation: items without metadata.art degrade to no art
# ---------------------------------------------------------------------------


@pytest.fixture
def inventory_db(sqlite_session):
    from plugins.inventory import database
    from plugins.inventory.models import Base

    return sqlite_session(database, Base)


def _seed_art_item(session, item_id: str, metadata_json: str) -> None:
    from plugins.inventory import models

    session.add(
        models.Item(
            item_id=item_id,
            category="cosmetic",
            name=item_id,
            stackable=False,
            visible=True,
            sort_order=0,
            metadata_json=metadata_json,
        )
    )
    session.add(
        models.CosmeticItem(item_id=item_id, cosmetic_type="standing_art", rarity=5)
    )
    session.commit()


def test_no_equipped_item_yields_no_art(inventory_db) -> None:
    import plugins.inventory as inventory

    assert inventory._equipped_cosmetic_art(None) is None
    assert inventory._equipped_cosmetic_art("") is None


def test_unknown_item_yields_no_art(inventory_db) -> None:
    import plugins.inventory as inventory

    assert inventory._equipped_cosmetic_art("ghost_item") is None


def test_item_without_art_metadata_degrades_to_no_art(inventory_db) -> None:
    # The placeholder standing arts ship without metadata.art; equipping one
    # must keep the profile card art-less rather than crash.
    import plugins.inventory as inventory

    _seed_art_item(inventory_db, "art_no_metadata", "{}")
    assert inventory._equipped_cosmetic_art("art_no_metadata") is None


def test_missing_art_file_degrades_to_no_art(inventory_db) -> None:
    import plugins.inventory as inventory

    _seed_art_item(
        inventory_db, "art_missing_file", '{"art": "does/not/exist.png"}'
    )
    assert inventory._equipped_cosmetic_art("art_missing_file") is None


def test_repo_relative_art_path_resolves_to_the_asset(inventory_db) -> None:
    import plugins.inventory as inventory

    relative = CUSTOM_ART.relative_to(ROOT).as_posix()
    _seed_art_item(inventory_db, "art_real", f'{{"art": "{relative}"}}')
    assert inventory._equipped_cosmetic_art("art_real") == CUSTOM_ART


# ---------------------------------------------------------------------------
# The authoring doc stays accurate
# ---------------------------------------------------------------------------


def test_authoring_doc_documents_the_standing_art_contract() -> None:
    doc = (ROOT / "docs" / "design" / "tier-a-authoring.md").read_text(
        encoding="utf-8"
    )
    # The documented signature carries the dispatcher-threaded keyword...
    assert "standing_art: ImageSource | None = None" in doc
    # ...and the doc's claims match the code: BaseKit's signature is
    # unchanged, while the dispatcher and every bespoke kit accept the
    # keyword with a None default.
    assert (
        "standing_art"
        not in inspect.signature(BaseKit.player_card).parameters
    )
    dispatcher = inspect.signature(cards.player_card).parameters["standing_art"]
    assert dispatcher.default is None
    for kit_cls in (KasumiKit, BanGDreamKit):
        parameter = inspect.signature(kit_cls.player_card).parameters[
            "standing_art"
        ]
        assert parameter.default is None, kit_cls
