"""The pull reveal page — what ``/抽卡 单抽`` and ``/抽卡 十连`` reply with.

The grid itself is the Tier A ``pull_reveal`` surface, dispatched through
``utils.cards.pull_reveal`` so a kit that authored a bespoke reveal wins and
every other kit gets the shared fallback. This module only assembles the page
around it: banner name as the title, 单抽/十连 as the subtitle, bundled bonus
grants and the pity counter as the footer.

:func:`pull_page_data` is the one place that maps ``GachaResult`` rows into
``PullRevealItem``. It is pure — the banner is passed in, and item names/art
come through the optional mappings the handler fills from the inventory on the
event-loop thread — so this module never touches a database and only the
raster is offloaded via ``await pull_page(...).render_async()``.
"""

import re
from typing import Mapping
from typing import Sequence
from pathlib import Path
from dataclasses import dataclass

from PIL import Image

from utils.cards import LABEL_SIZE
from utils.cards import CONTENT_WIDTH
from utils.cards import card_page
from utils.cards import pull_reveal
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PullRevealItem
from plugins.render.kits.bangdream import BanGDreamKit

from ..service import GachaBanner
from ..service import GachaResult

_COMPENSATION_PATTERN = re.compile(r"already_owned_compensated:(\d+)")

# A ten-pull is a result screen: ten narrow character tickets sit in one
# uninterrupted horizontal strip.
TEN_PULL_CONTENT_WIDTH = 1480


@dataclass(frozen=True)
class PullPageData:
    """Everything the reveal page shows, assembled by :func:`pull_page_data`.

    Attributes:
        banner_name: Player-facing banner name (page title).
        pulls: Reveal items in draw order (1-10).
        pity_after: Pity counter after the last pull of the batch.
        hard_pity: The banner's hard pity ceiling.
        bonus_grants: Player-facing names of items granted alongside a pull
            but not pulled themselves — the season frame/theme bundled with
            the first featured ★6. Empty when nothing extra was granted.
    """

    banner_name: str
    pulls: tuple[PullRevealItem, ...]
    pity_after: int
    hard_pity: int
    bonus_grants: tuple[str, ...] = ()


def pull_page_data(
    results: Sequence[GachaResult],
    banner: GachaBanner,
    *,
    item_names: Mapping[str, str] | None = None,
    item_art: Mapping[str, Path] | None = None,
) -> PullPageData:
    """Map service pull results onto the reveal page's data.

    ``is_new`` comes from the pulled item's own :class:`GrantDetail`: the tile
    is NEW exactly when that grant added a copy (``granted > 0``), so a
    featured ★6 whose standing art is fresh gets its badge even when the
    bundled frame/theme were duplicates. Results without grant details (older
    rows, tests) fall back to the message heuristic: an empty joined message
    can only come from a completely fresh grant chain.

    Args:
        results: Pull results in draw order; must be non-empty.
        banner: The banner the pulls came from, for featured flags.
        item_names: Optional item display names by id, filled by the handler
            from the inventory. Used for :attr:`PullPageData.bonus_grants`;
            ids missing from the mapping fall back to the raw item id.
        item_art: Optional art image paths by id, filled by the handler from
            item metadata. Pulled items present here get their art on the
            reveal tile.

    Returns:
        Page data ready for :func:`pull_page`.
    """

    if not results:
        raise ValueError("results must be non-empty")

    names = item_names or {}
    art = item_art or {}
    featured_ids = {entry.item_id for entry in banner.entries if entry.featured}
    pulls = tuple(
        PullRevealItem(
            name=result.name,
            rarity=result.rarity,
            is_new=_is_new(result),
            featured=result.item_id in featured_ids,
            image=art.get(result.item_id),
            note=grant_note(result.grant_message),
        )
        for result in results
    )
    return PullPageData(
        banner_name=banner.name,
        pulls=pulls,
        pity_after=results[-1].pity_after,
        hard_pity=banner.hard_pity,
        bonus_grants=_bonus_grants(results, names),
    )


def _is_new(result: GachaResult) -> bool:
    """Whether the pulled item itself was freshly granted."""

    for grant in result.grants:
        if grant.item_id == result.item_id:
            return grant.granted > 0
    return not result.grant_message


def _bonus_grants(
    results: Sequence[GachaResult], names: Mapping[str, str]
) -> tuple[str, ...]:
    """Names of freshly granted items that were not themselves pulled.

    These are the frame/theme bundled with the first featured ★6 — the
    theme-ships-with-gacha moment — surfaced in grant order, deduplicated.
    """

    seen: list[str] = []
    for result in results:
        for grant in result.grants:
            if grant.item_id == result.item_id or grant.granted <= 0:
                continue
            name = names.get(grant.item_id, grant.item_id)
            if name not in seen:
                seen.append(name)
    return tuple(seen)


def grant_note(message: str) -> str:
    """Decode a machine grant message into a short player-facing note.

    ``already_owned_compensated:120`` is the inventory service's duplicate
    path; the number is the 盆栽 compensation. Multiple joined messages (a
    featured ★6 grants up to three items) sum their compensation. Anything
    unrecognized passes through untouched so no information is silently lost.

    Args:
        message: Raw ``GachaResult.grant_message``.

    Returns:
        Short annotation for the reveal tile, empty for a clean grant.
    """

    if not message:
        return ""
    compensation = sum(int(m) for m in _COMPENSATION_PATTERN.findall(message))
    if compensation > 0:
        return f"盆栽 +{compensation}"
    if "already_owned" in message:
        return "重复"
    if message == "done":
        return "已发放"
    return message


def render_pull(data: PullPageData, kit: BaseKit | None = None) -> Image.Image:
    """Render the pull reveal page.

    Args:
        data: Pre-assembled page data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return pull_page(data, kit).render()


def pull_page(data: PullPageData, kit: BaseKit | None = None) -> AutoPage:
    """Build the pull reveal page without rendering it.

    Args:
        data: Pre-assembled page data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    is_ten = len(data.pulls) >= 10
    page_width = TEN_PULL_CONTENT_WIDTH if is_ten else CONTENT_WIDTH
    return card_page(
        kit,
        title=data.banner_name,
        subtitle="十连" if is_ten else "单抽",
        # The tickets are the result screen. Keeping them directly on the
        # themed sky lets the character art breathe instead of nesting it in
        # a second, featureless white card.
        body=pull_reveal(kit, data.pulls, width=page_width),
        footer=_footer(kit, data),
        width=page_width,
    )


def _footer(kit: BaseKit, data: PullPageData) -> Component:
    """Bonus-grant line (when any) above the pity counter."""

    rows: list[Component] = []
    if data.bonus_grants:
        rows.append(_bonus_line(kit, data.bonus_grants))
    rows.append(_pity_footer(kit, data))
    if len(rows) == 1:
        return rows[0]
    return VStack(rows, gap=10, align="stretch")


def _bonus_line(kit: BaseKit, bonus_grants: Sequence[str]) -> Component:
    """The bundled-grant announcement. Must-read: this is the moment the
    season theme/frame actually reach the player, so full text color."""

    return Frame(
        kit.text(
            "同时获得：" + " · ".join(bonus_grants),
            font_size=LABEL_SIZE,
            max_lines=2,
            overflow="ellipsis",
        ),
        align_x="start",
        align_y="center",
    )


def _pity_footer(kit: BaseKit, data: PullPageData) -> Component:
    """The pity counter. Content the player reads, so full text color."""

    return Frame(
        kit.text(
            f"保底计数 {data.pity_after}/{data.hard_pity}",
            font_size=LABEL_SIZE,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )
