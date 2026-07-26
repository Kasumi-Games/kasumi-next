"""The profile card — the identity hub behind ``/资料``.

The page is the Tier A ``player_card`` surface on top (dispatched through
``utils.cards.player_card`` so a kit with a bespoke treatment wins), with a
Tier B stats panel below it: currency balances, the season rank when a season
is running, and the equipped cosmetics by display name.

Everything the card shows arrives pre-assembled in :class:`ProfileData` — the
handler gathers it on the event loop thread (the inventory/monetary sessions
are process-global and not thread safe) and this module touches no database,
so ``render_async`` can offload the raster to a worker thread safely.
"""

from dataclasses import dataclass

from PIL import Image

from utils.cards import LABEL_SIZE
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import player_card
from utils.cards import panel_section
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit


@dataclass(frozen=True)
class ProfileData:
    """Everything the profile card shows, gathered by the handler.

    Attributes:
        identity: Player identity (nickname, level, optional avatar).
        current_pt: Season point balance (``monetary.get``).
        description: Player-authored profile line; empty renders no bio row.
        star_stickers: 星星贴纸 balance.
        bonsai: 盆栽 balance.
        season_name: Active season name, or ``None`` in the off-season.
        season_rank: Player's rank in the active season, or ``None``.
        equipped: ``(slot_label, item_name)`` pairs for equipped cosmetics,
            already resolved to player-facing names.
    """

    identity: PlayerIdentity
    current_pt: int
    description: str = ""
    star_stickers: int = 0
    bonsai: int = 0
    season_name: str | None = None
    season_rank: int | None = None
    equipped: tuple[tuple[str, str], ...] = ()


def render_profile(data: ProfileData, kit: BaseKit | None = None) -> Image.Image:
    """Render the profile card.

    Args:
        data: Pre-assembled profile data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return profile_page(data, kit).render()


def profile_page(data: ProfileData, kit: BaseKit | None = None) -> AutoPage:
    """Build the profile page without rendering it.

    The handler uses this so only the raster is offloaded to
    ``await page.render_async()``.

    Args:
        data: Pre-assembled profile data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()

    body = VStack(
        [
            player_card(
                kit,
                data.identity,
                current_pt=data.current_pt,
                description=data.description,
            ),
            panel_section(
                kit,
                VStack(_stat_rows(kit, data), gap=18, align="stretch"),
            ),
        ],
        gap=24,
        align="stretch",
    )

    return card_page(
        kit,
        title="资料",
        subtitle=data.season_name,
        body=body,
        footer=_footer(kit),
        owner_name=data.identity.nickname,
    )


def _stat_rows(kit: BaseKit, data: ProfileData) -> list[Component]:
    rows: list[Component] = [
        stat_row(kit, "星星贴纸", f"{data.star_stickers} 张"),
        stat_row(kit, "盆栽", f"{data.bonsai} 盆"),
    ]
    if data.season_name and data.season_rank:
        rows.append(stat_row(kit, "赛季排名", f"第 {data.season_rank} 名"))
    for slot_label, item_name in data.equipped:
        rows.append(stat_row(kit, slot_label, item_name))
    return rows


def _footer(kit: BaseKit) -> Component:
    return Frame(
        kit.text(
            "/资料 简介 <文本> 修改个人简介",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )
