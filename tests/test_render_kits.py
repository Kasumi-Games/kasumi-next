import sys
import inspect
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugins.render import Fill
from plugins.render import Page
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render.core import Size
from plugins.render.core import RenderContext
from plugins.render.kits import KITS
from plugins.render.kits.atoms import mix_color
from plugins.render.kits.atoms import vertical_gradient

#: Kits added on top of the original bangdream/minimal pair.
NEW_KIT_NAMES = (
    "midnight",
    "sailing",
    "sakura",
    "neon",
    "manga",
    "fluent",
    "kasumi",
    "mewtype",
    "endfield",
)


def _sample_page(kit: BaseKit, size: tuple[int, int] = (240, 180)) -> Page:
    swatch = Image.new("RGBA", (12, 12), (66, 133, 244, 255))
    return Page(
        size=size,
        background=kit.background(),
        padding=Insets.all(12),
        child=VStack(
            [
                kit.panel(kit.text("主题 Theme", font_size=18), padding=10),
                kit.separator(length=Fill()),
                kit.image(swatch, width=Fixed(24), height=Fixed(24)),
            ],
            gap=8,
            align="start",
        ),
    )


class KitRegistryTest(unittest.TestCase):
    def test_registry_contains_every_kit(self) -> None:
        self.assertEqual(
            set(KITS),
            {"bangdream", "minimal", *NEW_KIT_NAMES},
        )

    def test_every_registered_kit_is_a_base_kit(self) -> None:
        for name, kit_class in KITS.items():
            with self.subTest(kit=name):
                self.assertTrue(issubclass(kit_class, BaseKit))
                self.assertIsInstance(kit_class(), BaseKit)

    def test_every_kit_publishes_a_palette(self) -> None:
        for name, kit_class in KITS.items():
            with self.subTest(kit=name):
                kit = kit_class()
                for attribute in ("text_color", "muted_text_color", "panel_fill"):
                    color = getattr(kit, attribute)
                    self.assertEqual(len(tuple(color)), 4, attribute)

    def test_bangdream_panels_are_opaque_by_default(self) -> None:
        kit = KITS["bangdream"]()

        self.assertEqual(kit.panel_fill, (255, 255, 255, 255))
        self.assertEqual(kit.panel().fill, (255, 255, 255, 255))

    def test_bangdream_board_panels_use_the_translucent_fill(self) -> None:
        kit = KITS["bangdream"]()
        board = kit.board_frame(kit.text("board"))

        self.assertEqual(kit.board_panel_fill, (255, 255, 255, 230))
        self.assertEqual(board.fill, (255, 255, 255, 230))

    def test_mewtype_uses_the_common_yumemita_subpage_palette(self) -> None:
        kit = KITS["mewtype"]()

        self.assertEqual(kit.paper_fill, (252, 241, 255, 255))
        self.assertEqual(kit.text_color, (32, 47, 109, 255))
        self.assertEqual(kit.primary, (29, 211, 243, 255))
        self.assertEqual(kit.accent, (255, 115, 213, 255))
        self.assertIsNone(kit.panel().radius)
        self.assertEqual(kit.panel(radius=20).radius, 20)
        title = kit.page_title("STORY")
        self.assertEqual(title.font_size, 96)
        self.assertEqual(title.gradient_top, (214, 128, 241, 255))
        self.assertEqual(title.gradient_bottom, (61, 189, 245, 255))
        self.assertEqual(title.shadow_color, (70, 188, 248, 255))
        self.assertEqual(title.shadow_offset, 11)
        self.assertEqual(title.outline_width, 8)
        self.assertEqual(title.face_weight, 1)
        self.assertEqual(title.horizontal_scale, 1.16)
        self.assertEqual(title.punch_outline_color, (174, 236, 246, 255))
        self.assertEqual(title.ornament_color, (201, 130, 232, 255))
        self.assertEqual(title.ornament_square_color, (255, 115, 213, 255))
        self.assertEqual(kit.panel().fill, (255, 255, 255, 255))
        self.assertEqual(kit.grid_color, (255, 255, 255, 255))

    def test_mewtype_title_separates_text_and_ornament_extrusions(self) -> None:
        kit = KITS["mewtype"]()
        title = kit.page_title("ON AIR")

        image = Page(
            size=(960, 300),
            child=Frame(title, width=Fixed(960), height=Fixed(270)),
        ).render()
        cyan = title.shadow_color
        central_cyan = sum(
            pixel == cyan for pixel in image.crop((330, 0, 630, 300)).getdata()
        )
        total_cyan = sum(pixel == cyan for pixel in image.getdata())

        # The website's word image repeats its gradient into the lower text
        # ledge.  Only the separate +/square ornaments use a flat cyan drop.
        self.assertLess(central_cyan, 20)
        self.assertGreater(total_cyan, 10)
        self.assertIn("Medium", str(title.font))

    def test_endfield_uses_the_live_site_industrial_palette(self) -> None:
        kit = KITS["endfield"]()

        self.assertEqual(kit.primary, (25, 25, 25, 255))
        self.assertEqual(kit.accent, (255, 250, 0, 255))
        self.assertEqual(kit.rule_color, (217, 217, 217, 255))
        self.assertIsNone(kit.panel().radius)
        self.assertEqual(kit.panel(radius=4).radius, 4)
        self.assertEqual(kit.background().hatch_spacing, 6)
        title = kit.page_title("ENDFIELD")
        self.assertEqual(title.font_size, 54)
        self.assertEqual(title.signal_color, (255, 250, 0, 255))


