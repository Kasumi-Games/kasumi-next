"""Per-user render theme resolution.

A player's equipped ``theme`` cosmetic decides which render kit draws their
images. This module is the only thing that knows how to get from a ``user_id``
to a :class:`~plugins.render.kit.BaseKit`.

Three rules hold everywhere in here, and callers depend on all three:

1. **Never raises.** Every caller is a message handler. An exception escaping
   theme resolution would kill an unrelated command for a cosmetic reason.
2. **Never writes.** Resolving a theme is a read. No lazy grants, no repair.
3. **Call it from the event loop thread, never from inside a renderer.**
   ``plugins.inventory.database.get_session`` hands out one process-global
   SQLAlchemy ``Session``, which is not thread safe, and will run the full
   ``init_database()`` if it has not been opened yet. ``Page.render_async``
   offloads rendering to a worker thread. So resolve the kit first and pass the
   instance in, which is the shape every renderer already takes::

       kit = kit_for_user(event.get_user_id())
       image = await page_for(...).render_async()

The TTL cache exists to collapse bursts (a ten-pull result, a leaderboard
fan-out) into one query, not because a single lookup is slow. Deleting the cache
entirely would leave the bot correct and imperceptibly slower — do not
"optimize" it into something clever.
"""

import json
import time
import threading
from typing import Any
from typing import Iterable
from pathlib import Path
from dataclasses import field
from dataclasses import dataclass

from nonebot.log import logger

from plugins.render.kit import BaseKit
from plugins.render.kits import KITS
from plugins.render.kits import KIT_DISPLAY_NAMES

#: Item catalog, read directly rather than through
#: ``plugins.inventory.catalog``. Importing that module executes
#: ``plugins/inventory/__init__.py``, which ``require()``s an apscheduler plugin
#: and therefore needs a live NoneBot. Reading the file keeps catalog checks
#: usable from CI and keeps boot-time validation independent of plugin load
#: order. ``tests/test_theming.py`` asserts this path matches the one the
#: inventory plugin actually loads.
CATALOG_PATH = (
    Path(__file__).resolve().parents[1] / "plugins" / "inventory" / "items.json"
)

#: Equipment slot a theme occupies, matching ``CosmeticItem.cosmetic_type``.
THEME_SLOT = "theme"

#: Kit used when a player has equipped nothing, and the first fallback.
DEFAULT_KIT_NAME = "bangdream"

#: Last resort. ``MinimalKit`` is the only kit with no file dependencies, so it
#: still constructs when fonts or background assets are missing from a deploy.
LAST_RESORT_KIT_NAME = "minimal"

_TTL_SECONDS = 120.0
_NEGATIVE_TTL_SECONDS = 5.0
_MAX_CACHED_USERS = 4096

_lock = threading.RLock()
_resolved: dict[str, tuple[str, float]] = {}
_instances: dict[str, BaseKit] = {}
_broken_kits: set[str] = set()
_themes: dict[str, "ThemeInfo"] | None = None


@dataclass(frozen=True)
class ThemeInfo:
    """Catalog metadata for one ownable theme.

    Attributes:
        item_id: Inventory item id granting the theme.
        kit_name: Key into :data:`plugins.render.kits.KITS`.
        name: Player-facing theme name.
        description: Player-facing description.
        rarity: Cosmetic rarity.
        starter: Whether every player has this by default.
        aliases: Extra tokens that resolve to this theme in commands.
    """

    item_id: str
    kit_name: str
    name: str
    description: str = ""
    rarity: int = 1
    starter: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)


def kit_for_user(user_id: str) -> BaseKit:
    """Resolve a player's equipped theme into a kit instance.

    Args:
        user_id: Player id.

    Returns:
        Kit instance. Falls back to the default kit on any failure.
    """

    try:
        return kit_by_name(_cached_kit_name(user_id))
    except Exception:
        logger.opt(exception=True).warning(
            f"theme resolution failed for user {user_id!r}"
        )
        return kit_by_name(DEFAULT_KIT_NAME)


