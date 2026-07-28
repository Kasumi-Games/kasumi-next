"""Seasonal gacha commands."""

import json
from typing import Iterable
from typing import Sequence
from pathlib import Path

from nonebot import get_driver
from nonebot import get_plugin_config
from nonebot import on_command
from nonebot import require
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent
from pydantic import BaseModel

from utils import PassiveGenerator
from utils.images import image_segment
from utils.theming import kit_by_name
from utils.theming import kit_for_user
from utils.theming import kit_name_for_item
from plugins.render import BaseKit

from .render import BannerPageData
from .render import pull_page
from .render import banner_page
from .render import history_page
from .render import pull_page_data
from .render import banner_page_data
from .render import history_page_data
from .service import GachaBanner
from .service import GachaResult
from .service import pull
from .service import get_state
from .service import get_history
from .service import get_current_banner
from .database import init_database
from .standing_art import configure_standing_art_cache

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as localstore  # noqa: E402


class _BestdoriConfig(BaseModel):
    """Only the proxy is shared with CCK; gacha keeps no feature switch."""

    bestdori_proxy: str | None = None


#: Repo root; ``metadata.art`` paths in ``items.json`` are relative to it.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@get_driver().on_startup
async def init():
    init_database()
    config = get_plugin_config(_BestdoriConfig)
    cache = configure_standing_art_cache(
        localstore.get_data_dir("gacha"), proxy=config.bestdori_proxy
    )
    await cache.start()


gacha_cmd = on_command("gacha", aliases={"抽卡"}, priority=10, block=True)