class KitAtomContractTest(unittest.TestCase):
    def test_atoms_accept_the_base_signature(self) -> None:
        # A caller holding a BaseKit must be able to use these argument names
        # against any kit, so extra kit-specific parameters have to be optional.
        for name, kit_class in KITS.items():
            for method_name in ("text", "image", "panel", "separator"):
                with self.subTest(kit=name, method=method_name):
                    base = inspect.signature(getattr(BaseKit, method_name))
                    actual = inspect.signature(getattr(kit_class, method_name))
                    for parameter in base.parameters.values():
                        if parameter.name == "self":
                            continue
                        self.assertIn(parameter.name, actual.parameters)
                    for parameter in actual.parameters.values():
                        if parameter.name in base.parameters or parameter.kind in (
                            inspect.Parameter.VAR_KEYWORD,
                            inspect.Parameter.VAR_POSITIONAL,
                        ):
                            continue
                        self.assertIsNot(
                            parameter.default,
                            inspect.Parameter.empty,
                            f"{name}.{method_name} adds required parameter "
                            f"{parameter.name!r}",
                        )

    def test_background_takes_no_required_arguments(self) -> None:
        for name, kit_class in KITS.items():
            with self.subTest(kit=name):
                signature = inspect.signature(kit_class.background)
                for parameter in signature.parameters.values():
                    if parameter.name == "self" or parameter.kind in (
                        inspect.Parameter.VAR_KEYWORD,
                        inspect.Parameter.VAR_POSITIONAL,
                    ):
                        continue
                    self.assertIsNot(parameter.default, inspect.Parameter.empty)


class KitRenderTest(unittest.TestCase):
    def test_new_kits_render_a_page(self) -> None:
        for name in NEW_KIT_NAMES:
            with self.subTest(kit=name):
                image = _sample_page(KITS[name]()).render(RenderContext())
                self.assertEqual(image.size, (240, 180))
                self.assertEqual(image.mode, "RGBA")

    def test_new_kit_backgrounds_are_deterministic(self) -> None:
        # Scattered decoration (stars, petals) must be seeded, or repeated
        # renders of the same board would differ frame to frame.
        for name in NEW_KIT_NAMES:
            with self.subTest(kit=name):
                background = KITS[name]().background()
                first = background.render(RenderContext(), Size(96, 72))
                second = background.render(RenderContext(), Size(96, 72))
                self.assertEqual(first.size, (96, 72))
                self.assertEqual(first.tobytes(), second.tobytes())

    def test_new_kit_backgrounds_fill_every_pixel(self) -> None:
        for name in NEW_KIT_NAMES:
            with self.subTest(kit=name):
                image = KITS[name]().background().render(RenderContext(), Size(64, 48))
                alphas = image.getchannel("A").getextrema()
                self.assertEqual(alphas, (255, 255))

    def test_new_kits_render_at_higher_pixel_ratio(self) -> None:
        for name in NEW_KIT_NAMES:
            with self.subTest(kit=name):
                image = _sample_page(KITS[name]()).render(RenderContext(pixel_ratio=2))
                self.assertEqual(image.size, (240, 180))

    def test_kits_render_distinct_output(self) -> None:
        rendered = {
            name: _sample_page(KITS[name]()).render(RenderContext()).tobytes()
            for name in NEW_KIT_NAMES
        }
        self.assertEqual(len(set(rendered.values())), len(NEW_KIT_NAMES))

    def test_dark_and_light_kits_disagree_on_text_color(self) -> None:
        midnight = KITS["midnight"]()
        sakura = KITS["sakura"]()
        self.assertGreater(sum(midnight.text_color[:3]), sum(sakura.text_color[:3]))
        self.assertLess(sum(midnight.panel_fill[:3]), sum(sakura.panel_fill[:3]))

    def test_zero_sized_background_does_not_raise(self) -> None:
        for name in NEW_KIT_NAMES:
            with self.subTest(kit=name):
                image = KITS[name]().background().render(RenderContext(), Size(0, 0))
                self.assertEqual(image.size, (0, 0))


class KitAtomHelperTest(unittest.TestCase):
    def test_mix_color_interpolates_and_clamps(self) -> None:
        start = (0, 0, 0, 0)
        end = (100, 200, 50, 255)
        self.assertEqual(mix_color(start, end, 0), start)
        self.assertEqual(mix_color(start, end, 1), end)
        self.assertEqual(mix_color(start, end, 0.5), (50, 100, 25, 128))
        self.assertEqual(mix_color(start, end, -5), start)
        self.assertEqual(mix_color(start, end, 5), end)

    def test_vertical_gradient_runs_top_to_bottom(self) -> None:
        top = (0, 0, 0, 255)
        bottom = (255, 255, 255, 255)

        gradient = vertical_gradient(Size(8, 32), top, bottom)

        self.assertEqual(gradient.size, (8, 32))
        self.assertEqual(gradient.getpixel((0, 0)), top)
        self.assertEqual(gradient.getpixel((0, 31)), bottom)
        self.assertLess(
            gradient.getpixel((0, 8))[0],
            gradient.getpixel((0, 24))[0],
        )

    def test_vertical_gradient_handles_single_row(self) -> None:
        gradient = vertical_gradient(Size(4, 1), (10, 20, 30, 255), (40, 50, 60, 255))

        self.assertEqual(gradient.size, (4, 1))


if __name__ == "__main__":
    unittest.main()