def kit_by_name(name: str) -> BaseKit:
    """Return the shared instance of a kit, degrading through the fallback chain.

    Kits are stateless — every attribute on every kit is a class-level constant
    — so one instance per name can serve the whole process.

    Args:
        name: Key into :data:`plugins.render.kits.KITS`.

    Returns:
        Kit instance.

    Raises:
        RuntimeError: If no kit in the chain can be constructed, which means
            rendering is impossible and the caller should reply with text.
    """

    with _lock:
        cached = _instances.get(name)
    if cached is not None:
        return cached

    for candidate in (name, DEFAULT_KIT_NAME, LAST_RESORT_KIT_NAME):
        if not candidate:
            continue
        with _lock:
            if candidate in _broken_kits:
                continue
            cached = _instances.get(candidate)
        if cached is not None:
            return cached

        factory = KITS.get(candidate)
        if factory is None:
            continue
        try:
            instance = factory()
        except Exception:
            # A missing font or background asset. Never retry it this process.
            logger.opt(exception=True).error(f"kit {candidate!r} failed to construct")
            with _lock:
                _broken_kits.add(candidate)
            continue
        with _lock:
            _instances[candidate] = instance
        return instance

    raise RuntimeError("no render kit could be constructed")


def theme_for_kit(kit: BaseKit) -> ThemeInfo | None:
    """Return catalog metadata for the theme a kit belongs to.

    Args:
        kit: Kit instance.

    Returns:
        Theme metadata, or ``None`` when the kit has no catalog entry.
    """

    name = kit_name_of(kit)
    return all_themes().get(name) if name else None


def kit_name_of(kit: BaseKit) -> str | None:
    """Return the ``KITS`` key for a kit instance.

    Args:
        kit: Kit instance.

    Returns:
        Kit name, or ``None`` if the kit is not registered.
    """

    for name, factory in KITS.items():
        if type(kit) is factory:
            return name
    return None


def display_name(kit_name: str) -> str:
    """Return the player-facing name for a kit."""

    return KIT_DISPLAY_NAMES.get(kit_name, kit_name)


def all_themes() -> dict[str, ThemeInfo]:
    """Return every catalog theme, keyed by kit name. Built once per process."""

    global _themes
    with _lock:
        if _themes is not None:
            return _themes
    built = _build_theme_index()
    with _lock:
        _themes = built
    return built


def theme_by_token(token: str) -> ThemeInfo | None:
    """Resolve a player-typed token to a theme.

    Accepts the kit name, the item id, the display name, or any configured
    alias, so a player can type what they read off someone else's image.

    Args:
        token: Raw player input.

    Returns:
        Matching theme, or ``None``.
    """

    needle = token.strip().casefold()
    if not needle:
        return None
    for info in all_themes().values():
        candidates = (
            info.kit_name,
            info.item_id,
            info.name,
            *info.aliases,
        )
        if any(needle == str(value).casefold() for value in candidates):
            return info
    return None


def validate_theme_catalog() -> list[str]:
    """Check the theme catalog for problems.

    Reads ``items.json`` directly and touches no database, so it is safe to call
    from a test with no fixtures.

    Returns:
        Human-readable problems. An empty list means the catalog is healthy.
    """

    problems: list[str] = []
    try:
        entries = _load_catalog_entries()
    except Exception as error:
        return [f"theme catalog unreadable: {error}"]

    claimed: dict[str, str] = {}
    for entry in entries:
        cosmetic = entry.get("cosmetic") or {}
        if cosmetic.get("cosmetic_type") != THEME_SLOT:
            continue
        item_id = entry.get("item_id", "<missing item_id>")
        kit_name = (entry.get("metadata") or {}).get("kit")
        if kit_name not in KITS:
            problems.append(
                f"{item_id}: metadata.kit={kit_name!r} is not a known kit"
            )
            continue
        if kit_name in claimed:
            problems.append(
                f"{item_id}: kit {kit_name!r} is already claimed by {claimed[kit_name]}"
            )
            continue
        claimed[kit_name] = item_id
    return problems


def unclaimed_kits() -> list[str]:
    """Return kits with no theme item, and therefore no way to be equipped.

    This is informational rather than a catalog error: a kit may deliberately
    exist before the theme that ships it.
    """

    claimed = {info.kit_name for info in all_themes().values()}
    return [name for name in KITS if name not in claimed]


def invalidate_user(user_id: str) -> None:
    """Drop one player's cached theme. Call after an equip changes."""

    with _lock:
        _resolved.pop(user_id, None)


