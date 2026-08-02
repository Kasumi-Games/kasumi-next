import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import cards
from plugins.render import BaseKit
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits import KITS
from plugins.render.kits.endfield import EndfieldKit

IDENTITY = PlayerIdentity(nickname="管理员", level=42)
ART = Image.new("RGBA", (96, 128), (70, 78, 92, 255))
PULLS = [
    PullRevealItem(
        name=f"档案 {index + 1}",
        rarity=6 if index == 9 else 3 + index % 3,
        is_new=index % 2 == 0,
        featured=index == 9,
        image=ART if index % 2 else None,
        note="盆栽 +120" if index == 9 else "",
    )
    for index in range(10)
]


class EndfieldRegistrationTest(unittest.TestCase):
    def test_registered_in_kits(self) -> None:
        self.assertIs(KITS["endfield"], EndfieldKit)

    def test_all_three_tier_a_surfaces_are_bespoke(self) -> None:
        for surface in ("game_identity", "player_card", "pull_reveal"):
            with self.subTest(surface=surface):
                self.assertIsNot(
                    getattr(EndfieldKit, surface),
                    getattr(BaseKit, surface),
                )


class EndfieldSurfaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = EndfieldKit()
        self.ctx = RenderContext()
        self.constraints = Constraints(
            max_width=cards.CONTENT_WIDTH,
            max_height=4000,
        )

    def test_page_title_and_panel_keep_the_dossier_silhouette(self) -> None:
        self.assertEqual(type(self.kit.page_title("资料")).__name__, "EndfieldTitle")
        panel = self.kit.panel()
        self.assertEqual(type(panel).__name__, "EndfieldPanel")
        self.assertIsNone(panel.radius)

    def test_game_identity_prioritises_name_when_narrow(self) -> None:
        wide = _collect_text(
            cards.game_identity(
                self.kit,
                IDENTITY,
                width=cards.CONTENT_WIDTH,
                detail="押注 120 Pt",
            )
        )
        self.assertIn("管理员", wide)
        self.assertIn("LV // 42", wide)
        self.assertIn("押注 120 Pt", wide)

        squeezed = _collect_text(
            cards.game_identity(
                self.kit,
                IDENTITY,
                width=360,
                detail="押注 120 Pt",
            )
        )
        self.assertIn("管理员", squeezed)
        self.assertNotIn("LV // 42", squeezed)
        self.assertIn("押注 120 Pt", squeezed)

        tiny = _collect_text(
            cards.game_identity(
                self.kit,
                IDENTITY,
                width=220,
                detail="押注 120 Pt",
            )
        )
        self.assertIn("管理员", tiny)
        self.assertNotIn("LV // 42", tiny)
        self.assertNotIn("押注 120 Pt", tiny)

    def test_player_card_handles_empty_and_full_records(self) -> None:
        empty = cards.player_card(
            self.kit,
            PlayerIdentity(nickname="管理员"),
            current_pt=0,
        )
        self.assertIn("暂无公开档案。", _collect_text(empty))

        full = cards.player_card(
            self.kit,
            IDENTITY,
            current_pt=1240,
            description="协议已接入，工业系统运行正常。",
            standing_art=ART,
        )
        size = full.measure(self.ctx, self.constraints)
        self.assertEqual((size.width, size.height), (cards.CONTENT_WIDTH, 420))
        for expected in ("管理员", "LV // 42", "1,240"):
            self.assertIn(expected, _collect_text(full))

    def test_pull_reveal_renders_one_and_ten(self) -> None:
        for count in (1, 10):
            with self.subTest(count=count):
                reveal = cards.pull_reveal(
                    self.kit,
                    PULLS[:count],
                    width=cards.INNER_WIDTH,
                )
                size = reveal.measure(self.ctx, self.constraints)
                self.assertGreater(size.width, 0)
                self.assertGreater(size.height, 0)

    def test_top_rarity_has_heavier_dossier_frame(self) -> None:
        ordinary = self.kit._pull_tile(
            PULLS[0],
            134,
            324,
            art_slot=True,
            index=1,
        )
        top = self.kit._pull_tile(
            PULLS[9],
            134,
            324,
            art_slot=True,
            index=10,
        )
        self.assertEqual(ordinary.border_width, 2)
        self.assertEqual(top.border_width, 3)

    def test_full_page_is_deterministic(self) -> None:
        def render():
            return cards.response_card(
                self.kit,
                title="终末地工业",
                body=cards.player_card(
                    self.kit,
                    IDENTITY,
                    current_pt=1240,
                    description="协议已接入。",
                ),
            )

        first = render()
        second = render()
        self.assertEqual(first.size, second.size)
        self.assertEqual(first.tobytes(), second.tobytes())


def _collect_text(component) -> list[str]:
    texts: list[str] = []
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
