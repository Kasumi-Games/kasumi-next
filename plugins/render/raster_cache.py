"""Byte-bounded cache for immutable, data-independent render layers."""

from functools import wraps
from threading import RLock
from collections import OrderedDict
from collections.abc import Callable
from collections.abc import Hashable

from PIL import Image


class RasterCache:
    """Share static rasters across workers, returning private writable copies.

    Factories transfer ownership of their result to the cache. Expensive work
    runs outside the lock so different keys never serialize rendering workers.
    A concurrent miss may build twice; only one result is retained.
    """

    def __init__(self, max_bytes: int = 64 * 1024 * 1024, max_items: int = 128):
        self.max_bytes = max_bytes
        self.max_items = max_items
        self._items: OrderedDict[Hashable, tuple[Image.Image, int]] = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    @property
    def bytes_used(self) -> int:
        with self._lock:
            return self._bytes

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._bytes = 0

    def get_or_create(
        self, key: Hashable, factory: Callable[[], Image.Image]
    ) -> Image.Image:
        with self._lock:
            entry = self._items.get(key)
            if entry is not None:
                self._items.move_to_end(key)
        if entry is not None:
            return entry[0].copy()

        image = factory()
        # Other Pillow modes can have wider samples or an external palette;
        # bypass them so the byte budget remains exact for retained buffers.
        if image.mode not in ("L", "LA", "RGB", "RGBA"):
            return image
        weight = image.width * image.height * len(image.getbands())
        if weight > self.max_bytes or self.max_items <= 0:
            return image
        with self._lock:
            # Another worker may have populated this key while we drew it.
            entry = self._items.get(key)
            if entry is not None:
                self._items.move_to_end(key)
                image = entry[0]
            else:
                while self._items and (
                    self._bytes + weight > self.max_bytes
                    or len(self._items) >= self.max_items
                ):
                    _, (_, old_weight) = self._items.popitem(last=False)
                    self._bytes -= old_weight
                self._items[key] = image, weight
                self._bytes += weight
        return image.copy()


STATIC_RASTERS = RasterCache()


def cached_background(render):
    """Cache seeded, hashable backgrounds by parameters, scale, and size.

    In-memory images, mutable color lists, and unseeded effects bypass caching.
    Contexts and their request-specific image/measurement caches are not kept.
    """

    @wraps(render)
    def wrapped(self, ctx, size):
        key = (render, self, ctx.render_ratio, size)
        if getattr(self, "random_seed", 0) is None:
            return render(self, ctx, size)
        try:
            hash(key)
        except TypeError:
            return render(self, ctx, size)
        return STATIC_RASTERS.get_or_create(key, lambda: render(self, ctx, size))

    return wrapped
