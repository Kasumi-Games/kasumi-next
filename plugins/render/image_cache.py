import time
from pathlib import Path
from collections import OrderedDict
from dataclasses import dataclass

from PIL import Image


@dataclass
class _CacheEntry:
    """Cached image with last-access metadata.

    Attributes:
        image: Cached RGBA image.
        last_used_at: Monotonic timestamp of the last cache hit.
    """

    image: Image.Image
    last_used_at: float


class ImageCache:
    """TTL and size-limited cache for external image files."""

    def __init__(self, ttl_seconds: float = 300, max_items: int = 256) -> None:
        """Create an image cache.

        Args:
            ttl_seconds: Seconds an unused entry may remain in cache.
            max_items: Maximum number of cached images.
        """

        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._items: OrderedDict[Path, _CacheEntry] = OrderedDict()

    def load(self, source: str | Path) -> Image.Image:
        """Load an image path through the cache.

        Args:
            source: Image file path.

        Returns:
            Copy of the cached RGBA image.
        """

        path = Path(source)
        now = time.monotonic()
        self._evict(now)
        entry = self._items.get(path)
        if entry is None:
            entry = _CacheEntry(Image.open(path).convert("RGBA"), now)
            self._items[path] = entry
        else:
            entry.last_used_at = now
            self._items.move_to_end(path)
        self._evict(now)
        return entry.image.copy()

    def clear(self) -> None:
        """Remove all cached images."""

        self._items.clear()

    def _evict(self, now: float) -> None:
        """Evict expired and least-recently-used entries.

        Args:
            now: Current monotonic timestamp.
        """

        expired = [
            path
            for path, entry in self._items.items()
            if now - entry.last_used_at > self.ttl_seconds
        ]
        for path in expired:
            self._items.pop(path, None)
        while len(self._items) > self.max_items:
            self._items.popitem(last=False)
