"""Correctness and work-count guards for render optimizations."""

import io
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from plugins.render import Size
from plugins.render import Constraints
from plugins.render import RenderContext
from plugins.render.kits.atoms import KitText
from plugins.render.kits.fonts import CHINESE_FONT
from plugins.render.primitives import load_font


def test_tracked_text_layout_reuses_glyph_metrics(monkeypatch):
    """Cold mixed-CJK wrapping must not reload each glyph for every substring."""
    font = load_font(24, CHINESE_FONT)
    original = font.getbbox
    calls = 0

    def measured(text, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(text, *args, **kwargs)

    monkeypatch.setattr(font, "getbbox", measured)
    component = KitText(
        "星光舞台 Stage 123。" * 4,
        font=CHINESE_FONT,
        font_size=24,
        letter_spacing=2,
    )
    size = component.measure(RenderContext(pixel_ratio=1), Constraints(max_width=180))
    assert size.height > 24
    assert calls < 500, f"cold wrapping loaded {calls} glyph metric boxes"


def test_raster_cache_owns_outputs_and_evicts_by_bytes():
    from plugins.render.raster_cache import RasterCache

    cache = RasterCache(max_bytes=32, max_items=10)
    calls = []

    def make():
        calls.append(1)
        return Image.new("RGBA", (2, 2), (1, 2, 3, 4))

    first = cache.get_or_create("a", make)
    first.putpixel((0, 0), (9, 9, 9, 9))
    first.close()
    assert cache.get_or_create("a", make).getpixel((0, 0)) == (1, 2, 3, 4)
    assert len(calls) == 1
    cache.get_or_create("b", make)
    cache.get_or_create("a", make)  # a is now most recently used.
    cache.get_or_create("c", make)  # b must be evicted, despite the item cap.
    cache.get_or_create("a", make)
    assert len(calls) == 3
    cache.get_or_create("b", make)
    assert len(calls) == 4
    assert cache.bytes_used <= 32


def test_oversized_rasters_do_not_evict_useful_entries():
    from plugins.render.raster_cache import RasterCache

    cache = RasterCache(max_bytes=16)
    calls = []

    def small():
        calls.append(1)
        return Image.new("RGBA", (2, 2))

    cache.get_or_create("small", small)
    for _ in range(2):
        cache.get_or_create("large", lambda: Image.new("RGBA", (3, 3)))
    cache.get_or_create("small", small)
    assert len(calls) == 1
    assert cache.bytes_used == 16


def test_raster_cache_worker_outputs_are_independent():
    from plugins.render.raster_cache import RasterCache

    cache = RasterCache(max_bytes=1024)

    def worker(index):
        image = cache.get_or_create("shared", lambda: Image.new("RGBA", (4, 4)))
        image.putpixel((0, 0), (index, 0, 0, 255))
        return image.getpixel((0, 0))

    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(worker, range(32)))
    assert result == [(index, 0, 0, 255) for index in range(32)]
    assert cache.get_or_create("shared", lambda: None).getpixel((0, 0)) == (0, 0, 0, 0)


def test_seeded_background_cache_preserves_scale_seed_and_canvas_ownership():
    from plugins.render.kits.sakura.components import SakuraBackground

    size = Size(240, 180)
    for ratio in (1, 2):
        context = RenderContext(pixel_ratio=ratio).activate_pixel_ratio()
        for seed in (2, 3):
            background = SakuraBackground(random_seed=seed)
            expected = SakuraBackground.render.__wrapped__(background, context, size)
            first = background.render(context, size)
            assert first.tobytes() == expected.tobytes()
            first.paste((0, 0, 0, 0), (0, 0, size.width, size.height))
            first.close()
            assert background.render(context, size).tobytes() == expected.tobytes()


def test_backgrounds_with_no_seed_or_unhashable_parameters_bypass_cache():
    from plugins.render.raster_cache import cached_background

    calls = []

    class Background:
        random_seed = None

        @cached_background
        def render(self, ctx, size):
            calls.append(1)
            return Image.new("RGBA", (size.width, size.height))

    class UnhashableBackground(Background):
        random_seed = 1
        __hash__ = None

    for background in (Background(), UnhashableBackground()):
        for _ in range(2):
            background.render(RenderContext(), Size(8, 8))
    assert len(calls) == 4


def test_image_background_does_not_cache_mutable_source_images():
    from plugins.render.kits.bangdream.backgrounds import BanGDreamImageBackground

    source = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    background = BanGDreamImageBackground(
        source=source,
        brightness_add=0,
        triangle_size=0,
        blur_radius=0,
        star_density=0,
        text="",
    )
    context, size = RenderContext(), Size(32, 32)
    first = background.render(context, size)
    source.paste((0, 0, 255, 255), (0, 0, 16, 16))
    second = background.render(context, size)
    assert first.getpixel((0, 0)) == (255, 0, 0, 255)
    assert second.getpixel((0, 0)) == (0, 0, 255, 255)


def test_outgoing_png_preserves_opaque_and_translucent_pixels():
    import base64

    from utils.images import image_bytes
    from utils.images import image_segment

    for alpha in (255, 0, 127):
        source = Image.new("RGBA", (32, 16), (21, 34, 55, alpha))
        source.putpixel((4, 5), (255, 0, 128, 255))
        encoded = image_bytes(source)
        segment = image_segment(source)
        segment_bytes = base64.b64decode(segment.data["src"].split(",", 1)[1])
        for payload in (encoded, segment_bytes):
            with Image.open(io.BytesIO(payload)) as decoded:
                assert decoded.convert("RGBA").tobytes() == source.tobytes()
        assert source.mode == "RGBA"
        assert source.getpixel((0, 0)) == (21, 34, 55, alpha)
