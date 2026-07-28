import io
import sys
import asyncio
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import avatar


def _png_bytes(color: tuple[int, int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (8, 8), color).save(buffer, format="PNG")
    return buffer.getvalue()


PENGUIN = _png_bytes((10, 10, 10, 255))
REAL = _png_bytes((200, 60, 60, 255))


class AvatarFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        avatar._memory.clear()
        avatar._negative.clear()
        avatar._default_fingerprints = None
        self._tmp = Path(
            "/tmp/claude-avatar-test"
            if not Path("/private/tmp").exists()
            else "/private/tmp/claude-avatar-test"
        )
        self._tmp.mkdir(parents=True, exist_ok=True)
        self._patches = [
            mock.patch.object(avatar, "_cache_dir", return_value=self._tmp),
            mock.patch.object(avatar, "_app_id", return_value="123"),
        ]
        for patch in self._patches:
            patch.start()
        for stale in self._tmp.glob("*.png"):
            stale.unlink()

    def tearDown(self) -> None:
        for patch in self._patches:
            patch.stop()

    def _run(self, downloads: dict[str, bytes | None], user_id: str):
        async def fake_download(app_id: str, uid: str):
            return downloads.get(uid)

        with mock.patch.object(avatar, "_download", side_effect=fake_download):
            return asyncio.run(avatar.get_avatar(user_id))

    def test_stock_penguin_counts_as_no_avatar(self) -> None:
        # q.qlogo.cn answers unknown uids with HTTP 200 + the stock penguin;
        # the initial badge beats a generic penguin, so it must become None.
        result = self._run({avatar._SENTINEL_UID: PENGUIN, "42": PENGUIN}, "42")
        self.assertIsNone(result)
        # And it lands in the negative cache.
        self.assertIn("42", avatar._negative)

    def test_real_avatar_passes_through(self) -> None:
        result = self._run({avatar._SENTINEL_UID: PENGUIN, "42": REAL}, "42")
        self.assertIsNotNone(result)
        self.assertEqual(result.size, (8, 8))

    def test_failed_sentinel_degrades_open(self) -> None:
        # If the fingerprint fetch fails, avatars still flow (better to show a
        # possibly-default avatar than to hide every real one).
        result = self._run({avatar._SENTINEL_UID: None, "42": REAL}, "42")
        self.assertIsNotNone(result)

    def test_download_failure_is_negative_cached(self) -> None:
        result = self._run({avatar._SENTINEL_UID: PENGUIN, "42": None}, "42")
        self.assertIsNone(result)
        self.assertIn("42", avatar._negative)

    def test_never_raises(self) -> None:
        async def boom(app_id: str, uid: str):
            raise RuntimeError("network on fire")

        with mock.patch.object(avatar, "_download", side_effect=boom):
            self.assertIsNone(asyncio.run(avatar.get_avatar("42")))


if __name__ == "__main__":
    unittest.main()
