import sys
import time
import asyncio
import unittest
import threading
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import theming
from utils.images import image_bytes
from utils.images import image_segment
from utils.images import render_image_segment
from utils.image_tasks import IMAGE_WORKERS
from utils.image_tasks import run_image_task
from plugins.render.kit import BaseKit
from plugins.render.kits import KITS
from plugins.render.kits import KIT_DISPLAY_NAMES
from plugins.render.kits.minimal import MinimalKit
from plugins.render.kits.bangdream import BanGDreamKit


class _Item:
    """Stand-in for an inventory Item row."""

    def __init__(self, item_id="theme_x", metadata_json='{"kit": "neon"}'):
        self.item_id = item_id
        self.metadata_json = metadata_json


class ThemingCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        theming.invalidate_catalog()
        with theming._lock:
            theming._resolved.clear()
            theming._broken_kits.clear()

    def test_no_equipped_theme_resolves_to_default(self) -> None:
        with mock.patch.object(
            theming, "_resolve_kit_name", return_value=("bangdream", 120.0)
        ):
            self.assertIsInstance(theming.kit_for_user("u1"), BanGDreamKit)

    def test_equipped_theme_resolves_to_its_kit(self) -> None:
        with mock.patch.object(theming, "_resolve_kit_name", return_value=("neon", 120.0)):
            kit = theming.kit_for_user("u1")
        self.assertIs(type(kit), KITS["neon"])

    def test_result_is_cached_so_a_burst_hits_the_db_once(self) -> None:
        resolver = mock.Mock(return_value=("manga", 120.0))
        with mock.patch.object(theming, "_resolve_kit_name", resolver):
            for _ in range(10):
                theming.kit_for_user("u1")
        self.assertEqual(resolver.call_count, 1)

    def test_invalidate_user_forces_a_re_resolve(self) -> None:
        resolver = mock.Mock(return_value=("manga", 120.0))
        with mock.patch.object(theming, "_resolve_kit_name", resolver):
            theming.kit_for_user("u1")
            theming.invalidate_user("u1")
            theming.kit_for_user("u1")
        self.assertEqual(resolver.call_count, 2)

    def test_expired_entry_is_re_resolved(self) -> None:
        resolver = mock.Mock(return_value=("manga", -1.0))  # already expired
        with mock.patch.object(theming, "_resolve_kit_name", resolver):
            theming.kit_for_user("u1")
            theming.kit_for_user("u1")
        self.assertEqual(resolver.call_count, 2)

    def test_cache_is_bounded(self) -> None:
        with mock.patch.object(theming, "_resolve_kit_name", return_value=("neon", 120.0)):
            for index in range(theming._MAX_CACHED_USERS + 50):
                theming.kit_for_user(f"user{index}")
        self.assertLessEqual(len(theming._resolved), theming._MAX_CACHED_USERS)

    def test_kits_are_shared_singletons(self) -> None:
        self.assertIs(theming.kit_by_name("neon"), theming.kit_by_name("neon"))


class ThemingRobustnessTest(unittest.TestCase):
    def setUp(self) -> None:
        with theming._lock:
            theming._resolved.clear()
            theming._broken_kits.clear()
            theming._instances.clear()

    def test_kit_for_user_never_raises_when_resolution_explodes(self) -> None:
        with mock.patch.object(theming, "_resolve_kit_name", side_effect=RuntimeError("db is on fire")):
            kit = theming.kit_for_user("u1")
        self.assertIsInstance(kit, BaseKit)

    def test_kit_for_user_never_raises_when_inventory_import_fails(self) -> None:
        with mock.patch.dict(sys.modules, {"plugins.inventory.service": None}):
            name, ttl = theming._resolve_kit_name("u1")
        self.assertEqual(name, theming.DEFAULT_KIT_NAME)
        self.assertEqual(ttl, theming._NEGATIVE_TTL_SECONDS)

    def test_inventory_failure_uses_the_short_negative_ttl(self) -> None:
        # A sick database must not be cached for the full two minutes.
        with mock.patch("plugins.inventory.service.get_equipped", side_effect=RuntimeError):
            name, ttl = theming._resolve_kit_name("u1")
        self.assertEqual(name, theming.DEFAULT_KIT_NAME)
        self.assertEqual(ttl, theming._NEGATIVE_TTL_SECONDS)

    def test_unknown_kit_name_falls_back_to_default(self) -> None:
        self.assertIsInstance(theming.kit_by_name("no-such-kit"), BanGDreamKit)

    def test_broken_default_falls_through_to_minimal(self) -> None:
        # bangdream loads fonts and a background PNG from disk, so a partial
        # deploy can take it out; minimal has no file dependencies.
        broken = mock.Mock(side_effect=OSError("missing font"))
        with mock.patch.dict(KITS, {"bangdream": broken}):
            kit = theming.kit_by_name("bangdream")
        self.assertIsInstance(kit, MinimalKit)

    def test_a_broken_kit_is_only_tried_once_per_process(self) -> None:
        broken = mock.Mock(side_effect=OSError("missing font"))
        with mock.patch.dict(KITS, {"bangdream": broken}):
            theming.kit_by_name("bangdream")
            theming.kit_by_name("bangdream")
        self.assertEqual(broken.call_count, 1)

    def test_resolution_never_writes(self) -> None:
        equipped = mock.Mock(return_value={})
        with mock.patch("plugins.inventory.service.get_equipped", equipped):
            with mock.patch("plugins.inventory.service.grant_item") as grant:
                with mock.patch("plugins.inventory.service.set_quantity") as put:
                    theming._resolve_kit_name("u1")
        grant.assert_not_called()
        put.assert_not_called()


