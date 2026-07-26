"""Reward presentation shared by the three mailbox cards.

The mail detail card and the claim-all receipt show the same thing — an item
id, a quantity, and whether the player actually gained it — so the tile is
built once here and reused rather than copied.

Two constraints shape this module:

* ``plugins.inventory.service.get_item`` reads the process-global inventory
  session, which is not thread safe. Every lookup in here therefore has to run
  on the event loop thread while the component tree is being built, never
  inside ``Page.render_async``. That is why the handlers build the page first
  and only offload the raster.
* Item lookups are best effort. A card that cannot name an item is still worth
  sending, so a failed lookup degrades to the raw item id instead of raising
  out of a message handler.

Nothing in here carries meaning by hue, which is what lets one implementation
serve all eight kits. A tile the player just gained shows a large numeral; a
tile they already owned shows a word where the numeral would be. That is a
size difference, a glyph difference and a color difference at once, so it
survives ``MangaKit`` and it survives a chat client's downscale.
"""

from typing import Iterable
from typing import Sequence

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import Component
from plugins.render import normalize_color
from plugins.render.color import ColorLike
from plugins.render.kits.atoms import mix_color

#: One reward tile. Three of them plus two gaps span exactly ``INNER_WIDTH``.
TILE_WIDTH = 228
TILE_HEIGHT = 160
TILE_PADDING = 12
TILE_GAP = 18
TILE_COLUMNS = 3

#: Display numeral inside a tile. Large on purpose: the quantity is the payload
#: and it is the one thing that has to survive a client downscale.
NUMERAL_SIZE = 48

#: How far the tile surface is pushed away from its parent panel. A plain
#: ``panel_fill`` tile would be invisible inside a ``panel_fill`` panel in the
#: opaque kits, so the tile always gets the mixed inset.
TILE_MIX = 0.10


def tile_fill(kit: BaseKit) -> ColorLike:
    """Return the inset surface color for a reward tile.

    Args:
        kit: Active kit.

    Returns:
        Fill color, always distinguishable from ``kit.panel_fill``.
    """

    return mix_color(
        normalize_color(kit.panel_fill),
        normalize_color(kit.text_color),
        TILE_MIX,
    )


def item_facts(item_id: str) -> tuple[str, str, bool]:
    """Look up the player-facing facts about an item.

    Args:
        item_id: Inventory item id.

    Returns:
        ``(name, unit_name, stackable)``. Degrades to ``(item_id, "", True)``
        when the catalog is unavailable or the item is unknown.
    """

    try:
        from ...inventory.service import get_item

        item = get_item(item_id)
    except Exception:
        return item_id, "", True
    if item is None:
        return item_id, "", True
    unit = item.currency.unit_name if item.currency else ""
    return item.name, unit or "", bool(item.stackable)


def item_display(item_id: str, quantity: int) -> str:
    """Format one item amount the way the rest of the bot writes it.

    Args:
        item_id: Inventory item id.
        quantity: Amount.

    Returns:
        Display string, e.g. ``赛季积分 x100Pt``.
    """

    try:
        from ...inventory.service import display_item_amount

        return display_item_amount(item_id, quantity)
    except Exception:
        return f"{item_id} x{quantity}"


def summarize(
    amounts: Sequence[tuple[str, int]],
    *,
    limit: int | None = None,
    separator: str = " · ",
) -> str:
    """Join item amounts into one line, optionally collapsing the tail.

    Args:
        amounts: ``(item_id, quantity)`` pairs.
        limit: Show at most this many items and append ``+N`` for the rest.
        separator: Separator between items.

    Returns:
        Summary line, empty when there is nothing to show.
    """

    parts = [item_display(item_id, quantity) for item_id, quantity in amounts]
    if not parts:
        return ""
    if limit is not None and len(parts) > limit:
        return separator.join(parts[:limit]) + f" +{len(parts) - limit}"
    return separator.join(parts)


def attachment_summary(
    attachments: Sequence, *, limit: int | None = None, separator: str = " · "
) -> str:
    """Join mail attachments into one line.

    Args:
        attachments: Objects carrying ``item_id`` and ``quantity``.
        limit: Show at most this many items and append ``+N`` for the rest.
        separator: Separator between items.

    Returns:
        Summary line, empty when there are no attachments.
    """

    return summarize(
        [(item.item_id, item.quantity) for item in attachments],
        limit=limit,
        separator=separator,
    )


