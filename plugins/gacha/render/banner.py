"""The banner showcase — what ``/抽卡``（无参数 / 卡池 / 信息）replies with.

The old reply was a plain text dump; this page is the sell. Uniquely among all
surfaces it renders in the **current season's** theme kit rather than the
requesting player's own: the banner exists to sell this season's identity, and
the theme it ships is the thing being sold. The handler resolves that kit
(``banner.season_key`` → season metadata ``gacha_theme_item_id`` → theme item →
kit, falling back to the player's kit when any link is missing) and passes it
in — kit resolution is data assembly and stays out of this module.

No ``owner_name`` is passed to ``card_page`` on purpose: the season theme is
the subject of this card, not any player's equipped cosmetic. Themes that keep
the standard signature therefore render it without an owner; Starbeat itself
suppresses the line because its authored visual identity already carries it.

:func:`banner_page_data` is pure — the banner, the requester's pity count, and
the season's bundle item ids are passed in, and item names/art come through the
optional mappings the handler fills from the inventory on the event-loop
thread — so this module never touches a database and only the raster is
offloaded via ``await banner_page(...).render_async()``.
"""

from typing import Mapping
from typing import Sequence
from pathlib import Path
from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import CONTENT_WIDTH
from utils.cards import LABEL_SIZE
from utils.cards import badge
from utils.cards import meter
from utils.cards import stat_row
from utils.cards import card_page
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.mewtype import MewtypeKit

from ..service import GachaEntry
from ..service import GachaBanner
from ..service import current_rates

#: A contemporary gacha banner is one composed hero, not art stacked over
#: another generic information panel.
_HERO_HEIGHT = 500
_ARTLESS_HERO_HEIGHT = 280
_HERO_COPY_WIDTH = 340
_FRAME_PREVIEW = 82
_DETAIL_GAP = 16
_RATE_PANEL_WIDTH = 282
_STATE_PANEL_WIDTH = CONTENT_WIDTH - _RATE_PANEL_WIDTH - _DETAIL_GAP
_DETAIL_HEIGHT = 320


@dataclass(frozen=True)
class BannerPageData:
    """Everything the banner showcase shows, assembled by :func:`banner_page_data`.

    Attributes:
        banner_name: Player-facing banner name (page title).
        season_name: Season the banner belongs to (page subtitle).
        featured_name: Display name of the featured entry; empty when the
            banner has no entries at all.
        featured_rarity: The featured entry's star rarity.
        featured_art: Standing-art image path for the featured entry, when the
            catalog carries one that exists on disk.
        bundle_names: Player-facing names of the items bundled with the first
            featured ★6 — the season frame and theme. Empty when the season
            configures none.
        rates: ``(rarity, rate)`` pairs, rarity descending, already adjusted
            for the requester's pity via ``current_rates`` and limited to the
            rarities the banner actually offers.
        single_cost: 星星贴纸 cost of one pull.
        ten_cost: 星星贴纸 cost of a ten-pull.
        pity_count: The requesting player's current pity counter.
        hard_pity: The banner's hard-pity ceiling.
        frame_art: Preview art for the bundled cosmetics — in practice the
            season avatar-frame ring — shown under the bundle line so the
            card shows the frame instead of only naming it. ``None`` hides
            the preview.
    """

    banner_name: str
    season_name: str
    featured_name: str
    featured_rarity: int
    featured_art: Path | None
    bundle_names: tuple[str, ...]
    rates: tuple[tuple[int, float], ...]
    single_cost: int
    ten_cost: int
    pity_count: int
    hard_pity: int
    frame_art: Path | None = None


