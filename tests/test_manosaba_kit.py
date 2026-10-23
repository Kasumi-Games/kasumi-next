"""Manosaba's asset provenance, narrow layouts and production dispatcher contract."""

import json
import hashlib
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from utils import cards
from utils.theming import all_themes
from utils.theming import kit_by_name
from plugins.render import Page
from plugins.render import Rect
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import AutoPage
from plugins.render import Constraints
from plugins.render import RenderContext
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.kits.atoms import KitText
from plugins.render.primitives import load_font
from plugins.render.text_layout import wrap_text
from plugins.render.kits.manosaba import ManosabaKit
from plugins.render.kits.manosaba.components import INK
from plugins.render.kits.manosaba.components import SURFACE
from plugins.render.kits.manosaba.components import RESOURCES
from plugins.render.kits.manosaba.components import ManosabaPanel


def render(component, width=784, ratio=1):
    return AutoPage(
        Frame(component, width=Fixed(width)), background=ManosabaKit().background()
    ).render(RenderContext(pixel_ratio=ratio))


def pulls(count, art=False):
    return [
        PullRevealItem(
            "带有长名字的证物 " + str(i),
            i % 6 + 1,
            is_new=i % 2 == 0,
            featured=i == 5,
            image=RESOURCES / "portrait_ema.png" if art and i % 2 == 0 else None,
            note="盆栽 +120" if i == 1 else "",
        )
        for i in range(count)
    ]


def test_registered_theme_is_resolved_from_catalog():
    assert isinstance(kit_by_name("manosaba"), ManosabaKit)
    theme = all_themes()["manosaba"]
    assert theme.item_id == "theme_manosaba"
    assert "魔女审判" in theme.aliases


def test_asset_manifest_matches_delivered_files():
    manifest = json.loads((RESOURCES / "manifest.json").read_text())
    assert manifest["extractor"].startswith("UnityPy ")
    assert manifest["steam_app_id"] == 3101040
    assert len(manifest["assets"]) == 18
    for entry in manifest["assets"]:
        path = RESOURCES / entry["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], entry[
            "file"
        ]
        if entry["type"] == "Sprite":
            with Image.open(path) as image:
                assert list(image.size) == entry["size"]


@pytest.mark.parametrize("count", range(1, 11))
@pytest.mark.parametrize("width", [200, 784, 1460])
def test_all_pull_counts_fit_real_width_and_keep_equal_rows(count, width):
    kit = ManosabaKit()
    component = cards.pull_reveal(kit, pulls(count, art=True), width=width)
    size = component.measure(RenderContext(), Constraints(max_width=width))
    assert size.width == width
    image = render(component, width)
    assert image.width == width
    assert image.height == size.height
    if count > 1:
        grid = component.child
        assert len(grid.children) == count
        heights = {
            tile.measure(RenderContext(), Constraints()).height
            for tile in grid.children
        }
        assert len(heights) == 1
        assert (
            sum(tile.width for tile in grid.children[: grid.columns])
            + grid.gap * (min(count, grid.columns) - 1)
            <= width
        )


@pytest.mark.parametrize("width", [200, 784])
@pytest.mark.parametrize("ratio", [1, 2])
def test_player_card_none_assets_long_description_and_fixed_tokens(width, ratio):
    component = cards.player_card(
        ManosabaKit(),
        PlayerIdentity("很长的昵称用于检查容器边界", 24),
        current_pt=1234567,
        description="证言与故事。" * 40,
        width=width,
    )
    image = render(component, width, ratio)
    assert image.size == (width, 420)


def test_identity_relinquishes_secondary_content_at_narrow_width():
    identity = PlayerIdentity("很长的玩家昵称", 42)
    component = cards.game_identity(
        ManosabaKit(), identity, width=200, detail="押注 120 Pt"
    )
    assert component.measure(RenderContext(), Constraints()).height == 80
    assert len(component.child.children) == 2
    assert render(component, 200).size == (200, 80)


def test_identity_equipped_frame_keeps_full_outer_geometry():
    identity = PlayerIdentity(
        "艾玛", 24, RESOURCES / "portrait_ema.png", RESOURCES / "diamond.png"
    )
    component = cards.game_identity(ManosabaKit(), identity, width=784)
    avatar = component.child.children[0]
    assert avatar.measure(RenderContext(), Constraints()).height == round(
        52 * 512 / 416
    )
    assert component.height - component.padding.vertical >= round(52 * 512 / 416)


def test_custom_panel_alpha_and_clipping():
    component = ManosabaPanel(
        ManosabaKit().text("很长的文字" * 50, font_size=30),
        padding=10,
        fill=(255, 255, 255, 90),
        border=(0, 0, 0, 0),
        ornate=False,
    )
    canvas = Image.new("RGBA", (300, 180), INK)
    component.render(RenderContext(), canvas, Rect(50, 40, 200, 80))
    assert canvas.getpixel((49, 50)) == INK
    assert canvas.getpixel((250, 50)) == INK
    assert canvas.getpixel((70, 121)) == INK
    assert canvas.getpixel((51, 41))[3] == 255


def test_deterministic_concurrent_high_resolution_renders():
    kit = ManosabaKit()
    component = kit.player_card(
        avatar_image=None,
        frame_image=None,
        title1_image=None,
        title2_image=None,
        nickname="艾玛",
        level=24,
        current_pt=2350,
        description="",
        width=784,
        height=420,
    )
    expected = render(component, ratio=2).tobytes()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(
            pool.map(lambda _: render(component, ratio=2).tobytes(), range(6))
        )
    assert all(result == expected for result in results)


def test_portrait_titles_and_frames_change_pixels_without_changing_card_size():
    kit = ManosabaKit()
    options = dict(
        avatar_image=None,
        frame_image=None,
        title1_image=None,
        title2_image=None,
        nickname="艾玛",
        level=24,
        current_pt=2350,
        description="",
        width=784,
        height=420,
    )
    plain = render(kit.player_card(**options))
    art = RESOURCES / "diamond.png"
    for key in (
        "avatar_image",
        "frame_image",
        "title1_image",
        "title2_image",
        "standing_art",
    ):
        changed = render(kit.player_card(**{**options, key: art}))
        assert changed.size == plain.size
        assert changed.tobytes() != plain.tobytes(), key


def test_choice_ribbon_and_title_survive_tiny_slots():
    kit = ManosabaKit()
    for component in (
        kit.choice("证言", width=1),
        kit.page_title("很长的标题"),
        kit.ornament(width=1),
    ):
        for ratio in (1, 2):
            image = Page(size=(1, 1), child=component).render(
                RenderContext(pixel_ratio=ratio)
            )
            assert image.size == (1, 1)


@pytest.mark.parametrize("ratio", [1, 2])
def test_fixed_choice_stays_narrow_inside_a_stretched_stack(ratio):
    component = VStack([ManosabaKit().choice("窄幅选项", width=300)], align="stretch")
    image = Page(size=(864, 80), child=component).render(
        RenderContext(pixel_ratio=ratio)
    )
    assert image.getbbox()[2] <= 301  # Allow the downsampling filter's one-pixel edge.
    assert image.crop((320, 0, 864, 80)).getbbox() is None


def test_rare_pull_has_additional_shape_and_both_statuses():
    kit = ManosabaKit()
    common = PullRevealItem("证物", 3, is_new=True, featured=True)
    ordinary = kit._pull_tile(common, 1, 200, 256, False)
    rare = kit._pull_tile(replace(common, rarity=6), 1, 200, 256, False)
    assert rare.weight > ordinary.weight
    assert rare.ornate and not ordinary.ornate
    labels = [
        getattr(getattr(row, "child", None), "text", "") for row in rare.child.children
    ]
    assert "初次获得" in labels and "本期精选" in labels


def test_shared_surface_text_contrast():
    def luminance(color):
        values = [c / 255 for c in color[:3]]
        values = [
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in values
        ]
        return sum(a * b for a, b in zip(values, (0.2126, 0.7152, 0.0722)))

    kit = ManosabaKit()
    for fg, bg in [(kit.text_color, SURFACE), (kit.primary, SURFACE), (SURFACE, INK)]:
        a, b = sorted([luminance(fg), luminance(bg)])
        assert (b + 0.05) / (a + 0.05) >= 4.5


@pytest.mark.parametrize("ratio", [1, 2])
@pytest.mark.parametrize(
    "value,font_size",
    [("乐器", 22), ("巡演", 22), ("赛季积分", 18), ("一笔画 - 竞速排行榜", 24)],
)
def test_intrinsic_text_keeps_all_glyphs_when_drawn_at_its_measured_size(
    value, font_size, ratio, monkeypatch
):
    """Exercise the fit-to-content Frames used in tour cells and profile stats."""
    labels = []
    original = KitText.render

    def record(self, ctx, canvas, rect):
        constraints = ctx.unscale_constraints(
            Constraints(max_width=rect.width, max_height=rect.height)
        )
        labels.extend(self._layout_text(constraints)[0])
        original(self, ctx, canvas, rect)

    monkeypatch.setattr(KitText, "render", record)
    render(Frame(ManosabaKit().text(value, font_size=font_size)), ratio=ratio)
    assert labels == [value]


@pytest.mark.parametrize("ratio", [1, 2])
@pytest.mark.parametrize(
    "message",
    [
        "现在没有可以抢的红包\n发一个就会出现在这里",
        "没有可领取的邮件\n3 封邮件都已领取过了",
    ],
)
def test_business_empty_states_preserve_both_complete_lines(
    message, ratio, monkeypatch
):
    labels = []
    original = KitText.render

    def record(self, ctx, canvas, rect):
        labels.extend(
            self._layout_text(
                ctx.unscale_constraints(
                    Constraints(max_width=rect.width, max_height=rect.height)
                )
            )[0]
        )
        original(self, ctx, canvas, rect)

    monkeypatch.setattr(KitText, "render", record)
    render(cards.empty_state(ManosabaKit(), message), ratio=ratio)
    assert labels == message.splitlines()


@pytest.mark.parametrize(
    "text,font_size,width",
    [
        ("户山香澄 抬头看，星星在跳动立绘", 32, 492),
        ("将原作的审判与图鉴视觉带入每一张卡片。", 26, 468),
    ],
)
def test_wrapping_avoids_one_character_final_lines(text, font_size, width):
    lines = wrap_text(text, load_font(font_size, ManosabaKit().text("").font), width)
    assert "".join(lines).replace(" ", "") == text.replace(" ", "")
    assert len(lines[-1].rstrip("。，！？")) > 1
