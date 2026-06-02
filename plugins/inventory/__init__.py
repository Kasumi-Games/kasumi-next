"""Inventory plugin commands, season commands, and exports."""

from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.exception import MatcherException
from nonebot import get_driver, on_command, require
from nonebot.adapters.satori import Message, MessageEvent, MessageSegment

from utils import PassiveGenerator

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler  # noqa: E402

from .database import init_database  # noqa: E402
from .season_render import render_snapshot_trend  # noqa: E402
from .models import ItemAmount, SEASON_POINT_ITEM_ID  # noqa: E402
from .season_service import (  # noqa: E402
    settle_season,
    get_latest_season,
    get_season_by_key,
    get_active_ranking,
    get_current_season,
    settle_due_seasons,
    get_user_season_rank,
    list_settled_rankings,
    capture_rank_snapshots,
)
from .service import (  # noqa: E402
    get_equipped,
    get_quantity,
    display_scope,
    equip_cosmetic,
    list_inventory,
    unequip_cosmetic,
    parse_item_amount,
    display_item_amount,
)


@get_driver().on_startup
async def init():
    init_database()


@get_driver().on_startup
@scheduler.scheduled_job(id="season_lifecycle", trigger="interval", minutes=1)
async def process_season_lifecycle():
    settle_due_seasons()


@get_driver().on_startup
@scheduler.scheduled_job(id="season_rank_snapshots", trigger="interval", minutes=5)
async def process_season_snapshots():
    capture_rank_snapshots()


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
            rows = list_inventory(user_id, category="cosmetic", include_season=False)
            equipped = get_equipped(user_id)
            lines = ["装扮："]
            if equipped:
                lines.append(
                    "当前装备：" + "，".join(f"{k}: {v}" for k, v in equipped.items())
                )
            if rows:
                lines.extend(f"- {row.item.name} ({row.item_id})" for row in rows)
            else:
                lines.append("还没有可用装扮。")
            await matcher.finish(
                "\n".join(lines) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        parts = text.split()
        action = parts[0]
        if action in {"装备", "equip"} and len(parts) == 2:
            equipped = equip_cosmetic(user_id, parts[1])
            await matcher.finish(
                f"已装备 {parts[1]} 到 {equipped.slot}。" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        if action in {"卸下", "unequip"} and len(parts) == 2:
            removed = unequip_cosmetic(user_id, parts[1])
            msg = "已卸下装扮。" if removed else "这个位置没有装备装扮。"
            await matcher.finish(
                msg + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        await matcher.finish(
            "用法：装扮 / 装扮 装备 <item_id> / 装扮 卸下 <头像框|称号>"
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


season_cmd = on_command("season", aliases={"赛季"}, priority=10, block=True)


@season_cmd.handle()
async def handle_season(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()
    passive_generator = PassiveGenerator(event)

    parts = text.split()
    if len(parts) == 2 and parts[0] == "settle":
        if user_id not in get_driver().config.superusers:
            await matcher.finish(referrer=event.referrer)
        season = get_season_by_key(parts[1])
        if season is None:
            await matcher.finish(
                "未知赛季。" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        count = settle_season(parts[1])
        await matcher.finish(
            f"已结算 {season.name}，记录 {count} 名玩家。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    if text:
        await matcher.finish(
            "用法：/赛季 或 /season settle <season_key>" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    season = get_current_season()
    balance = get_quantity(user_id, SEASON_POINT_ITEM_ID)

    if season is None:
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

    rank, points = get_user_season_rank(user_id, season)
    await matcher.finish(
        f"{season.name}\n"
        f"赛季时间：{_format_time(season.start_time)} - {_format_time(season.end_time)}\n"
        f"当前 Pt: {points} Pt\n"
        f"当前排名：第 {rank} 名" + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


season_rank_cmd = on_command(
    "seasonrank", aliases={"赛季排行", "赛季排行榜"}, priority=10, block=True
)


@season_rank_cmd.handle()
async def handle_season_rank(matcher: Matcher, event: MessageEvent):
    passive_generator = PassiveGenerator(event)
    season = get_current_season()
    lines = []

    if season is not None:
        rows = get_active_ranking(limit=50, season=season)
        lines.append(f"{season.name} 排行榜")
        lines.extend(
            f"{idx}. {_display_name(row.user_id)}: {row.quantity} Pt"
            for idx, row in enumerate(rows, start=1)
        )
    else:
        season = get_latest_season()
        if season is None:
            await matcher.finish(
                "还没有赛季记录。" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        rows = list_settled_rankings(season, limit=50)
        lines.append(f"{season.name} 最终排行榜")
        lines.extend(
            f"{row.rank}. {_display_name(row.user_id)}: {row.final_points} Pt"
            for row in rows
        )

    if len(lines) == 1:
        lines.append("暂无排行数据。")
    await matcher.finish(
        "\n".join(lines) + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


season_trend_cmd = on_command(
    "seasontrend", aliases={"赛季趋势"}, priority=10, block=True
)


@season_trend_cmd.handle()
async def handle_season_trend(matcher: Matcher, event: MessageEvent):
    passive_generator = PassiveGenerator(event)
    season = get_current_season() or get_latest_season()
    if season is None:
        await matcher.finish(
            "还没有赛季趋势数据。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    try:
        chart = render_snapshot_trend(season)
    except ValueError:
        await matcher.finish(
            "还没有足够的赛季趋势快照。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    await matcher.finish(
        MessageSegment.image(raw=chart, mime="image/png") + passive_generator.element,
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
    from .database import get_session
    from .models import Season, SeasonRanking

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
    if len(parts) == 2 and parts[0] == "settle":
        season = get_season_by_key(parts[1])
        if season is None:
            await matcher.finish(
                "未知赛季。" + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )
        count = settle_season(parts[1])
        await matcher.finish(
            f"已结算 {season.name}，记录 {count} 名玩家。" + passive_generator.element,
            referrer=passive_generator.event.referrer,
        )

    await matcher.finish(
        "用法：/season-admin settle <season_key>" + passive_generator.element,
        referrer=passive_generator.event.referrer,
    )


def _format_time(timestamp: int) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _display_name(user_id: str) -> str:
    try:
        from ..nickname import nickname

        return nickname.get(user_id) or user_id
    except Exception:
        return user_id


__all__ = [
    "ItemAmount",
    "display_item_amount",
    "display_scope",
    "parse_item_amount",
]
