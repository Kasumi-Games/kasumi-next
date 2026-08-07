import unittest
from dataclasses import field
from dataclasses import dataclass

from PIL import Image

from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Page
from plugins.render import Rect
from plugins.render import Size
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import Overlay
from plugins.render import AutoPage
from plugins.render import Fraction
from plugins.render import SizeValue
from plugins.render import Constraints
from plugins.render import LayoutError
from plugins.render import RenderContext
from plugins.render.sizing import Fit


@dataclass
class RecordingBox:
    name: str
    intrinsic: Size
    width: SizeValue | int | None = None
    height: SizeValue | int | None = None
    renders: list[tuple[str, Rect]] = field(default_factory=list)
    measures: list[tuple[str, Constraints]] = field(default_factory=list)

    def measure(self, ctx: RenderContext, constraints: Constraints) -> Size:
        self.measures.append((self.name, constraints))
        return constraints.clamp(
            Size(
                _resolve_test_axis(
                    self.width, constraints.max_width, self.intrinsic.width, "width"
                ),
                _resolve_test_axis(
                    self.height,
                    constraints.max_height,
                    self.intrinsic.height,
                    "height",
                ),
            )
        )

    def render(self, ctx: RenderContext, canvas: Image.Image, rect: Rect) -> None:
        self.renders.append((self.name, rect))


def _resolve_test_axis(
    value: SizeValue | int | None,
    bound: int | None,
    intrinsic: int,
    owner: str,
) -> int:
    if value is None or isinstance(value, Fit):
        return intrinsic
    if isinstance(value, int):
        return value
    if isinstance(value, Fixed):
        return value.value
    if isinstance(value, Fill):
        if bound is None:
            raise LayoutError(f"test box {owner} Fill requires a bound")
        return bound
    if isinstance(value, Fraction):
        if bound is None:
            raise LayoutError(f"test box {owner} Fraction requires a bound")
        return round(bound * value.value)
    raise TypeError(f"unsupported test size value: {value!r}")


class PageLayoutTest(unittest.TestCase):
    def test_auto_page_reuses_measurements_during_paint(self) -> None:
        child = RecordingBox("child", Size(40, 20), width=Fill(), height=Fill())
        page = AutoPage(VStack([child]), max_width=100, max_height=20)

        page.render(RenderContext(pixel_ratio=2))

        self.assertEqual(len(child.measures), 1)

    def test_measurement_cache_is_fresh_for_each_root_render(self) -> None:
        child = RecordingBox("child", Size(40, 20), width=Fill(), height=Fill())
        page = AutoPage(VStack([child]), max_width=100, max_height=20)

        page.render(RenderContext())
        page.render(RenderContext())

        self.assertEqual(len(child.measures), 2)

    def test_page_renders_child_inside_padding_rect(self) -> None:
        child = RecordingBox("child", Size(10, 20))

        Page(
            size=(100, 80),
            padding=Insets.only(left=5, top=7, right=11, bottom=13),
            child=child,
        ).render(RenderContext())

        self.assertEqual(child.renders, [("child", Rect(10, 14, 168, 120))])

    def test_auto_page_measures_with_padding_adjusted_constraints(self) -> None:
        child = RecordingBox("child", Size(80, 40))

        image = AutoPage(
            child=child,
            padding=Insets.xy(x=5, y=7),
            min_width=100,
            max_width=120,
            min_height=90,
            max_height=100,
        ).render(RenderContext())

        self.assertEqual(image.size, (100, 90))
        self.assertEqual(
            child.measures[0],
            (
                "child",
                Constraints(min_width=90, max_width=110, min_height=76, max_height=86),
            ),
        )
        self.assertEqual(child.renders, [("child", Rect(10, 14, 180, 152))])


