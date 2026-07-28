"""Bestdori transparent standing-art cache for the general gacha pool.

Unlike the season's hand-picked ★6 reward, the normal pool is the complete
Bestdori card catalogue.  Bestdori exposes the transparent character cut-outs
as ``trim_normal.png`` and ``trim_after_training.png``.  They are kept in the
bot's data directory, rather than in this repository: a complete cache is
large and is operational data in exactly the same sense as CCK's card cache.

The manifest is useful before the image crawl has finished.  ``pool_cards``
only returns files that are already present, so an interrupted first crawl
never creates an art-less result tile.  It simply continues to use the small
built-in fallback pool until more cards are cached.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiofiles
import aiohttp
from nonebot import logger


SUMMARY_URL = "https://bestdori.com/api/cards/all.5.json"
ART_URL = (
    "https://bestdori.com/assets/{server}/characters/resourceset/"
    "{resource_set}_rip/trim_{variant}.png"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://bestdori.com/",
}

# Prefer Simplified Chinese for player-facing card titles; fall back to the
# same server order CCK uses when a localized title is unavailable.
_TITLE_PICK_ORDER = (3, 0, 2, 1, 4)
_SERVER_PICK_ORDER = (0, 3, 2, 1, 4)


@dataclass(frozen=True)
class StandingArtCard:
    """One downloadable transparent CG variant from a Bestdori card."""

    card_id: int
    character_id: int
    rarity: int
    resource_set: str
    server: str
    variant: str
    title: str

    @property
    def item_id(self) -> str:
        return f"bestdori_standing_art_{self.card_id}_{self.variant}"

    @property
    def filename(self) -> str:
        return f"{self.card_id}_{self.variant}.png"

    @property
    def name(self) -> str:
        return self.title


class StandingArtCache:
    """Persist the Bestdori card manifest and download every transparent CG.

    ``refresh`` is intentionally safe to repeat.  Existing valid files are
    skipped, so it also acts as a resumable retry after a network interruption.
    """

    def __init__(self, data_dir: Path, *, proxy: str | None = None) -> None:
        self.data_dir = data_dir
        self.art_dir = data_dir / "standing"
        self.manifest_path = data_dir / "standing-art-manifest.json"
        self.proxy = proxy
        self.cards: tuple[StandingArtCard, ...] = ()
        self._refresh_task: asyncio.Task[None] | None = None

    def load_cached_manifest(self) -> tuple[StandingArtCard, ...]:
        """Load a previous crawl's index without contacting Bestdori."""

        if not self.manifest_path.exists():
            return ()
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.cards = tuple(StandingArtCard(**row) for row in raw["cards"])
        except (KeyError, OSError, TypeError, ValueError) as exc:
            logger.warning(f"gacha standing-art manifest ignored: {exc}")
            self.cards = ()
        return self.cards

    async def start(self) -> None:
        """Run the boot-time cache check, then repair it in the background.

        This is called from the gacha plugin's ``on_startup`` hook.  A bot
        restart therefore validates its local cache against the last manifest
        immediately and refreshes the Bestdori index / missing files without
        delaying the connection to Satori.
        """

        self.load_cached_manifest()
        expected, cached = self.cache_status()
        logger.info(
            "gacha standing art boot check: "
            f"cached={cached}/{expected} transparent CGs"
        )
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._refresh_safely())

    async def _refresh_safely(self) -> None:
        """Keep a temporary Bestdori outage from becoming an unhandled task."""

        try:
            await self.refresh()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
            logger.warning(f"gacha standing art refresh deferred: {exc}")

    async def refresh(self) -> None:
        """Refresh the card index and cache every available transparent CG."""

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.art_dir.mkdir(parents=True, exist_ok=True)
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
            summary = await self._fetch_json(session, SUMMARY_URL)
            cards = _cards_from_summary(summary)
            self.cards = cards
            await self._write_manifest(cards)
            await self._download_missing(session, cards)

    def pool_cards(
        self, *, min_rarity: int = 2, max_rarity: int = 4
    ) -> tuple[StandingArtCard, ...]:
        """Return cached cards that are safe to show in a reveal tile."""

        return tuple(
            card
            for card in self.cards
            if min_rarity <= card.rarity <= max_rarity
            and self._is_valid_png(self.art_path(card))
        )

    def art_path(self, card: StandingArtCard) -> Path:
        return self.art_dir / card.filename

    def cache_status(self) -> tuple[int, int]:
        """Return ``(expected, valid)`` for concise startup diagnostics."""

        return len(self.cards), sum(
            self._is_valid_png(self.art_path(card)) for card in self.cards
        )

    @staticmethod
    def _is_valid_png(path: Path) -> bool:
        """Reject truncated files and HTML error pages left by an interrupted run."""

        try:
            with path.open("rb") as file:
                return file.read(8) == b"\x89PNG\r\n\x1a\n"
        except OSError:
            return False

    async def _fetch_json(self, session: aiohttp.ClientSession, url: str) -> dict:
        async with session.get(url, proxy=self.proxy) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
        if not isinstance(data, dict):
            raise ValueError("Bestdori card summary is not an object")
        return data

    async def _write_manifest(self, cards: tuple[StandingArtCard, ...]) -> None:
        payload = json.dumps(
            {"version": 1, "cards": [asdict(card) for card in cards]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        async with aiofiles.open(self.manifest_path, "w", encoding="utf-8") as file:
            await file.write(payload)

    async def _download_missing(
        self, session: aiohttp.ClientSession, cards: tuple[StandingArtCard, ...]
    ) -> None:
        missing = [card for card in cards if not self._is_valid_png(self.art_path(card))]
        if not missing:
            logger.success("gacha standing art: all transparent CGs are cached")
            return

        logger.info(f"gacha standing art: caching {len(missing)} transparent CGs")
        semaphore = asyncio.Semaphore(8)
        downloaded = 0

        async def download(card: StandingArtCard) -> None:
            nonlocal downloaded
            async with semaphore:
                url = ART_URL.format(
                    server=card.server,
                    resource_set=card.resource_set,
                    variant=card.variant,
                )
                try:
                    async with session.get(url, proxy=self.proxy) as response:
                        if response.status != 200:
                            return
                        content = await response.read()
                    # Bestdori's missing-image pages are HTML.  Do not cache
                    # them under a .png name or consider the card playable.
                    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                        return
                    async with aiofiles.open(self.art_path(card), "wb") as file:
                        await file.write(content)
                    downloaded += 1
                    if downloaded % 100 == 0:
                        logger.info(
                            "gacha standing art: cached "
                            f"{downloaded}/{len(missing)} new CGs"
                        )
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    logger.debug(f"gacha standing art: {card.card_id} skipped: {exc}")

        # Batching bounds memory and prevents thousands of queued coroutines
        # from delaying bot shutdown while preserving eight concurrent fetches.
        for offset in range(0, len(missing), 128):
            await asyncio.gather(
                *(download(card) for card in missing[offset : offset + 128])
            )
        logger.success(
            f"gacha standing art: cached {downloaded} new CGs; "
            f"{len(self.pool_cards())} are now available to draw"
        )


def _cards_from_summary(summary: dict[str, Any]) -> tuple[StandingArtCard, ...]:
    """Turn ``cards/all.5`` into normal/trained trim variants.

    A 1★ card cannot be a gacha standing-art reward, but is still downloaded:
    the request is for the complete transparent CG archive and future pools
    may choose to expose it.  ``others`` is excluded because it is not a
    player character card and frequently lacks a trim resource.
    """

    cards: list[StandingArtCard] = []
    for raw_id, row in summary.items():
        try:
            card_id = int(raw_id)
            rarity = int(row.get("rarity", 0))
            character_id = int(row["characterId"])
            resource_set = str(row["resourceSetName"])
        except (KeyError, TypeError, ValueError):
            continue
        if rarity < 1 or row.get("type") == "others" or not resource_set:
            continue
        server = _pick_server(row.get("prefix"))
        title = _localized(row.get("prefix")) or f"Bestdori 卡面 #{card_id}"
        variants = _variants_for(row)
        cards.extend(
            StandingArtCard(
                card_id=card_id,
                character_id=character_id,
                rarity=rarity,
                resource_set=resource_set,
                server=server,
                variant=variant,
                title=title,
            )
            for variant in variants
        )
    return tuple(sorted(cards, key=lambda card: (card.card_id, card.variant)))


def _localized(value: Any) -> str | None:
    if not isinstance(value, (tuple, list)):
        return None
    for index in _TITLE_PICK_ORDER:
        if index < len(value) and value[index]:
            return str(value[index])
    return None


def _variants_for(row: dict[str, Any]) -> list[str]:
    """Match Bestdori's card-type-specific trim availability.

    Birthday and kirafes cards are trained-only even though their summary rows
    do not consistently expose a ``stat.training`` flag.  Dreamfes and
    special cards ship both variants.  This mirrors CCK's resource selection
    rather than assuming all card types behave like a permanent card.
    """

    card_type = str(row.get("type", ""))
    if card_type in {"birthday", "kirafes"}:
        return ["after_training"]
    if card_type in {"dreamfes", "special"}:
        return ["normal", "after_training"]
    variants = ["normal"]
    if bool(row.get("stat", {}).get("training")):
        variants.append("after_training")
    return variants


def _pick_server(prefix: Any) -> str:
    if isinstance(prefix, (tuple, list)):
        for index in _SERVER_PICK_ORDER:
            if index < len(prefix) and prefix[index]:
                return ("jp", "en", "tw", "cn", "kr")[index]
    return "jp"


# The plugin owns one cache, initialised in ``plugins.gacha.__init__``.
standing_art_cache: StandingArtCache | None = None


def configure_standing_art_cache(data_dir: Path, *, proxy: str | None = None) -> StandingArtCache:
    global standing_art_cache
    if standing_art_cache is None or standing_art_cache.data_dir != data_dir:
        standing_art_cache = StandingArtCache(data_dir, proxy=proxy)
    return standing_art_cache