@gacha_cmd.handle()
async def handle_gacha(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    try:
        if not text or text in {"info", "卡池", "信息"}:
            banner = get_current_banner()
            if banner is None:
                # Offseason keeps the text reply; there is nothing to sell.
                await matcher.finish(
                    "当前没有开放的限定卡池。" + passive_generator.element,
                    referrer=passive_generator.event.referrer,
                )
            await _send_banner_showcase(matcher, user_id, banner, passive_generator)

        parts = text.split()
        if parts[0] in {"pull", "抽", "抽取", "单抽"}:
            count = _parse_pull_count(parts[1:] if len(parts) > 1 else [])
            await _send_pull_reveal(matcher, user_id, count, passive_generator)

        if parts[0] in {"10", "十连", "十连抽"}:
            await _send_pull_reveal(matcher, user_id, 10, passive_generator)

        if parts[0] in {"history", "记录", "历史"}:
            page = _parse_page(parts[1:] if len(parts) > 1 else [])
            await _send_history(matcher, user_id, page, passive_generator)

        await matcher.finish(
            "用法：/gacha info /gacha pull /gacha pull 10 /gacha history <页码>"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    except MatcherException:
        raise
    except Exception as e:
        await matcher.finish(
            f"抽卡失败：{e}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


async def _send_banner_showcase(
    matcher: Matcher,
    user_id: str,
    banner: GachaBanner,
    passive_generator: PassiveGenerator,
):
    """Reply with the banner showcase card, rendered in the season's theme.

    Kit resolution and every inventory/season lookup happen here on the event
    loop thread; only the raster is offloaded. Failures raise and land in the
    caller's text error path — errors stay text.
    """

    kit = _season_kit(banner.season_key, user_id)
    data = _banner_showcase_data(user_id, banner)
    image = await banner_page(data, kit).render_async()
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _season_kit(season_key: str, user_id: str) -> BaseKit:
    """Resolve the season's own theme kit for the banner showcase.

    The banner sells the season's identity, so this one surface renders in the
    current season's theme rather than the requester's own: season →
    metadata ``gacha_theme_item_id`` → theme item → ``metadata.kit`` →
    kit instance. Any missing link (unknown season, no theme configured, item
    absent from the catalog, metadata without a kit) falls back to the
    player's own kit — a broken cosmetic chain must never change whether the
    command replies.
    """

    try:
        from ..inventory.service import get_item
        from ..inventory.season_service import get_season_by_key
        from ..inventory.season_service import get_season_metadata

        season = get_season_by_key(season_key)
        if season is not None:
            theme_item_id = get_season_metadata(season).get("gacha_theme_item_id")
            if theme_item_id:
                item = get_item(theme_item_id)
                if item is not None:
                    kit_name = kit_name_for_item(item)
                    if kit_name:
                        return kit_by_name(kit_name)
    except Exception:
        logger.opt(exception=True).warning(
            f"season theme resolution failed for season {season_key!r}"
        )
    return kit_for_user(user_id)


def _banner_showcase_data(user_id: str, banner: GachaBanner) -> BannerPageData:
    """Assemble the showcase card's data on the event loop thread.

    The requester's pity comes from their real ``GachaState``; the bundle item
    ids (season frame + theme) come from season metadata; display names and
    the featured standing-art path come from the inventory catalog. The render
    layer receives only plain values.
    """

    state = get_state(user_id)
    bundle_item_ids = _season_bundle_item_ids(banner.season_key)
    item_ids = {entry.item_id for entry in banner.entries}
    item_ids.update(bundle_item_ids)
    names, art = _item_maps(item_ids)
    return banner_page_data(
        banner,
        pity_count=state.pity_count,
        bundle_item_ids=bundle_item_ids,
        item_names=names,
        item_art=art,
    )


def _season_bundle_item_ids(season_key: str) -> tuple[str, ...]:
    """The first-featured-★6 bundle: season frame, then theme, in grant order.

    Mirrors ``grant_featured_character_reward``'s frame-then-theme order. A
    season without the metadata (or an unknown season key) yields no bundle
    and the card simply omits the 「首次入手同时获得」 line.
    """

    from ..inventory.season_service import get_season_by_key
    from ..inventory.season_service import get_season_metadata

    season = get_season_by_key(season_key)
    if season is None:
        return ()
    metadata = get_season_metadata(season)
    return tuple(
        item_id
        for item_id in (
            metadata.get("gacha_character_frame_item_id"),
            metadata.get("gacha_theme_item_id"),
        )
        if item_id
    )


async def _send_pull_reveal(
    matcher: Matcher, user_id: str, count: int, passive_generator: PassiveGenerator
):
    """Pull, then reply with the rendered reveal page.

    The banner is read before the pull so the page can show its name and
    featured flags; kit/data assembly stays on the event loop thread and only
    the raster is offloaded. Failures raise and land in the caller's text
    error path — errors stay text.
    """

    banner = get_current_banner()
    if banner is None:
        raise ValueError("当前没有开放的限定卡池")
    results = pull(user_id, count)

    kit = kit_for_user(user_id)
    item_names, item_art = _pull_item_maps(results)
    data = pull_page_data(results, banner, item_names=item_names, item_art=item_art)
    image = await pull_page(data, kit).render_async()
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _pull_item_maps(
    results: Sequence[GachaResult],
) -> tuple[dict[str, str], dict[str, Path]]:
    """Resolve item names and art paths for a pull batch.

    The render layer never touches a database, so the handler looks up every
    item the batch granted (pulled items plus bundled frame/theme grants) here
    on the event-loop thread and passes plain mappings into
    :func:`pull_page_data`.
    """

    item_ids = {result.item_id for result in results}
    for result in results:
        item_ids.update(grant.item_id for grant in result.grants)
    return _item_maps(item_ids)


def _item_maps(
    item_ids: Iterable[str],
) -> tuple[dict[str, str], dict[str, Path]]:
    """Resolve display names and art paths for a set of item ids.

    Art paths come from ``metadata.art`` in the item catalog; missing files
    are skipped so a bad path degrades to an art-less surface instead of a
    render crash. Items absent from the catalog are simply omitted — callers
    fall back to the raw id.
    """

    from ..inventory.service import get_item

    names: dict[str, str] = {}
    art: dict[str, Path] = {}
    for item_id in sorted(set(item_ids)):
        item = get_item(item_id)
        if item is None:
            continue
        names[item_id] = item.name
        try:
            metadata = json.loads(item.metadata_json or "{}")
        except ValueError:
            metadata = {}
        art_value = metadata.get("art")
        if not art_value:
            continue
        path = Path(art_value)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        if path.exists():
            art[item_id] = path
    return names, art


async def _send_history(
    matcher: Matcher, user_id: str, page: int, passive_generator: PassiveGenerator
):
    """Reply with the rendered pull-history card.

    History rows, pity state, the open banner's pity ceiling, and item names
    are all read here on the event loop thread; only the raster is offloaded.
    An empty history still replies with the card (its empty state), matching
    the mailbox precedent. Failures raise and land in the caller's text error
    path — errors stay text.
    """

    history = get_history(user_id, page)
    state = get_state(user_id)
    banner = get_current_banner()
    kit = kit_for_user(user_id)
    names, _art = _item_maps(row.item_id for row in history.rows)
    data = history_page_data(
        history,
        pity_count=state.pity_count,
        hard_pity=banner.hard_pity if banner is not None else None,
        item_names=names,
    )
    image = await history_page(data, kit).render_async()
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _parse_pull_count(parts: list[str]) -> int:
    if not parts:
        return 1
    if parts[0] in {"10", "十连", "十连抽"}:
        return 10
    if parts[0] in {"1", "单抽"}:
        return 1
    raise ValueError("只能单抽或十连")


def _parse_page(parts: list[str]) -> int:
    """Parse the optional page argument; a non-number stays a text error."""

    if not parts:
        return 1
    try:
        return int(parts[0])
    except ValueError:
        raise ValueError("页码需要是数字") from None
