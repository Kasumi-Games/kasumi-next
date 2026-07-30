"""流星堂 — the permanent bonsai shop."""

from dataclasses import replace

from nonebot import get_driver
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.exception import MatcherException
from nonebot.adapters.satori import Message
from nonebot.adapters.satori import MessageEvent

from utils import PassiveGenerator
from utils.images import image_segment_async
from utils.theming import kit_for_user
from plugins.inventory.models import BONSAI_ITEM_ID
from plugins.inventory.render import InventoryListData
from plugins.inventory.render import InventoryListRow
from plugins.inventory.render import inventory_list_page

from .database import init_database
from .service import ShopOffer
from .service import buy_offer
from .service import get_offer
from .service import list_offers
from .service import buy_season_pull
from .service import season_pull_status
from .render import ThemePreviewData
from .render import theme_preview_page

PAGE_SIZE = 8
SECTION_ALIASES = {
    "立绘": "standing_art",
    "standing_art": "standing_art",
    "头像框": "avatar_frame",
    "头框": "avatar_frame",
    "frame": "avatar_frame",
    "主题": "theme",
    "theme": "theme",
}
SECTION_NAMES = {
    "standing_art": "立绘",
    "avatar_frame": "头像框",
    "theme": "主题",
}


@get_driver().on_startup
async def init() -> None:
    init_database()


shop_cmd = on_command(
    "流星堂",
    aliases={"盆栽商店", "ryuseido"},
    priority=10,
    block=True,
)


@shop_cmd.handle()
async def handle_shop(
    matcher: Matcher,
    event: MessageEvent,
    arg: Message = CommandArg(),
):
    user_id = event.get_user_id()
    text = arg.extract_plain_text().strip()
    passive = PassiveGenerator(event)

    try:
        if not text:
            await _send_home(matcher, user_id, passive)

        parts = text.split()
        if parts[0] in {"预览", "preview"}:
            if len(parts) != 2:
                raise ValueError("用法：/流星堂 预览 <主题商品编号>")
            offer = get_offer(parts[1])
            if offer is None or offer.section != "theme":
                raise ValueError("这个编号不是可预览的主题")
            await _send_theme_preview(matcher, user_id, offer, passive)

        if parts[0] in SECTION_ALIASES:
            section = SECTION_ALIASES[parts[0]]
            page = _parse_page(parts[1:])
            await _send_section(
                matcher,
                user_id,
                section,
                page,
                passive,
            )

        if parts[0] in {"购买", "买", "buy"}:
            if len(parts) < 2:
                raise ValueError("用法：/流星堂 购买 <商品编号>")
            if len(parts) > 2 and (
                len(parts) != 3 or parts[2] not in {"确认", "confirm"}
            ):
                raise ValueError("用法：/流星堂 购买 <商品编号>")
            offer = get_offer(parts[1])
            if offer is None:
                raise ValueError("没有这个商品编号")
            purchase = buy_offer(user_id, offer.sku)
            if offer.section == "theme":
                await _send_theme_preview(
                    matcher,
                    user_id,
                    offer,
                    passive,
                    notice=f"已购入 · 余额 {purchase.balance_after} 盆",
                )
            await _send_section(
                matcher,
                user_id,
                offer.section,
                _offer_page(offer),
                passive,
                notice=f"已购入 {offer.sku} · 余额 {purchase.balance_after} 盆",
            )

        if parts[0] in {"加抽", "抽卡", "pull"}:
            status = season_pull_status(user_id)
            if len(parts) < 2 or parts[1] not in {"确认", "confirm"}:
                if status.season_id is None:
                    raise ValueError("当前没有开放的限定卡池")
                await _send_home(
                    matcher,
                    user_id,
                    passive,
                    notice=(
                        f"本季加抽 {status.used}/{status.limit} · "
                        f"本次 {status.price} 盆栽"
                    ),
                    footer="/流星堂 加抽 确认",
                )
            await _send_bonus_pull(matcher, user_id, passive)

        raise ValueError(
            "用法：/流星堂 [立绘|头像框|主题]，或 /流星堂 加抽"
        )
    except MatcherException:
        raise
    except Exception as error:
        await matcher.finish(
            f"流星堂：{error}" + passive.element,
            referrer=passive.event.referrer,
        )


