"""Cached QQ avatar fetching for identity surfaces.

The identity strip and player card were shipping with the initial-letter
fallback because the only avatar path in the codebase
(``bang_avatar.utils.get_group_member_head``) downloads per call. This module
makes real avatars affordable on per-move surfaces:

- memory cache for the hot path (a mines game renders every dig),
- disk cache under the localstore cache dir with a TTL,
- a negative cache so an id that failed to resolve does not add an HTTP
  round-trip to every message for the next few minutes,
- hard timeout, never raises: on any failure the caller gets ``None`` and the
  surfaces keep their initial-badge fallback.

Call from handlers (they are async); pass the result into
``identity_for(user_id, avatar=...)``.
"""

import time
import asyncio
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image
from nonebot import get_driver
from nonebot.log import logger

from .image_tasks import run_image_task

#: Where q.qlogo.cn serves QQ-bot app avatars; mode 5 is the 140px variant,
#: plenty for the 52-96px render sizes.
_URL_TEMPLATE = "https://q.qlogo.cn/qqapp/{app_id}/{user_id}/5"

#: A user id no account can have; q.qlogo.cn answers it with the stock
#: penguin avatar, which is how we fingerprint "this uid has no real avatar".
_SENTINEL_UID = "0"

_FETCH_TIMEOUT_SECONDS = 3.0
_DISK_TTL_SECONDS = 24 * 60 * 60
_NEGATIVE_TTL_SECONDS = 600.0
_MAX_MEMORY_ENTRIES = 512

_memory: dict[str, Image.Image] = {}
_negative: dict[str, float] = {}
_default_fingerprints: set[bytes] | None = None
_lock = asyncio.Lock()


def _cache_dir() -> Path:
    import nonebot_plugin_localstore as store

    return store.get_cache_dir("avatars")


def _app_id() -> str | None:
    config = get_driver().config
    value = getattr(config, "qq_bot_app_id", None)
    return str(value) if value else None


def _load_rgba(source: Path | BytesIO) -> Image.Image:
    """Decode an image fully so no lazy PIL file handle crosses threads."""

    with Image.open(source) as opened:
        return opened.convert("RGBA")


def _decode_and_store(payload: bytes, disk_path: Path) -> Image.Image:
    image = _load_rgba(BytesIO(payload))
    disk_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(disk_path)
    return image


async def get_avatar(user_id: str) -> Image.Image | None:
    """Fetch a user's QQ avatar, cached. Never raises.

    Args:
        user_id: Platform user id.

    Returns:
        Avatar image, or ``None`` when unavailable (caller keeps its fallback).
    """

    try:
        return await _get_avatar(user_id)
    except Exception:
        logger.opt(exception=True).debug(f"avatar fetch failed for {user_id!r}")
        return None


async def _get_avatar(user_id: str) -> Image.Image | None:
    cached = _memory.get(user_id)
    if cached is not None:
        return cached
    if _negative.get(user_id, 0.0) > time.monotonic():
        return None

    disk_path = _cache_dir() / f"{user_id}.png"
    if disk_path.exists() and time.time() - disk_path.stat().st_mtime < _DISK_TTL_SECONDS:
        try:
            image = await run_image_task(_load_rgba, disk_path)
            _remember(user_id, image)
            return image
        except OSError:
            disk_path.unlink(missing_ok=True)

    app_id = _app_id()
    if not app_id:
        _negative[user_id] = time.monotonic() + _NEGATIVE_TTL_SECONDS
        return None

    async with _lock:
        # Re-check after the lock: a concurrent handler may have fetched it.
        cached = _memory.get(user_id)
        if cached is not None:
            return cached
        payload = await _download(app_id, user_id)
        if payload is None or await _is_default_penguin(app_id, payload):
            # q.qlogo.cn answers unknown uids with 200 + the stock penguin
            # rather than an error; the initial badge looks better than a
            # generic penguin, so the stock image counts as "no avatar".
            _negative[user_id] = time.monotonic() + _NEGATIVE_TTL_SECONDS
            return None
        image = await run_image_task(_decode_and_store, payload, disk_path)
        _remember(user_id, image)
        return image


async def _download(app_id: str, user_id: str) -> bytes | None:
    timeout = aiohttp.ClientTimeout(total=_FETCH_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(
            _URL_TEMPLATE.format(app_id=app_id, user_id=user_id)
        ) as response:
            if response.status != 200:
                return None
            payload = await response.read()
    return payload or None


async def _is_default_penguin(app_id: str, payload: bytes) -> bool:
    """Whether the fetched bytes are the stock default avatar.

    Fingerprinted at runtime by fetching the sentinel uid once per process:
    hardcoding the hash would break the day Tencent redesigns the default.
    Unable-to-fingerprint degrades to False — showing a real-looking avatar
    wrongly is better than hiding every avatar behind a failed sentinel fetch.
    """

    import hashlib

    global _default_fingerprints
    if _default_fingerprints is None:
        sentinel = await _download(app_id, _SENTINEL_UID)
        _default_fingerprints = (
            {hashlib.sha256(sentinel).digest()} if sentinel else set()
        )
    return hashlib.sha256(payload).digest() in _default_fingerprints


def _remember(user_id: str, image: Image.Image) -> None:
    if len(_memory) >= _MAX_MEMORY_ENTRIES:
        _memory.pop(next(iter(_memory)), None)
    _memory[user_id] = image


def invalidate(user_id: str) -> None:
    """Drop one user's cached avatar (memory, negative, and disk)."""

    _memory.pop(user_id, None)
    _negative.pop(user_id, None)
    try:
        (_cache_dir() / f"{user_id}.png").unlink(missing_ok=True)
    except OSError:
        pass
