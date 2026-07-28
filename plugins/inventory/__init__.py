"""Inventory plugin commands, season commands, and exports."""

import json
import time
from pathlib import Path

from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.exception import MatcherException
from nonebot.permission import SUPERUSER
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent

from utils import PassiveGenerator
from utils.clock import format_ts
from utils.avatar import get_avatar
from utils.images import image_segment
from utils.theming import kit_for_user
from utils.theming import theme_by_token
from utils.identity import identity_for

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from .. import monetary  # noqa: E402
from .models import BONSAI_ITEM_ID  # noqa: E402
from .models import SEASON_POINT_ITEM_ID  # noqa: E402
from .models import STAR_STICKER_ITEM_ID  # noqa: E402
from .models import ItemAmount  # noqa: E402
from .render import ProfileData  # noqa: E402
from .render import SeasonInfoData  # noqa: E402
from .render import SeasonRankRow  # noqa: E402
from .render import SeasonRankData  # noqa: E402
from .render import SeasonRewardRow  # noqa: E402
from .render import profile_page  # noqa: E402
from .render import season_info_page  # noqa: E402
from .render import season_rank_page  # noqa: E402
from .service import get_item  # noqa: E402
from .service import get_equipped  # noqa: E402
from .service import get_quantity  # noqa: E402
from .service import display_scope  # noqa: E402
from .service import equip_cosmetic  # noqa: E402
from .service import list_inventory  # noqa: E402
from .service import unequip_cosmetic  # noqa: E402
from .service import parse_item_amount  # noqa: E402
from .service import display_item_amount  # noqa: E402
from .service import get_profile_description  # noqa: E402
from .service import set_profile_description  # noqa: E402
from .database import init_database  # noqa: E402
from ..render.types import ImageSource  # noqa: E402
from .season_render import season_trend_data  # noqa: E402
from .season_render import season_trend_page  # noqa: E402
from .season_service import settle_season  # noqa: E402
from .season_service import list_snapshots  # noqa: E402
from .season_service import get_latest_season  # noqa: E402
from .season_service import get_next_season  # noqa: E402
from .season_service import get_season_metadata  # noqa: E402
from .season_service import get_season_by_key  # noqa: E402
from .season_service import get_active_ranking  # noqa: E402
from .season_service import get_current_season  # noqa: E402
from .season_service import settle_due_seasons  # noqa: E402
from .season_service import settlement_preview  # noqa: E402
from .season_service import activate_due_seasons  # noqa: E402
from .season_service import get_due_seasons  # noqa: E402
from .season_service import get_user_season_rank  # noqa: E402
from .season_service import list_settled_rankings  # noqa: E402
from .season_service import capture_rank_snapshots  # noqa: E402
from .season_service import dispatch_pending_season_rewards  # noqa: E402
from .season_service import grant_featured_character_reward  # noqa: E402

#: Repo root; ``metadata.art`` paths in ``items.json`` are relative to it.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@get_driver().on_startup
async def init():
    init_database()
    _report_theme_catalog_problems()


def _report_theme_catalog_problems() -> None:
    """Log theme catalog problems at startup without blocking the boot.

    A cosmetic mapped to a missing kit degrades to the default theme at render
    time, so it must never stop the bot from starting. ``tests/test_theming.py``
    turns the same check into a hard CI failure.
    """

    try:
        from utils.theming import validate_theme_catalog

        for problem in validate_theme_catalog():
            logger.error(f"theme catalog: {problem}")
    except Exception:
        logger.opt(exception=True).error("theme catalog validation failed")


@get_driver().on_startup
@scheduler.scheduled_job(id="season_lifecycle", trigger="interval", minutes=1)
async def process_season_lifecycle():
    try:
        from .migration import migrate_legacy_monetary_balances

        opening_time = int(time.time())
        for season in get_due_seasons(now=opening_time):
            migrate_legacy_monetary_balances(season=season)
        opened = activate_due_seasons(now=opening_time)
        settled = settle_due_seasons()
        delivered = dispatch_pending_season_rewards()
        if opened or settled or delivered:
            logger.info(
                f"season lifecycle: opened={opened}, settled={settled}, "
                f"delivered_rewards={delivered}"
            )
    except Exception:
        from .database import get_session

        get_session().rollback()
        logger.opt(exception=True).error("season lifecycle job failed")