async def _send_home(
    matcher: Matcher,
    user_id: str,
    passive: PassiveGenerator,
    *,
    notice: str = "",
    footer: str = "",
) -> None:
    offers = list_offers()
    status = season_pull_status(user_id)
    grouped = {
        section: [offer for offer in offers if offer.section == section]
        for section in SECTION_NAMES
    }
    rows = []
    for code, section in (("A", "standing_art"), ("F", "avatar_frame"), ("T", "theme")):
        section_offers = grouped[section]
        prices = [offer.price for offer in section_offers]
        price_text = (
            f"{min(prices)}–{max(prices)} 盆"
            if min(prices) != max(prices)
            else f"{prices[0]} 盆"
        )
        rows.append(
            InventoryListRow(
                index=code,
                name=SECTION_NAMES[section],
                detail=f"{len(section_offers)} 件 · {price_text}",
                kind=SECTION_NAMES[section],
                show_art_slot=False,
                show_trailing=False,
            )
        )
    pull_detail = (
        "休赛期暂不开放"
        if status.season_id is None
        else f"{status.price} 盆/抽 · 本季 {status.used}/{status.limit}"
    )
    rows.append(
        InventoryListRow(
            index="P",
            name="本季加抽",
            detail=pull_detail,
            kind="加抽",
            show_art_slot=False,
            show_trailing=False,
        )
    )
    await _send_page(
        matcher,
        user_id,
        tuple(rows),
        passive,
        title="流星堂",
        subtitle=_subtitle(user_id),
        summary=notice or "旧藏流转 · 盆栽换收藏",
        footer=footer or "/流星堂 立绘 · 头像框 · 主题 · 加抽",
    )


