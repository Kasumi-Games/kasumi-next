I have everything I need, including real measurements. Here is the design.

---

# Theme Plumbing — implementation-ready design

Measured on this repo (`uv run`, this machine, SQLite, 3000 users × 2 equip rows, 60 items):

| operation | cost |
|---|---|
| full theme resolve (2 queries + `json.loads`) | **133 µs** |
| smallest realistic card render, per kit | **25 ms (manga) – 101 ms (bangdream)** |
| dict cache lookup | 0.065 µs |

**The DB hit is 0.1–0.5% of the cheapest render that exists.** Caching is therefore *not* a latency decision. It is a thread-safety and burst-protection decision. That reframing drives section 3.

---

## 1. How a theme item maps to a kit

### Decision: `metadata_json` = `{"kit": "<KITS key>"}`, validated at catalog-sync time.

`plugins/inventory/catalog.py:34` already writes `metadata_json` from `entry.get("metadata", {})`, and nothing currently reads it (verified: the only readers of `metadata_json` are `Season`'s copy). So the carrier is free — zero migration, zero new column, and `items.json` is git-tracked, which is exactly the operating model a solo maintainer wants: **adding a theme is a JSON diff, not a code diff.**

Alternatives, and why not:

| option | verdict |
|---|---|
| **New `kit_name` column on `CosmeticItem`** | Needs a hand-written `ALTER TABLE` in `migration.py` (the pattern at `migration.py:38-48`), and the column is meaningless for the 3 other `cosmetic_type`s that share the table. Rejected. |
| **Python dict `THEME_ITEM_KITS = {...}` in `utils/theming.py`** | Second source of truth beside `items.json`; drift is invisible until render time. Rejected. |
| **Convention: strip `theme_` prefix from `item_id`** | Free, but breaks the moment a season theme is named `theme_s2_starlight` while reusing the `neon` kit — which is precisely what the design doc's "Theme Policy" allows (one theme item, multiple sources, reused assets). Rejected even as a fallback: a fallback that guesses is worse than one that degrades. |
| **`metadata_json`** | ✅ |

The known weakness of `metadata_json` is that it is an unvalidated TEXT blob. Fix it by moving the failure from **render time in production** to **sync time in CI**:

```python
# utils/theming.py
def validate_theme_catalog() -> list[str]:
    """Return human-readable problems with the theme catalog. Empty == healthy."""
    from plugins.inventory.catalog import load_catalog

    problems: list[str] = []
    seen_kits: dict[str, str] = {}
    for entry in load_catalog():
        cosmetic = entry.get("cosmetic") or {}
        if cosmetic.get("cosmetic_type") != THEME_SLOT:
            continue
        item_id = entry["item_id"]
        kit_name = (entry.get("metadata") or {}).get("kit")
        if kit_name not in KITS:
            problems.append(f"{item_id}: metadata.kit={kit_name!r} is not a known kit")
            continue
        if kit_name in seen_kits:
            problems.append(f"{item_id}: kit {kit_name!r} already claimed by {seen_kits[kit_name]}")
        seen_kits[kit_name] = item_id
    for kit_name in KITS:
        if kit_name not in seen_kits:
            problems.append(f"kit {kit_name!r} has no theme item and is unobtainable")
    return problems
```

Wire it in two places, deliberately differently:

- **`tests/test_theming.py`** — `assert validate_theme_catalog() == []`. A typo fails CI.
- **`plugins/inventory/__init__.py::init()`** — log each problem at `ERROR` after `init_database()`; **do not raise**. A cosmetic typo must never stop the bot from booting.

`load_catalog()` reads the JSON directly and touches no DB, so the test needs no fixtures.

---

## 2. `items.json` entries for all 8 kits

### Distribution rationale

Two free themes, not one. A player with exactly one theme cannot experience "switching" and will never learn the mechanic exists. The second free theme (`minimal`) is deliberately the plainest one — its job is to teach the verb and make the paid kits look better by contrast.

One theme stays **unbuyable** (`theme_s1_sailing`, season-limited) so the ladder has a top that money-equivalent grinding cannot reach. Everything else is purchasable with 盆栽, which also fixes a live problem: the design doc states players "can receive 盆栽 from duplicates, but they cannot spend it yet" — a dead currency. Themes are the correct first sink because `bonsai_price` lives on the item, so **no shop JSON file is needed** (the doc defers the shop loader; this design doesn't need it).

| item_id | kit | rarity | source | 盆栽 |
|---|---|---|---|---|
| `theme_default` | bangdream | 3 | auto-granted | — |
| `theme_minimal` | minimal | 3 | auto-granted | — |
| `theme_midnight` | midnight | 4 | shop | 200 |
| `theme_sakura` | sakura | 4 | shop | 200 |
| `theme_fluent` | fluent | 5 | shop | 350 |
| `theme_manga` | manga | 5 | shop | 450 |
| `theme_neon` | neon | 6 | shop | 700 |
| `theme_s1_sailing` | sailing | 6 | S1 6★ gacha / rank 1–3 | **not for sale** |

**This deviates from the design doc line "All themes should be ★★★★★★"** (`docs/design/season-gacha-cosmetics.md:161`). Deliberate: once eight themes exist, rarity is the only signal the gallery has for visual weight, and if all eight are 6★ the signal is dead. Update that line to "all *season-limited* themes should be ★★★★★★".

That requires extending `DUPLICATE_BONSAI_COMPENSATION` in `service.py:51-53`, which today only has `{"theme": {6: 120}}` — a duplicate 4★ theme silently compensates 0:

```python
    "theme": {6: 120, 5: 60, 4: 40, 3: 0},
```

### JSON to append to `plugins/inventory/items.json`

```json
    {
      "item_id": "theme_default",
      "category": "cosmetic",
      "name": "Kasumi 原色",
      "description": "Kasumi 的默认外观，人人都有。",
      "stackable": false,
      "visible": true,
      "sort_order": 200,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 3 },
      "metadata": {
        "kit": "bangdream",
        "starter": true,
        "aliases": ["default", "bangdream", "默认", "原色"]
      }
    },
    {
      "item_id": "theme_minimal",
      "category": "cosmetic",
      "name": "留白",
      "description": "去掉一切装饰，只留内容。",
      "stackable": false,
      "visible": true,
      "sort_order": 201,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 3 },
      "metadata": {
        "kit": "minimal",
        "starter": true,
        "aliases": ["minimal", "留白", "极简"]
      }
    },
    {
      "item_id": "theme_midnight",
      "category": "cosmetic",
      "name": "深夜巡演",
      "description": "深炭底色配靛蓝辉光，夜里看不刺眼。",
      "stackable": false,
      "visible": true,
      "sort_order": 210,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 4 },
      "metadata": {
        "kit": "midnight",
        "bonsai_price": 200,
        "aliases": ["midnight", "深夜", "夜"]
      }
    },
    {
      "item_id": "theme_sakura",
      "category": "cosmetic",
      "name": "樱色",
      "description": "奶油与樱粉，八套里最柔和的一套。",
      "stackable": false,
      "visible": true,
      "sort_order": 211,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 4 },
      "metadata": {
        "kit": "sakura",
        "bonsai_price": 200,
        "aliases": ["sakura", "樱", "樱花"]
      }
    },
    {
      "item_id": "theme_fluent",
      "category": "cosmetic",
      "name": "云母窗",
      "description": "Windows 11 的云母材质与 8px 圆角。",
      "stackable": false,
      "visible": true,
      "sort_order": 212,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 5 },
      "metadata": {
        "kit": "fluent",
        "bonsai_price": 350,
        "aliases": ["fluent", "云母", "win11"]
      }
    },
    {
      "item_id": "theme_manga",
      "category": "cosmetic",
      "name": "网点纸",
      "description": "纯黑白漫画分镜，被聊天软件压缩后依然锐利。",
      "stackable": false,
      "visible": true,
      "sort_order": 213,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 5 },
      "metadata": {
        "kit": "manga",
        "bonsai_price": 450,
        "aliases": ["manga", "漫画", "网点"]
      }
    },
    {
      "item_id": "theme_neon",
      "category": "cosmetic",
      "name": "霓虹街机",
      "description": "近黑机台上的品红与青色霓虹灯管。",
      "stackable": false,
      "visible": true,
      "sort_order": 214,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 6 },
      "metadata": {
        "kit": "neon",
        "bonsai_price": 700,
        "aliases": ["neon", "霓虹", "街机"]
      }
    }
```

And **edit the existing entry** (`items.json:192-203`) — add `metadata`, bump `sort_order` so limited sorts last:

```json
    {
      "item_id": "theme_s1_sailing",
      "category": "cosmetic",
      "name": "扬帆主题",
      "description": "第一赛季主题装扮。",
      "stackable": false,
      "visible": true,
      "sort_order": 220,
      "cosmetic": { "cosmetic_type": "theme", "rarity": 6 },
      "metadata": {
        "kit": "sailing",
        "limited": "2026-s01",
        "aliases": ["sailing", "扬帆", "s1"]
      }
    }
```

`sync_catalog()` overwrites `sort_order` and `metadata_json` unconditionally, so this is a safe in-place edit with no migration.

### Auto-granting the starters

`equip_cosmetic` rejects unowned items (`service.py:299-300`), so starters need a real grant. Do it lazily, **only on the `/主题` command path — never during a render**:

```python
# plugins/inventory/service.py
def ensure_starter_cosmetics(user_id: str) -> None:
    """Grant the always-available cosmetics. Idempotent; safe to call on every command."""
    for item_id in _starter_item_ids():
        grant_item(user_id, item_id, 1, "starter_cosmetic",
                   idempotency_key=f"starter:{item_id}")
```

`_tx_key` (`service.py:545-556`) already folds `user_id` into the idempotency key, so `f"starter:{item_id}"` is correctly per-user. After the first call it costs one `item_transactions` lookup per starter and writes nothing.

---

## 3. `kit_for_user` — full implementation

### Three constraints that actually shape this

1. **`get_session()` returns one module-global `Session`** (`plugins/inventory/database.py:15-40`) shared process-wide. `Page.render_async` (`layout.py:82`) offloads rendering to a thread. A SQLAlchemy `Session` is **not thread-safe**. Therefore: *resolve the kit on the event-loop thread and pass the instance into the renderer* — which is exactly the shape the existing renderers already take (`render(field, kit: BaseKit | None = None)` at `mines/render/field.py:110`). `kit_for_user` must never be called from inside a render.
2. **`kit_for_user` must never write.** No lazy grants, no `_ensure_*`. A render is a read.
3. **`kit_for_user` must never raise.** Every caller is a message handler; a `KeyError` here would silently kill an unrelated command.

`utils/passive_generator.py` already ships an `ExpiringDict`, but it does an **O(n) sweep on every `__getitem__`** and has no size bound — wrong shape for a per-message hot path. Use a small purpose-built cache.

### `utils/theming.py`

```python
"""Per-user render theme resolution.

``kit_for_user`` is on the path of every rendered response. It never raises, never
writes to the database, and must be called from the event loop thread — the
inventory Session is process-global and not thread safe, so resolve the kit first
and pass the instance into the renderer.
"""

from __future__ import annotations

import io
import json
import time
import threading
from dataclasses import dataclass

from PIL import Image
from nonebot.log import logger
from nonebot.adapters.satori import MessageSegment

from plugins.render.kit import BaseKit
from plugins.render.kits import KITS

THEME_SLOT = "theme"
DEFAULT_KIT_NAME = "bangdream"
LAST_RESORT_KIT_NAME = "minimal"     # zero file dependencies; cannot fail on missing assets

_TTL_SECONDS = 120.0
_NEGATIVE_TTL_SECONDS = 5.0
_MAX_CACHED_USERS = 4096

_lock = threading.Lock()
_resolved: dict[str, tuple[str, float]] = {}   # user_id -> (kit_name, expires_at)
_instances: dict[str, BaseKit] = {}            # kit_name -> singleton
_broken_kits: set[str] = set()
_themes: dict[str, "ThemeInfo"] | None = None  # kit_name -> ThemeInfo
_kit_names_by_type: dict[type, str] | None = None


@dataclass(frozen=True)
class ThemeInfo:
    item_id: str
    kit_name: str
    name: str
    description: str
    rarity: int
    sort_order: int
    starter: bool = False
    limited: str = ""
    bonsai_price: int | None = None
    aliases: tuple[str, ...] = ()

    @property
    def purchasable(self) -> bool:
        return self.bonsai_price is not None
```

**Public API**

```python
def kit_for_user(user_id: str) -> BaseKit:
    """Resolve a user's equipped theme into a kit instance. Never raises."""
    try:
        return kit_by_name(_cached_kit_name(user_id))
    except Exception:
        logger.opt(exception=True).warning(f"theme resolution failed for user {user_id}")
        return kit_by_name(DEFAULT_KIT_NAME)


def kit_by_name(name: str) -> BaseKit:
    """Instantiate (once) a kit by its ``KITS`` key, degrading through the fallback chain."""
    with _lock:
        cached = _instances.get(name)
    if cached is not None:
        return cached

    for candidate in (name, DEFAULT_KIT_NAME, LAST_RESORT_KIT_NAME):
        if not candidate or candidate in _broken_kits:
            continue
        factory = KITS.get(candidate)
        if factory is None:
            continue
        try:
            instance = factory()
        except Exception:
            # Missing font/BG asset, bad import — never retry this kit for this process.
            logger.opt(exception=True).error(f"kit {candidate!r} failed to construct")
            _broken_kits.add(candidate)
            continue
        with _lock:
            _instances[candidate] = instance
        return instance

    raise RuntimeError("no render kit could be constructed")   # unrecoverable; rendering is impossible
```

Kits are stateless — every attribute in all eight `kit.py` files is a class-level constant — so one shared instance per kit name is safe and lets eight objects serve the whole bot.

**Cache**

```python
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
    for key in [k for k, (_, expiry) in _resolved.items() if expiry <= now]:
        _resolved.pop(key, None)
    while len(_resolved) >= _MAX_CACHED_USERS:            # all still live: drop oldest insertions
        _resolved.pop(next(iter(_resolved)), None)


def invalidate_user(user_id: str) -> None:
    with _lock:
        _resolved.pop(user_id, None)


def invalidate_catalog() -> None:
    """Drop the cached theme index. Call after ``sync_catalog``."""
    global _themes
    with _lock:
        _themes = None
        _resolved.clear()
```

**Resolution**

```python
def _resolve_kit_name(user_id: str) -> tuple[str, float]:
    """Return (kit_name, ttl). Inventory imports are function-local to avoid an
    import cycle: plugins.inventory imports utils, so utils must not import
    plugins.inventory at module scope."""
    try:
        from plugins.inventory.service import get_equipped, get_item
    except Exception:
        logger.opt(exception=True).error("inventory service unavailable")
        return DEFAULT_KIT_NAME, _NEGATIVE_TTL_SECONDS

    try:
        item_id = get_equipped(user_id).get(THEME_SLOT)
    except Exception:
        logger.opt(exception=True).warning("inventory unavailable while resolving theme")
        return DEFAULT_KIT_NAME, _NEGATIVE_TTL_SECONDS

    if not item_id:
        return DEFAULT_KIT_NAME, _TTL_SECONDS          # no theme equipped: normal, silent

    try:
        item = get_item(item_id)
    except Exception:
        logger.opt(exception=True).warning("inventory unavailable while loading theme item")
        return DEFAULT_KIT_NAME, _NEGATIVE_TTL_SECONDS

    if item is None:
        logger.warning(f"equipped theme {item_id!r} is not in the catalog")
        return DEFAULT_KIT_NAME, _TTL_SECONDS

    return kit_name_for_item(item) or DEFAULT_KIT_NAME, _TTL_SECONDS


def kit_name_for_item(item) -> str | None:
    try:
        metadata = json.loads(item.metadata_json or "{}")
    except (TypeError, ValueError):
        logger.warning(f"theme item {item.item_id!r} has unparseable metadata_json")
        return None
    name = metadata.get("kit") if isinstance(metadata, dict) else None
    if not isinstance(name, str) or name not in KITS:
        logger.warning(f"theme item {item.item_id!r} maps to unknown kit {name!r}")
        return None
    return name
```

**Reverse index (kit → theme metadata), built once per process from the catalog file**

```python
def all_themes() -> dict[str, ThemeInfo]:
    global _themes
    with _lock:
        if _themes is not None:
            return _themes
    built = _build_theme_index()
    with _lock:
        _themes = built
    return built


def _build_theme_index() -> dict[str, ThemeInfo]:
    try:
        from plugins.inventory.catalog import load_catalog
        entries = load_catalog()
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
        if kit_name not in KITS or kit_name in index:
            continue
        index[kit_name] = ThemeInfo(
            item_id=entry["item_id"],
            kit_name=kit_name,
            name=entry.get("name", kit_name),
            description=entry.get("description", ""),
            rarity=int(cosmetic.get("rarity", 1)),
            sort_order=int(entry.get("sort_order", 0)),
            starter=bool(metadata.get("starter", False)),
            limited=str(metadata.get("limited", "")),
            bonsai_price=metadata.get("bonsai_price"),
            aliases=tuple(metadata.get("aliases", ())),
        )
    return index


def kit_name_of(kit: BaseKit) -> str:
    """Reverse a kit instance back to its ``KITS`` key."""
    global _kit_names_by_type
    if _kit_names_by_type is None:
        _kit_names_by_type = {factory: name for name, factory in KITS.items()}
    return _kit_names_by_type.get(type(kit), DEFAULT_KIT_NAME)


def theme_for_kit(kit: BaseKit) -> ThemeInfo | None:
    return all_themes().get(kit_name_of(kit))


def theme_by_token(token: str) -> ThemeInfo | None:
    """Resolve player input: kit name, item id, display name, or alias."""
    needle = token.strip().casefold()
    for info in all_themes().values():
        candidates = {info.kit_name, info.item_id, info.name, *info.aliases}
        if needle in {c.casefold() for c in candidates}:
            return info
    return None
```

**`image_segment`** — replaces the four duplicated copies (`plugins/one_stroke/__init__.py:42`, and the inline `MessageSegment.image(raw=..., mime="image/png")` calls in `inventory/__init__.py:312` and elsewhere):

```python
_JPEG_SWITCH_BYTES = 900_000


def image_segment(image: Image.Image) -> MessageSegment:
    """Encode a PIL image as a satori image segment.

    PNG keeps text edges crisp, which matters because clients downscale. Large
    opaque cards fall back to high-quality JPEG so a themed full card does not
    push a multi-megabyte upload into a group chat.
    """
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    if buffer.tell() <= _JPEG_SWITCH_BYTES or image.mode == "RGBA":
        return MessageSegment.image(raw=buffer, mime="image/png")
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=92, subsampling=0)
    return MessageSegment.image(raw=buffer, mime="image/jpeg")
```

`subsampling=0` (4:4:4) is required — default 4:2:0 chroma subsampling destroys the magenta/cyan edges in the `neon` kit and the pink text in `sakura`.

**Do not re-export `theming` from `utils/__init__.py`.** `plugins/inventory/__init__.py:14` does `from utils import PassiveGenerator`; if `utils/__init__` pulled in theming, and theming imported inventory at module scope, that is a cycle. Callers use `from utils.theming import kit_for_user`, and theming's inventory imports stay function-local. State this as a comment in `utils/__init__.py`.

### Invalidation on equip

Add to `plugins/inventory/service.py`, after the `session.commit()` in `equip_cosmetic` (line 314) and `unequip_cosmetic` (line 329):

```python
def _invalidate_theme_cache(user_id: str, slot: str) -> None:
    if slot != "theme":
        return
    try:
        from utils.theming import invalidate_user   # local import: avoids an import cycle
        invalidate_user(user_id)
    except Exception:
        logger.opt(exception=True).debug("theme cache invalidation skipped")
```

Called as `_invalidate_theme_cache(user_id, cosmetic.cosmetic_type)` and `_invalidate_theme_cache(user_id, slot)`. The 120 s TTL is the backstop if this is ever missed; eager invalidation is what makes `/主题 霓虹` feel instant.

Also append `invalidate_catalog()` (same guarded-local-import pattern) to the end of `sync_catalog()` in `catalog.py`, so tests and restarts pick up JSON edits.

### Why 120 s TTL, given the DB costs 133 µs

Not for speed. Three real reasons:

1. A ten-image burst (a `/十连` result set, a leaderboard fan-out) makes ten identical queries against a single global `Session` — the cache collapses those to one.
2. It bounds the blast radius of `_NEGATIVE_TTL_SECONDS` when the DB is sick: 5 s of stale-default instead of a hot retry loop.
3. It keeps the resolve off any future code path that drifts into a worker thread before someone notices rule (1) above.

If the cache were deleted entirely the bot would still work correctly and imperceptibly slower. Say so in the module docstring so nobody later "optimizes" it into something clever and wrong.

---

## 4. Failure modes and the fallback chain

| # | failure | detection | behavior | log |
|---|---|---|---|---|
| 1 | No `theme` row in `equipped_items` | `get_equipped(uid).get("theme")` is `None` | `bangdream`, TTL 120 s | none — this is the majority case |
| 2 | Equipped `item_id` not in `items` (catalog entry removed) | `get_item()` → `None` | `bangdream`, TTL 120 s | `WARNING` |
| 3 | `metadata_json` unparseable | `json.loads` raises | `bangdream`, TTL 120 s | `WARNING` |
| 4 | `metadata.kit` missing / not in `KITS` | key check | `bangdream`, TTL 120 s | `WARNING` |
| 5 | Kit class raises on construction (missing font, missing `BG/*.png`) | `except` in `kit_by_name` | next candidate; kit added to `_broken_kits` so it is tried **once per process** | `ERROR` |
| 6 | DB unavailable (`session is None`, `OperationalError`, locked file) | `except` around each query | `bangdream`, TTL **5 s** | `WARNING` |
| 7 | `plugins.inventory` import fails entirely | `except ImportError` | `bangdream`, TTL 5 s | `ERROR` |
| 8 | `bangdream` itself is broken | chain step 2 | `minimal` — the only kit with **zero file dependencies** (verified: `MinimalKit` imports no `fonts.py` constants and no resource dir) | `ERROR` |
| 9 | `minimal` also broken | chain exhausted | `RuntimeError` from `kit_by_name`, caught by `kit_for_user`'s own guard → recursion into `kit_by_name(DEFAULT)` → raises | rendering is genuinely impossible; let the handler's `except` produce a text reply |

Note step 8 specifically: **`bangdream` is the default but not the last resort.** It loads `resources/BG/bg_object_big.png` and `resources/Fonts/old.ttf` from disk; a bad checkout or a partial deploy takes it out. `MinimalKit` is pure code and cannot fail that way.

Two invariants worth a test each:

```python
def test_kit_for_user_never_raises_when_inventory_is_dead(monkeypatch): ...
def test_kit_for_user_never_writes(sqlite_session): ...   # assert item_transactions row count unchanged
```

And the anti-log-spam rule: failures 2–4 log per resolve, but a resolve only happens once per user per 120 s, so a permanently broken equip costs 30 log lines/hour, not one per message. That is by design — do not add per-message logging in the render path.

---

## 5. The "yo where'd you get that" mechanic

Two tiers, and the anti-clutter property comes from tier 1 being **conditional**.

### Tier 1 — the signature line (passive, on the image)

A single right-aligned footer line in the outermost card, `muted_text_color`, 22 px logical, preceded by a short vertical tick rule.

**Exact wording:**

- default form: `主题 · 霓虹街机`
- when the image is a shared surface (leaderboard, group result, anything not obviously about one player): `香澄 的主题 · 霓虹街机`

Nothing else. No command, no price, no "get yours". The line reads as a photo credit, which is what makes it survive being on hundreds of images without feeling like an ad.

**The suppression rule is the whole design:**

> The signature renders **only when the equipped theme is not a starter theme.**

Players on `theme_default` or `theme_minimal` — which will be most players for a while — get no footer at all. Their images stay completely clean. That means *the presence of the line is itself the status signal*: an onlooker learns "this is a thing you can have" from the fact that most images don't have it and this one does. It inverts the ad problem — scarcity does the advertising, so the text doesn't have to.

Second suppression rule, for latency and noise:

> The signature renders on composed response cards (`response_card`) and final results. It does **not** render on interactive mid-game boards (blackjack table between hits, mines field between digs).

Justification: on those surfaces the theme is already carried by the background and panels — repeating a credit line every turn is exactly the clutter the user is worried about. The theme is *more* visible there, not less.

```python
# utils/cards.py
from plugins.render import Fixed, HStack
from plugins.render.kit import BaseKit
from plugins.render.core import Component


def theme_signature(kit: BaseKit, theme_name: str, owner_name: str | None = None) -> Component:
    """A credit line naming the theme in play. Right-align it in a card footer."""
    text = f"{owner_name} 的主题 · {theme_name}" if owner_name else f"主题 · {theme_name}"
    return HStack(
        [
            kit.separator(orientation="vertical", length=Fixed(22), thickness=3),
            kit.text(text, font_size=22, color=kit.muted_text_color, wrap=False, max_lines=1),
        ],
        gap=10,
        align="center",
    )


def signature_for(kit: BaseKit, owner_name: str | None = None) -> Component | None:
    """Return the signature, or ``None`` when this theme should stay silent."""
    from utils.theming import theme_for_kit

    info = theme_for_kit(kit)
    if info is None or info.starter:
        return None
    return theme_signature(kit, info.name, owner_name)
```

`response_card(...)` composes `footer` as `VStack([footer, signature_for(kit, owner)])` and simply omits the row when it is `None`.

**Legibility:** 22 px logical is the floor named in the constraints, and it clears it — `RenderContext.pixel_ratio` defaults to `2` (`core.py:171`), so the line is drawn at 44 device px before the page downsamples, then downscaled again by the client. It reads; it does not compete with 44 px titles.

**Manga degradation:** the signature is ink-black text plus a solid ink tick — no hue involved anywhere. It is arguably *most* legible in manga. In `midnight`/`neon`, `muted_text_color` is a light grey-violet on a dark panel (`(142,152,182)` on `(30,36,56)` and `(150,140,190)` on `(14,12,28)`) — both clear the ~4:1 contrast the rest of those kits already rely on. The vertical tick uses each kit's own `separator` default color, so it is never invisible on its own panel.

### Tier 2 — `/主题` (active, on demand)

The onlooker types `/主题`. What comes back is the payoff, and it is the single place the whole design earns its images:

**One portrait card, a 2×4 grid of eight live swatches — each cell rendered by its own kit.** Not a colour chip: a real ~260×180 mini-card produced by that kit's own `background()`/`panel()`/`text()`, showing the theme name and one line of body text. You see what you would actually get.

Cell states, all encoded by **shape and text, never hue** (so manga survives):
- **owned** — full-opacity swatch, kit-native border
- **equipped** — owned, plus a solid inset rule around the cell and the word `使用中` in the corner
- **locked** — swatch drawn at `opacity=0.35` through `kit.image(...)`, with the price rendered over it: `200 盆栽` — or `第一赛季限定` for `theme_s1_sailing`
- footer of the card: `盆栽 480 · 已解锁 3/8`

This is the interaction redesign the brief asks for: a paginated `/装扮` text list (`inventory/__init__.py:124-138`, which today prints `- 樱色 (theme_sakura)` lines) becomes one scannable grid, and **there is no pagination command at all** — eight is the whole set, forever, by construction of `validate_theme_catalog`.

Cost: eight nested renders. Measured single-card renders are 25–101 ms, but these are ~1/12 the area, so budget **~120–250 ms total**. Render it through `AutoPage.render_async` and cache the *locked/unowned* composite per-process — the eight swatches are identical for every user, only opacity and the owned-badge overlay differ.

**Command surface:**

| command | response | why |
|---|---|---|
| `/主题` | the gallery card | one image, no pagination |
| `/主题 <name\|alias>` | **equips it, and replies with a full sample card already rendered in the new kit** | the confirmation *is* the demo — one message instead of "equipped ✓" then "now go run something to see it" |
| `/主题 兑换 <name>` | buys with 盆栽, then behaves exactly like equip above | purchase and first-look collapse into one image |
| `/主题 卸下` | text | see below |

`/主题 <name>` resolving through `theme_by_token` means `霓虹`, `neon`, and `theme_neon` all work — the alias list exists precisely so an onlooker can type the Chinese name they just read off someone else's signature line.

### What stays text, and why

| response | form | reason |
|---|---|---|
| `未找到主题「xxx」，发送 /主题 查看全部。` | text | An error must not cost 200 ms and a download. |
| `盆栽不足：需要 700，你有 480。` | text | Same. The number is the whole message; an image adds nothing. |
| `你还没有这个主题，可以用 700 盆栽兑换：/主题 兑换 霓虹` | text | Short, actionable, latency-sensitive. |
| `已切回默认主题。` (`/主题 卸下`) | text | Rendering a card in the theme they *just removed* is actively confusing. |
| `已装备 xxx。` for non-theme slots | text | Frames/titles have their own surfaces; don't inflate them here. |

Rule of thumb to write into the module docstring: **an image is warranted when the theme is the subject or the payload is spatial. Errors, refusals and acknowledgements stay text.**

---

## 6. Files to touch

| file | change |
|---|---|
| `utils/theming.py` | **new** — everything in §3 |
| `utils/cards.py` | `theme_signature`, `signature_for`; `response_card` gains the conditional footer row |
| `utils/__init__.py` | comment only: do **not** re-export `theming` (import cycle) |
| `plugins/inventory/items.json` | 7 new theme entries; `theme_s1_sailing` gains `metadata`, `sort_order` 170→220 |
| `plugins/inventory/service.py` | `_invalidate_theme_cache` + 2 call sites; `ensure_starter_cosmetics`; `_starter_item_ids`; extend `DUPLICATE_BONSAI_COMPENSATION["theme"]` to `{6:120, 5:60, 4:40, 3:0}` |
| `plugins/inventory/catalog.py` | call `invalidate_catalog()` at the end of `sync_catalog()` |
| `plugins/inventory/__init__.py` | in `init()`, log the result of `validate_theme_catalog()` at ERROR (never raise) |
| `plugins/one_stroke/__init__.py` | delete `_image_segment`, import from `utils.theming` |
| `docs/design/season-gacha-cosmetics.md` | amend "All themes should be ★★★★★★" → season-limited themes only |

No database migration. No changes to `plugins/render/`.

## 7. Tests

```
tests/test_theming.py
  test_catalog_is_valid                  # validate_theme_catalog() == []
  test_every_kit_has_exactly_one_theme_item
  test_kit_for_user_defaults_without_equipment
  test_kit_for_user_resolves_equipped_metadata
  test_kit_for_user_falls_back_on_unknown_kit_name
  test_kit_for_user_falls_back_on_broken_metadata_json
  test_kit_for_user_falls_back_when_inventory_raises
  test_kit_for_user_never_writes_to_the_database
  test_equip_invalidates_the_cache
  test_theme_by_token_matches_name_alias_kit_and_item_id
  test_signature_is_none_for_starter_themes
  test_signature_renders_in_all_eight_kits   # smoke: 8 renders, assert non-empty image
```

The last one is the cheap insurance that matters most — it is the only thing standing between a new kit and a footer that renders as an invisible or clipped line in exactly one theme.