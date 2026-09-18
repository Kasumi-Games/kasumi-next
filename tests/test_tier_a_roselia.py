import sys
import json
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import cards
from plugins.render import Page
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import BaseKit
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits import KITS
from plugins.render.kits.roselia import RoseliaKit
from plugins.render.kits.roselia.components import RULE
from plugins.render.kits.roselia.components import BODY_FONT
from plugins.render.kits.roselia.components import DISPLAY_FONT
from plugins.render.kits.roselia.components import RoseliaPanel
from plugins.render.kits.roselia.components import RoseliaTitle
from plugins.render.kits.roselia.components import rose_crest
from plugins.render.kits.roselia.components import frame_overlay

IDENTITY = PlayerIdentity(nickname="凑友希那", level=42)
PULLS = [
    PullRevealItem(
        name=f"蔷薇收藏 {index + 1}",
        rarity=rarity,
        is_new=index % 3 == 0,
        featured=rarity == 6,
        note="盆栽 +120" if index == 1 else "",
    )
    for index, rarity in enumerate((3, 3, 4, 3, 5, 3, 4, 6, 3, 4))
]


class RoseliaRegistrationTest(unittest.TestCase):
    def test_registered_with_all_tier_a_surfaces(self) -> None:
        self.assertIs(KITS["roselia"], RoseliaKit)
        self.assertTrue(issubclass(RoseliaKit, BaseKit))
        for surface in ("game_identity", "player_card", "pull_reveal"):
            with self.subTest(surface=surface):
                self.assertIsNot(
                    getattr(RoseliaKit, surface), getattr(BaseKit, surface)
                )

    def test_palette_has_complete_rgba_channels(self) -> None:
        kit = RoseliaKit()
        for name in (
            "background_top",
            "background_bottom",
            "text_color",
            "muted_text_color",
            "panel_fill",
            "primary",
            "rose",
            "accent",
            "glass",
            "rule",
        ):
            self.assertEqual(len(getattr(kit, name)), 4, name)

    def test_font_assets_and_manifest_are_self_contained(self) -> None:
        self.assertTrue(BODY_FONT.exists())
        self.assertTrue(DISPLAY_FONT.exists())
        manifest_path = BODY_FONT.parents[1] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["assets"]), 2)
        self.assertTrue(all(asset["license"] == "SIL OFL 1.1" for asset in manifest["assets"]))

    def test_atom_defaults_preserve_explicit_zero_values(self) -> None:
        kit = RoseliaKit()
        transparent = (0, 0, 0, 0)
        self.assertEqual(kit.text("x", color=transparent).color, transparent)
        panel = kit.panel(fill=transparent, radius=0)
        self.assertEqual(panel.fill, transparent)
        self.assertEqual(panel.radius, 0)

    def test_compact_panels_keep_outer_rule_but_drop_inner_rule(self) -> None:
        kit = RoseliaKit()
        for width, height in ((120, 120), (720, 20), (20, 22)):
            with self.subTest(size=(width, height)):
                panel = kit.panel(
                    width=Fixed(width),
                    height=Fixed(height),
                    ornate=False,
                )
                image = Page(size=(width, height), child=panel).render(
                    RenderContext(pixel_ratio=1)
                )
                self.assertEqual(image.getpixel((1, height // 2)), kit.primary)
                self.assertNotEqual(image.getpixel((6, height // 2)), RULE)


class RoseliaSurfaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = RoseliaKit()
        self.ctx = RenderContext(pixel_ratio=1)
        self.constraints = Constraints(max_width=784, max_height=4000)

    def test_game_identity_measures_at_all_contract_widths(self) -> None:
        for width in (200, 240, 420, 720):
            with self.subTest(width=width):
                component = cards.game_identity(
                    self.kit, IDENTITY, width=width, detail="押注 120 Pt"
                )
                size = component.measure(
                    self.ctx, Constraints(max_width=width, max_height=200)
                )
                self.assertEqual((size.width, size.height), (width, 80))

    def test_game_identity_drops_level_then_detail(self) -> None:
        wide = _collect_text(
            cards.game_identity(
                self.kit, IDENTITY, width=720, detail="押注 120 Pt"
            )
        )
        medium = _collect_text(
            cards.game_identity(
                self.kit, IDENTITY, width=420, detail="押注 120 Pt"
            )
        )
        tiny = _collect_text(
            cards.game_identity(
                self.kit, IDENTITY, width=200, detail="押注 120 Pt"
            )
        )
        self.assertIn("Lv.42", wide)
        self.assertIn("押注 120 Pt", wide)
        self.assertNotIn("Lv.42", medium)
        self.assertIn("押注 120 Pt", medium)
        self.assertEqual(tiny, ["凑友希那"])

    def test_player_card_handles_empty_assets_and_copy(self) -> None:
        for description in ("一同前往更高处。", ""):
            with self.subTest(description=description):
                card = cards.player_card(
                    self.kit,
                    PlayerIdentity(nickname="新玩家", level=0),
                    current_pt=0,
                    description=description,
                )
                size = card.measure(self.ctx, self.constraints)
                self.assertEqual((size.width, size.height), (784, 420))
                self.assertIn(
                    description or "这个人还没有写简介。", _collect_text(card)
                )

    def test_player_card_drops_standing_art_on_narrow_width(self) -> None:
        art = Image.new("RGBA", (100, 300), (80, 40, 120, 255))
        card = self.kit.player_card(
            avatar_image=None,
            frame_image=None,
            title1_image=None,
            title2_image=None,
            nickname="凑友希那",
            level=42,
            current_pt=2350,
            description="",
            standing_art=art,
            width=Fixed(420),
            height=Fixed(420),
        )
        self.assertFalse(
            any(getattr(node, "source", None) is art for node in _walk(card))
        )

    def test_pull_reveal_renders_every_count_and_narrow_mode(self) -> None:
        for count in range(1, 11):
            with self.subTest(count=count):
                reveal = cards.pull_reveal(
                    self.kit, PULLS[:count], width=cards.INNER_WIDTH
                )
                self.assertGreater(
                    reveal.measure(self.ctx, self.constraints).height, 0
                )
        narrow = self.kit.pull_reveal(PULLS, width=Fixed(200))
        self.assertEqual(narrow.child.columns, 1)

    def test_reveal_tiles_use_fixed_equal_height_tracks(self) -> None:
        reveal = self.kit.pull_reveal(PULLS, width=Fixed(cards.INNER_WIDTH))
        grid = reveal.child
        self.assertIsInstance(grid.row_track, Fixed)
        self.assertEqual({child.height.value for child in grid.children}, {360})

    def test_six_star_has_structural_not_only_colour_upgrade(self) -> None:
        ordinary = self.kit._pull_tile(PULLS[0], 134, tile_height=360)
        rare = self.kit._pull_tile(PULLS[7], 134, tile_height=360)
        self.assertIsInstance(ordinary, RoseliaPanel)
        self.assertEqual(ordinary.outer_width, 1)
        self.assertEqual(ordinary.inner_width, 0)
        self.assertEqual(rare.outer_width, 3)
        self.assertEqual(rare.inner_width, 1)
        self.assertIn("PetalScatter", _collect_component_type_names(rare))
        self.assertIn("RoseCrest", _collect_component_type_names(rare))

    def test_single_pull_name_reserves_full_serif_line_height(self) -> None:
        tile = self.kit._pull_tile(
            PULLS[7],
            cards.INNER_WIDTH,
            tile_height=310,
            hero=True,
        )
        name = next(
            node
            for node in _collect_text_nodes(tile)
            if node.text == PULLS[7].name
        )
        self.assertGreaterEqual(name.line_height, 38)

    def test_roselia_text_centres_glyphs_inside_fixed_height_pills(self) -> None:
        text = self.kit.text("Kasumi - 共 1 + ? 点", font_size=36)
        self.assertTrue(text.center_glyphs_in_line)

    def test_blackjack_hand_label_shrinks_instead_of_ellipsizing(self) -> None:
        from plugins.blackjack.render import BlackjackRenderer

        renderer = object.__new__(BlackjackRenderer)
        renderer.kit = self.kit
        label = renderer._hand_label(
            "Kasumi", "共 1 + ? 点", (255, 85, 34, 255)
        )
        text = next(
            node
            for node in _collect_text_nodes(label)
            if node.text.startswith("Kasumi")
        )
        self.assertFalse(text.wrap)
        self.assertEqual(text.overflow, "shrink")

    def test_one_stroke_uses_roselia_game_title_on_board_and_leaderboard(self) -> None:
        from plugins.one_stroke.render import graph
        from plugins.one_stroke.render import leaderboard

        board_title = graph._title_bar(
            self.kit,
            "一笔画",
            "普通 | 6/12 | 奖励 120/120",
            width=560,
            height=57,
        )
        rank_title = leaderboard._title_bar(
            self.kit,
            "一笔画",
            "竞速排行榜",
            width=420,
            height=57,
        )
        self.assertIsInstance(board_title, RoseliaTitle)
        self.assertIsInstance(rank_title, RoseliaTitle)

    def test_all_required_tile_text_starts_at_22px_or_larger(self) -> None:
        tile = self.kit._pull_tile(PULLS[7], 134, tile_height=360)
        for node in _collect_text_nodes(tile):
            self.assertGreaterEqual(node.font_size, 22)

    def test_same_inputs_render_identically_at_one_and_two_x(self) -> None:
        component = cards.pull_reveal(
            self.kit, PULLS, width=cards.INNER_WIDTH
        )
        for ratio in (1, 2):
            with self.subTest(ratio=ratio):
                def render():
                    return Page(
                        size=(720, 680),
                        background=self.kit.background(),
                        child=Frame(
                            component,
                            width=Fixed(720),
                            height=Fixed(680),
                            align_y="start",
                        ),
                    ).render(RenderContext(pixel_ratio=ratio))

                first = render()
                second = render()
                self.assertEqual(first.size, (720, 680))
                self.assertEqual(first.tobytes(), second.tobytes())

    def test_randomness_uses_crc32_not_python_hash(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "plugins/render/kits/roselia/kit.py"
        ).read_text(encoding="utf-8")
        self.assertIn("crc32", source)
        self.assertNotIn("hash(pull.name)", source)


class RoseliaAssetTest(unittest.TestCase):
    def test_rose_crest_is_cached_and_has_alpha(self) -> None:
        first = rose_crest(32)
        second = rose_crest(32)
        self.assertIs(first, second)
        self.assertEqual(first.size, (32, 32))
        self.assertGreater(first.getchannel("A").getextrema()[1], 0)

    def test_unequipped_frame_respects_avatar_contract(self) -> None:
        overlay = frame_overlay(84)
        expected = round(84 * 512 / 416)
        self.assertEqual(overlay.size, (expected, expected))
        centre = expected // 2
        self.assertEqual(overlay.getpixel((centre, centre))[3], 0)


class RoseliaCatalogTest(unittest.TestCase):
    def test_theme_resolves_from_all_player_tokens(self) -> None:
        from utils import theming

        theming.invalidate_catalog()
        for token in ("roselia", "ロゼリア", "蔷薇穹庭", "theme_roselia"):
            with self.subTest(token=token):
                info = theming.theme_by_token(token)
                self.assertIsNotNone(info, token)
                self.assertEqual(info.kit_name, "roselia")


def _collect_text(component) -> list[str]:
    return [node.text for node in _collect_text_nodes(component)]


def _collect_text_nodes(component) -> list[object]:
    return [node for node in _walk(component) if isinstance(getattr(node, "text", None), str)]


def _collect_component_type_names(component) -> set[str]:
    return {type(node).__name__ for node in _walk(component)}


def _walk(component) -> list[object]:
    nodes: list[object] = []
    stack = [component]
    while stack:
        node = stack.pop()
        nodes.append(node)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                stack.append(value)
    return nodes


if __name__ == "__main__":
    unittest.main()
