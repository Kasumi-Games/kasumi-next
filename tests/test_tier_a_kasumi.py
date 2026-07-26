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
        # The asset is generated by scripts/draw_kasumi_frame.py per
        # docs/design/avatar-frame-spec.md: 512 canvas, RGBA.
        self.assertTrue(AVATAR_FRAME.exists())
        from PIL import Image

        asset = Image.open(AVATAR_FRAME)
        self.assertEqual(asset.size, (512, 512))
        self.assertEqual(asset.mode, "RGBA")

    def test_asset_is_used_and_scaled(self) -> None:
        overlay = frame_overlay(84)
        expected = round(84 * 512 / 416)
        self.assertEqual(overlay.size, (expected, expected))
        self.assertGreater(overlay.getchannel("A").getextrema()[1], 0)

    def test_placeholder_still_carries_when_asset_missing(self) -> None:
        # The drop-in contract cuts both ways: removing the asset must fall
        # back to the code-drawn placeholder, never crash.
        from unittest import mock

        from plugins.render.kits.kasumi import components

        missing = components.FRAMES_DIR / "definitely_missing.png"
        with mock.patch.object(components, "AVATAR_FRAME", missing):
            overlay = components.frame_overlay(84)
        expected = round(84 * 512 / 416)
        self.assertEqual(overlay.size, (expected, expected))
        self.assertGreater(overlay.getchannel("A").getextrema()[1], 0)

    def test_frame_center_is_transparent_for_the_avatar(self) -> None:
        overlay = frame_overlay(84)
        center = overlay.size[0] // 2
        self.assertEqual(overlay.getpixel((center, center))[3], 0)

    def test_asset_respects_the_intrusion_allowance(self) -> None:
        # No opaque pixel may sit deeper than the spec's decoration allowance
        # (48px at 512 scale) inside the avatar circle.
        from PIL import Image

        asset = Image.open(AVATAR_FRAME).convert("RGBA")
        alpha = asset.getchannel("A")
        center = 256
        avatar_radius = 208
        allowance = 48
        limit = avatar_radius - allowance
        for x in range(0, 512, 4):
            for y in range(0, 512, 4):
                if alpha.getpixel((x, y)) > 8:
                    distance = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
                    self.assertGreaterEqual(
                        distance,
                        limit,
                        f"opaque pixel at ({x},{y}) is {avatar_radius - distance:.0f}px inside the circle",
                    )

    def test_sparkle_helper_produces_requested_size(self) -> None:
        glint = sparkle(24, (255, 214, 150, 255))
        self.assertEqual(glint.size, (24, 24))


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

    def test_signature_reads_display_name_not_item_name(self) -> None:
        signature = cards.signature_for(KasumiKit(), "香澄")
        self.assertIsNotNone(signature)
        # The credit line must read 「…主题 · 星之鼓动」, never the redundant
        # 「…主题 · 星之鼓动主题」 the item name would produce.
        joined = " ".join(_collect_text(signature))
        self.assertIn("星之鼓动", joined)
        self.assertNotIn("星之鼓动主题", joined)


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


if __name__ == "__main__":
    unittest.main()
