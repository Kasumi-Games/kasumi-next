import sys
import types
import unittest
import importlib.util
from types import SimpleNamespace
from pathlib import Path

from PIL import Image
from PIL import ImageFont

from plugins.render.kits.minimal import MinimalKit
from plugins.render.kits.bangdream import BanGDreamKit

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_package(name: str, path: Path):
    package = sys.modules.get(name)
    if package is None:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    return package


class RendererMigrationTest(unittest.TestCase):
    def test_migrated_renderers_do_not_import_render_service(self) -> None:
        for path in (ROOT / "plugins").rglob("*.py"):
            if "render_service" in path.parts:
                continue
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("plugins.render_service", content, str(path))
            self.assertNotIn("render_service.resources", content, str(path))

    def test_blackjack_hand_and_table_render_with_new_components(self) -> None:
        sys.modules.setdefault(
            "nonebot_plugin_localstore",
            types.SimpleNamespace(get_data_dir=lambda _name: ROOT),
        )
        render_module = _load_module(
            "blackjack_render_for_test", ROOT / "plugins" / "blackjack" / "render.py"
        )
        models_module = _load_module(
            "blackjack_models_for_test", ROOT / "plugins" / "blackjack" / "models.py"
        )
        renderer = object.__new__(render_module.BlackjackRenderer)
        renderer.kit = BanGDreamKit()
        renderer.card_back = Image.new("RGBA", (640, 896), (40, 40, 40, 255))
        renderer.get_font = lambda size: ImageFont.load_default(size)

        def card(rank: str):
            item = models_module.Card("cool", rank)
            item._get_image = lambda ace_value=None: Image.new(
                "RGBA", (640, 896), (200, 100, 100, 255)
            )
            return item

        dealer = models_module.Hand()
        dealer.add_card(card("A"))
        dealer.add_card(card("10"))
        player = models_module.Hand()
        player.add_card(card("8"))
        player.add_card(card("7"))

        hand_image = renderer.generate_hand(dealer, second_card_back=True)
        table_image = renderer.generate_table(dealer, player, dealer_card_back=True)

        self.assertEqual(hand_image.mode, "RGBA")
        self.assertEqual(table_image.mode, "RGB")
        self.assertGreater(hand_image.width, 0)
        self.assertGreater(hand_image.height, 0)
        self.assertGreater(table_image.width, 0)
        self.assertGreater(table_image.height, hand_image.height)

        minimal_renderer = object.__new__(render_module.BlackjackRenderer)
        minimal_renderer.kit = MinimalKit()
        minimal_renderer.card_back = Image.new("RGBA", (640, 896), (40, 40, 40, 255))
        minimal_renderer.get_font = lambda size: ImageFont.load_default(size)

        minimal_table = minimal_renderer.generate_table(
            dealer, player, dealer_card_back=True
        )
        self.assertEqual(minimal_table.mode, "RGB")
        self.assertGreater(minimal_table.width, 0)
        self.assertGreater(minimal_table.height, 0)

    def test_one_stroke_leaderboard_render_uses_new_components(self) -> None:
        leaderboard_module = _load_module(
            "one_stroke_leaderboard_for_test",
            ROOT / "plugins" / "one_stroke" / "render" / "leaderboard.py",
        )

        image = leaderboard_module.render_leaderboard(
            [("kasumi", 12.34)],
            [("a very very long player name", 23.45)],
            [],
        )

        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.width, 0)
        self.assertGreater(image.height, 0)

        minimal_image = leaderboard_module.render_leaderboard(
            [("kasumi", 12.34)],
            [],
            [],
            kit=MinimalKit(),
        )
        self.assertEqual(minimal_image.mode, "RGBA")
        self.assertGreater(minimal_image.width, 0)
        self.assertGreater(minimal_image.height, 0)

    def test_one_stroke_leaderboard_rows_have_a_fixed_vertical_budget(self) -> None:
        leaderboard_module = _load_module(
            "one_stroke_leaderboard_budget_for_test",
            ROOT / "plugins" / "one_stroke" / "render" / "leaderboard.py",
        )
        from plugins.render.sizing import Fixed
        from plugins.render.kits import KasumiKit

        rows = leaderboard_module._ranking_rows(
            KasumiKit(),
            [(f"player-{index}-with-a-very-long-name", 10.0 + index) for index in range(10)],
        )
        self.assertTrue(rows.children)
        self.assertTrue(
            all(isinstance(row.height, Fixed) for row in rows.children)
        )
        total_height = (
            sum(row.height.value for row in rows.children)
            + rows.gap * (len(rows.children) - 1)
        )
        self.assertLessEqual(total_height, 620)

    def test_one_stroke_leaderboard_uses_bangdream_titled_panels(self) -> None:
        leaderboard_module = _load_module(
            "one_stroke_leaderboard_titled_panel_for_test",
            ROOT / "plugins" / "one_stroke" / "render" / "leaderboard.py",
        )

        class CountingBanGDreamKit(BanGDreamKit):
            titled_panel_count = 0

            def titled_panel(self, *args, **kwargs):
                self.titled_panel_count += 1
                return super().titled_panel(*args, **kwargs)

        kit = CountingBanGDreamKit()
        image = leaderboard_module.render_leaderboard(
            [("kasumi", 12.34)],
            [("tae", 23.45)],
            [("ran", 34.56)],
            kit=kit,
        )

        self.assertEqual(kit.titled_panel_count, 3)
        self.assertEqual(image.mode, "RGBA")

    def test_mines_render_accepts_base_kit_components(self) -> None:
        _ensure_package("plugins.mines", ROOT / "plugins" / "mines")
        _ensure_package("plugins.mines.render", ROOT / "plugins" / "mines" / "render")
        models_module = _load_module(
            "plugins.mines.models", ROOT / "plugins" / "mines" / "models.py"
        )
        field_module = _load_module(
            "plugins.mines.render.field",
            ROOT / "plugins" / "mines" / "render" / "field.py",
        )
        field = SimpleNamespace(
            width=2,
            height=2,
            field=[
                [models_module.BlockType.EMPTY, models_module.BlockType.EMPTY],
                [models_module.BlockType.EMPTY, models_module.BlockType.EMPTY],
            ],
        )

        image = field_module.render(field, kit=MinimalKit())

        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.width, 0)
        self.assertGreater(image.height, 0)

    def test_one_stroke_graph_render_accepts_base_kit_components(self) -> None:
        _ensure_package("plugins.one_stroke", ROOT / "plugins" / "one_stroke")
        _ensure_package(
            "plugins.one_stroke.render",
            ROOT / "plugins" / "one_stroke" / "render",
        )
        models_module = _load_module(
            "plugins.one_stroke.models",
            ROOT / "plugins" / "one_stroke" / "models.py",
        )
        session_module = _load_module(
            "plugins.one_stroke.session",
            ROOT / "plugins" / "one_stroke" / "session.py",
        )
        graph_module = _load_module(
            "plugins.one_stroke.render.graph",
            ROOT / "plugins" / "one_stroke" / "render" / "graph.py",
        )
        graph = models_module.Graph(
            rows=2,
            cols=2,
            nodes={(0, 0), (0, 1), (1, 0), (1, 1)},
            edges={
                frozenset(((0, 0), (0, 1))),
                frozenset(((0, 0), (1, 0))),
            },
            start_node=(0, 0),
        )
        session = session_module.GameSession(
            user_id="u",
            channel_id="c",
            difficulty_name="普通",
            reward=100,
            graph=graph,
        )

        image = graph_module.render(session, kit=MinimalKit())

        self.assertEqual(image.mode, "RGBA")
        self.assertGreater(image.width, 0)
        self.assertGreater(image.height, 0)


if __name__ == "__main__":
    unittest.main()
