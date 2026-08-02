import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import cards
from plugins.render import Fill
from plugins.render import VStack
from plugins.render.core import Size
from plugins.render.core import Constraints
from plugins.render.core import RenderContext
from plugins.render.kits import KITS
from plugins.render.color import normalize_color

LADDER = [
    (1, "香澄", "1240"),
    (2, "有咲", "980"),
    (3, "沙绫", "870"),
    (7, "莉美", "410"),
]


def _relative_luminance(rgb) -> float:
    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(v) for v in rgb[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _composite(foreground, background):
    alpha = foreground[3] / 255
    return tuple(
        round(foreground[i] * alpha + background[i] * (1 - alpha)) for i in range(3)
    )


def _contrast(first, second) -> float:
    a, b = _relative_luminance(first), _relative_luminance(second)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def _sample_body(kit):
    return cards.panel_section(
        kit,
        VStack(
            [
                cards.stat_row(kit, "赛季积分", "1,240 Pt"),
                kit.separator(length=Fill()),
                cards.meter(kit, value=7, total=10),
                cards.ladder_rows(kit, LADDER, highlight="莉美"),
            ],
            gap=20,
            align="stretch",
        ),
    )


class EmphasisContrastTest(unittest.TestCase):
    """The rule the whole toolkit rests on, re-measured on every run."""

    def test_emphasis_clears_aa_in_every_kit(self) -> None:
        for name, factory in KITS.items():
            with self.subTest(kit=name):
                kit = factory()
                fill, on_fill = cards.emphasis(kit)
                base = _composite(normalize_color(kit.panel_fill), (128, 128, 128))
                ratio = _contrast(
                    _composite(normalize_color(fill), base),
                    _composite(normalize_color(on_fill), base),
                )
                self.assertGreaterEqual(ratio, 4.5, f"{name} emphasis is {ratio:.2f}:1")

    def test_emphasis_is_text_color_on_panel_fill(self) -> None:
        # The rule itself, stated directly. Note this cannot be expressed as
        # "differs from primary": manga is monochrome, so its primary and
        # text_color are deliberately the same ink.
        for name, factory in KITS.items():
            with self.subTest(kit=name):
                kit = factory()
                fill, on_fill = cards.emphasis(kit)
                self.assertEqual(normalize_color(fill), normalize_color(kit.text_color))
                self.assertEqual(
                    normalize_color(on_fill), normalize_color(kit.panel_fill)
                )

    def test_the_rejected_rule_really_does_fail(self) -> None:
        # Guards the reasoning behind emphasis(): if primary+white ever became
        # safe across all kits this test would fail and the rule could be
        # revisited. Today it fails in sakura, midnight, neon and bangdream.
        failures = []
        for name, factory in KITS.items():
            kit = factory()
            primary = getattr(kit, "primary", None)
            if primary is None:
                continue
            base = _composite(normalize_color(kit.panel_fill), (128, 128, 128))
            ratio = _contrast(
                _composite(normalize_color(primary), base), (255, 255, 255)
            )
            if ratio < 4.5:
                failures.append(name)
        self.assertTrue(
            failures, "primary+white now passes everywhere; revisit emphasis()"
        )


class ComponentTest(unittest.TestCase):
    def test_every_component_measures_in_every_kit(self) -> None:
        ctx = RenderContext()
        constraints = Constraints(max_width=cards.INNER_WIDTH, max_height=2000)
        for name, factory in KITS.items():
            kit = factory()
            components = {
                "badge": cards.badge(kit, "1"),
                "stat_row": cards.stat_row(kit, "标签", "值"),
                "meter": cards.meter(kit, value=3, total=10),
                "ladder_rows": cards.ladder_rows(kit, LADDER),
                "empty_state": cards.empty_state(kit, "空"),
            }
            for label, component in components.items():
                with self.subTest(kit=name, component=label):
                    size = component.measure(ctx, constraints)
                    self.assertIsInstance(size, Size)
                    self.assertGreater(size.width, 0)
                    self.assertGreater(size.height, 0)

    def test_meter_handles_degenerate_totals(self) -> None:
        kit = KITS["minimal"]()
        ctx = RenderContext()
        constraints = Constraints(max_width=cards.INNER_WIDTH, max_height=200)
        for value, total in ((0, 0), (5, 0), (-3, 10), (99, 10)):
            with self.subTest(value=value, total=total):
                meter = cards.meter(kit, value=value, total=total)
                self.assertGreater(meter.measure(ctx, constraints).height, 0)

    def test_meter_label_can_be_suppressed(self) -> None:
        kit = KITS["minimal"]()
        ctx = RenderContext()
        constraints = Constraints(max_width=cards.INNER_WIDTH, max_height=200)
        labelled = cards.meter(kit, value=5, total=10).measure(ctx, constraints)
        bare = cards.meter(kit, value=5, total=10, label="").measure(ctx, constraints)
        self.assertLess(bare.height, labelled.height)

    def test_ladder_rows_handles_empty_input(self) -> None:
        kit = KITS["minimal"]()
        rows = cards.ladder_rows(kit, [])
        size = rows.measure(RenderContext(), Constraints(max_width=cards.INNER_WIDTH))
        self.assertEqual(size.height, 0)

    def test_geometry_constants_are_consistent(self) -> None:
        self.assertEqual(
            cards.INNER_WIDTH, cards.CONTENT_WIDTH - cards.PANEL_PADDING * 2
        )


class SharedResultComponentTest(unittest.TestCase):
    """The Phase-1-leftover shared shapes: headline, gains, task, level-up."""

    def test_components_measure_in_every_kit(self) -> None:
        ctx = RenderContext()
        constraints = Constraints(max_width=cards.INNER_WIDTH, max_height=2000)
        for name, factory in KITS.items():
            kit = factory()
            components = {
                "headline_win": cards.headline(kit, "胜利"),
                "headline_loss": cards.headline(kit, "挑战失败", positive=False),
                "gain_rows": cards.gain_rows(
                    kit, [("+120 Pt", "探险收益"), ("+2 张", "星星贴纸")]
                ),
                "task_progress": cards.task_progress(kit, "游玩 3 局小游戏", 2, 3),
                "level_up": cards.level_up(kit, 41, 42),
            }
            for label, component in components.items():
                with self.subTest(kit=name, component=label):
                    size = component.measure(ctx, constraints)
                    self.assertGreater(size.height, 0)

    def test_win_and_loss_headlines_differ_by_shape(self) -> None:
        # Filled band vs plain text: distinguishable in the monochrome kit.
        kit = KITS["manga"]()
        win = cards.response_card(
            kit, title="A", body=cards.headline(kit, "胜利")
        )
        loss = cards.response_card(
            kit, title="A", body=cards.headline(kit, "胜利", positive=False)
        )
        self.assertNotEqual(win.tobytes(), loss.tobytes())

    def test_gain_rows_handles_empty(self) -> None:
        kit = KITS["minimal"]()
        size = cards.gain_rows(kit, []).measure(
            RenderContext(), Constraints(max_width=cards.INNER_WIDTH)
        )
        self.assertEqual(size.height, 0)


class CardPageTest(unittest.TestCase):
    def test_card_renders_in_every_kit_at_a_stable_width(self) -> None:
        widths = set()
        for name, factory in KITS.items():
            with self.subTest(kit=name):
                kit = factory()
                image = cards.response_card(
                    kit,
                    title="测试卡片",
                    subtitle="共享组件",
                    body=_sample_body(kit),
                    owner_name="香澄",
                )
                self.assertEqual(image.mode, "RGBA")
                self.assertGreater(image.height, 200)
                widths.add(image.width)
        # A fixed content column means every card is the same width, so grids
        # and side-by-side comparisons line up across plugins.
        self.assertEqual(len(widths), 1, f"cards disagree on width: {widths}")

    def test_card_renders_without_a_subtitle(self) -> None:
        for name, factory in KITS.items():
            with self.subTest(kit=name):
                kit = factory()
                image = cards.response_card(
                    kit, title="仅标题", body=cards.empty_state(kit, "空")
                )
                self.assertGreater(image.width, 0)

    def test_card_render_is_deterministic(self) -> None:
        kit = KITS["midnight"]()
        first = cards.response_card(kit, title="A", body=cards.empty_state(kit, "空"))
        second = cards.response_card(kit, title="A", body=cards.empty_state(kit, "空"))
        self.assertEqual(first.tobytes(), second.tobytes())

    async def _render_async(self, kit):
        return await cards.card_page(
            kit, title="异步", body=cards.empty_state(kit, "空")
        ).render_async()

    def test_card_page_exposes_async_render(self) -> None:
        import asyncio

        kit = KITS["fluent"]()
        image = asyncio.run(self._render_async(kit))
        self.assertGreater(image.width, 0)


class SignatureTest(unittest.TestCase):
    def test_signature_is_absent_for_kits_with_no_theme_item(self) -> None:
        # bangdream ships no theme item, so it must render no credit line.
        self.assertIsNone(cards.signature_for(KITS["bangdream"]()))

    def test_sakura_theme_never_renders_a_signature(self) -> None:
        # Sakura's petals and palette already identify it; the repeated
        # bottom-right 「谁谁的主题 · 樱色」 credit only adds visual clutter.
        self.assertIsNone(cards.signature_for(KITS["sakura"](), "香澄"))

    def test_signature_present_for_a_catalogued_theme(self) -> None:
        from utils import theming

        theming.invalidate_catalog()
        info = theming.all_themes().get("sailing")
        if info is None:
            self.skipTest("sailing theme is not in the catalog")
        signature = cards.signature_for(KITS["sailing"](), "香澄")
        self.assertIsNotNone(signature)

    def test_signature_survives_a_broken_theming_layer(self) -> None:
        from unittest import mock

        from utils import theming

        with mock.patch.object(theming, "theme_for_kit", side_effect=RuntimeError):
            self.assertIsNone(cards.signature_for(KITS["sailing"]()))


class TierADispatchTest(unittest.TestCase):
    """The bespoke-or-fallback dispatch that Tier A rests on."""

    def _identity(self):
        from plugins.render import PlayerIdentity

        return PlayerIdentity(nickname="香澄", level=42)

    def _pulls(self, count=10):
        from plugins.render import PullRevealItem

        rarities = [3, 3, 4, 3, 5, 3, 4, 6, 3, 4]
        return [
            PullRevealItem(
                name=f"占位 {i}",
                rarity=rarities[i % len(rarities)],
                is_new=i % 3 == 0,
                featured=rarities[i % len(rarities)] == 6,
                note="盆栽 +12" if i == 7 else "",
            )
            for i in range(count)
        ]

    def test_generic_fallbacks_render_in_every_kit(self) -> None:
        ctx = RenderContext()
        constraints = Constraints(max_width=cards.CONTENT_WIDTH, max_height=4000)
        for name, factory in KITS.items():
            kit = factory()
            surfaces = {
                "game_identity": cards.game_identity(
                    kit, self._identity(), width=cards.CONTENT_WIDTH, detail="押注 120 Pt"
                ),
                "player_card": cards.player_card(
                    kit, self._identity(), current_pt=1240, description="描述"
                ),
                "pull_reveal_10": cards.pull_reveal(kit, self._pulls(10)),
                "pull_reveal_1": cards.pull_reveal(kit, self._pulls(1)),
            }
            for label, component in surfaces.items():
                with self.subTest(kit=name, surface=label):
                    size = component.measure(ctx, constraints)
                    self.assertGreater(size.width, 0)
                    self.assertGreater(size.height, 0)

    def test_bespoke_override_wins_the_dispatch(self) -> None:
        from plugins.render import Fixed as FixedSize
        from plugins.render import Spacer
        from plugins.render.kits.minimal import MinimalKit

        marker = Spacer(width=FixedSize(7), height=FixedSize(7))

        class BespokeKit(MinimalKit):
            def game_identity(self, identity, *, width, detail=None):
                return marker

            def pull_reveal(self, pulls, *, width):
                return marker

        kit = BespokeKit()
        self.assertIs(
            cards.game_identity(kit, self._identity(), width=100), marker
        )
        self.assertIs(cards.pull_reveal(kit, self._pulls(3)), marker)

    def test_unimplemented_base_surface_never_reaches_the_caller(self) -> None:
        # Whether a kit has bespoke surfaces (bangdream) or not (the rest),
        # dispatch must never surface BaseKit's NotImplementedError.
        for name, factory in KITS.items():
            with self.subTest(kit=name):
                cards.game_identity(factory(), self._identity(), width=200)

    def test_avatar_or_initial_falls_back_to_first_character(self) -> None:
        component = cards.avatar_or_initial(KITS["minimal"](), self._identity())
        size = component.measure(
            RenderContext(), Constraints(max_width=200, max_height=200)
        )
        self.assertEqual((size.width, size.height), (56, 56))

    def test_reveal_tiles_are_uniform_height(self) -> None:
        # Mixed note/no-note pulls must not produce ragged grid rows.
        kit = KITS["minimal"]()
        ctx = RenderContext()
        constraints = Constraints(max_width=200, max_height=400)
        with_note = cards._reveal_tile(kit, self._pulls(10)[7], 134)
        without = cards._reveal_tile(kit, self._pulls(10)[0], 134)
        self.assertEqual(
            with_note.measure(ctx, constraints).height,
            without.measure(ctx, constraints).height,
        )


class IdentityHelperTest(unittest.TestCase):
    def test_identity_for_never_raises_when_sources_are_dead(self) -> None:
        from unittest import mock

        import plugins.monetary as monetary
        from utils import identity as identity_module

        # nickname dies at import; monetary dies at call time (patching
        # sys.modules alone cannot block `from plugins import monetary` once
        # the attribute is bound on the package).
        with mock.patch.dict(sys.modules, {"plugins.nickname": None}):
            with mock.patch.object(
                monetary, "get_level", side_effect=RuntimeError("db down")
            ):
                identity = identity_module.identity_for("1234567890")
        self.assertTrue(identity.nickname)
        self.assertIsNone(identity.level)

    def test_identity_fallback_nickname_uses_id_tail(self) -> None:
        from unittest import mock

        from utils import identity as identity_module

        with mock.patch.object(identity_module, "_nickname", wraps=identity_module._nickname):
            with mock.patch.dict(sys.modules, {"plugins.nickname": None}):
                identity = identity_module.identity_for("1234567890")
        self.assertEqual(identity.nickname, "玩家7890")


class KitAgnosticismTest(unittest.TestCase):
    def test_toolkit_never_calls_a_bangdream_only_helper_unguarded(self) -> None:
        source = Path(cards.__file__).read_text(encoding="utf-8")
        guarded = "isinstance(kit, BanGDreamKit)" in source
        for helper in ("title_pill", "board_frame", "titled_panel", "pill("):
            if helper in source:
                self.assertTrue(
                    guarded, f"{helper} used without an isinstance guard in utils/cards.py"
                )


if __name__ == "__main__":
    unittest.main()
