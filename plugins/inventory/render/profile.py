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
from utils.cards import CONTENT_WIDTH
from utils.cards import meter
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import player_card
from utils.cards import panel_section
from plugins.render import Frame
from plugins.render import Fixed
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.types import ImageSource
from plugins.render.kits.bangdream import BanGDreamKit
from plugins.render.kits.kasumi import KasumiKit
from plugins.render.kits.kasumi.components import STANDING_ART


_ART_WIDTH = 288
_SHOWCASE_GAP = 20
_SHOWCASE_HEIGHT = 420


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
        xp_in_level: XP earned inside the current level
            (``user.xp - total_xp_for_level(user.level)``).
        xp_level_span: XP between the current level and the next
            (``total_xp_for_level(level + 1) - total_xp_for_level(level)``).
            ``0`` renders no XP meter row.
        offseason: Whether the Pt balance is off-season temporary Pt
            (``monetary.is_using_offseason_points()``). Labels the Pt row
            休赛期临时 Pt and adds the not-carried-over note.
        standing_art: Art asset of the equipped 立绘 cosmetic, resolved by the
            handler from the item's ``metadata.art`` path. The page renders it
            in a sibling frame beside the identity panel. ``None`` uses the
            Kasumi theme's built-in art, and no art in other themes.
        avatar_frame: Art asset of the equipped 头像框 cosmetic. ``None`` keeps
            the kit's unequipped avatar treatment.
    """

    identity: PlayerIdentity
    current_pt: int
    description: str = ""
    star_stickers: int = 0
    bonsai: int = 0
    season_name: str | None = None
    season_rank: int | None = None
    equipped: tuple[tuple[str, str], ...] = ()
    xp_in_level: int = 0
    xp_level_span: int = 0
    offseason: bool = False
    standing_art: ImageSource | None = None
    avatar_frame: ImageSource | None = None


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
            _profile_showcase(kit, data),
            panel_section(
                kit,
                VStack(_stat_rows(kit, data), gap=18, align="stretch"),
                fill=(255, 255, 255, 255) if isinstance(kit, BanGDreamKit) else None,
            ),
        ],
        gap=24,
        align="stretch",
    )

    return card_page(
        kit,
        title="资料",
        subtitle="个人资料" if isinstance(kit, BanGDreamKit) else data.season_name,
        body=body,
        footer=_footer(kit),
        owner_name=data.identity.nickname,
    )


def _profile_showcase(kit: BaseKit, data: ProfileData) -> Component:
    """Keep identity information and standing art in separate layout regions."""

    art = data.standing_art
    if art is None and isinstance(kit, KasumiKit):
        art = STANDING_ART

    identity_width = (
        CONTENT_WIDTH
        if art is None
        else CONTENT_WIDTH - _ART_WIDTH - _SHOWCASE_GAP
    )
    identity = player_card(
        kit,
        data.identity,
        current_pt=data.current_pt,
        description=data.description,
        width=identity_width,
        height=_SHOWCASE_HEIGHT,
        frame_image=data.avatar_frame,
    )
    if art is None:
        return identity

    return HStack(
        [
            identity,
            Frame(
                kit.image(art, height=Fixed(_SHOWCASE_HEIGHT), fit="contain"),
                width=Fixed(_ART_WIDTH),
                height=Fixed(_SHOWCASE_HEIGHT),
                align_x="end",
                align_y="end",
            ),
        ],
        gap=_SHOWCASE_GAP,
        align="stretch",
    )


def _stat_rows(kit: BaseKit, data: ProfileData) -> list[Component]:
    rows: list[Component] = []
    if data.xp_level_span > 0:
        rows.append(_xp_row(kit, data))
    if data.offseason:
        rows.append(stat_row(kit, "休赛期临时 Pt", f"{data.current_pt} Pt"))
        # Must-read: the note is the whole point of the off-season flag, so it
        # gets the full text color, never muted.
        rows.append(
            kit.text(
                "休赛期临时 Pt 不会计入下一赛季",
                font_size=LABEL_SIZE,
                wrap=False,
                max_lines=1,
            )
        )
    rows.append(stat_row(kit, "星星贴纸", f"{data.star_stickers} 张"))
    rows.append(stat_row(kit, "盆栽", f"{data.bonsai} 盆"))
    if data.season_name and data.season_rank:
        rows.append(stat_row(kit, "赛季排名", f"第 {data.season_rank} 名"))
    for slot_label, item_name in data.equipped:
        rows.append(stat_row(kit, slot_label, item_name))
    return rows


def _xp_row(kit: BaseKit, data: ProfileData) -> Component:
    """Level-XP progress: a stat row stating the numbers, plus the bare track.

    The meter's own label is suppressed because the stat row's value already
    states ``current/span`` — exactly the case the ``meter`` docstring allows.
    """

    return VStack(
        [
            stat_row(
                kit, "等级经验", f"{data.xp_in_level}/{data.xp_level_span} XP"
            ),
            meter(
                kit,
                value=data.xp_in_level,
                total=data.xp_level_span,
                label="",
            ),
        ],
        gap=10,
        align="stretch",
    )


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
