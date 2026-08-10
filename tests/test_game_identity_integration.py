"""Identity strip integration on the three game boards.

Each board renderer takes an optional ``identity``/``detail`` pair. ``None``
must reproduce the exact pre-identity layout (the preview script and older
tests call the renderers without it), while a present identity must add the
strip through the ``utils.cards.game_identity`` dispatcher — verified here with
a counting kit subclass in two kits per game.
"""

import sys
import types
import unittest
import importlib.util
from types import SimpleNamespace
from pathlib import Path

from PIL import Image
from PIL import ImageFont

from utils import cards
from plugins.render import BaseKit
from plugins.render import PlayerIdentity
from plugins.render.kits.minimal import MinimalKit
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.kasumi import KasumiKit

ROOT = Path(__file__).resolve().parents[1]

IDENTITY = PlayerIdentity(nickname="香澄", level=12)


def _image_sources(component) -> set[object]:
    sources: set[object] = set()

    def visit(node) -> None:
        for attr in ("source", "image"):
            value = getattr(node, attr, None)
            if value is not None:
                try:
                    sources.add(value)
                except TypeError:
                    pass
        for attr in ("children", "child"):
            value = getattr(node, attr, None)
            if isinstance(value, (list, tuple)):
                for child in value:
                    visit(child)
            elif value is not None:
                visit(value)

    visit(component)
    return sources


def test_game_identity_uses_the_equipped_avatar_frame_in_every_tier_a_path() -> None:
    frame = ROOT / "plugins/inventory/resources/items/avatar_frames/frame_starbeat_top50.png"
    identity = PlayerIdentity(
        nickname="香澄", level=12, avatar_frame=frame
    )
    for kit in (MinimalKit(), BanGDreamKit(), KasumiKit()):
        component = cards.game_identity(kit, identity, width=720)
        assert frame in _image_sources(component)


def _bind_to_parent(name: str, module) -> None:
    """Mirror what the import system does: expose a child on its parent.

    Later tests resolve dotted monkeypatch targets via ``getattr`` on the
    parent package, so a module registered only in ``sys.modules`` is not
    enough.
    """

    parent_name, _, child = name.rpartition(".")
    if not parent_name:
        return
    parent = sys.modules.get(parent_name)
    if parent is not None:
        setattr(parent, child, module)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _bind_to_parent(name, module)
    return module


def _ensure_package(name: str, path: Path):
    package = sys.modules.get(name)
    if package is None:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    _bind_to_parent(name, package)
    return package


def _counting_kit(base: type[BaseKit]) -> BaseKit:
    """A kit that counts identity-strip renders via the Tier A dispatcher."""

    class CountingKit(base):
        def __init__(self):
            super().__init__()
            self.game_identity_calls = 0

        def game_identity(self, identity, *, width, detail=None):
            self.game_identity_calls += 1
            return cards._generic_game_identity(
                self, identity, width=width, detail=detail
            )

    return CountingKit()


class MinesIdentityTest(unittest.TestCase):
    def _modules(self):
        _ensure_package("plugins.mines", ROOT / "plugins" / "mines")
        _ensure_package("plugins.mines.render", ROOT / "plugins" / "mines" / "render")
        models_module = _load_module(
            "plugins.mines.models", ROOT / "plugins" / "mines" / "models.py"
        )
        field_module = _load_module(
            "plugins.mines.render.field",
            ROOT / "plugins" / "mines" / "render" / "field.py",
        )
        return models_module, field_module

    def test_identity_strip_present_and_absent(self) -> None:
        models_module, field_module = self._modules()
        field = SimpleNamespace(
            width=2,
            height=2,
            field=[
                [models_module.BlockType.EMPTY, models_module.BlockType.EMPTY],
                [models_module.BlockType.EMPTY, models_module.BlockType.EMPTY],
            ],
        )

        for base in (BanGDreamKit, MinimalKit):
            kit = _counting_kit(base)

            plain = field_module.render(field, kit=kit)
            self.assertEqual(kit.game_identity_calls, 0)

            with_identity = field_module.render(
                field,
                kit=kit,
                identity=IDENTITY,
                detail="押注 120 Pt · 剩 5 雷",
            )
            self.assertEqual(kit.game_identity_calls, 1)
            self.assertEqual(with_identity.width, plain.width)
            self.assertGreater(with_identity.height, plain.height)

    def test_bangdream_board_panel_uses_the_board_fill(self) -> None:
        _, field_module = self._modules()
        kit = BanGDreamKit()

        panel = field_module._board_panel(kit, kit.text("board"))

        self.assertEqual(panel.fill, (255, 255, 255, 230))


class OneStrokeIdentityTest(unittest.TestCase):
    def _session(self, models_module, session_module):
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
        return session_module.GameSession(
            user_id="u",
            channel_id="c",
            difficulty_name="普通",
            reward=100,
            graph=graph,
        )

    def _modules(self):
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
        return models_module, session_module, graph_module

    def test_identity_strip_present_and_absent(self) -> None:
        models_module, session_module, graph_module = self._modules()
        session = self._session(models_module, session_module)

        for base in (BanGDreamKit, MinimalKit):
            kit = _counting_kit(base)

            plain = graph_module.render(session, kit=kit)
            self.assertEqual(kit.game_identity_calls, 0)

            with_identity = graph_module.render(
                session,
                kit=kit,
                identity=IDENTITY,
                detail="难度 普通 · 奖励 100 Pt",
            )
            self.assertEqual(kit.game_identity_calls, 1)
            self.assertEqual(with_identity.width, plain.width)
            self.assertGreater(with_identity.height, plain.height)

    def test_bangdream_board_panel_uses_the_board_fill(self) -> None:
        _, _, graph_module = self._modules()
        kit = BanGDreamKit()

        panel = graph_module._board_panel(kit, kit.text("board"))

        self.assertEqual(panel.fill, (255, 255, 255, 230))


class BlackjackIdentityTest(unittest.TestCase):
    def _renderer(self, kit: BaseKit):
        sys.modules.setdefault(
            "nonebot_plugin_localstore",
            types.SimpleNamespace(get_data_dir=lambda _name: ROOT),
        )
        render_module = _load_module(
            "blackjack_render_for_identity_test",
            ROOT / "plugins" / "blackjack" / "render.py",
        )
        models_module = _load_module(
            "blackjack_models_for_identity_test",
            ROOT / "plugins" / "blackjack" / "models.py",
        )
        renderer = object.__new__(render_module.BlackjackRenderer)
        renderer.kit = kit
        renderer.card_back = Image.new("RGBA", (640, 896), (40, 40, 40, 255))
        renderer.get_font = lambda size: ImageFont.load_default(size)
        return renderer, models_module

    @staticmethod
    def _card(models_module, rank: str):
        item = models_module.Card("cool", rank)
        item._get_image = lambda ace_value=None: Image.new(
            "RGBA", (640, 896), (200, 100, 100, 255)
        )
        return item

    def test_identity_strip_present_and_absent(self) -> None:
        for base in (BanGDreamKit, MinimalKit):
            kit = _counting_kit(base)
            renderer, models_module = self._renderer(kit)

            dealer = models_module.Hand()
            dealer.add_card(self._card(models_module, "9"))
            dealer.add_card(self._card(models_module, "10"))
            player = models_module.Hand()
            player.add_card(self._card(models_module, "8"))
            player.add_card(self._card(models_module, "7"))

            plain_hand = renderer.generate_hand(dealer, second_card_back=True)
            plain_table = renderer.generate_table(
                dealer, player, dealer_card_back=True
            )
            self.assertEqual(kit.game_identity_calls, 0)

            hand_with_identity = renderer.generate_hand(
                dealer,
                second_card_back=True,
                identity=IDENTITY,
                detail="押注 120 Pt",
            )
            self.assertEqual(kit.game_identity_calls, 1)
            table_with_identity = renderer.generate_table(
                dealer,
                player,
                dealer_card_back=True,
                identity=IDENTITY,
                detail="押注 120 Pt",
            )
            self.assertEqual(kit.game_identity_calls, 2)

            self.assertEqual(hand_with_identity.width, plain_hand.width)
            self.assertGreater(hand_with_identity.height, plain_hand.height)
            self.assertEqual(table_with_identity.width, plain_table.width)
            self.assertGreater(table_with_identity.height, plain_table.height)


if __name__ == "__main__":
    unittest.main()