class ThemeMetadataTest(unittest.TestCase):
    def test_kit_name_read_from_metadata(self) -> None:
        self.assertEqual(theming.kit_name_for_item(_Item()), "neon")

    def test_unparseable_metadata_returns_none(self) -> None:
        self.assertIsNone(theming.kit_name_for_item(_Item(metadata_json="{oops")))

    def test_missing_kit_key_returns_none(self) -> None:
        self.assertIsNone(theming.kit_name_for_item(_Item(metadata_json="{}")))

    def test_unknown_kit_returns_none(self) -> None:
        self.assertIsNone(
            theming.kit_name_for_item(_Item(metadata_json='{"kit": "vaporwave"}'))
        )

    def test_non_dict_metadata_returns_none(self) -> None:
        self.assertIsNone(theming.kit_name_for_item(_Item(metadata_json="[1,2]")))

    def test_kit_name_of_round_trips_every_kit(self) -> None:
        for name, factory in KITS.items():
            with self.subTest(kit=name):
                self.assertEqual(theming.kit_name_of(factory()), name)


class ThemeCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        theming.invalidate_catalog()

    def test_shipped_catalog_has_no_theme_problems(self) -> None:
        self.assertEqual(theming.validate_theme_catalog(), [])

    def test_catalog_path_matches_the_one_inventory_loads(self) -> None:
        # theming reads items.json directly to stay usable without a live
        # NoneBot; this guards against the two paths drifting apart.
        from plugins.inventory.catalog import CATALOG_PATH

        self.assertEqual(theming.CATALOG_PATH, CATALOG_PATH)

    def test_catalog_reading_needs_no_plugin_import(self) -> None:
        with mock.patch.dict(sys.modules, {"plugins.inventory.catalog": None}):
            theming.invalidate_catalog()
            self.assertEqual(theming.validate_theme_catalog(), [])
            self.assertIn("sailing", theming.all_themes())

    def test_every_kit_has_a_display_name(self) -> None:
        self.assertEqual(set(KIT_DISPLAY_NAMES), set(KITS))

    def test_theme_index_maps_kits_to_items(self) -> None:
        themes = theming.all_themes()
        for kit_name, info in themes.items():
            with self.subTest(kit=kit_name):
                self.assertIn(kit_name, KITS)
                self.assertEqual(info.kit_name, kit_name)

    def test_theme_by_token_accepts_kit_name_item_id_and_display_name(self) -> None:
        themes = theming.all_themes()
        if not themes:
            self.skipTest("no theme items in the catalog yet")
        info = next(iter(themes.values()))
        for token in (info.kit_name, info.item_id, info.name):
            with self.subTest(token=token):
                self.assertEqual(theming.theme_by_token(token), info)

    def test_theme_by_token_rejects_junk(self) -> None:
        self.assertIsNone(theming.theme_by_token("  "))
        self.assertIsNone(theming.theme_by_token("definitely-not-a-theme"))

    def test_unclaimed_kits_are_reported_not_errors(self) -> None:
        # Kits may ship before the theme item that grants them; that is a
        # planning fact, not a catalog error.
        unclaimed = theming.unclaimed_kits()
        self.assertNotIn(unclaimed, ([None],))
        for name in unclaimed:
            self.assertIn(name, KITS)


class ImageHelperTest(unittest.TestCase):
    def test_image_bytes_are_png(self) -> None:
        data = image_bytes(Image.new("RGBA", (4, 4), (1, 2, 3, 255)))
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_image_segment_is_an_image_segment(self) -> None:
        # The satori adapter folds the mime type into a data URI rather than
        # keeping it as a separate key.
        segment = image_segment(Image.new("RGBA", (4, 4), (1, 2, 3, 255)))
        self.assertEqual(segment.type, "img")
        self.assertTrue(segment.data["src"].startswith("data:image/png"))

    def test_transparency_survives_encoding(self) -> None:
        source = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        import io

        decoded = Image.open(io.BytesIO(image_bytes(source)))
        self.assertEqual(decoded.mode, "RGBA")
        self.assertEqual(decoded.getpixel((0, 0))[3], 0)

    def test_plugin_helpers_delegate_to_the_shared_encoder(self) -> None:
        # These four call sites each carried their own copy of the encoder.
        from plugins.cck.draw import image_to_message as cck_encode
        from plugins.bang_avatar.utils import image_to_message as avatar_encode

        for encode in (cck_encode, avatar_encode):
            with self.subTest(encode=encode.__module__):
                segment = encode(Image.new("RGBA", (4, 4), (1, 2, 3, 255)))
                self.assertEqual(segment.type, "img")
                self.assertTrue(segment.data["src"].startswith("data:image/png"))


class AsyncImageHelperTest(unittest.IsolatedAsyncioTestCase):
    async def test_render_and_encoding_do_not_block_event_loop(self) -> None:
        def slow_renderer() -> Image.Image:
            time.sleep(0.1)
            return Image.new("RGBA", (4, 4), (1, 2, 3, 255))

        render_task = asyncio.create_task(render_image_segment(slow_renderer))
        await asyncio.sleep(0.02)

        self.assertFalse(render_task.done())
        segment = await render_task
        self.assertEqual(segment.type, "img")
        self.assertTrue(segment.data["src"].startswith("data:image/png"))

    async def test_image_bursts_have_bounded_concurrency(self) -> None:
        lock = threading.Lock()
        active = 0
        peak = 0

        def slow_image_work() -> None:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with lock:
                active -= 1

        await asyncio.gather(
            *(run_image_task(slow_image_work) for _ in range(IMAGE_WORKERS + 4))
        )

        self.assertLessEqual(peak, IMAGE_WORKERS)


if __name__ == "__main__":
    unittest.main()
