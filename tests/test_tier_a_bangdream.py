import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from utils import cards
from plugins.render import Insets
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits.bangdream import BanGDreamKit

RARITIES = [3, 3, 4, 3, 5, 3, 4, 6, 3, 4]


def _identity(**overrides) -> PlayerIdentity:
    values = {"nickname": "户山香澄", "level": 42, "avatar": None}
    values.update(overrides)
    return PlayerIdentity(**values)


def _pulls(count: int) -> list[PullRevealItem]:
    return [
        PullRevealItem(
            name=f"占位卡面 {index + 1}",
            rarity=RARITIES[index % len(RARITIES)],
            is_new=index % 3 == 0,
            featured=RARITIES[index % len(RARITIES)] == 6,
            note="盆栽 +120" if index == 1 else "",
        )
        for index in range(count)
    ]


def _render(kit: BanGDreamKit, component) -> Image.Image:
    return AutoPage(
        component, background=kit.background(), padding=Insets.all(40)
    ).render()


class DispatchTest(unittest.TestCase):
    """The dispatcher must route BanGDreamKit to the bespoke implementations."""

    def test_all_three_surfaces_are_overridden(self) -> None:
        for surface in ("game_identity", "player_card", "pull_reveal"):
            with self.subTest(surface=surface):
                self.assertIsNot(
                    getattr(BanGDreamKit, surface), getattr(BaseKit, surface)
                )

    def test_dispatcher_reaches_the_bespoke_component(self) -> None:
        kit = BanGDreamKit()
        # The bespoke strip is a themed panel, not the generic fallback's
        # 80px composition: its measured height is the kit's own 76px capsule.
        strip = cards.game_identity(kit, _identity(), width=720)
        size = strip.measure(
            RenderContext(), Constraints(max_width=784, max_height=400)
        )
        self.assertEqual(size.height, 76)


class GameIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = BanGDreamKit()

    def test_strip_stays_within_the_tier_a_height_band(self) -> None:
        strip = cards.game_identity(
            self.kit, _identity(), width=720, detail="押注 120 Pt"
        )
        size = strip.measure(
            RenderContext(), Constraints(max_width=784, max_height=400)
        )
        self.assertEqual(size.width, 720)
        self.assertGreaterEqual(size.height, 64)
        self.assertLessEqual(size.height, 88)

    def test_strip_renders_without_avatar_level_or_detail(self) -> None:
        image = _render(
            self.kit,
            cards.game_identity(
                self.kit, PlayerIdentity(nickname="纯"), width=720
            ),
        )
        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.width, 0)

    def test_strip_renders_with_an_avatar_image(self) -> None:
        avatar = Image.new("RGBA", (128, 128), (90, 140, 240, 255))
        image = _render(
            self.kit,
            cards.game_identity(
                self.kit, _identity(avatar=avatar), width=720, detail="ROUND 3"
            ),
        )
        self.assertGreater(image.width, 0)

    def test_strip_survives_a_degenerate_width(self) -> None:
        # test_cards exercises width=200 through the dispatcher; the bespoke
        # path must not crash there either.
        image = _render(
            self.kit,
            cards.game_identity(
                self.kit, _identity(), width=200, detail="押注 120 Pt"
            ),
        )
        self.assertGreater(image.width, 0)


class PlayerCardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = BanGDreamKit()

    def test_card_fills_the_requested_canvas(self) -> None:
        card = cards.player_card(
            self.kit, _identity(), current_pt=2350, description="描述"
        )
        size = card.measure(
            RenderContext(), Constraints(max_width=784, max_height=4000)
        )
        self.assertEqual((size.width, size.height), (784, 420))

    def test_card_renders_without_avatar_and_with_empty_description(self) -> None:
        image = _render(
            self.kit,
            cards.player_card(self.kit, _identity(), current_pt=0, description=""),
        )
        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.height, 400)

    def test_card_renders_with_avatar_and_cosmetic_slots_empty(self) -> None:
        avatar = Image.new("RGBA", (256, 256), (240, 180, 90, 255))
        image = _render(
            self.kit,
            cards.player_card(
                self.kit,
                _identity(avatar=avatar),
                current_pt=1240,
                description="每天都想打黑香澄，输光了就来一笔画混口饭吃。",
            ),
        )
        self.assertGreater(image.width, 0)


class PullRevealTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = BanGDreamKit()

    def test_single_pull_renders(self) -> None:
        image = _render(self.kit, cards.pull_reveal(self.kit, _pulls(1)))
        self.assertGreater(image.width, 0)

    def test_ten_pull_renders_with_a_rarity_six_tile(self) -> None:
        pulls = _pulls(10)
        self.assertIn(6, [pull.rarity for pull in pulls])
        image = _render(self.kit, cards.pull_reveal(self.kit, pulls))
        self.assertGreater(image.width, 0)

    def test_rows_are_uniform_regardless_of_tile_content(self) -> None:
        ctx = RenderContext()
        constraints = Constraints(max_width=784, max_height=4000)
        one_row = cards.pull_reveal(self.kit, _pulls(5)).measure(ctx, constraints)
        two_rows = cards.pull_reveal(self.kit, _pulls(10)).measure(ctx, constraints)
        # Mixed note/marker/rarity-6 content must not produce ragged rows: two
        # rows measure exactly twice one row plus the grid gap.
        self.assertEqual(two_rows.height, one_row.height * 2 + 12)

    def test_reveal_render_is_deterministic(self) -> None:
        # The rarity-6 star scatter is seeded; the same pull sequence must
        # produce byte-identical images.
        first = _render(self.kit, cards.pull_reveal(self.kit, _pulls(10)))
        second = _render(self.kit, cards.pull_reveal(self.kit, _pulls(10)))
        self.assertEqual(first.tobytes(), second.tobytes())


if __name__ == "__main__":
    unittest.main()