class FrameLayoutTest(unittest.TestCase):
    def test_frame_measures_child_plus_padding_and_centers_by_default(self) -> None:
        child = RecordingBox("child", Size(40, 20))
        frame = Frame(child, padding=Insets.xy(x=5, y=3))

        self.assertEqual(frame.measure(RenderContext(), Constraints()), Size(50, 26))
        frame.render(RenderContext(), Image.new("RGBA", (100, 80)), Rect(0, 0, 100, 80))

        self.assertEqual(child.renders, [("child", Rect(30, 30, 40, 20))])

    def test_frame_stretches_child_inside_padding(self) -> None:
        child = RecordingBox("child", Size(40, 20))

        Frame(
            child,
            padding=Insets.only(left=4, top=6, right=8, bottom=10),
            align_x="stretch",
            align_y="stretch",
        ).render(RenderContext(), Image.new("RGBA", (100, 80)), Rect(0, 0, 100, 80))

        self.assertEqual(child.renders, [("child", Rect(4, 6, 88, 64))])

    def test_frame_applies_max_size_before_aspect_ratio(self) -> None:
        frame = Frame(width=Fixed(160), height=Fixed(90), max_width=100, aspect_ratio=1)

        self.assertEqual(frame.measure(RenderContext(), Constraints()), Size(90, 90))


class StackLayoutTest(unittest.TestCase):
    def test_hstack_measures_fixed_children_with_gaps(self) -> None:
        stack = HStack(
            [
                RecordingBox("a", Size(20, 10)),
                RecordingBox("b", Size(30, 40)),
            ],
            gap=7,
        )

        self.assertEqual(stack.measure(RenderContext(), Constraints()), Size(57, 40))

    def test_hstack_fill_splits_remainder_after_fixed_fraction_and_gaps(self) -> None:
        children = [
            RecordingBox("fixed", Size(0, 10), width=Fixed(30)),
            RecordingBox("fraction", Size(0, 10), width=Fraction(0.2)),
            RecordingBox("fill-a", Size(0, 10), width=Fill()),
            RecordingBox("fill-b", Size(0, 10), width=Fill()),
        ]
        stack = HStack(children, gap=10, align="stretch")

        stack.render(RenderContext(), Image.new("RGBA", (200, 50)), Rect(0, 0, 200, 50))

        self.assertEqual(
            [render for child in children for render in child.renders],
            [
                ("fixed", Rect(0, 0, 30, 50)),
                ("fraction", Rect(40, 0, 34, 50)),
                ("fill-a", Rect(84, 0, 53, 50)),
                ("fill-b", Rect(147, 0, 53, 50)),
            ],
        )

    def test_stack_wrapper_propagates_fill_axis_from_child(self) -> None:
        left = RecordingBox("left", Size(0, 0), width=Fraction(0.35), height=Fill())
        right = RecordingBox("right", Size(0, 0), width=Fill(), height=Fill())
        stack = HStack([left, VStack([right])], gap=24, align="stretch")

        self.assertEqual(
            stack.measure(RenderContext(), Constraints(max_width=836, max_height=296)),
            Size(836, 296),
        )

        stack.render(
            RenderContext(), Image.new("RGBA", (836, 296)), Rect(0, 0, 836, 296)
        )

        self.assertEqual(left.renders, [("left", Rect(0, 0, 284, 296))])
        self.assertEqual(right.renders, [("right", Rect(308, 0, 528, 296))])

    def test_hstack_center_aligns_children_on_cross_axis(self) -> None:
        child = RecordingBox("child", Size(20, 10))

        HStack([child], align="center").render(
            RenderContext(),
            Image.new("RGBA", (100, 50)),
            Rect(0, 0, 100, 50),
        )

        self.assertEqual(child.renders, [("child", Rect(0, 20, 20, 10))])

    def test_vstack_fill_splits_remainder_after_fixed_fraction_and_gaps(self) -> None:
        children = [
            RecordingBox("fixed", Size(10, 0), height=Fixed(30)),
            RecordingBox("fraction", Size(10, 0), height=Fraction(0.2)),
            RecordingBox("fill-a", Size(10, 0), height=Fill()),
            RecordingBox("fill-b", Size(10, 0), height=Fill()),
        ]
        stack = VStack(children, gap=10, align="stretch")

        stack.render(RenderContext(), Image.new("RGBA", (50, 200)), Rect(0, 0, 50, 200))

        self.assertEqual(
            [render for child in children for render in child.renders],
            [
                ("fixed", Rect(0, 0, 50, 30)),
                ("fraction", Rect(0, 40, 50, 34)),
                ("fill-a", Rect(0, 84, 50, 53)),
                ("fill-b", Rect(0, 147, 50, 53)),
            ],
        )

    def test_vstack_end_aligns_children_on_cross_axis(self) -> None:
        child = RecordingBox("child", Size(20, 10))

        VStack([child], align="end").render(
            RenderContext(),
            Image.new("RGBA", (100, 50)),
            Rect(0, 0, 100, 50),
        )

        self.assertEqual(child.renders, [("child", Rect(80, 0, 20, 10))])

    def test_fill_and_fraction_require_bounded_stack_axis(self) -> None:
        with self.assertRaises(LayoutError):
            HStack([RecordingBox("fill", Size(10, 10), width=Fill())]).measure(
                RenderContext(),
                Constraints(),
            )
        with self.assertRaises(LayoutError):
            VStack(
                [RecordingBox("fraction", Size(10, 10), height=Fraction(0.5))]
            ).measure(
                RenderContext(),
                Constraints(),
            )


class GridLayoutTest(unittest.TestCase):
    def test_grid_resolves_fixed_fraction_fill_tracks_and_tuple_gaps(self) -> None:
        children = [RecordingBox(str(index), Size(1, 1)) for index in range(6)]
        grid = Grid(
            columns=[Fixed(20), Fraction(0.5), Fill()],
            rows=[Fixed(10), Fill()],
            gap=(5, 7),
            children=children,
        )

        self.assertEqual(
            grid.measure(RenderContext(), Constraints(max_width=100, max_height=50)),
            Size(100, 50),
        )
        grid.render(RenderContext(), Image.new("RGBA", (100, 50)), Rect(0, 0, 100, 50))

        self.assertEqual(
            [render for child in children for render in child.renders],
            [
                ("0", Rect(0, 0, 20, 10)),
                ("1", Rect(25, 0, 45, 10)),
                ("2", Rect(75, 0, 25, 10)),
                ("3", Rect(0, 17, 20, 33)),
                ("4", Rect(25, 17, 45, 33)),
                ("5", Rect(75, 17, 25, 33)),
            ],
        )

    def test_grid_fit_tracks_use_max_intrinsic_size_per_column_and_row(self) -> None:
        grid = Grid(
            columns=2,
            gap=(5, 3),
            children=[
                RecordingBox("0", Size(10, 5)),
                RecordingBox("1", Size(30, 7)),
                RecordingBox("2", Size(20, 11)),
                RecordingBox("3", Size(15, 13)),
            ],
        )

        self.assertEqual(grid.measure(RenderContext(), Constraints()), Size(55, 23))

    def test_grid_requires_at_least_one_column(self) -> None:
        with self.assertRaises(LayoutError):
            Grid(columns=0).measure(RenderContext(), Constraints())

    def test_grid_fill_tracks_require_bounded_axis(self) -> None:
        with self.assertRaises(LayoutError):
            Grid(
                columns=[Fill()], children=[RecordingBox("child", Size(1, 1))]
            ).measure(
                RenderContext(),
                Constraints(),
            )


class OverlayLayoutTest(unittest.TestCase):
    def test_overlay_measures_max_child_size(self) -> None:
        overlay = Overlay(
            [
                RecordingBox("a", Size(30, 10)),
                RecordingBox("b", Size(20, 40)),
            ]
        )

        self.assertEqual(overlay.measure(RenderContext(), Constraints()), Size(30, 40))

    def test_overlay_aligns_each_child_inside_same_rect(self) -> None:
        children = [
            RecordingBox("a", Size(30, 10)),
            RecordingBox("b", Size(20, 40)),
        ]

        Overlay(children, align_x="end", align_y="center").render(
            RenderContext(),
            Image.new("RGBA", (100, 60)),
            Rect(0, 0, 100, 60),
        )

        self.assertEqual(
            [render for child in children for render in child.renders],
            [
                ("a", Rect(70, 25, 30, 10)),
                ("b", Rect(80, 10, 20, 40)),
            ],
        )

    def test_overlay_stretches_children_when_requested(self) -> None:
        child = RecordingBox("child", Size(30, 10))

        Overlay([child], align_x="stretch", align_y="stretch").render(
            RenderContext(),
            Image.new("RGBA", (100, 60)),
            Rect(0, 0, 100, 60),
        )

        self.assertEqual(child.renders, [("child", Rect(0, 0, 100, 60))])


if __name__ == "__main__":
    unittest.main()