def banner_page_data(
    banner: GachaBanner,
    *,
    pity_count: int,
    bundle_item_ids: Sequence[str] = (),
    item_names: Mapping[str, str] | None = None,
    item_art: Mapping[str, Path] | None = None,
) -> BannerPageData:
    """Map a banner plus the requester's pity onto the showcase page's data.

    Args:
        banner: The open banner.
        pity_count: The requesting player's pity counter, from ``GachaState``.
        bundle_item_ids: Item ids granted alongside the first featured ★6
            (season frame, then theme), read from season metadata by the
            handler. Order is preserved.
        item_names: Optional display names by item id, filled by the handler
            from the inventory. Ids missing from the mapping fall back to the
            raw item id (bundles) or the banner entry name (featured).
        item_art: Optional art image paths by item id, filled by the handler
            from item metadata. The featured entry's art becomes the
            centerpiece; the first bundle item carrying art (the season
            avatar frame) becomes the ring preview under the bundle line.

    Returns:
        Page data ready for :func:`banner_page`.
    """

    names = item_names or {}
    art = item_art or {}
    featured = _featured_entry(banner)
    # ``current_rates`` writes 0.0 entries for rarities 2/1 when the pity
    # boost overflows the rarity-4/3 pool (near hard pity), even when the
    # banner never drops those rarities. Showing 「★2 0.00%」 for a rarity that
    # does not exist in the pool would be misleading, so the card keeps only
    # the rarities the banner actually offers (★6 always: it is the boosted
    # target and the reason hard pity exists).
    shown = set(banner.base_rates) | {6}
    rates = {
        rarity: rate
        for rarity, rate in current_rates(banner, pity_count).items()
        if rarity in shown
    }
    return BannerPageData(
        banner_name=banner.name,
        season_name=banner.season_name,
        featured_name=(
            names.get(featured.item_id, featured.name) if featured else ""
        ),
        featured_rarity=featured.rarity if featured else 0,
        featured_art=art.get(featured.item_id) if featured else None,
        bundle_names=tuple(
            names.get(item_id, item_id) for item_id in bundle_item_ids
        ),
        rates=tuple(sorted(rates.items(), reverse=True)),
        single_cost=banner.single_cost,
        ten_cost=banner.ten_cost,
        pity_count=pity_count,
        hard_pity=banner.hard_pity,
        frame_art=next(
            (art[item_id] for item_id in bundle_item_ids if item_id in art), None
        ),
    )


def _featured_entry(banner: GachaBanner) -> GachaEntry | None:
    """The entry the showcase leads with: the highest-rarity featured entry.

    A banner without featured entries (a misconfiguration the service
    tolerates) falls back to its highest-rarity entry so the card still has a
    face; an entry-less banner yields ``None`` and the page simply omits the
    featured row.
    """

    if not banner.entries:
        return None
    return max(banner.entries, key=lambda entry: (entry.featured, entry.rarity))


def render_banner(data: BannerPageData, kit: BaseKit | None = None) -> Image.Image:
    """Render the banner showcase page.

    Args:
        data: Pre-assembled page data.
        kit: Active kit — the season's theme kit, resolved by the handler.
            Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return banner_page(data, kit).render()


def banner_page(data: BannerPageData, kit: BaseKit | None = None) -> AutoPage:
    """Build the banner showcase page without rendering it.

    Args:
        data: Pre-assembled page data.
        kit: Active kit — the season's theme kit, resolved by the handler.
            Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    sections: list[Component] = []
    showcase = _showcase(kit, data)
    if showcase is not None:
        sections.append(showcase)
    sections.append(_details_deck(kit, data))
    return card_page(
        kit,
        title=data.banner_name,
        subtitle=(
            data.season_name
            if isinstance(kit, MewtypeKit)
            else f"{data.season_name} · 期间限定"
        ),
        article_title="限定卡池",
        body=VStack(sections, gap=24, align="stretch"),
        footer=_footer(kit),
    )


