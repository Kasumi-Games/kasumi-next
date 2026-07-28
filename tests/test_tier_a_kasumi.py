import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import cards
from plugins.render import BaseKit
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits import KITS
from plugins.render.kits.kasumi import KasumiKit
from plugins.render.kits.kasumi.components import AVATAR_FRAME
from plugins.render.kits.kasumi.components import STANDING_ART
from plugins.render.kits.kasumi.components import sparkle
from plugins.render.kits.kasumi.components import frame_overlay

IDENTITY = PlayerIdentity(nickname="户山香澄", level=42)

PULLS = [
    PullRevealItem(
        name=f"占位卡面 {index + 1}",
        rarity=rarity,
        is_new=index % 3 == 0,
        featured=rarity == 6,
        note="盆栽 +120" if index == 1 else "",
    )
    for index, rarity in enumerate([3, 3, 4, 3, 5, 3, 4, 6, 3, 4])
]


class KasumiRegistrationTest(unittest.TestCase):
    def test_registered_in_kits(self) -> None:
        self.assertIs(KITS["kasumi"], KasumiKit)

    def test_all_three_tier_a_surfaces_are_bespoke(self) -> None:
        for surface in ("game_identity", "player_card", "pull_reveal"):
            with self.subTest(surface=surface):
                self.assertIsNot(
                    getattr(KasumiKit, surface), getattr(BaseKit, surface)
                )

    def test_standing_art_asset_exists(self) -> None:
        self.assertTrue(STANDING_ART.exists(), STANDING_ART)

    def test_starbeat_palette_is_light_not_near_black(self) -> None:
        """Shared colourful components should sit on an airy, light surface."""

        kit = KasumiKit()
        self.assertGreater(sum(kit.sky_top[:3]), 650)
        self.assertGreater(sum(kit.sky_bottom[:3]), 650)
        self.assertGreater(sum(kit.panel_fill[:3]), 700)
        self.assertLess(sum(kit.text_color[:3]), 260)


class KasumiSurfaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = KasumiKit()
        self.ctx = RenderContext()
        self.constraints = Constraints(max_width=cards.CONTENT_WIDTH, max_height=4000)

    def test_game_identity_dispatches_to_bespoke(self) -> None:
        strip = cards.game_identity(
            self.kit, IDENTITY, width=cards.CONTENT_WIDTH, detail="押注 120 Pt"
        )
        size = strip.measure(self.ctx, self.constraints)
        self.assertEqual(size.height, 78)  # the bespoke capsule, not generic 80

    def test_game_title_is_a_large_open_lockup_without_a_rule(self) -> None:
        title = self.kit.game_title(
            "一笔画",
            "普通 | 6/12 | 奖励 120/120",
            width=560,
            height=57,
        )
        self.assertEqual(_collect_text(title), ["普通 | 6/12 | 奖励 120/120", "一笔画"])
        size = title.measure(self.ctx, self.constraints)
        self.assertEqual(size.width, 720)
        self.assertEqual(size.height, 104)
        self.assertNotEqual(type(title).__name__, "KasumiPanel")
        self.assertNotIn("KitSeparator", _collect_component_type_names(title))
        subtitle = next(
            node
            for node in _collect_text_nodes(title)
            if getattr(node, "text", "") == "普通 | 6/12 | 奖励 120/120"
        )
        self.assertIsNone(subtitle.line_height)

    def test_game_identity_handles_missing_level_and_detail(self) -> None:
        strip = cards.game_identity(
            self.kit, PlayerIdentity(nickname="香"), width=cards.CONTENT_WIDTH
        )
        self.assertGreater(strip.measure(self.ctx, self.constraints).width, 0)

    def test_narrow_strip_drops_chip_then_detail_never_the_name(self) -> None:
        # Authoring guide §2.4: when the strip is too narrow, the level chip
        # goes first, then the detail — the nickname never collapses to "…".
        wide = _collect_text(
            cards.game_identity(
                self.kit, IDENTITY, width=cards.CONTENT_WIDTH, detail="押注 120 Pt"
            )
        )
        self.assertIn("户山香澄", wide)
        self.assertIn("Lv.42", wide)
        self.assertIn("押注 120 Pt", wide)

        squeezed = _collect_text(
            cards.game_identity(self.kit, IDENTITY, width=420, detail="押注 120 Pt")
        )
        self.assertIn("户山香澄", squeezed)
        self.assertNotIn("Lv.42", squeezed)
        self.assertIn("押注 120 Pt", squeezed)

        tiny = _collect_text(
            cards.game_identity(self.kit, IDENTITY, width=240, detail="押注 120 Pt")
        )
        self.assertIn("户山香澄", tiny)
        self.assertNotIn("Lv.42", tiny)
        self.assertNotIn("押注 120 Pt", tiny)

    def test_player_card_renders_with_and_without_description(self) -> None:
        for description in ("キラキラドキドキ！", ""):
            with self.subTest(description=bool(description)):
                card = cards.player_card(
                    self.kit, IDENTITY, current_pt=1240, description=description
                )
                size = card.measure(self.ctx, self.constraints)
                self.assertGreater(size.height, 0)

    def test_player_card_uses_equal_transparent_stat_frames_with_grey_rule(self) -> None:
        card = cards.player_card(
            self.kit,
            PlayerIdentity(nickname="新玩家", level=0),
            current_pt=0,
            description="",
        )
        texts = _collect_text(card)
        self.assertIn("Lv.0", texts)
        self.assertIn("0 Pt", texts)
        self.assertIn("KitSeparator", _collect_component_type_names(card))
        self.assertEqual(_count_component_type(card, "KitSeparator"), 1)
        # 外层资料卡 + 原有等级胶囊；没有新增的 Pt/等级实体小卡。
        self.assertEqual(_count_component_type(card, "KasumiPanel"), 2)
        self.assertNotIn("SparkleScatter", _collect_component_type_names(card))

    def test_pull_reveal_renders_one_and_ten(self) -> None:
        for count in (1, 10):
            with self.subTest(count=count):
                reveal = cards.pull_reveal(
                    self.kit, PULLS[:count], width=cards.INNER_WIDTH
                )
                self.assertGreater(
                    reveal.measure(self.ctx, self.constraints).height, 0
                )

    def test_pull_reveal_requires_concrete_width(self) -> None:
        from plugins.render.sizing import Fill

        with self.assertRaises(ValueError):
            self.kit.pull_reveal(PULLS[:1], width=Fill())

    def test_six_star_reveal_stays_in_the_light_starbeat_palette(self) -> None:
        top = self.kit._pull_tile(PULLS[7], 132, art_slot=False)
        self.assertGreater(sum(top.fill[:3]), 650)

    def test_pull_tiles_are_deterministic_across_processes(self) -> None:
        # The ★6 sparkle seed must come from a stable hash, not str.__hash__.
        source = Path(
            Path(__file__).resolve().parents[1],
            "plugins",
            "render",
            "kits",
            "kasumi",
            "kit.py",
        ).read_text(encoding="utf-8")
        self.assertNotIn("hash(pull.name)", source)
        self.assertIn("crc32", source)

    def test_full_page_renders(self) -> None:
        image = cards.response_card(
            self.kit,
            title="星之鼓动",
            body=cards.panel_section(
                self.kit, cards.pull_reveal(self.kit, PULLS, width=cards.INNER_WIDTH)
            ),
            owner_name="香澄",
        )
        self.assertEqual(image.width, cards.CONTENT_WIDTH + cards.PAGE_PADDING * 2)

    def test_mines_unrevealed_tile_uses_theme_ink(self) -> None:
        from plugins.mines.render.field import generate_unrevealed_field

        tile = generate_unrevealed_field(7, self.kit)
        text_nodes = _collect_text_nodes(tile)
        self.assertEqual(len(text_nodes), 1)
        self.assertEqual(text_nodes[0].color, (255, 255, 255, 255))

    def test_page_render_is_deterministic(self) -> None:
        def render():
            return cards.response_card(
                self.kit,
                title="确定性",
                body=cards.game_identity(self.kit, IDENTITY, width=cards.CONTENT_WIDTH),
            )

        self.assertEqual(render().tobytes(), render().tobytes())


