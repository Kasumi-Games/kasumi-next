"""Art-bearing reveal tiles: uniform tile heights across mixed batches.

The rule under test: when any pull in a batch carries art, every tile in that
batch reserves the art slot and all tiles share one (taller) height; a batch
with no art keeps the exact pre-art tile height so existing surfaces do not
shift.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import cards
from plugins.render import PullRevealItem
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits import MinimalKit
from plugins.render.kits.kasumi import KasumiKit
from plugins.render.kits.bangdream import BanGDreamKit

ROOT = Path(__file__).resolve().parents[1]
KASUMI_ART = (
    ROOT
    / "plugins/render/kits/kasumi/resources/standing/kasumi_starry_after_training.png"
)

RARITIES = [3, 3, 4, 3, 5, 3, 4, 6, 3, 4]


def _mixed_pulls() -> list[PullRevealItem]:
    """A ten-pull where only the ★6 carries art."""

    return [
        PullRevealItem(
            name="户山香澄 抬头看，星星在跳动立绘" if rarity == 6 else f"占位卡面 {index + 1}",
            rarity=rarity,
            is_new=rarity == 6,
            featured=rarity == 6,
            image=KASUMI_ART if rarity == 6 else None,
            note="盆栽 +120" if index == 1 else "",
        )
        for index, rarity in enumerate(RARITIES)
    ]


def _plain_pulls() -> list[PullRevealItem]:
    return [
        PullRevealItem(name=f"占位卡面 {index + 1}", rarity=rarity)
        for index, rarity in enumerate(RARITIES)
    ]


class ArtAssetTest(unittest.TestCase):
    def test_the_kasumi_standing_art_exists(self) -> None:
        self.assertTrue(KASUMI_ART.exists(), KASUMI_ART)


class KasumiArtTileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = KasumiKit()
        self.ctx = RenderContext()
        self.constraints = Constraints(max_width=800, max_height=4000)

    def _tile_heights(self, pulls, *, art_slot: bool) -> set[int]:
        return {
            self.kit._pull_tile(pull, 134, art_slot=art_slot)
            .measure(self.ctx, self.constraints)
            .height
            for pull in pulls
        }

    def test_mixed_batch_tiles_share_one_height(self) -> None:
        heights = self._tile_heights(_mixed_pulls(), art_slot=True)
        self.assertEqual(len(heights), 1, heights)
        # Modern roster tickets reserve one portrait stage in every state.
        self.assertEqual(heights, {317})

    def test_art_less_batch_keeps_the_plain_height(self) -> None:
        self.assertEqual(self._tile_heights(_plain_pulls(), art_slot=False), {317})

    def test_reveal_grid_with_art_renders(self) -> None:
        image = cards.response_card(
            self.kit,
            title="星之鼓动 限定卡池",
            body=cards.panel_section(
                self.kit,
                cards.pull_reveal(self.kit, _mixed_pulls(), width=cards.INNER_WIDTH),
            ),
        )
        self.assertEqual(image.width, cards.CONTENT_WIDTH + cards.PAGE_PADDING * 2)

    def test_art_and_placeholder_batches_share_the_ticket_height(self) -> None:
        reveal_with_art = cards.pull_reveal(
            self.kit, _mixed_pulls(), width=cards.INNER_WIDTH
        )
        reveal_plain = cards.pull_reveal(
            self.kit, _plain_pulls(), width=cards.INNER_WIDTH
        )
        with_art = reveal_with_art.measure(self.ctx, self.constraints).height
        plain = reveal_plain.measure(self.ctx, self.constraints).height
        self.assertEqual(with_art, plain)

    def test_narrow_tile_keeps_new_over_pick_up(self) -> None:
        # 「NEW · PICK UP」 cannot fit a ten-pull tile; the tile must keep the
        # NEW marker (told nowhere else) instead of an ellipsis. On a wide
        # single-pull tile both markers stay.
        featured = next(pull for pull in _mixed_pulls() if pull.rarity == 6)
        narrow = _collect_text(self.kit._pull_tile(featured, 134, art_slot=True))
        self.assertIn("NEW", narrow)
        self.assertNotIn("NEW / PICK UP", narrow)
        wide = _collect_text(self.kit._pull_tile(featured, 720, art_slot=True))
        self.assertIn("NEW / PICK UP", wide)

    def test_wide_and_compact_tiles_use_only_one_rarity_notation(self) -> None:
        featured = next(pull for pull in _mixed_pulls() if pull.rarity == 6)
        wide = _collect_text(self.kit._pull_tile(featured, 300, art_slot=True))
        self.assertIn("★★★★★★", wide)
        self.assertNotIn("6★", wide)
        self.assertNotIn("★6", wide)

        compact = _collect_text(self.kit._pull_tile(featured, 130, art_slot=True))
        self.assertIn("6★", compact)
        self.assertNotIn("★★★★★★", compact)
        self.assertNotIn("★6", compact)

    def test_single_pull_sparkles_are_a_quiet_effect_layer(self) -> None:
        from plugins.render.kits.kasumi.components import SparkleScatter

        featured = next(pull for pull in _mixed_pulls() if pull.rarity == 6)
        tile = self.kit._pull_tile(featured, 300, art_slot=True)
        sparkle_layers = _collect_types(tile, SparkleScatter)
        self.assertEqual(len(sparkle_layers), 1)
        self.assertLessEqual(sparkle_layers[0].opacity, 0.35)


class BanGDreamArtTileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = BanGDreamKit()
        self.ctx = RenderContext()
        self.constraints = Constraints(max_width=800, max_height=4000)

    def test_mixed_batch_tiles_share_one_height(self) -> None:
        # 220 base + 96 art slot + one extra 6px row gap.
        heights = {
            self.kit._pull_tile(pull, 134, 322, seed=index, art_slot=True)
            .measure(self.ctx, self.constraints)
            .height
            for index, pull in enumerate(_mixed_pulls())
        }
        self.assertEqual(heights, {322})

    def test_art_less_batch_keeps_the_original_height(self) -> None:
        heights = {
            self.kit._pull_tile(pull, 134, 220, seed=index, art_slot=False)
            .measure(self.ctx, self.constraints)
            .height
            for index, pull in enumerate(_plain_pulls())
        }
        self.assertEqual(heights, {220})

    def test_reveal_grid_with_art_renders(self) -> None:
        image = cards.response_card(
            self.kit,
            title="星之鼓动 限定卡池",
            body=cards.panel_section(
                self.kit,
                cards.pull_reveal(self.kit, _mixed_pulls(), width=cards.INNER_WIDTH),
            ),
        )
        self.assertEqual(image.width, cards.CONTENT_WIDTH + cards.PAGE_PADDING * 2)


class GenericArtTileTest(unittest.TestCase):
    """The shared fallback tile, exercised through a kit with no bespoke grid."""

    def setUp(self) -> None:
        self.kit = MinimalKit()
        self.ctx = RenderContext()
        self.constraints = Constraints(max_width=800, max_height=4000)

    def _tile_heights(self, pulls, *, art_slot: bool) -> set[int]:
        return {
            cards._reveal_tile(self.kit, pull, 134, art_slot=art_slot)
            .measure(self.ctx, self.constraints)
            .height
            for pull in pulls
        }

    def test_mixed_batch_tiles_share_one_height(self) -> None:
        heights = self._tile_heights(_mixed_pulls(), art_slot=True)
        self.assertEqual(len(heights), 1, heights)
        # 196 base + 96 art slot + one extra 8px row gap.
        self.assertEqual(heights, {300})

    def test_art_less_batch_keeps_the_original_height(self) -> None:
        self.assertEqual(self._tile_heights(_plain_pulls(), art_slot=False), {196})

    def test_reveal_grid_with_art_renders(self) -> None:
        image = cards.response_card(
            self.kit,
            title="星之鼓动 限定卡池",
            body=cards.panel_section(
                self.kit,
                cards.pull_reveal(self.kit, _mixed_pulls(), width=cards.INNER_WIDTH),
            ),
        )
        self.assertEqual(image.width, cards.CONTENT_WIDTH + cards.PAGE_PADDING * 2)

    def test_narrow_tile_keeps_new_over_pick_up(self) -> None:
        # Same policy as the bespoke kits: on a ten-pull tile too narrow for
        # 「NEW · PICK UP」 the generic tile keeps NEW instead of ellipsizing
        # into a dangling 「NEW · …」. A wide single-pull tile keeps both.
        featured = next(pull for pull in _mixed_pulls() if pull.rarity == 6)
        narrow = _collect_text(cards._reveal_tile(self.kit, featured, 134, art_slot=True))
        self.assertIn("NEW", narrow)
        self.assertNotIn("NEW · PICK UP", narrow)
        wide = _collect_text(cards._reveal_tile(self.kit, featured, 720, art_slot=True))
        self.assertIn("NEW · PICK UP", wide)


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


def _collect_types(component, expected_type):
    found = []

    def visit(node) -> None:
        if isinstance(node, expected_type):
            found.append(node)
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
    return found


if __name__ == "__main__":
    unittest.main()