def reward_tile(
    kit: BaseKit,
    item_id: str,
    quantity: int,
    *,
    claimed: bool = True,
    owned_label: str = "已有",
) -> Component:
    """One reward as a tile: numeral over item name.

    Args:
        kit: Active kit.
        item_id: Inventory item id.
        quantity: Amount granted, or the amount that was already owned.
        claimed: Whether this grant actually landed now.
        owned_label: Word shown in place of the numeral when it did not.

    Returns:
        Tile component of :data:`TILE_WIDTH` x :data:`TILE_HEIGHT`.
    """

    name, unit, stackable = item_facts(item_id)
    inner = TILE_WIDTH - TILE_PADDING * 2

    if not claimed:
        head: Component = kit.text(
            owned_label,
            font_size=BODY_SIZE,
            color=kit.muted_text_color,
            align="center",
            wrap=False,
            max_lines=1,
        )
        caption = name
    elif stackable or quantity > 1:
        head = kit.text(
            str(quantity),
            font_size=NUMERAL_SIZE,
            align="center",
            wrap=False,
            max_lines=1,
        )
        caption = f"{name} {unit}".strip()
    else:
        head = kit.text(
            "获得",
            font_size=BODY_SIZE,
            color=kit.muted_text_color,
            align="center",
            wrap=False,
            max_lines=1,
        )
        caption = name

    return kit.panel(
        Frame(
            VStack(
                [
                    Frame(head, width=Fixed(inner), align_x="stretch"),
                    Frame(
                        kit.text(
                            caption,
                            font_size=LABEL_SIZE,
                            align="center",
                            max_lines=2,
                        ),
                        width=Fixed(inner),
                        align_x="stretch",
                    ),
                ],
                gap=8,
                align="center",
            ),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(TILE_WIDTH),
        height=Fixed(TILE_HEIGHT),
        padding=TILE_PADDING,
        fill=tile_fill(kit),
    )


def reward_grid(kit: BaseKit, tiles: Sequence[Component]) -> Component:
    """Lay tiles out in a centered grid of at most three columns.

    Args:
        kit: Active kit.
        tiles: Tiles from :func:`reward_tile`.

    Returns:
        Grid component, centered inside :data:`utils.cards.INNER_WIDTH`.
    """

    columns = max(1, min(TILE_COLUMNS, len(tiles)))
    rows = max(1, -(-len(tiles) // columns))
    return Frame(
        Grid(
            children=list(tiles),
            columns=columns,
            rows=rows,
            column_track=Fixed(TILE_WIDTH),
            row_track=Fixed(TILE_HEIGHT),
            gap=TILE_GAP,
        ),
        width=Fixed(INNER_WIDTH),
        align_x="center",
        align_y="center",
    )


def section_band(
    kit: BaseKit,
    caption: str,
    note: str | None = None,
    *,
    width: int = INNER_WIDTH,
) -> Component:
    """A section caption on the left with an optional count on the right.

    This is the inverse of :func:`utils.cards.stat_row`: here the left side is
    the heading and carries the emphasis, and the right side is the scaffolding.

    Args:
        kit: Active kit.
        caption: Section heading.
        note: Optional muted note, usually a count.
        width: Band width.

    Returns:
        Band component.
    """

    cells: list[Component] = [
        Frame(
            kit.text(caption, font_size=BODY_SIZE, wrap=False, max_lines=1),
            width=Fill(),
            align_x="start",
            align_y="center",
        )
    ]
    if note:
        cells.append(
            kit.text(
                note,
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                align="right",
                wrap=False,
                max_lines=1,
            )
        )
    return Frame(
        HStack(cells, gap=16, align="center"),
        width=Fixed(width),
        align_x="stretch",
        align_y="center",
    )


def tiles_for_attachments(
    kit: BaseKit,
    attachments: Sequence,
    results: Sequence,
) -> list[Component]:
    """Build one tile per attachment, pairing it with its grant result.

    ``grant_many`` returns results positionally, so attachment ``i`` owns
    result ``i``. An empty ``results`` means the mail had already been claimed
    on an earlier read, which is a third state and gets its own word.

    Args:
        kit: Active kit.
        attachments: Mail attachments.
        results: ``GrantResult`` values from ``grant_many``, possibly empty.

    Returns:
        Tiles in attachment order.
    """

    ordered = list(results)
    tiles: list[Component] = []
    for index, attachment in enumerate(attachments):
        result = ordered[index] if index < len(ordered) else None
        if result is None:
            tiles.append(
                reward_tile(
                    kit,
                    attachment.item_id,
                    attachment.quantity,
                    claimed=False,
                    owned_label="已领取",
                )
            )
        elif result.granted > 0:
            tiles.append(reward_tile(kit, result.item_id, result.granted))
        else:
            tiles.append(
                reward_tile(
                    kit,
                    result.item_id,
                    result.quantity,
                    claimed=False,
                )
            )
    return tiles


def any_granted(results: Iterable) -> bool:
    """Whether any grant result actually added something."""

    return any(getattr(result, "granted", 0) > 0 for result in results)
