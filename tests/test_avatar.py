import io
import sys
import asyncio
import unittest
from pathlib import Path
from unittest import mock
from weakref import WeakValueDictionary

import pytest
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


@pytest.fixture
def avatar_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(avatar, "_memory", {})
    monkeypatch.setattr(avatar, "_negative", {})
    monkeypatch.setattr(avatar, "_default_fingerprints", set())
    monkeypatch.setattr(avatar, "_locks", WeakValueDictionary())
    monkeypatch.setattr(avatar, "_fingerprint_lock", asyncio.Lock())
    monkeypatch.setattr(avatar, "_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(avatar, "_app_id", lambda: "123")


async def test_slow_avatar_does_not_block_another_user(avatar_cache, monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def download(app_id, user_id):
        if user_id == "slow":
            started.set()
            await release.wait()
        return REAL

    monkeypatch.setattr(avatar, "_download", download)
    slow = asyncio.create_task(avatar.get_avatar("slow"))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        # The second player's card can finish while the first download hangs.
        result = await asyncio.wait_for(avatar.get_avatar("fast"), timeout=0.5)
        assert result is not None
        assert not slow.done()
    finally:
        release.set()
        await slow


async def test_concurrent_failed_avatar_download_is_not_retried(
    avatar_cache, monkeypatch
):
    started = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def download(app_id, user_id):
        calls.append(user_id)
        started.set()
        await release.wait()
        return None

    monkeypatch.setattr(avatar, "_download", download)
    first = asyncio.create_task(avatar.get_avatar("same"))
    await asyncio.wait_for(started.wait(), timeout=1)
    second = asyncio.create_task(avatar.get_avatar("same"))
    # Let the second call reach the cache miss while the first is downloading.
    await asyncio.sleep(0)
    release.set()
    assert await asyncio.gather(first, second) == [None, None]
    assert calls == ["same"]


async def test_avatar_total_wait_is_bounded(avatar_cache, monkeypatch):
    monkeypatch.setattr(avatar, "_FETCH_TIMEOUT_SECONDS", 0.05)

    async def download(app_id, user_id):
        await asyncio.Event().wait()

    monkeypatch.setattr(avatar, "_download", download)
    result = await asyncio.wait_for(avatar.get_avatar("slow"), timeout=0.5)
    assert result is None
    assert "slow" in avatar._negative


async def test_network_exception_is_negative_cached(avatar_cache, monkeypatch):
    download = mock.AsyncMock(side_effect=OSError("unreachable"))
    monkeypatch.setattr(avatar, "_download", download)
    assert await avatar.get_avatar("offline") is None
    assert await avatar.get_avatar("offline") is None
    assert download.await_count == 1


async def test_concurrent_successful_avatar_download_is_shared(
    avatar_cache, monkeypatch
):
    download = mock.AsyncMock(return_value=REAL)
    monkeypatch.setattr(avatar, "_download", download)
    results = await asyncio.gather(*(avatar.get_avatar("same") for _ in range(4)))
    assert all(result is results[0] for result in results)
    assert results[0] is not None
    assert download.await_count == 1
    assert not avatar._locks


async def test_total_timeout_also_covers_the_sentinel(avatar_cache, monkeypatch):
    monkeypatch.setattr(avatar, "_default_fingerprints", None)
    monkeypatch.setattr(avatar, "_FETCH_TIMEOUT_SECONDS", 0.05)
    calls = []

    async def download(app_id, user_id):
        calls.append(user_id)
        if user_id == avatar._SENTINEL_UID:
            await asyncio.Event().wait()
        return REAL

    monkeypatch.setattr(avatar, "_download", download)
    assert await asyncio.wait_for(avatar.get_avatar("real"), timeout=0.5) is None
    assert calls == ["real", avatar._SENTINEL_UID]


if __name__ == "__main__":
    unittest.main()