@get_driver().on_startup
@scheduler.scheduled_job(id="season_rank_snapshots", trigger="interval", minutes=5)
async def process_season_snapshots():
    try:
        capture_rank_snapshots()
    except Exception:
        from .database import get_session

        get_session().rollback()
        logger.opt(exception=True).error("season snapshot job failed")


inventory_cmd = on_command(
    "inventory", aliases={"仓库", "背包"}, priority=10, block=True
)


@inventory_cmd.handle()
async def handle_inventory(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    category_map = {
        "": None,
        "全部": None,
        "货币": "currency",
        "装扮": "cosmetic",
        "道具": "item",
        "currency": "currency",
        "cosmetic": "cosmetic",
        "item": "item",
    }
    if text not in category_map:
        await matcher.finish(
            "仓库分类可用：全部 / 货币 / 装扮 / 道具" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    rows = list_inventory(user_id, category=category_map[text])
    if not rows:
        await matcher.finish(
            "仓库里还没有对应物品。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    lines = ["仓库："]
    for row in rows:
        scope_name = display_scope(row.scope_type, row.scope_id)
        scope = f" [{scope_name}]" if scope_name else ""
        lines.append(f"- {display_item_amount(row.item_id, row.quantity)}{scope}")

    await matcher.finish(
        "\n".join(lines) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


cosmetic_cmd = on_command("cosmetic", aliases={"装扮"}, priority=10, block=True)


@cosmetic_cmd.handle()
async def handle_cosmetic(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    try:
        if not text:
            await matcher.finish(
                _cosmetic_listing(user_id) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        # ``maxsplit=1`` keeps the whole rest as one token: display names can
        # contain spaces（户山香澄 抬头看，星星在跳动立绘）.
        parts = text.split(maxsplit=1)
        action = parts[0]
        if action in {"装备", "equip"} and len(parts) == 2:
            item = _resolve_cosmetic_token(user_id, parts[1])
            if get_quantity(user_id, item.item_id) <= 0:
                await matcher.finish(
                    f"还没有拥有 {item.name}，无法装备。" + passive_generator.element,
                    referrer=passive_generator.event.referrer,
                )
            equipped = equip_cosmetic(user_id, item.item_id)
            slot_name = _COSMETIC_SLOT_NAMES.get(equipped.slot, equipped.slot)
            await matcher.finish(
                f"已装备 {item.name} 到 {slot_name}。" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        if action in {"卸下", "unequip"} and len(parts) == 2:
            removed = unequip_cosmetic(user_id, parts[1].strip())
            msg = "已卸下装扮。" if removed else "这个位置没有装备装扮。"
            await matcher.finish(
                msg + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        await matcher.finish(
            "用法：装扮 / 装扮 装备 <名称或item_id> / 装扮 卸下 <头像框|主题|立绘>"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    except MatcherException:
        raise
    except Exception as e:
        await matcher.finish(
            f"装扮操作失败：{e}" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )


def _cosmetic_listing(user_id: str) -> str:
    """Build the ``/装扮`` overview text.

    Every row shows the display name the player can type back into
    ``装扮 装备 <名称>``, with the Chinese slot word for orientation.
    """

    rows = list_inventory(user_id, category="cosmetic", include_season=False)
    equipped_map = get_equipped(user_id)
    lines = ["装扮："]
    if equipped_map:
        worn: list[str] = []
        for slot, label in _COSMETIC_SLOT_LABELS:
            item_id = equipped_map.get(slot)
            if not item_id:
                continue
            item = get_item(item_id)
            worn.append(f"{label}: {item.name if item else item_id}")
        for slot, item_id in equipped_map.items():
            if slot not in _COSMETIC_SLOT_NAMES:
                worn.append(f"{slot}: {item_id}")
        lines.append("当前装备：" + "，".join(worn))
    if rows:
        for row in rows:
            cosmetic = row.item.cosmetic
            slot_name = (
                _COSMETIC_SLOT_NAMES.get(cosmetic.cosmetic_type, cosmetic.cosmetic_type)
                if cosmetic
                else ""
            )
            suffix = f"（{slot_name}）" if slot_name else ""
            lines.append(f"- {row.item.name}{suffix}")
        lines.append("发送 装扮 装备 <名称> 即可装备，主题也可以用别名。")
        lines.append("装备立绘后，/资料 的资料卡会展示这张立绘。")
    else:
        lines.append("还没有可用装扮。")
    return "\n".join(lines)


def _resolve_cosmetic_token(user_id: str, token: str):
    """Resolve player input to a cosmetic catalog ``Item``.

    Resolution order, all case-insensitive: exact item id → theme token
    (``utils.theming.theme_by_token``: kit name / item id / display name /
    alias) → unique display-name match among the player's owned cosmetics →
    catalog-wide unique display-name match.

    Raises:
        ValueError: With a player-facing message — listing the candidates on
            an ambiguous name and near matches on an unknown one.
    """

    needle = token.strip()
    folded = needle.casefold()
    catalog = _catalog_cosmetics()

    for item in catalog:
        if item.item_id.casefold() == folded:
            return item

    theme = theme_by_token(needle)
    if theme is not None:
        item = get_item(theme.item_id)
        if item is not None:
            return item

    owned_ids = {
        row.item_id
        for row in list_inventory(user_id, category="cosmetic", include_season=False)
    }
    named = [item for item in catalog if item.name.casefold() == folded]
    owned_named = [item for item in named if item.item_id in owned_ids]
    for candidates in (owned_named, named):
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            listing = "、".join(
                f"{item.name}（{item.item_id}）" for item in candidates
            )
            raise ValueError(
                f"「{needle}」匹配到多个装扮：{listing}。请改用 item_id 装备。"
            )

    near = [
        item
        for item in catalog
        if folded
        and (folded in item.name.casefold() or folded in item.item_id.casefold())
    ]
    if near:
        listing = "、".join(item.name for item in near[:5])
        raise ValueError(f"没有找到装扮「{needle}」。相近的装扮：{listing}")
    raise ValueError(f"没有找到装扮「{needle}」。发送 装扮 查看可用装扮名称。")


def _catalog_cosmetics() -> list:
    """Every cosmetic catalog item, in catalog order. Handler-side by design."""

    from .models import Item
    from .models import CosmeticItem
    from .database import get_session

    return (
        get_session()
        .query(Item)
        .join(CosmeticItem, CosmeticItem.item_id == Item.item_id)
        .order_by(Item.sort_order.asc(), Item.item_id.asc())
        .all()
    )


season_cmd = on_command("season", aliases={"赛季"}, priority=10, block=True)


@season_cmd.handle()
async def handle_season(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    parts = text.split()
    if len(parts) == 4 and parts[0] == "grant-character":
        if user_id not in get_driver().config.superusers:
            await matcher.finish(referrer=event.referrer)
        results = grant_featured_character_reward(
            parts[2],
            parts[1],
            parts[3],
            idempotency_key=f"admin_grant_character:{parts[1]}:{parts[3]}",
        )
        lines = [
            f"{result.item_id}: {result.message or 'granted'}"
            for result in results
        ]
        await matcher.finish(
            "已发放六星角色奖励：\n" + "\n".join(lines) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if (
        len(parts) in (2, 3)
        and parts[0] == "settle"
        and (len(parts) == 2 or parts[2] == "--force")
    ):
        if user_id not in get_driver().config.superusers:
            await matcher.finish(referrer=event.referrer)
        season = get_season_by_key(parts[1])
        if season is None:
            await matcher.finish(
                "未知赛季。" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        try:
            count = settle_season(
                parts[1],
                force=len(parts) == 3,
            )
        except ValueError as exc:
            await matcher.finish(
                str(exc) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        await matcher.finish(
            f"已结算 {season.name}，记录 {count} 名玩家。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if text:
        await matcher.finish(
            "用法：/赛季 /season settle <season_key> [--force] /season grant-character <season_key> <user_id> <character_id>"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    now = int(time.time())
    season = get_current_season(now=now)
    state = "active"

    if season is None:
        season = get_next_season(now=now)
        state = "upcoming"

    if season is None:
        balance = get_quantity(user_id, SEASON_POINT_ITEM_ID)
        latest = get_latest_season()
        latest_text = f"\n最近赛季：{latest.name}" if latest else ""
        await matcher.finish(
            "当前是休赛期。\n"
            f"临时 Pt: {balance} Pt\n"
            "休赛期 Pt 可以游玩和转账，但不会计入下一赛季。"
            + latest_text
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    data = _assemble_season_info(user_id, season, state=state, now=now)
    kit = kit_for_user(user_id)
    try:
        image = await season_info_page(data, kit).render_async()
    except Exception:
        logger.opt(exception=True).warning("season info card render failed")
        await matcher.finish(
            _season_info_text(data) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _assemble_season_info(
    user_id: str,
    season,
    *,
    state: str,
    now: int,
) -> SeasonInfoData:
    """Gather the active/upcoming overview without touching the render thread."""

    metadata = get_season_metadata(season)
    rank: int | None = None
    points: int | None = None
    if state == "active":
        rank, points = get_user_season_rank(user_id, season)

    reward_rows: list[SeasonRewardRow] = []
    for tier in metadata.get("reward_tiers", []):
        from_rank = int(tier["from_rank"])
        to_rank = int(tier["to_rank"])
        placement = (
            f"第 {from_rank} 名"
            if from_rank == to_rank
            else f"第 {from_rank}–{to_rank} 名"
        )
        rewards = tuple(
            _season_reward_name(item["item_id"], int(item["quantity"]))
            for item in tier.get("items", [])
        )
        reward_rows.append(
            SeasonRewardRow(
                placement=placement,
                rewards=rewards,
            )
        )

    banner = metadata.get("gacha_banner") or {}
    featured_names = tuple(
        str(character.get("name", "")).strip()
        for character in metadata.get("featured_characters", [])
        if str(character.get("name", "")).strip()
    )
    return SeasonInfoData(
        season_name=season.name,
        state=state,
        starts_at=season.start_time,
        ends_at=season.end_time,
        now=now,
        points=points,
        rank=rank,
        reward_rows=tuple(reward_rows),
        banner_name=str(banner.get("name", "")).strip() or None,
        featured_names=featured_names,
    )


def _season_reward_name(item_id: str, quantity: int) -> str:
    item = get_item(item_id)
    if item is None:
        return f"{item_id} ×{quantity}" if quantity != 1 else item_id
    if item.currency is not None:
        return f"{item.name} {quantity}{item.currency.unit_name}"
    return item.name if quantity == 1 else f"{item.name} ×{quantity}"


def _season_info_text(data: SeasonInfoData) -> str:
    """Degraded reply carrying the card's essential information."""

    lines = [
        f"{data.season_name}（{'进行中' if data.state == 'active' else '即将开始'}）",
        f"赛季时间：{_format_time(data.starts_at)} - {_format_time(data.ends_at)}",
    ]
    if data.state == "active":
        lines.append(f"当前 Pt：{data.points or 0} Pt")
        lines.append(
            f"当前排名：第 {data.rank} 名" if data.rank is not None else "当前排名：暂未上榜"
        )
    if data.banner_name:
        lines.append(f"限定卡池：{data.banner_name}")
    return "\n".join(lines)


# In season, 排行/排行榜 mean the Pt ladder, so the bare spellings live here;
# the level ladder answers to 等级排行 (plugins/daily). The two trigger sets
# must stay disjoint or nonebot logs duplicated-prefix warnings.
season_rank_cmd = on_command(
    "seasonrank",
    aliases={"赛季排行", "赛季排行榜", "排行", "排行榜"},
    priority=10,
    block=True,
)


@season_rank_cmd.handle()
async def handle_season_rank(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    passive_generator = PassiveGenerator(event)
    season = get_current_season()

    if season is None:
        # Off-season: the final settled rankings stay a text list.
        season = get_latest_season()
        if season is None:
            await matcher.finish(
                "还没有赛季记录。想看排行可以发送 /等级排行 查看等级排行榜。"
                + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        rows = list_settled_rankings(season, limit=50)
        lines = [f"{season.name} 最终排行榜"]
        lines.extend(
            f"{row.rank}. {_display_name(row.user_id)}: {row.final_points} Pt"
            for row in rows
        )
        if len(lines) == 1:
            lines.append("暂无排行数据。")
        lines.append("当前是休赛期，想看排行可以发送 /等级排行 查看等级排行榜。")
        await matcher.finish(
            "\n".join(lines) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    # In season the Pt ladder is a card. Data and kit resolve on the event
    # loop thread — the inventory session is process-global and not thread
    # safe — and only the raster is offloaded.
    data = _assemble_season_rank(user_id, season)
    kit = kit_for_user(user_id)
    try:
        image = await season_rank_page(data, kit).render_async()
    except Exception:
        logger.opt(exception=True).warning("season rank card render failed")
        await matcher.finish(
            _season_rank_text(data) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


#: How many neighbours 「你的附近」 shows on each side of the viewer.
_NEARBY_SPAN = 5

#: How many rows the ladder's top section shows.
_LADDER_TOP = 10


def _assemble_season_rank(user_id: str, season) -> SeasonRankData:
    """Gather the in-season Pt ladder.

    Handler-side by design: the render module touches no database. Call on
    the event loop thread only.
    """

    viewer_rank, viewer_points = get_user_season_rank(user_id, season)
    top_rows = get_active_ranking(limit=_LADDER_TOP, season=season)
    rows = tuple(
        SeasonRankRow(
            rank=idx, name=_display_name(row.user_id), points=row.quantity
        )
        for idx, row in enumerate(top_rows, start=1)
    )
    viewer_name = _display_name(user_id)

    nearby: tuple[SeasonRankRow, ...] = ()
    if rows and all(row.user_id != user_id for row in top_rows):
        fetched = get_active_ranking(
            limit=viewer_rank + _NEARBY_SPAN, season=season
        )
        # Clip the window's start below the rows the top section already
        # shows: a rank-12 viewer must not see ranks 7-10 twice on one card
        # (and with a short ladder the whole top used to repeat).
        start = max(len(rows), viewer_rank - _NEARBY_SPAN - 1)
        window = fetched[start : viewer_rank + _NEARBY_SPAN]
        built = [
            SeasonRankRow(
                rank=start + offset + 1,
                name=_display_name(row.user_id),
                points=row.quantity,
            )
            for offset, row in enumerate(window)
        ]
        if all(row.user_id != user_id for row in window):
            # The viewer has no Pt row yet: ``get_user_season_rank`` places
            # them one past the ladder's tail, so pin their zero row to keep
            # 「你的附近」 anchored on the viewer.
            built.append(
                SeasonRankRow(
                    rank=viewer_rank, name=viewer_name, points=viewer_points
                )
            )
        nearby = tuple(built)

    return SeasonRankData(
        season_name=season.name,
        rows=rows,
        nearby=nearby,
        viewer_name=viewer_name,
        viewer_rank=viewer_rank,
        viewer_points=viewer_points,
    )


def _season_rank_text(data: SeasonRankData) -> str:
    """Text fallback with the same information as the ladder card."""

    lines = [f"{data.season_name} 排行榜"]
    if not data.rows:
        lines.append("暂无排行数据。")
    lines.extend(f"{row.rank}. {row.name}: {row.points} Pt" for row in data.rows)
    if data.nearby:
        lines.append("你的附近：")
        lines.extend(
            f"{row.rank}. {row.name}: {row.points} Pt" for row in data.nearby
        )
    lines.append(f"你当前排名第 {data.viewer_rank} 名，{data.viewer_points} Pt")
    return "\n".join(lines)


season_trend_cmd = on_command(
    "seasontrend", aliases={"赛季趋势"}, priority=10, block=True
)


@season_trend_cmd.handle()
async def handle_season_trend(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    passive_generator = PassiveGenerator(event)
    season = get_current_season() or get_latest_season()
    if season is None:
        await matcher.finish(
            "还没有赛季趋势数据。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    # Data, kit, and identity resolve on the event loop thread — the
    # inventory session is process-global and not thread safe — and only the
    # raster is offloaded. The avatar fetch is async and cached (utils.avatar).
    avatar = await get_avatar(user_id)
    try:
        data = season_trend_data(
            season,
            list_snapshots(season),
            owner_name=identity_for(user_id, avatar=avatar).nickname,
        )
    except ValueError:
        await matcher.finish(
            "还没有足够的赛季趋势快照。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    kit = kit_for_user(user_id)
    image = await season_trend_page(data, kit).render_async()
    await matcher.finish(
        image_segment(image) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


season_history_cmd = on_command(
    "seasonhistory", aliases={"赛季历史"}, priority=10, block=True
)


@season_history_cmd.handle()
async def handle_season_history(matcher: Matcher, event: MessageEvent):
    user_id = event.get_user_id()
    passive_generator = PassiveGenerator(event)
    latest = get_latest_season()
    if latest is None:
        await matcher.finish(
            "还没有赛季历史。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    lines = ["赛季历史："]
    from .models import Season
    from .models import SeasonRanking
    from .database import get_session

    seasons = (
        get_session()
        .query(Season)
        .filter(Season.start_time <= latest.start_time)
        .order_by(Season.start_time.desc())
        .limit(5)
        .all()
    )
    for season in seasons:
        ranking = (
            get_session()
            .query(SeasonRanking)
            .filter(
                SeasonRanking.season_id == season.id, SeasonRanking.user_id == user_id
            )
            .first()
        )
        if ranking:
            lines.append(
                f"- {season.name}: 第 {ranking.rank} 名，{ranking.final_points} Pt"
            )
        else:
            lines.append(f"- {season.name}: 暂无个人结算记录")

    await matcher.finish(
        "\n".join(lines) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


profile_cmd = on_command(
    "profile", aliases={"个人资料", "档案"}, priority=10, block=True
)


@profile_cmd.handle()
async def handle_profile(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    if not text:
        # kit/identity/data on the event loop thread; only the raster is
        # offloaded — the inventory session is process-global and not
        # thread safe. The avatar fetch is async and cached (utils.avatar).
        kit = kit_for_user(user_id)
        data = assemble_profile(user_id, avatar=await get_avatar(user_id))
        image = await profile_page(data, kit).render_async()
        await matcher.finish(
            image_segment(image) + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    parts = text.split(maxsplit=1)
    if parts[0] in {"简介", "description", "desc"}:
        description = parts[1] if len(parts) > 1 else ""
        try:
            set_profile_description(user_id, description)
        except ValueError as e:
            await matcher.finish(
                str(e) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        await matcher.finish(
            "已更新个人简介。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    await matcher.finish(
        "用法：/个人资料 或 /个人资料 简介 <100字以内文本>"
        + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


season_admin_cmd = on_command(
    "seasonadmin",
    aliases={"season-admin"},
    priority=10,
    block=True,
    permission=SUPERUSER,
)


@season_admin_cmd.handle()
async def handle_season_admin(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    if event.get_user_id() not in get_driver().config.superusers:
        await matcher.finish(referrer=event.referrer)

    passive_generator = PassiveGenerator(event)
    parts = arg.extract_plain_text().strip().split()
    if (
        len(parts) in (2, 3)
        and parts[0] == "settle"
        and (len(parts) == 2 or parts[2] == "--force")
    ):
        season = get_season_by_key(parts[1])
        if season is None:
            await matcher.finish(
                "未知赛季。" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        try:
            count = settle_season(
                parts[1],
                force=len(parts) == 3,
            )
        except ValueError as exc:
            await matcher.finish(
                str(exc) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        await matcher.finish(
            f"已结算 {season.name}，记录 {count} 名玩家。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if parts == ["retry-rewards"]:
        delivered = dispatch_pending_season_rewards()
        await matcher.finish(
            f"已重试赛季奖励，成功投递 {delivered} 封邮件。"
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if len(parts) == 2 and parts[0] == "preview":
        try:
            preview = settlement_preview(parts[1])
        except ValueError as exc:
            await matcher.finish(
                str(exc) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        await matcher.finish(
            "\n".join(
                [
                    f"赛季：{preview['season_key']}",
                    f"状态：{preview['status']}",
                    f"排名钱包：{preview['rankings']}",
                    f"参与玩家：{preview['participants']}",
                    f"预计奖励邮件：{preview['reward_mails']}",
                    f"待投递邮件：{preview['pending_mails']}",
                ]
            )
            + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    await matcher.finish(
        "用法：/season-admin preview <season_key> /season-admin settle <season_key> [--force] /season-admin retry-rewards"
        + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


#: Fixed display order for equipped cosmetics on the profile card, matching
#: the slot vocabulary of ``/装扮 卸下 <头像框|主题|立绘>``.
_COSMETIC_SLOT_LABELS = (
    ("avatar_frame", "头像框"),
    ("theme", "主题"),
    ("standing_art", "立绘"),
)

#: Slot key → Chinese slot word, for equip messages and the 装扮 listing.
_COSMETIC_SLOT_NAMES = dict(_COSMETIC_SLOT_LABELS)


def assemble_profile(
    user_id: str, *, avatar: ImageSource | None = None
) -> ProfileData:
    """Gather everything the profile card shows.

    Handler-side by design: the render function touches no database. Call on
    the event loop thread only. Both ``/资料`` (here) and ``/info`` (the daily
    plugin) build their card from this one assembly.

    Args:
        user_id: Player id.
        avatar: Avatar image the calling handler already fetched
            (``await utils.avatar.get_avatar(user_id)``); ``None`` keeps the
            initial-badge fallback.

    Returns:
        Pre-assembled profile card data.
    """

    season = get_current_season()
    season_rank: int | None = None
    if season is not None:
        rank, _points = get_user_season_rank(user_id, season)
        season_rank = rank

    equipped: list[tuple[str, str]] = []
    equipped_map = get_equipped(user_id)
    for slot, label in _COSMETIC_SLOT_LABELS:
        item_id = equipped_map.get(slot)
        if not item_id:
            continue
        item = get_item(item_id)
        equipped.append((label, item.name if item else item_id))

    user = monetary.get_user(user_id)
    _xp_needed, next_level_total = monetary.xp_to_next_level(user.xp)
    level_base = monetary.total_xp_for_level(user.level)

    return ProfileData(
        identity=identity_for(user_id, avatar=avatar),
        current_pt=monetary.get(user_id),
        description=get_profile_description(user_id),
        star_stickers=get_quantity(user_id, STAR_STICKER_ITEM_ID),
        bonsai=get_quantity(user_id, BONSAI_ITEM_ID),
        season_name=season.name if season else None,
        season_rank=season_rank,
        equipped=tuple(equipped),
        xp_in_level=max(0, user.xp - level_base),
        xp_level_span=max(0, next_level_total - level_base),
        offseason=monetary.is_using_offseason_points(),
        standing_art=_equipped_cosmetic_art(equipped_map.get("standing_art")),
        avatar_frame=_equipped_cosmetic_art(equipped_map.get("avatar_frame")),
    )


def _equipped_cosmetic_art(item_id: str | None) -> Path | None:
    """Resolve an equipped cosmetic item to its art asset path.

    ``metadata.art`` in ``items.json`` is repo-relative (the same contract the
    gacha reveal uses). Any missing link — no item equipped, item gone from
    the catalog, no ``metadata.art``, file absent on disk — degrades to
    ``None`` and the profile card keeps its art-less treatment.
    """

    if not item_id:
        return None
    item = get_item(item_id)
    if item is None:
        return None
    try:
        metadata = json.loads(item.metadata_json or "{}")
    except ValueError:
        return None
    art_value = metadata.get("art") if isinstance(metadata, dict) else None
    if not art_value:
        return None
    path = Path(art_value)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path if path.exists() else None


def _format_time(timestamp: int) -> str:
    return format_ts(timestamp)


def _display_name(user_id: str) -> str:
    """Display name for a ladder row.

    Falls back to the id tail rather than the raw id so rows stay readable
    and consistent with the level ladder's fallback.
    """

    try:
        from ..nickname import nickname

        name = nickname.get(user_id)
        if name:
            return str(name)
    except Exception:
        pass
    return f"玩家{user_id[-4:]}" if len(user_id) >= 4 else f"玩家{user_id}"


__all__ = [
    "ItemAmount",
    "ProfileData",
    "assemble_profile",
    "display_item_amount",
    "display_scope",
    "parse_item_amount",
    "profile_page",
]
