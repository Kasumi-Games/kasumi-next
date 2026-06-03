import time
import asyncio
import tempfile
import unittest
from pathlib import Path
from dataclasses import dataclass

from PIL import Image

from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Page
from plugins.render import Rect
from plugins.render import Size
from plugins.render import Fixed
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import Spacer
from plugins.render import VStack
from plugins.render import AutoPage
from plugins.render import Fraction
from plugins.render import Constraints
from plugins.render import LayoutError
from plugins.render import RenderContext
from plugins.render.kit import BaseKit
from plugins.render.primitives import load_font
from plugins.render.image_cache import ImageCache
from plugins.render.kits.minimal import MinimalKit
from plugins.render.kits.bangdream import CHINESE_FONT
from plugins.render.kits.bangdream import DISPLAY_FONT
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.minimal.components import MinimalText
from plugins.render.kits.minimal.components import MinimalImage
from plugins.render.kits.minimal.components import MinimalPanel
from plugins.render.kits.bangdream.components import BanGDreamImage


def _font_text_width(text: str, font) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


@dataclass(frozen=True)
class SlowRenderBox:
    delay: float

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        return constraints.clamp(Size(10, 10))

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        time.sleep(self.delay)


class RenderLayoutTest(unittest.TestCase):
    def test_fill_requires_bounded_axis(self) -> None:
        with self.assertRaises(LayoutError):
            HStack([Spacer(width=Fill(), height=Fixed(10))]).measure(
                RenderContext(), Constraints()
            )

    def test_fraction_requires_bounded_axis(self) -> None:
        with self.assertRaises(LayoutError):
            HStack([Spacer(width=Fraction(0.5), height=Fixed(10))]).measure(
                RenderContext(), Constraints()
            )

    def test_stack_splits_fill_children_equally(self) -> None:
        ctx = RenderContext()
        stack = HStack(
            [
                Spacer(width=Fixed(100), height=Fixed(10)),
                Spacer(width=Fill(), height=Fixed(10)),
                Spacer(width=Fill(), height=Fixed(10)),
            ],
            gap=10,
        )
        self.assertEqual(stack.measure(ctx, Constraints(max_width=500)).width, 500)
        canvas = Image.new("RGBA", (500, 20), (0, 0, 0, 0))
        stack.render(ctx, canvas, rect=Rect(0, 0, 500, 20))

    def test_grid_fit_tracks_use_child_intrinsic_size(self) -> None:
        grid = Grid(
            columns=2,
            gap=5,
            children=[
                Spacer(width=Fixed(20), height=Fixed(30)),
                Spacer(width=Fixed(20), height=Fixed(30)),
                Spacer(width=Fixed(20), height=Fixed(30)),
                Spacer(width=Fixed(20), height=Fixed(30)),
            ],
        )
        self.assertEqual(grid.measure(RenderContext(), Constraints()), Size(45, 65))

    def test_grid_fill_tracks_require_bounds(self) -> None:
        grid = Grid(
            columns=2,
            column_track=Fill(),
            children=[
                Spacer(width=Fixed(20), height=Fixed(20)),
                Spacer(width=Fixed(20), height=Fixed(20)),
            ],
        )
        with self.assertRaises(LayoutError):
            grid.measure(RenderContext(), Constraints())

    def test_auto_page_sizes_to_child_plus_padding(self) -> None:
        page = AutoPage(
            Spacer(width=Fixed(20), height=Fixed(30)), padding=Insets.all(5)
        )
        self.assertEqual(page.render(RenderContext()).size, (30, 40))

    def test_render_context_rejects_invalid_pixel_ratio(self) -> None:
        for value in (0, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RenderContext(pixel_ratio=value)

    def test_page_render_pixel_ratio_preserves_logical_size(self) -> None:
        page = Page(size=(64, 48), child=Spacer(width=Fill(), height=Fill()))

        image = page.render(RenderContext(pixel_ratio=2))

        self.assertEqual(image.size, (64, 48))

    def test_auto_page_render_pixel_ratio_preserves_logical_size(self) -> None:
        page = AutoPage(
            Spacer(width=Fixed(20), height=Fixed(30)), padding=Insets.all(5)
        )

        image = page.render(RenderContext(pixel_ratio=2))

        self.assertEqual(image.size, (30, 40))

    def test_global_pixel_ratio_antialiases_rounded_panel_edge(self) -> None:
        page = Page(
            size=(32, 32),
            child=MinimalPanel(
                fill=(0, 0, 0, 255), radius=8, width=Fill(), height=Fill()
            ),
        )

        image = page.render(RenderContext(pixel_ratio=2))

        edge_alphas = [
            image.getpixel((x, y))[3] for x in range(0, 12) for y in range(0, 12)
        ]
        self.assertTrue(any(0 < alpha < 255 for alpha in edge_alphas))

    def test_base_kit_is_strict_contract(self) -> None:
        with self.assertRaises(TypeError):
            BaseKit()

    def test_base_kit_exposes_only_general_atoms(self) -> None:
        for method_name in (
            "board_frame",
            "badge",
            "label_value",
            "list_row",
            "title_pill",
        ):
            self.assertFalse(hasattr(BaseKit, method_name), method_name)

    def test_minimal_kit_smoke_render(self) -> None:
        kit = MinimalKit()
        source = Image.new("RGBA", (12, 12), (66, 133, 244, 255))
        page = Page(
            size=(180, 120),
            background=kit.page_background(fill=(1, 2, 3, 255)),
            padding=Insets.all(10),
            child=VStack(
                [
                    kit.panel(kit.text("Base", font_size=18), padding=8),
                    kit.separator(length=Fill()),
                    kit.image(source, width=Fixed(24), height=Fixed(24)),
                ],
                gap=6,
                align="start",
            ),
        )

        image = page.render(RenderContext())

        self.assertEqual(image.size, (180, 120))
        self.assertEqual(image.getpixel((0, 0)), (1, 2, 3, 255))

    def test_minimal_text_clips_horizontal_overflow_to_rect(self) -> None:
        canvas = Image.new("RGBA", (120, 40), (255, 255, 255, 255))
        text = MinimalText(
            "This line is intentionally too long",
            font_size=28,
            color=(0, 0, 0, 255),
            wrap=False,
            overflow="clip",
        )

        text.render(RenderContext(), canvas, Rect(10, 8, 32, 24))

        outside_pixels = [
            canvas.getpixel((x, y)) for x in range(42, 120) for y in range(0, 40)
        ]
        self.assertTrue(all(pixel == (255, 255, 255, 255) for pixel in outside_pixels))

    def test_minimal_text_clips_vertical_overflow_to_rect(self) -> None:
        canvas = Image.new("RGBA", (80, 120), (255, 255, 255, 255))
        text = MinimalText(
            "\n".join(["line"] * 8),
            font_size=24,
            color=(0, 0, 0, 255),
            overflow="clip",
        )

        text.render(RenderContext(), canvas, Rect(8, 10, 64, 32))

        outside_pixels = [
            canvas.getpixel((x, y)) for x in range(0, 80) for y in range(42, 120)
        ]
        self.assertTrue(all(pixel == (255, 255, 255, 255) for pixel in outside_pixels))

    def test_minimal_text_wrap_prefers_word_boundaries(self) -> None:
        text = MinimalText("alpha beta gamma", font_size=20)
        font = load_font(20)
        max_width = font.getbbox("alpha beta")[2] - font.getbbox("alpha beta")[0]

        lines, _font_size = text._layout_text(Constraints(max_width=max_width))

        self.assertEqual(lines, ["alpha beta", "gamma"])

    def test_minimal_text_wrap_keeps_cjk_closing_punctuation_off_line_start(
        self,
    ) -> None:
        text_value = "你好，世界"
        text = MinimalText(text_value, font_size=20)
        font = load_font(20)
        max_width = sum(_font_text_width(char, font) for char in "你好")

        lines, _font_size = text._layout_text(Constraints(max_width=max_width))

        self.assertEqual(lines, ["你好，", "世界"])
        self.assertEqual("".join(lines), text_value)
        self.assertFalse(any(line.startswith("，") for line in lines[1:]))

    def test_minimal_text_wrap_keeps_cjk_multiple_closers_attached(self) -> None:
        text_value = "你好！？世界"
        text = MinimalText(text_value, font_size=20)
        font = load_font(20)
        max_width = sum(_font_text_width(char, font) for char in "你好")

        lines, _font_size = text._layout_text(Constraints(max_width=max_width))

        self.assertEqual(lines, ["你好！？", "世界"])
        self.assertEqual("".join(lines), text_value)
        self.assertFalse(any(line[0] in "！？" for line in lines[1:]))

    def test_minimal_text_wrap_keeps_cjk_opening_punctuation_off_line_end(self) -> None:
        text_value = "今日は「最高」ですね"
        text = MinimalText(text_value, font_size=20)
        font = load_font(20)
        max_width = sum(_font_text_width(char, font) for char in "今日は「")

        lines, _font_size = text._layout_text(Constraints(max_width=max_width))

        self.assertEqual(lines, ["今日は", "「最高」", "ですね"])
        self.assertEqual("".join(lines), text_value)
        self.assertFalse(any(line.endswith("「") for line in lines[:-1]))

    def test_bangdream_text_wrap_uses_cjk_punctuation_rules(self) -> None:
        text_value = "你好，世界"
        text = BanGDreamKit().text(text_value, font_size=20)
        font = load_font(20, text.font)
        max_width = sum(_font_text_width(char, font) for char in "你好")

        lines, _font_size = text._layout_text(Constraints(max_width=max_width))

        self.assertEqual(lines, ["你好，", "世界"])
        self.assertEqual("".join(lines), text_value)
        self.assertFalse(any(line.startswith("，") for line in lines[1:]))

    def test_bangdream_text_can_select_bundled_font(self) -> None:
        text = BanGDreamKit().text("BanG Dream!", font="display")

        self.assertEqual(text.font, DISPLAY_FONT)

    def test_minimal_text_ellipsizes_wrapped_vertical_overflow(self) -> None:
        text = MinimalText(
            "alpha beta gamma delta epsilon zeta eta theta",
            font_size=20,
            line_height=24,
            overflow="ellipsis",
        )
        font = load_font(20)
        max_width = font.getbbox("alpha beta")[2] - font.getbbox("alpha beta")[0]

        lines, _font_size = text._layout_text(
            Constraints(max_width=max_width, max_height=48)
        )

        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith("..."))

    def test_minimal_text_clips_under_page_pixel_ratio(self) -> None:
        page = Page(
            size=(80, 40),
            background=MinimalKit().page_background(fill=(255, 255, 255, 255)),
            padding=Insets.only(left=8, top=8, right=40, bottom=8),
            child=MinimalText(
                "This line is intentionally too long",
                font_size=28,
                color=(0, 0, 0, 255),
                wrap=False,
                overflow="clip",
            ),
        )

        image = page.render(RenderContext(pixel_ratio=2))

        outside_pixels = [
            image.getpixel((x, y)) for x in range(42, 80) for y in range(0, 40)
        ]
        self.assertTrue(all(pixel == (255, 255, 255, 255) for pixel in outside_pixels))

    def test_minimal_image_fit_measure_preserves_aspect_with_bounds(self) -> None:
        image = MinimalImage(Image.new("RGBA", (1024, 1024), (1, 2, 3, 255)))

        size = image.measure(
            RenderContext(), Constraints(max_width=702, max_height=430)
        )

        self.assertEqual(size, Size(430, 430))

    def test_bangdream_image_fit_measure_preserves_aspect_with_bounds(self) -> None:
        image = BanGDreamImage(Image.new("RGBA", (1024, 1024), (1, 2, 3, 255)))

        size = image.measure(
            RenderContext(), Constraints(max_width=702, max_height=430)
        )

        self.assertEqual(size, Size(430, 430))

    def test_bangdream_pill_measures_authored_logical_size(self) -> None:
        pill = BanGDreamKit().pill("Label", width=120, height=36, font_size=20)

        size = pill.measure(RenderContext(pixel_ratio=2), Constraints())

        self.assertEqual(size, Size(120, 36))

    def test_bangdream_pill_can_select_bundled_font(self) -> None:
        pill = BanGDreamKit().pill(
            "Label",
            width=120,
            height=36,
            font="display",
        )

        self.assertEqual(pill.font, DISPLAY_FONT)

    def test_bangdream_pill_resolves_size_values(self) -> None:
        pill = BanGDreamKit().pill(
            "Label",
            width=Fill(),
            height=Fraction(0.5),
            font_size=20,
        )

        size = pill.measure(RenderContext(), Constraints(max_width=120, max_height=80))

        self.assertEqual(size, Size(120, 40))

    def test_bangdream_pill_fill_requires_bounded_axis(self) -> None:
        pill = BanGDreamKit().pill("Label", width=Fill(), height=36, font_size=20)

        with self.assertRaises(LayoutError):
            pill.measure(RenderContext(), Constraints())

    def test_bangdream_pill_clips_overlong_text_to_rect(self) -> None:
        canvas = Image.new("RGBA", (120, 48), (255, 255, 255, 255))
        pill = BanGDreamKit().pill(
            "This label is intentionally too long",
            width=40,
            height=24,
            font_size=20,
            align="left",
        )

        pill.render(RenderContext(), canvas, Rect(10, 8, 40, 24))

        outside_pixels = [
            canvas.getpixel((x, y)) for x in range(50, 120) for y in range(0, 48)
        ]
        self.assertTrue(all(pixel == (255, 255, 255, 255) for pixel in outside_pixels))

    def test_bangdream_title_pill_can_select_bundled_fonts(self) -> None:
        title_pill = BanGDreamKit().title_pill(
            "Event",
            "活动",
            title_font="display",
            subtitle_font="chinese",
        )

        self.assertEqual(title_pill.title_font, DISPLAY_FONT)
        self.assertEqual(title_pill.subtitle_font, CHINESE_FONT)

    def test_minimal_image_renders_under_page_pixel_ratio(self) -> None:
        source = Image.new("RGBA", (10, 20), (1, 2, 3, 255))
        page = Page(
            size=(40, 40),
            child=MinimalImage(
                source, width=Fixed(20), height=Fixed(20), fit="contain"
            ),
        )

        image = page.render(RenderContext(pixel_ratio=2))

        self.assertEqual(image.size, (40, 40))

    def test_image_cache_uses_ttl_eviction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.png"
            Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(path)
            cache = ImageCache(ttl_seconds=0.01, max_items=2)
            self.assertEqual(cache.load(path).size, (4, 4))
            time.sleep(0.02)
            Image.new("RGBA", (5, 5), (1, 2, 3, 255)).save(path)
            self.assertEqual(cache.load(path).size, (5, 5))

    def test_bangdream_smoke_render(self) -> None:
        kit = BanGDreamKit()
        cell = Image.new("RGBA", (24, 24), (234, 78, 116, 255))
        page = Page(
            size=(200, 220),
            background=kit.page_background_simple(),
            padding=Insets.all(10),
            child=VStack(
                [
                    kit.title_pill("T", "S", pill_width=100, pill_height=30),
                    kit.board_frame(
                        Grid(
                            columns=2,
                            gap=4,
                            children=[kit.image(cell) for _ in range(4)],
                        ),
                        width=Fill(),
                        height=Fill(),
                        padding=8,
                    ),
                ],
                gap=8,
            ),
        )
        image = page.render(RenderContext())
        self.assertEqual(image.size, (200, 220))

    def test_bangdream_source_background_renders_deterministically(self) -> None:
        kit = BanGDreamKit()
        source = Image.new("RGBA", (40, 24), (234, 78, 116, 255))
        for x in range(20, 40):
            for y in range(24):
                source.putpixel((x, y), (66, 133, 244, 255))

        background = kit.page_background(
            source=source,
            text="BD",
            blur_radius=4,
            triangle_size=48,
            star_density=0,
            random_seed=123,
        )

        first = background.render(RenderContext(), Size(128, 96))
        second = background.render(RenderContext(), Size(128, 96))

        self.assertEqual(first.size, (128, 96))
        self.assertEqual(first.tobytes(), second.tobytes())

    def test_render_module_does_not_import_shared_visual_layer(self) -> None:
        render_root = Path(__file__).resolve().parents[1] / "plugins" / "render"
        forbidden = (
            "plugins.render.visual",
            "render.visual",
            "from .visual",
            "from plugins.render import visual",
        )
        for path in render_root.rglob("*.py"):
            if path.name == "visual.py":
                self.fail(
                    "plugins/render/visual.py should not exist; visual components belong to kits"
                )
            content = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(
                    marker, content, f"{path} imports the shared visual layer"
                )


class AsyncRenderTest(unittest.IsolatedAsyncioTestCase):
    async def test_page_render_async_returns_logical_size(self) -> None:
        page = Page(size=(64, 48), child=Spacer(width=Fill(), height=Fill()))

        image = await page.render_async(RenderContext(pixel_ratio=2))

        self.assertEqual(image.size, (64, 48))

    async def test_auto_page_render_async_returns_logical_size(self) -> None:
        page = AutoPage(
            Spacer(width=Fixed(20), height=Fixed(30)), padding=Insets.all(5)
        )

        image = await page.render_async(RenderContext(pixel_ratio=2))

        self.assertEqual(image.size, (30, 40))

    async def test_render_async_does_not_block_event_loop(self) -> None:
        page = Page(size=(24, 24), child=SlowRenderBox(delay=0.1))

        render_task = asyncio.create_task(page.render_async(RenderContext()))
        await asyncio.sleep(0.02)

        self.assertFalse(render_task.done())
        image = await render_task
        self.assertEqual(image.size, (24, 24))


if __name__ == "__main__":
    unittest.main()