async def _send_section(
    matcher: Matcher,
    user_id: str,
    section: str,
    page: int,
    passive: PassiveGenerator,
    *,
    notice: str = "",
    footer: str = "",
) -> None:
    offers = list_offers(section)
    total_pages = max(1, (len(offers) + PAGE_SIZE - 1) // PAGE_SIZE)
    if page < 1 or page > total_pages:
        raise ValueError(f"页码应为 1–{total_pages}")
    start = (page - 1) * PAGE_SIZE
    page_offers = offers[start : start + PAGE_SIZE]
    rows = tuple(_offer_row(user_id, offer) for offer in page_offers)
    command = next(key for key, value in SECTION_ALIASES.items() if value == section)
    if footer:
        page_footer = footer
    elif section == "theme":
        page_footer = "/流星堂 预览 <编号> · /流星堂 购买 <编号>"
    elif total_pages > 1:
        page_footer = f"/流星堂 {command} <页码> · /流星堂 购买 <编号>"
    else:
        page_footer = "/流星堂 购买 <编号>"
    await _send_page(
        matcher,
        user_id,
        rows,
        passive,
        title=f"流星堂 · {SECTION_NAMES[section]}",
        subtitle=f"{_subtitle(user_id)} · 第 {page}/{total_pages} 页",
        summary=notice,
        footer=page_footer,
        page=page,
        total_pages=total_pages,
    )


def _offer_row(user_id: str, offer: ShopOffer) -> InventoryListRow:
    from plugins.inventory.service import get_item
    from plugins.inventory.service import get_item_art
    from plugins.inventory.service import get_quantity

    item = get_item(offer.item_id)
    if item is None or item.cosmetic is None:
        raise ValueError(f"商品目录缺失：{offer.item_id}")
    owned = get_quantity(user_id, offer.item_id) > 0
    return InventoryListRow(
        index=offer.sku,
        name=item.name,
        detail="已拥有" if owned else f"{offer.price} 盆栽",
        kind=SECTION_NAMES[offer.section],
        rarity=item.cosmetic.rarity,
        art=get_item_art(offer.item_id),
        equipped=owned,
        show_art_slot=offer.section != "theme",
    )


async def _send_page(
    matcher: Matcher,
    user_id: str,
    rows: tuple[InventoryListRow, ...],
    passive: PassiveGenerator,
    *,
    title: str,
    subtitle: str,
    summary: str,
    footer: str,
    page: int = 1,
    total_pages: int = 1,
) -> None:
    data = InventoryListData(
        title=title,
        page=page,
        total_pages=total_pages,
        rows=rows,
        subtitle=subtitle,
        equipped_summary=summary,
        footer=footer,
    )
    image = await inventory_list_page(data, kit_for_user(user_id)).render_async()
    await matcher.finish(
        await image_segment_async(image) + passive.element,
        referrer=passive.event.referrer,
    )


async def _send_bonus_pull(
    matcher: Matcher,
    user_id: str,
    passive: PassiveGenerator,
) -> None:
    from plugins.gacha.render import pull_page
    from plugins.gacha.render import pull_page_data
    from plugins.gacha.service import get_current_banner
    from plugins.inventory.service import get_item
    from plugins.inventory.service import get_item_art

    banner = get_current_banner()
    if banner is None:
        raise ValueError("当前没有开放的限定卡池")
    result = buy_season_pull(user_id)
    item_ids = {result.item_id, *(grant.item_id for grant in result.grants)}
    names = {}
    art = {}
    for item_id in item_ids:
        item = get_item(item_id)
        if item is not None:
            names[item_id] = item.name
        path = get_item_art(item_id)
        if path is not None:
            art[item_id] = path
    data = pull_page_data((result,), banner, item_names=names, item_art=art)
    data = replace(data, banner_name=f"流星堂 · {banner.name}")
    image = await pull_page(data, kit_for_user(user_id)).render_async()
    await matcher.finish(
        await image_segment_async(image) + passive.element,
        referrer=passive.event.referrer,
    )


async def _send_theme_preview(
    matcher: Matcher,
    user_id: str,
    offer: ShopOffer,
    passive: PassiveGenerator,
    *,
    notice: str = "",
    footer: str = "",
) -> None:
    from utils.theming import kit_by_name
    from utils.theming import kit_name_for_item
    from plugins.inventory.service import get_item
    from plugins.inventory.service import get_quantity

    item = get_item(offer.item_id)
    if item is None:
        raise ValueError("主题商品目录缺失")
    kit_name = kit_name_for_item(item)
    if not kit_name:
        raise ValueError("主题预览配置缺失")
    owned = get_quantity(user_id, offer.item_id) > 0
    balance = get_quantity(user_id, BONSAI_ITEM_ID)
    data = ThemePreviewData(
        sku=offer.sku,
        name=item.name,
        description=item.description,
        price=offer.price,
        balance=balance,
        owned=owned,
        notice=notice,
        footer=footer,
    )
    page = theme_preview_page(data, kit_by_name(kit_name))
    image = await page.render_async()
    await matcher.finish(
        await image_segment_async(image) + passive.element,
        referrer=passive.event.referrer,
    )


def _parse_page(parts: list[str]) -> int:
    if not parts:
        return 1
    if len(parts) != 1 or not parts[0].isdigit() or int(parts[0]) < 1:
        raise ValueError("页码必须是正整数")
    return int(parts[0])


def _offer_page(offer: ShopOffer) -> int:
    offers = list_offers(offer.section)
    return next(index // PAGE_SIZE + 1 for index, row in enumerate(offers) if row == offer)


def _subtitle(user_id: str) -> str:
    from plugins.inventory.service import get_quantity

    return f"盆栽 {get_quantity(user_id, BONSAI_ITEM_ID)} 盆"