class KasumiFrameTest(unittest.TestCase):
    def test_hand_drawn_asset_exists_and_is_spec_shaped(self) -> None:
        # The finished Kasumi frame now belongs to its inventory item.
        self.assertTrue(AVATAR_FRAME.exists())
        from PIL import Image

        asset = Image.open(AVATAR_FRAME)
        self.assertEqual(asset.size, (512, 512))
        self.assertEqual(asset.mode, "RGBA")

    def test_unequipped_kit_decoration_is_scaled(self) -> None:
        overlay = frame_overlay(84)
        expected = round(84 * 512 / 416)
        self.assertEqual(overlay.size, (expected, expected))
        self.assertGreater(overlay.getchannel("A").getextrema()[1], 0)

    def test_unequipped_kit_decoration_never_depends_on_item_art(self) -> None:
        overlay = frame_overlay(84)
        expected = round(84 * 512 / 416)
        self.assertEqual(overlay.size, (expected, expected))
        self.assertGreater(overlay.getchannel("A").getextrema()[1], 0)

    def test_frame_center_is_transparent_for_the_avatar(self) -> None:
        overlay = frame_overlay(84)
        center = overlay.size[0] // 2
        self.assertEqual(overlay.getpixel((center, center))[3], 0)

    def test_asset_preserves_the_face_safe_zone(self) -> None:
        # The final hand-drawn fringe may enter the forehead band, but the
        # central 96×112 face window beneath it must stay fully clear.
        from PIL import Image

        asset = Image.open(AVATAR_FRAME).convert("RGBA")
        alpha = asset.getchannel("A")
        face_safe_zone = alpha.crop((208, 240, 304, 352))
        self.assertEqual(
            face_safe_zone.getextrema(),
            (0, 0),
            "avatar-frame art overlaps the central face-safe window",
        )

    def test_sparkle_helper_produces_requested_size(self) -> None:
        color = (255, 214, 150, 255)
        glint = sparkle(24, color)
        self.assertEqual(glint.size, (24, 24))
        # Transparent pixels retain the glint colour rather than black RGB, so
        # resampling them for a halo cannot produce a dirty dark fringe.
        self.assertEqual(glint.getpixel((0, 0))[:3], color[:3])


class KasumiCatalogTest(unittest.TestCase):
    def test_theme_item_maps_to_the_kit(self) -> None:
        from utils import theming

        theming.invalidate_catalog()
        info = theming.all_themes().get("kasumi")
        self.assertIsNotNone(info)
        self.assertEqual(info.item_id, "theme_kasumi_starbeat")

    def test_theme_resolves_from_player_tokens(self) -> None:
        from utils import theming

        for token in ("香澄", "kasumi", "星之鼓动", "theme_kasumi_starbeat"):
            with self.subTest(token=token):
                info = theming.theme_by_token(token)
                self.assertIsNotNone(info, token)
                self.assertEqual(info.kit_name, "kasumi")

    def test_signature_is_suppressed_for_starbeat(self) -> None:
        self.assertIsNone(cards.signature_for(KasumiKit(), "香澄"))
        self.assertIsNone(cards.signature_for(KasumiKit()))


def _collect_text(component) -> list[str]:
    texts = []
    stack = [component]
    while stack:
        node = stack.pop()
        text = getattr(node, "text", None)
        if isinstance(text, str):
            texts.append(text)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                stack.append(value)
    return texts


def _collect_text_nodes(component) -> list[object]:
    nodes: list[object] = []
    stack = [component]
    while stack:
        node = stack.pop()
        if isinstance(getattr(node, "text", None), str):
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


def _collect_component_type_names(component) -> set[str]:
    names: set[str] = set()
    stack = [component]
    while stack:
        node = stack.pop()
        names.add(type(node).__name__)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                stack.append(value)
    return names


def _count_component_type(component, name: str) -> int:
    count = 0
    stack = [component]
    while stack:
        node = stack.pop()
        count += type(node).__name__ == name
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                stack.append(value)
    return count


if __name__ == "__main__":
    unittest.main()
