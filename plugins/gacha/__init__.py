"""Seasonal gacha commands."""

import json
from typing import Sequence
from pathlib import Path

from nonebot import get_driver
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent

from utils import PassiveGenerator
from utils.images import image_segment
from utils.theming import kit_for_user

from .render import pull_page
from .render import pull_page_data
from .service import GachaResult
from .service import pull
from .service import get_state
from .service import get_history
from .service import current_rates
from .service import get_current_banner
from .database import init_database

#: Repo root; ``metadata.art`` paths in ``items.json`` are relative to it.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@get_driver().on_startup
async def init():
    init_database()


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
            await matcher.finish(
                _format_banner_info(user_id) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

        parts = text.split()
        if parts[0] in {"pull", "抽", "抽取", "单抽"}:
            count = _parse_pull_count(parts[1:] if len(parts) > 1 else [])
            await _send_pull_reveal(matcher, user_id, count, passive_generator)

        if parts[0] in {"10", "十连", "十连抽"}:
            await _send_pull_reveal(matcher, user_id, 10, passive_generator)

        if parts[0] in {"history", "记录", "历史"}:
            page = int(parts[1]) if len(parts) > 1 else 1
            await matcher.finish(
                _format_history(user_id, page) + passive_generator.element,
                referrer=passive_generator.event.referrer,
            )

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
    :func:`pull_page_data`. Art paths come from ``metadata.art`` in the item
    catalog; missing files are skipped so a bad path degrades to an art-less
    tile instead of a render crash.
    """

    from ..inventory.service import get_item

    item_ids = {result.item_id for result in results}
    for result in results:
        item_ids.update(grant.item_id for grant in result.grants)

    names: dict[str, str] = {}
    art: dict[str, Path] = {}
    for item_id in sorted(item_ids):
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


def _parse_pull_count(parts: list[str]) -> int:
    if not parts:
        return 1
    if parts[0] in {"10", "十连", "十连抽"}:
        return 10
    if parts[0] in {"1", "单抽"}:
        return 1
    raise ValueError("只能单抽或十连")


def _format_banner_info(user_id: str) -> str:
    banner = get_current_banner()
    if banner is None:
        return "当前没有开放的限定卡池。"
    state = get_state(user_id)
    rates = current_rates(banner, state.pity_count)
    lines = [
        f"{banner.name}",
        f"赛季：{banner.season_name}",
        f"单抽：{banner.single_cost} 张星星贴纸；十连：{banner.ten_cost} 张星星贴纸",
        f"当前保底计数：{state.pity_count}/{banner.hard_pity}",
        "当前概率："
        + " / ".join(
            f"稀有度 {rarity}: {rates[rarity] * 100:.2f}%"
            for rarity in sorted(rates.keys(), reverse=True)
        ),
        "卡池内容：",
    ]
    for entry in sorted(banner.entries, key=lambda item: (-item.rarity, item.name)):
        featured = " featured" if entry.featured else ""
        lines.append(f"- 稀有度 {entry.rarity}: {entry.name}{featured}")
    return "\n".join(lines)


def _format_history(user_id: str, page: int) -> str:
    history = get_history(user_id, page)
    lines = [f"抽卡记录 第 {history.page}/{history.total_pages} 页，共 {history.total} 条"]
    if not history.rows:
        lines.append("暂无抽卡记录。")
        return "\n".join(lines)

    from ..inventory.service import get_item

    for row in history.rows:
        item = get_item(row.item_id)
        name = item.name if item else row.item_id
        message = f"（{row.message}）" if row.message else ""
        lines.append(
            f"#{row.id} {row.banner_key} 稀有度 {row.rarity} {name}{message}"
        )
    state = get_state(user_id)
    lines.append(f"当前保底计数：{state.pity_count}")
    return "\n".join(lines)