def _showcase(kit: BaseKit, data: BannerPageData) -> Component | None:
    """One cinematic hero: product copy on the left, character art on the right."""

    if not data.featured_name and data.featured_art is None and not data.bundle_names:
        return None

    hero_height = _HERO_HEIGHT if data.featured_art is not None else _ARTLESS_HERO_HEIGHT
    copy_rows: list[Component] = [
        badge(kit, "LIMITED", width=112, height=34, font_size=18),
    ]
    if data.featured_name:
        copy_rows.extend(
            [
                kit.text(
                    data.featured_name,
                    font_size=36,
                    max_lines=3,
                    overflow="ellipsis",
                ),
                kit.text(
                    "★" * data.featured_rarity,
                    font_size=26,
                    wrap=False,
                    max_lines=1,
                ),
            ]
        )
    if data.bundle_names:
        copy_rows.extend(
            [
                Frame(None, height=Fill()),
                kit.separator(length=Fill()),
                kit.text(
                    "首次入手加赠",
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
                _bundle_offer(kit, data.bundle_names, data.frame_art),
            ]
        )

    copy = Frame(
        VStack(copy_rows, gap=14, align="start"),
        width=Fixed(
            _HERO_COPY_WIDTH if data.featured_art is not None else CONTENT_WIDTH
        ),
        height=Fill(),
        align_x="stretch",
        align_y="stretch",
    )
    children: list[Component] = [copy]
    if data.featured_art is not None:
        children.append(
            Frame(
                kit.image(
                    data.featured_art,
                    width=Fill(),
                    height=Fill(),
                    fit="contain",
                ),
                width=Fill(),
                height=Fill(),
                align_x="end",
                align_y="end",
            )
        )

    return kit.panel(
        HStack(children, gap=8, align="stretch"),
        width=Fixed(CONTENT_WIDTH),
        height=Fixed(hero_height),
        padding=Insets.only(left=30, top=28, right=18, bottom=24),
        radius=24,
    )


def _bundle_offer(
    kit: BaseKit,
    bundle_names: Sequence[str],
    frame_art: Path | None,
) -> Component:
    """Compact bonus product line, with the frame shown beside the copy."""

    copy = kit.text(
        " · ".join(bundle_names),
        font_size=BODY_SIZE,
        max_lines=3,
        overflow="ellipsis",
    )
    if frame_art is None:
        return copy
    return HStack(
        [
            Frame(copy, width=Fill(), align_x="start", align_y="center"),
            _frame_preview(kit, frame_art),
        ],
        gap=12,
        align="center",
    )


def _frame_preview(kit: BaseKit, frame_art: Path) -> Component:
    """The bundled avatar-frame ring, shown rather than only named.

    Live round 3: the bundle line said 「星之鼓动六星角色头像框」 but the card
    never showed the ring. Contain-fit into a square slot, centered under the
    bundle line, clearly smaller than the standing art above — a product
    shot, not a second centerpiece.
    """

    return Frame(
        kit.image(
            frame_art,
            width=Fixed(_FRAME_PREVIEW),
            height=Fixed(_FRAME_PREVIEW),
            fit="contain",
        ),
        width=Fixed(_FRAME_PREVIEW),
        height=Fixed(_FRAME_PREVIEW),
        align_x="center",
        align_y="center",
    )


def _details_deck(kit: BaseKit, data: BannerPageData) -> Component:
    """Two instrument-like bays: rarity rates, then pull cost and pity state."""

    rate_rows: list[Component] = [
        kit.text(
            "当前出率",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        )
    ]
    rate_rows.extend(_rate_row(kit, rarity, rate) for rarity, rate in data.rates)
    rates = kit.panel(
        VStack(rate_rows, gap=14, align="stretch"),
        width=Fixed(_RATE_PANEL_WIDTH),
        height=Fixed(_DETAIL_HEIGHT),
        padding=Insets.all(24),
        radius=22,
    )

    state = kit.panel(
        VStack(
            [
                kit.text(
                    "跃迁配置",
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
                HStack(
                    [
                        _cost_block(kit, "单抽", data.single_cost),
                        kit.separator(
                            orientation="vertical",
                            length=Fixed(58),
                        ),
                        _cost_block(kit, "十连", data.ten_cost),
                    ],
                    gap=20,
                    align="center",
                ),
                kit.separator(length=Fill()),
                _pity_block(kit, data),
            ],
            gap=16,
            align="stretch",
        ),
        width=Fixed(_STATE_PANEL_WIDTH),
        height=Fixed(_DETAIL_HEIGHT),
        padding=Insets.all(24),
        radius=22,
    )
    return HStack([rates, state], gap=_DETAIL_GAP, align="stretch")


def _cost_block(kit: BaseKit, label: str, cost: int) -> Component:
    return Frame(
        VStack(
            [
                kit.text(
                    label,
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
                kit.text(
                    f"{cost}",
                    font_size=34,
                    wrap=False,
                    max_lines=1,
                ),
                kit.text(
                    "张星星贴纸",
                    font_size=18,
                    color=kit.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=2,
            align="start",
        ),
        width=Fill(),
        align_x="start",
        align_y="center",
    )


def _rate_row(kit: BaseKit, rarity: int, rate: float) -> Component:
    """One rarity's rate: star label left, percentage right.

    The star label is content, not scaffolding — the percentage is meaningless
    without it — so it gets the full text color at body size, never a tiny
    glyph run.
    """

    return HStack(
        [
            Frame(
                kit.text(
                    f"★{rarity}", font_size=BODY_SIZE, wrap=False, max_lines=1
                ),
                width=Fill(),
                align_x="start",
                align_y="center",
            ),
            kit.text(
                f"{rate * 100:.2f}%",
                font_size=26,
                align="right",
                wrap=False,
                max_lines=1,
            ),
        ],
        gap=16,
        align="center",
    )


def _pity_block(kit: BaseKit, data: BannerPageData) -> Component:
    """The requester's pity as a meter.

    The meter's own label is suppressed because the stat row's value already
    states ``count/ceiling`` — exactly the case the ``meter`` docstring allows.
    """

    return VStack(
        [
            stat_row(kit, "保底计数", f"{data.pity_count}/{data.hard_pity}"),
            meter(
                kit,
                value=data.pity_count,
                total=data.hard_pity,
                label="",
            ),
        ],
        gap=10,
        align="stretch",
    )


def _footer(kit: BaseKit) -> Component:
    """The pull commands. Scaffolding, muted — the card above is the content."""

    return Frame(
        kit.text(
            "/抽卡 单抽 · /抽卡 十连 · /抽卡 记录",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )
