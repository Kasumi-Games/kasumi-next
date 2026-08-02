"""The pull-history card — what ``/抽卡 记录 [页码]`` replies with.

Live round 3: the history reply was still a terse text list. It is now a card:
one row per pull (rarity chip, item name, pull time), a page footer, and the
requester's pity line — rendered in the player's own kit like every other
player surface.

Rarity is encoded by shape and weight, never hue alone, so the card survives
the monochrome manga kit and client downscaling: a ★6 pull gets a filled
``badge`` chip and a slightly taller row, while every rarity stays on the
list's one shared panel.  Other rarities use a bare ``★n`` numeral — the
same two-signal idiom as the reveal tile and ``ladder_rows`` without nesting
one surface inside another.

:func:`history_page_data` is the one place that maps service history rows into
plain display rows. It is pure given its inputs — item names come through the
mapping the handler fills from the inventory on the event-loop thread — so
this module never touches a database and only the raster is offloaded via
``await history_page(...).render_async()``. Timestamps go through
``utils.clock`` (today/yesterday collapse to a word, the rest to a date), so
every displayed time is Beijing time regardless of the host machine.
"""

from typing import TYPE_CHECKING
from typing import Mapping
from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import badge
from utils.cards import card_page
from utils.cards import empty_state
from utils.cards import panel_section
from utils.clock import bot_date
from utils.clock import bot_today
from utils.clock import format_ts
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

from .pull import grant_note

if TYPE_CHECKING:  # service types only annotate; the module stays DB-free
    from ..service import HistoryPage

#: Row height for a plain pull and for the lifted ★6 panel row.
_ROW_HEIGHT = 56
_TOP_ROW_HEIGHT = 64

#: Horizontal inset shared by both row variants so the rarity/name/time
#: columns stay aligned whether or not the row sits on its own panel.
_ROW_INSET = 16

#: Width of the rarity column (chip or bare numeral).
_RARITY_CELL = 64

#: Width of the right-aligned time column; fits ``2026-12-31 23:59``.
_TIME_COLUMN = 180

_ROW_GAP = 14


@dataclass(frozen=True)
class HistoryRow:
    """One rendered pull row.

    Attributes:
        rarity: Star rarity of the pull (1-6).
        name: Player-facing item name (catalog name; raw item id fallback).
        time_text: Display time of the pull, already product-timezone.
        note: Short annotation from the grant message (「盆栽 +60」 for a
            duplicate), empty for a clean grant.
    """

    rarity: int
    name: str
    time_text: str
    note: str = ""


@dataclass(frozen=True)
class HistoryPageData:
    """Everything the history card shows, assembled by :func:`history_page_data`.

    Attributes:
        rows: Pull rows, newest first, at most one page.
        page: 1-based page number after clamping.
        total_pages: Total page count (at least 1).
        total: Total pulls the player has ever made.
        pity_count: The requester's current pity counter.
        hard_pity: The open banner's hard-pity ceiling, or ``None`` when no
            banner is open (offseason) — the pity line then shows the bare
            count.
    """

    rows: tuple[HistoryRow, ...]
    page: int
    total_pages: int
    total: int
    pity_count: int
    hard_pity: int | None = None


def history_page_data(
    history: "HistoryPage",
    *,
    pity_count: int,
    hard_pity: int | None = None,
    item_names: Mapping[str, str] | None = None,
) -> HistoryPageData:
    """Map a service history page onto the card's display data.

    Args:
        history: One page of pulls from ``get_history`` (newest first).
        pity_count: The requester's pity counter, from ``GachaState``.
        hard_pity: The open banner's hard pity, or ``None`` offseason.
        item_names: Optional display names by item id, filled by the handler
            from the inventory. Ids missing from the mapping fall back to the
            raw item id.

    Returns:
        Page data ready for :func:`history_page`.
    """

    names = item_names or {}
    rows = tuple(
        HistoryRow(
            rarity=row.rarity,
            name=names.get(row.item_id, row.item_id),
            time_text=_time_text(row.created_at),
            note=grant_note(row.message),
        )
        for row in history.rows
    )
    return HistoryPageData(
        rows=rows,
        page=history.page,
        total_pages=history.total_pages,
        total=history.total,
        pity_count=pity_count,
        hard_pity=hard_pity,
    )


