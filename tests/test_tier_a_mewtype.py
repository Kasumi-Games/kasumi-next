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
from plugins.render.core import Rect
from plugins.render.core import RenderContext
from plugins.render.core import Size
from plugins.render.kits import KITS
from plugins.render.kits.mewtype import MewtypeKit
from plugins.render.kits.mewtype import MewtypePanel

IDENTITY = PlayerIdentity(nickname="梦限大", level=42)
ART = Image.new("RGBA", (96, 128), (110, 180, 240, 255))
AVATAR = Image.new("RGBA", (128, 128), (255, 178, 216, 255))
FRAME = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
TITLE = Image.new("RGBA", (180, 36), (190, 105, 229, 255))
PULLS = [
    PullRevealItem(
        name=f"结果 {index + 1}",
        rarity=6 if index == 7 else 3 + index % 3,
        is_new=index % 3 == 0,
        featured=index == 7,
        image=ART if index % 2 else None,
        note="盆栽 +12" if index == 7 else "",
    )
    for index in range(10)
]


class MewtypeRegistrationTest(unittest.TestCase):
    def test_registered_in_kits(self) -> None:
        self.assertIs(KITS["mewtype"], MewtypeKit)

    def test_all_three_tier_a_surfaces_are_bespoke(self) -> None:
        for surface in ("game_identity", "player_card", "pull_reveal"):
            with self.subTest(surface=surface):
                self.assertIsNot(
                    getattr(MewtypeKit, surface),
                    getattr(BaseKit, surface),
                )


class MewtypeSurfaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kit = MewtypeKit()
        self.ctx = RenderContext()
        self.constraints = Constraints(max_width=cards.CONTENT_WIDTH, max_height=4000)

    def test_game_identity_dispatches_to_punched_strip(self) -> None:
        strip = cards.game_identity(
            self.kit,
            IDENTITY,
            width=cards.CONTENT_WIDTH,
            detail="押注 120 Pt",
        )
        size = strip.measure(self.ctx, self.constraints)
        self.assertEqual(size.height, 82)
        self.assertEqual(type(strip).__name__, "MewtypePanel")
        self.assertIsNone(strip.radius)

    def test_game_identity_prioritises_name_when_narrow(self) -> None:
        wide = _collect_text(
            cards.game_identity(
                self.kit,
                IDENTITY,
                width=cards.CONTENT_WIDTH,
                detail="押注 120 Pt",
            )
        )
        self.assertIn("梦限大", wide)
        self.assertIn("Lv.42", wide)
        self.assertIn("押注 120 Pt", wide)

        squeezed = _collect_text(
            cards.game_identity(
                self.kit,
                IDENTITY,
                width=360,
                detail="押注 120 Pt",
            )
        )
        self.assertIn("梦限大", squeezed)
        self.assertNotIn("Lv.42", squeezed)
        self.assertIn("押注 120 Pt", squeezed)

        tiny = _collect_text(
            cards.game_identity(
                self.kit,
                IDENTITY,
                width=220,
                detail="押注 120 Pt",
            )
        )
        self.assertIn("梦限大", tiny)
        self.assertNotIn("Lv.42", tiny)
        self.assertNotIn("押注 120 Pt", tiny)

    def test_game_identity_handles_missing_optional_data(self) -> None:
        strip = cards.game_identity(
            self.kit,
            PlayerIdentity(nickname="梦"),
            width=220,
        )
        self.assertGreater(strip.measure(self.ctx, self.constraints).width, 0)

    def test_player_card_handles_every_cosmetic_slot(self) -> None:
        identity = PlayerIdentity(nickname="梦限大", level=42, avatar=AVATAR)
        card = cards.player_card(
            self.kit,
            identity,
            current_pt=1240,
            description="音が止んでも、あらがえ。",
            frame_image=FRAME,
            title1_image=TITLE,
            title2_image=TITLE,
            standing_art=ART,
        )
        size = card.measure(self.ctx, self.constraints)
        self.assertEqual((size.width, size.height), (cards.CONTENT_WIDTH, 420))
        self.assertEqual(type(card).__name__, "MewtypePanel")
        texts = _collect_text(card)
        for expected in ("梦限大", "Lv.42", "1,240", "音が止んでも、あらがえ。"):
            self.assertIn(expected, texts)

    def test_player_card_handles_empty_profile_and_avatar(self) -> None:
        card = cards.player_card(
            self.kit,
            PlayerIdentity(nickname="梦", level=0),
            current_pt=0,
            description="",
        )
        self.assertGreater(card.measure(self.ctx, self.constraints).height, 0)
        self.assertIn("这个人还没有写简介。", _collect_text(card))

    def test_profile_description_color_is_stable_when_empty(self) -> None:
        populated = cards.player_card(
            self.kit,
            IDENTITY,
            current_pt=1240,
            description="这是一段简介。",
        )
        empty = cards.player_card(
            self.kit,
            IDENTITY,
            current_pt=1240,
            description="",
        )
        self.assertEqual(_text_color(populated, "这是一段简介。"), self.kit.text_color)
        self.assertEqual(
            _text_color(empty, "这个人还没有写简介。"),
            self.kit.text_color,
        )

    def test_article_header_is_not_an_offset_panel(self) -> None:
        heading = self.kit.article_header("签到成功", width=cards.CONTENT_WIDTH)
        self.assertEqual(type(heading).__name__, "MewtypeArticleHeader")
        self.assertEqual(_collect_text(heading), ["签到成功"])

    def test_ordinary_mixed_copy_stays_in_one_chinese_font(self) -> None:
        body = self.kit.text("邮箱 MAILBOX 1200", font_size=20)
        article = self.kit.article_header("收件箱", width=cards.CONTENT_WIDTH)
        article_text = _find_text_node(article, "收件箱")

        self.assertEqual(Path(body.font).name, "ResourceHanRoundedCN-Medium.ttf")
        self.assertEqual(body.letter_spacing, 1)
        self.assertEqual(
            Path(article_text.font).name,
            "ResourceHanRoundedCN-Bold.ttf",
        )

        loaded = body._load_font(20)
        self.assertEqual(loaded.letter_spacing, 1)
        self.assertFalse(hasattr(loaded, "latin"))

    def test_site_latin_face_is_opt_in_for_display_tokens(self) -> None:
        level = self.kit.text("Lv.42", font_size=20, font="display")
        points = self.kit.text("1,240 Pt", font_size=20, font="display")
        wordmark = self.kit.page_title("邮箱")

        self.assertEqual(Path(level.font).name, "Montserrat-ExtraBold.ttf")
        self.assertEqual(Path(points.font).name, "Montserrat-ExtraBold.ttf")
        self.assertEqual(Path(wordmark.font).name, "MPLUSRounded1c-Medium.ttf")
        self.assertLess(wordmark.face_weight, 3)

    def test_compact_article_header_does_not_crop_chinese_descenders(self) -> None:
        header = self.kit.article_header(
            "游戏", detail="3 项", width=400, height=45, font_size=22
        )
        canvas = Image.new("RGBA", (400, 45), (0, 0, 0, 0))
        header.render(RenderContext(pixel_ratio=1), canvas, Rect(0, 0, 400, 45))

        white = Image.new("L", canvas.size, 0)
        source = canvas.load()
        target = white.load()
        for y in range(canvas.height):
            for x in range(canvas.width):
                red, green, blue, _alpha = source[x, y]
                if red > 180 and green > 180 and blue > 180:
                    target[x, y] = 255
        bbox = white.getbbox()
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(bbox[3] - bbox[1], 20)

    def test_mewtype_text_centres_visible_glyphs_inside_the_line_box(self) -> None:
        text = self.kit.text(
            "梦", font_size=48, line_height=64, wrap=False, max_lines=1
        )
        canvas = Image.new("RGBA", (80, 64), (0, 0, 0, 0))
        text.render(RenderContext(pixel_ratio=1), canvas, Rect(0, 0, 80, 64))
        bbox = canvas.getchannel("A").getbbox()

        self.assertIsNotNone(bbox)
        top_margin = bbox[1]
        bottom_margin = canvas.height - bbox[3]
        self.assertLessEqual(abs(top_margin - bottom_margin), 2)

    def test_separator_uses_the_theme_cyan_without_muting(self) -> None:
        separator = self.kit.separator(length=100)

        self.assertEqual(separator.color, self.kit.primary)
        self.assertEqual(separator.thickness, 2)

    def test_offset_pill_centres_child_inside_the_upper_face(self) -> None:
        recorder = _RectRecorder()
        panel = MewtypePanel(
            recorder,
            width=100,
            height=40,
            radius=8,
            frame_offset=4,
        )
        canvas = Image.new("RGBA", (120, 60), (0, 0, 0, 0))
        panel.render(self.ctx, canvas, Rect(10, 8, 100, 40))

        self.assertEqual(recorder.rect, Rect(10, 8, 96, 36))

    def test_wordmark_translates_known_chinese_titles(self) -> None:
        self.assertEqual(self.kit.page_title("资料").text, "PROFILE")
        self.assertEqual(self.kit.page_title("一笔画").text, "ONE STROKE")
        self.assertEqual(self.kit.page_title("黑香澄").text, "BLACKKASUMI")

    def test_subtitle_context_is_integrated_into_the_secondary_header(self) -> None:
        page = cards.card_page(
            self.kit,
            title="邮箱",
            subtitle="星之鼓动",
            article_title="收件箱",
            body=cards.empty_state(self.kit, "空"),
        )
        header = page.child.children[0]

        self.assertEqual(_text_color(header, "星之鼓动"), (255, 255, 255, 255))
        self.assertNotEqual(_text_color(header, "星之鼓动"), self.kit.accent)

    def test_blackkasumi_calls_the_house_kasumi(self) -> None:
        from plugins.blackjack.render import BlackjackRenderer

        renderer = object.__new__(BlackjackRenderer)
        renderer.kit = self.kit
        label = renderer._hand_label("Kasumi", "共 17 点", (0, 0, 0, 255))

        self.assertIn("KASUMI · 共 17 点", _collect_text(label))
        self.assertNotIn("DEALER · 共 17 点", _collect_text(label))

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

    def test_pull_tiles_reserve_uniform_art_and_note_rows(self) -> None:
        with_note = self.kit._pull_tile(
            PULLS[7],
            134,
            308,
            art_slot=True,
        )
        without = self.kit._pull_tile(
            PULLS[0],
            134,
            308,
            art_slot=True,
        )
        self.assertEqual(
            with_note.measure(self.ctx, self.constraints).height,
            without.measure(self.ctx, self.constraints).height,
        )
        self.assertEqual(with_note.frame_color, self.kit.accent)
        self.assertEqual(without.frame_color, self.kit.primary)

    def test_full_pages_are_deterministic(self) -> None:
        def render():
            return cards.response_card(
                self.kit,
                title="梦限大",
                body=cards.player_card(
                    self.kit,
                    IDENTITY,
                    current_pt=1240,
                    description="音が止んでも、あらがえ。",
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


def _text_color(component, target: str):
    stack = [component]
    while stack:
        node = stack.pop()
        if getattr(node, "text", None) == target:
            return getattr(node, "color", None)
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                stack.append(value)
    raise AssertionError(f"Text not found: {target}")


def _find_text_node(component, target: str):
    stack = [component]
    while stack:
        node = stack.pop()
        if getattr(node, "text", None) == target:
            return node
        for attribute in ("children", "child"):
            value = getattr(node, attribute, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                stack.extend(value)
            else:
                stack.append(value)
    raise AssertionError(f"Text not found: {target}")


class _RectRecorder:
    def __init__(self) -> None:
        self.rect = None

    def measure(self, ctx, constraints) -> Size:
        return constraints.clamp(Size(1, 1))

    def render(self, ctx, canvas, rect) -> None:
        self.rect = rect


if __name__ == "__main__":
    unittest.main()