def invalidate_catalog() -> None:
    """Drop the cached theme index and all resolutions. Call after a catalog sync."""

    global _themes
    with _lock:
        _themes = None
        _resolved.clear()


def _cached_kit_name(user_id: str) -> str:
    now = time.monotonic()
    with _lock:
        hit = _resolved.get(user_id)
        if hit is not None and hit[1] > now:
            return hit[0]

    name, ttl = _resolve_kit_name(user_id)

    with _lock:
        if len(_resolved) >= _MAX_CACHED_USERS:
            _purge_locked(now)
        _resolved[user_id] = (name, now + ttl)
    return name


def _purge_locked(now: float) -> None:
    for key in [key for key, (_, expiry) in _resolved.items() if expiry <= now]:
        _resolved.pop(key, None)
    while len(_resolved) >= _MAX_CACHED_USERS:
        _resolved.pop(next(iter(_resolved)), None)


def _resolve_kit_name(user_id: str) -> tuple[str, float]:
    """Resolve without caching. Returns ``(kit_name, ttl_seconds)``.

    Inventory imports are function-local on purpose: ``plugins.inventory``
    imports ``utils``, so importing inventory at module scope here would close
    an import cycle.
    """

    try:
        from plugins.inventory.service import get_item
        from plugins.inventory.service import get_equipped
    except Exception:
        logger.opt(exception=True).error("inventory service unavailable")
        return DEFAULT_KIT_NAME, _NEGATIVE_TTL_SECONDS

    try:
        item_id = get_equipped(user_id).get(THEME_SLOT)
    except Exception:
        logger.opt(exception=True).warning(
            "inventory unavailable while resolving theme"
        )
        return DEFAULT_KIT_NAME, _NEGATIVE_TTL_SECONDS

    if not item_id:
        # The common case: no theme equipped. Deliberately silent.
        return DEFAULT_KIT_NAME, _TTL_SECONDS

    try:
        item = get_item(item_id)
    except Exception:
        logger.opt(exception=True).warning(
            "inventory unavailable while loading theme item"
        )
        return DEFAULT_KIT_NAME, _NEGATIVE_TTL_SECONDS

    if item is None:
        logger.warning(f"equipped theme {item_id!r} is not in the catalog")
        return DEFAULT_KIT_NAME, _TTL_SECONDS

    return kit_name_for_item(item) or DEFAULT_KIT_NAME, _TTL_SECONDS


def kit_name_for_item(item: Any) -> str | None:
    """Read the kit name out of a theme item's ``metadata_json``.

    Args:
        item: An inventory ``Item`` row.

    Returns:
        Kit name, or ``None`` when the metadata is missing or invalid.
    """

    metadata = _parse_metadata(getattr(item, "metadata_json", None))
    if metadata is None:
        logger.warning(
            f"theme item {getattr(item, 'item_id', '?')!r} has unparseable metadata_json"
        )
        return None
    name = metadata.get("kit")
    if not isinstance(name, str) or name not in KITS:
        logger.warning(
            f"theme item {getattr(item, 'item_id', '?')!r} maps to unknown kit {name!r}"
        )
        return None
    return name


def _parse_metadata(raw: Any) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _load_catalog_entries() -> list[dict[str, Any]]:
    """Read the item catalog from disk. No database, no plugin import."""

    with open(CATALOG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle).get("items", [])


def _build_theme_index() -> dict[str, ThemeInfo]:
    try:
        entries = _load_catalog_entries()
    except Exception:
        logger.opt(exception=True).error("theme catalog unreadable")
        return {}

    index: dict[str, ThemeInfo] = {}
    for entry in entries:
        cosmetic = entry.get("cosmetic") or {}
        if cosmetic.get("cosmetic_type") != THEME_SLOT:
            continue
        metadata = entry.get("metadata") or {}
        kit_name = metadata.get("kit")
        if not isinstance(kit_name, str) or kit_name not in KITS:
            continue
        if kit_name in index:
            continue
        index[kit_name] = ThemeInfo(
            item_id=entry["item_id"],
            kit_name=kit_name,
            name=entry.get("name", display_name(kit_name)),
            description=entry.get("description", ""),
            rarity=int(cosmetic.get("rarity", 1)),
            starter=bool(metadata.get("starter", False)),
            aliases=_as_tuple(metadata.get("aliases")),
        )
    return index


def _as_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value)
    return ()