def _time_text(created_at: float) -> str:
    """A pull's display time: today/yesterday by word, then by date.

    Calendar days in the product timezone, not elapsed hours — 「昨天」 has to
    mean yesterday's date, exactly like the mailbox expiry wording.
    """

    day = bot_date(created_at)
    today = bot_today()
    if day == today:
        return "今天 " + format_ts(created_at, "%H:%M")
    if (today - day).days == 1:
        return "昨天 " + format_ts(created_at, "%H:%M")
    if day.year == today.year:
        return format_ts(created_at, "%m-%d %H:%M")
    return format_ts(created_at, "%Y-%m-%d %H:%M")


def render_history(data: HistoryPageData, kit: BaseKit | None = None) -> Image.Image:
    """Render the pull-history card.

    Args:
        data: Pre-assembled page data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return history_page(data, kit).render()


def history_page(data: HistoryPageData, kit: BaseKit | None = None) -> AutoPage:
    """Build the pull-history page without rendering it.

    Args:
        data: Pre-assembled page data.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()

    if not data.rows:
        return card_page(
            kit,
            title="抽卡记录",
            subtitle="共 0 抽",
            article_title="抽卡记录",
            show_subtitle=False,
            body=panel_section(
                kit,
                empty_state(kit, "暂无抽卡记录\n试试 /抽卡 单抽"),
            ),
        )

    rows = [_row(kit, row) for row in data.rows]
    return card_page(
        kit,
        title="抽卡记录",
        subtitle=f"共 {data.total} 抽",
        article_title="抽卡记录",
        show_subtitle=False,
        body=panel_section(kit, VStack(rows, gap=_ROW_GAP, align="stretch")),
        footer=_footer(kit, data),
    )


def _row(kit: BaseKit, row: HistoryRow) -> Component:
    """One pull row: rarity chip, name, optional note, time.

    A ★6 row uses a filled chip and a slightly taller rhythm, but remains
    on the list's shared surface. Both variants share :data:`_ROW_INSET` so
    the columns line up down the whole card.
    """

    line = HStack(_cells(kit, row), gap=_ROW_GAP, align="center")
    return Frame(
        line,
        width=Fixed(INNER_WIDTH),
        height=Fixed(_TOP_ROW_HEIGHT if row.rarity >= 6 else _ROW_HEIGHT),
        padding=Insets.only(left=_ROW_INSET, right=_ROW_INSET),
        align_x="stretch",
        align_y="stretch",
    )


def _cells(kit: BaseKit, row: HistoryRow) -> list[Component]:
    cells: list[Component] = [
        _rarity_cell(kit, row.rarity),
        Frame(
            kit.text(
                row.name,
                font_size=BODY_SIZE,
                wrap=False,
                max_lines=1,
                overflow="ellipsis",
            ),
            width=Fill(),
            align_x="start",
            align_y="center",
        ),
    ]
    if row.note:
        cells.append(
            kit.text(
                row.note,
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            )
        )
    cells.append(
        Frame(
            kit.text(
                row.time_text,
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                align="right",
                wrap=False,
                max_lines=1,
            ),
            width=Fixed(_TIME_COLUMN),
            align_x="end",
            align_y="center",
        )
    )
    return cells


def _rarity_cell(kit: BaseKit, rarity: int) -> Component:
    """Filled chip for a ★6 pull, bare full-color numeral otherwise."""

    if rarity >= 6:
        return badge(kit, f"★{rarity}", width=_RARITY_CELL, height=32)
    return Frame(
        kit.text(f"★{rarity}", font_size=LABEL_SIZE, wrap=False, max_lines=1),
        width=Fixed(_RARITY_CELL),
        align_x="center",
        align_y="center",
    )


def _footer(kit: BaseKit, data: HistoryPageData) -> Component:
    """Pity line above the page line. Both are content the player reads to
    decide their next pull or page, so full text color; only the paging
    command hint is muted scaffolding."""

    pity = (
        f"保底计数 {data.pity_count}/{data.hard_pity}"
        if data.hard_pity is not None
        else f"保底计数 {data.pity_count}"
    )
    page_cells: list[Component] = [
        Frame(
            kit.text(
                f"第 {data.page}/{data.total_pages} 页 · 共 {data.total} 抽",
                font_size=LABEL_SIZE,
                wrap=False,
                max_lines=1,
            ),
            width=Fill(),
            align_x="start",
            align_y="center",
        )
    ]
    if data.total_pages > 1:
        page_cells.append(
            kit.text(
                "/抽卡 记录 <页码> 翻页",
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                align="right",
                wrap=False,
                max_lines=1,
            )
        )
    return VStack(
        [
            Frame(
                kit.text(pity, font_size=LABEL_SIZE, wrap=False, max_lines=1),
                align_x="start",
                align_y="center",
            ),
            HStack(page_cells, gap=16, align="center"),
        ],
        gap=10,
        align="stretch",
    )
