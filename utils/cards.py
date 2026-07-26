"""Shared card composition for themed image responses.

This is the Tier B toolkit: composition built **only** from ``BaseKit`` atoms, so
one implementation renders correctly in all eight kits. High-visibility surfaces
— game boards, the player card, gacha reveals — are Tier A and get bespoke
per-kit treatments in each kit's own ``components.py`` instead.

It lives outside ``plugins/render`` deliberately. The render module's rule is
that visual components belong to kits; nothing here invents a visual primitive,
it only arranges the atoms a kit already provides.

Two rules in here are load-bearing and were derived from measurement, not taste:

**Filled emphasis never uses ``primary``.** Filling a shape with ``kit.primary``
and putting white text on it measures below AA in four of the eight kits
(sakura 2.16:1, midnight 2.59:1, neon 3.43:1, bangdream 3.60:1). Filling with
``kit.text_color`` and drawing the foreground in ``kit.panel_fill`` measures
6.58:1 or better in all eight. Use :func:`emphasis`; do not pick these colors
at a call site.

**``muted_text_color`` is decoration, not content.** It measures below AA on its
own panel in half the kits (sakura 2.72:1, bangdream 3.09:1, sailing 3.38:1,
minimal 3.47:1). Use it for labels and scaffolding, never for a number or name
the player actually has to read.
"""

from typing import Sequence

from PIL import Image

from plugins.render import Fill
from plugins.render import Grid
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import Insets
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render import PullRevealItem
from plugins.render.color import ColorLike

#: Outer content column. Every card uses this so grids line up across plugins.
CONTENT_WIDTH = 784

#: Padding between a panel edge and its contents.
PANEL_PADDING = 32

#: Usable width inside a full-width panel (``CONTENT_WIDTH - 2 * PANEL_PADDING``).
INNER_WIDTH = CONTENT_WIDTH - PANEL_PADDING * 2

#: Padding between the page edge and the content column.
PAGE_PADDING = 40

TITLE_SIZE = 40
SUBTITLE_SIZE = 26
BODY_SIZE = 24
LABEL_SIZE = 22

#: Floor for anything a player must read. Chat clients downscale, and the page
#: itself already downsamples from ``pixel_ratio`` 2.
MIN_READABLE_SIZE = 22


def emphasis(kit: BaseKit) -> tuple[ColorLike, ColorLike]:
    """Return ``(fill, on_fill)`` for a filled emphasis shape.

    Args:
        kit: Active kit.

    Returns:
        Fill color and the foreground color to draw on top of it.
    """

    return kit.text_color, kit.panel_fill


def badge(
    kit: BaseKit,
    text: str,
    *,
    width: int | None = None,
    height: int = 40,
    font_size: int = LABEL_SIZE,
) -> Component:
    """A small filled chip, for ranks, counts, and status words.

    Args:
        kit: Active kit.
        text: Chip label.
        width: Optional fixed width; defaults to a square-ish chip.
        height: Chip height.
        font_size: Label size.

    Returns:
        Chip component.
    """

    fill, on_fill = emphasis(kit)
    return kit.panel(
        Frame(
            kit.text(
                text,
                font_size=font_size,
                color=on_fill,
                align="center",
                wrap=False,
                max_lines=1,
            ),
            align_x="center",
            align_y="center",
        ),
        width=Fixed(width if width is not None else height),
        height=Fixed(height),
        fill=fill,
        radius=height // 2,
    )


def stat_row(
    kit: BaseKit,
    label: str,
    value: str,
    *,
    value_size: int = BODY_SIZE,
    label_size: int = LABEL_SIZE,
    width: int | None = None,
) -> Component:
    """A label on the left and a value on the right.

    The label is muted scaffolding; the value carries the information and is
    drawn in the kit's primary text color.

    Args:
        kit: Active kit.
        label: Field name.
        value: Field value.
        value_size: Value font size.
        label_size: Label font size.
        width: Optional fixed row width.

    Returns:
        Row component.
    """

    return Frame(
        HStack(
            [
                Frame(
                    kit.text(
                        label,
                        font_size=label_size,
                        color=kit.muted_text_color,
                        wrap=False,
                        max_lines=1,
                    ),
                    width=Fill(),
                    align_x="start",
                    align_y="center",
                ),
                kit.text(
                    value,
                    font_size=value_size,
                    align="right",
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=16,
            align="center",
        ),
        width=Fixed(width) if width is not None else Fill(),
        align_x="stretch",
        align_y="center",
    )


def meter(
    kit: BaseKit,
    *,
    value: float,
    total: float,
    width: int = INNER_WIDTH,
    height: int = 20,
    label: str | None = None,
) -> Component:
    """A progress track with its fill, and always a numeric label.

    The label is not optional decoration. At the sizes chat clients downscale
    to, the fill/track boundary is the first thing to disappear — in ``fluent``
    the panel fill is only alpha 178, and in ``sakura`` the fill-on-panel ratio
    is 2.16:1. The number is what survives.

    Args:
        kit: Active kit.
        value: Current progress.
        total: Progress denominator. Values ``<= 0`` render an empty track.
        width: Track width.
        height: Track height.
        label: Override for the default ``value/total`` label. Pass ``""`` to
            suppress it only when an adjacent element already states the number.

    Returns:
        Meter component.
    """

    ratio = 0.0 if total <= 0 else max(0.0, min(1.0, value / total))
    filled = round(width * ratio)
    fill_color, _ = emphasis(kit)

    track = kit.panel(
        Frame(
            kit.panel(
                None,
                width=Fixed(filled),
                height=Fixed(height),
                fill=fill_color,
                radius=height // 2,
            )
            if filled > 0
            else None,
            align_x="start",
            align_y="center",
        ),
        width=Fixed(width),
        height=Fixed(height),
        radius=height // 2,
    )

    text = f"{_trim(value)}/{_trim(total)}" if label is None else label
    if not text:
        return track
    return VStack(
        [
            track,
            Frame(
                kit.text(text, font_size=LABEL_SIZE, align="right", wrap=False),
                width=Fixed(width),
                align_x="stretch",
            ),
        ],
        gap=8,
        align="start",
    )


def headline(kit: BaseKit, text: str, *, positive: bool = True) -> Component:
    """An outcome banner: 胜利/结算 headline for result cards.

    A positive outcome gets the filled emphasis band; a negative one stays
    un-filled so wins and losses are distinguishable by shape in every kit,
    including the monochrome one.

    Args:
        kit: Active kit.
        text: Outcome text, short (胜利 / 挑战失败 / 全部翻开).
        positive: Whether this is a win-like outcome.

    Returns:
        Banner component.
    """

    if positive:
        fill, on_fill = emphasis(kit)
        return kit.panel(
            Frame(
                kit.text(
                    text, font_size=34, color=on_fill, align="center", wrap=False
                ),
                align_x="center",
                align_y="center",
            ),
            width=Fill(),
            height=Fixed(64),
            fill=fill,
            radius=32,
        )
    return Frame(
        kit.text(text, font_size=34, align="center", wrap=False),
        width=Fill(),
        height=Fixed(64),
        align_x="center",
        align_y="center",
    )


def gain_rows(
    kit: BaseKit,
    gains: Sequence[tuple[str, str]],
    *,
    width: int = INNER_WIDTH,
) -> Component:
    """Reward strip: a leading amount column with its label.

    The amount leads and carries the information (``+120 Pt`` in full text
    color); the label is scaffolding. This is the one shared shape for "what
    this interaction earned you" — check-ins, game results, and reveals all use
    it so gains read identically everywhere.

    Deliberately NOT the self-marker left-rule: that shape is reserved for
    "this row is you / is now" (ladder highlight, today's task).

    Args:
        kit: Active kit.
        gains: ``(amount, label)`` pairs, e.g. ``("+120 Pt", "探险收益")``.
        width: Strip width.

    Returns:
        Rows component.
    """

    rows = [
        HStack(
            [
                Frame(
                    kit.text(amount, font_size=26, wrap=False, max_lines=1),
                    width=Fixed(180),
                    align_x="start",
                    align_y="center",
                ),
                Frame(
                    kit.text(
                        label,
                        font_size=LABEL_SIZE,
                        color=kit.muted_text_color,
                        wrap=False,
                        max_lines=1,
                    ),
                    width=Fill(),
                    align_x="start",
                    align_y="center",
                ),
            ],
            gap=16,
            align="center",
        )
        for amount, label in gains
    ]
    return Frame(
        VStack(rows, gap=10, align="stretch"),
        width=Fixed(width),
        align_x="stretch",
        align_y="center",
    )


def task_progress(
    kit: BaseKit,
    name: str,
    done: float,
    total: float,
    *,
    width: int = INNER_WIDTH,
) -> Component:
    """One compact daily-task line: name, mini meter, count.

    The single shared rendering of "today's task" (consistency review #18: it
    previously appeared in three layouts).

    Args:
        kit: Active kit.
        name: Task name; content, so full text color.
        done: Completed count.
        total: Target count.
        width: Row width.

    Returns:
        Row component.
    """

    return Frame(
        HStack(
            [
                Frame(
                    kit.text(name, font_size=BODY_SIZE, wrap=False, max_lines=1),
                    width=Fill(),
                    align_x="start",
                    align_y="center",
                ),
                meter(kit, value=done, total=total, width=180, height=16, label=""),
                kit.text(
                    f"{_trim(done)}/{_trim(total)}",
                    font_size=LABEL_SIZE,
                    align="right",
                    wrap=False,
                    max_lines=1,
                ),
            ],
            gap=14,
            align="center",
        ),
        width=Fixed(width),
        align_x="stretch",
        align_y="center",
    )


def level_up(kit: BaseKit, old_level: int, new_level: int) -> Component:
    """A level-up celebration row: filled chip plus the transition text."""

    return HStack(
        [
            badge(kit, f"Lv.{new_level}", width=96, height=40, font_size=24),
            kit.text(
                f"等级提升！Lv.{old_level} → Lv.{new_level}",
                font_size=BODY_SIZE,
                wrap=False,
                max_lines=1,
            ),
        ],
        gap=14,
        align="center",
    )


def ladder_rows(
    kit: BaseKit,
    rows: list[tuple[int, str, str]],
    *,
    highlight: str | None = None,
    width: int = INNER_WIDTH,
    row_height: int = 56,
    gap: int = 18,
) -> Component:
    """Ranked rows with a filled badge for the top three.

    Rank is encoded twice by shape rather than by hue, so it survives the
    monochrome kit: the top three get a filled badge, everyone else a bare
    numeral. The viewer's own row additionally gets a leading rule.

    Args:
        kit: Active kit.
        rows: ``(rank, name, value)`` triples.
        highlight: Name whose row belongs to the viewer.
        width: Row width.
        row_height: Height of one row.
        gap: Gap between rows.

    Returns:
        Rows component.
    """

    rank_cell = 72
    built: list[Component] = []
    for rank, name, value in rows:
        is_self = highlight is not None and name == highlight
        if rank <= 3:
            marker: Component = badge(kit, str(rank), width=rank_cell, height=40)
        else:
            marker = Frame(
                kit.text(
                    str(rank),
                    font_size=BODY_SIZE,
                    color=kit.muted_text_color,
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
                width=Fixed(rank_cell),
                align_x="center",
                align_y="center",
            )

        cells: list[Component] = [marker]
        if is_self:
            cells.append(
                kit.separator(orientation="vertical", length=Fixed(28), thickness=6)
            )
        cells.append(
            Frame(
                kit.text(name, font_size=BODY_SIZE, wrap=False, max_lines=1),
                width=Fill(),
                align_x="start",
                align_y="center",
            )
        )
        cells.append(
            kit.text(value, font_size=BODY_SIZE, align="right", wrap=False, max_lines=1)
        )

        built.append(
            Frame(
                HStack(cells, gap=16, align="center"),
                width=Fixed(width),
                height=Fixed(row_height),
                align_x="stretch",
                align_y="center",
            )
        )
    return VStack(built, gap=gap, align="stretch")


def empty_state(kit: BaseKit, message: str, *, width: int = INNER_WIDTH) -> Component:
    """A centered placeholder for a card with nothing to show.

    Drawn in the full text color, not muted: when a card is empty the message
    is its entire content, which makes it must-read by this module's own rule.
    """

    return Frame(
        kit.text(
            message,
            font_size=BODY_SIZE,
            align="center",
        ),
        width=Fixed(width),
        height=Fixed(120),
        align_x="center",
        align_y="center",
    )


def theme_signature(
    kit: BaseKit, theme_name: str, owner_name: str | None = None
) -> Component:
    """A credit line naming the theme in play.

    Reads as a photo credit rather than an advert, which is what lets it sit on
    hundreds of images without becoming clutter.

    Args:
        kit: Active kit.
        theme_name: Player-facing theme name.
        owner_name: Whose theme it is, when the image is a shared surface.

    Returns:
        Signature component.
    """

    text = f"{owner_name} 的主题 · {theme_name}" if owner_name else f"主题 · {theme_name}"
    return HStack(
        [
            kit.separator(orientation="vertical", length=Fixed(22), thickness=3),
            kit.text(
                text,
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            ),
        ],
        gap=10,
        align="center",
    )


def signature_for(kit: BaseKit, owner_name: str | None = None) -> Component | None:
    """Return the theme signature, or ``None`` when this theme stays silent.

    A theme marked ``starter`` in the catalog renders no signature, so the
    presence of the line is itself the signal that a theme is worth having.

    Args:
        kit: Active kit.
        owner_name: Whose theme it is, when the image is a shared surface.

    Returns:
        Signature component, or ``None``.
    """

    try:
        from utils.theming import display_name
        from utils.theming import theme_for_kit

        info = theme_for_kit(kit)
    except Exception:
        return None
    if info is None or info.starter:
        return None
    # The kit display name, not the item name: item names carry a 主题 suffix
    # for inventory clarity, which would read as 「主题 · 星之鼓动主题」 here.
    return theme_signature(kit, display_name(info.kit_name), owner_name)


def card_page(
    kit: BaseKit,
    *,
    title: str,
    body: Component,
    subtitle: str | None = None,
    footer: Component | None = None,
    owner_name: str | None = None,
    width: int = CONTENT_WIDTH,
    background_source: object | None = None,
) -> AutoPage:
    """Build the page for a standard response card.

    This is the only header constructor. Renderers must not define their own
    title bar: ``kit.title_pill`` exists on ``BanGDreamKit`` alone, and calling
    it unguarded crashes the other seven kits.

    Args:
        kit: Active kit.
        title: Card title.
        body: Card content.
        subtitle: Optional secondary line under the title.
        footer: Optional footer content, placed above the theme signature.
        owner_name: Whose card this is, for the signature on shared surfaces.
        width: Content column width.
        background_source: Optional image passed to kits whose background
            accepts a source. Ignored by kits that do not.

    Returns:
        Page ready to ``render()`` or ``await render_async()``.
    """

    sections: list[Component] = [_header(kit, title, subtitle, width), body]

    tail: list[Component] = []
    if footer is not None:
        tail.append(footer)
    signature = signature_for(kit, owner_name)
    if signature is not None:
        tail.append(
            Frame(signature, width=Fixed(width), align_x="end", align_y="center")
        )
    if tail:
        sections.append(VStack(tail, gap=12, align="stretch"))

    return AutoPage(
        VStack(sections, gap=24, align="stretch"),
        background=_background(kit, background_source),
        padding=Insets.all(PAGE_PADDING),
        min_width=width + PAGE_PADDING * 2,
        max_width=width + PAGE_PADDING * 2,
    )


def response_card(
    kit: BaseKit,
    *,
    title: str,
    body: Component,
    subtitle: str | None = None,
    footer: Component | None = None,
    owner_name: str | None = None,
    width: int = CONTENT_WIDTH,
) -> Image.Image:
    """Render a standard response card.

    Args:
        kit: Active kit.
        title: Card title.
        body: Card content.
        subtitle: Optional secondary line.
        footer: Optional footer content.
        owner_name: Whose card this is, for the signature.
        width: Content column width.

    Returns:
        Rendered card.
    """

    return card_page(
        kit,
        title=title,
        body=body,
        subtitle=subtitle,
        footer=footer,
        owner_name=owner_name,
        width=width,
    ).render()


def panel_section(
    kit: BaseKit,
    child: Component,
    *,
    width: int = CONTENT_WIDTH,
    padding: int = PANEL_PADDING,
) -> Component:
    """Wrap content in the kit's panel at the standard width and padding."""

    return kit.panel(child, width=Fixed(width), padding=Insets.all(padding))


# ---------------------------------------------------------------------------
# Tier A dispatchers.
#
# The three high-visibility surfaces (game identity strip, player card, gacha
# reveal) are hand-authored per kit. These dispatchers are the only entry
# points callers use: a kit that overrides the BaseKit method gets full
# control, and every other kit falls back to the generic atom composition
# below, so a surface never crashes on a kit that has no bespoke treatment yet.
# ---------------------------------------------------------------------------


def game_identity(
    kit: BaseKit,
    identity: PlayerIdentity,
    *,
    width: int = INNER_WIDTH,
    detail: str | None = None,
) -> Component:
    """Identity strip for a game board, bespoke when the kit authored one.

    Args:
        kit: Active kit.
        identity: Player identity data.
        width: Strip width; games pass their board width.
        detail: Optional game-specific right-hand text, e.g. ``押注 120 Pt``.

    Returns:
        Strip component.
    """

    if type(kit).game_identity is not BaseKit.game_identity:
        return kit.game_identity(identity, width=width, detail=detail)
    return _generic_game_identity(kit, identity, width=width, detail=detail)


def player_card(
    kit: BaseKit,
    identity: PlayerIdentity,
    *,
    current_pt: int,
    description: str = "",
    width: int = CONTENT_WIDTH,
    height: int = 420,
    frame_image: object | None = None,
    title1_image: object | None = None,
    title2_image: object | None = None,
) -> Component:
    """Player identity card, bespoke when the kit authored one.

    Args:
        kit: Active kit.
        identity: Player identity data.
        current_pt: Season points to display.
        description: Player-authored profile line.
        width: Card width.
        height: Card height.
        frame_image: Equipped avatar-frame asset, when one exists.
        title1_image: First equipped title asset, when one exists.
        title2_image: Second equipped title asset, when one exists.

    Returns:
        Card component.
    """

    if type(kit).player_card is not BaseKit.player_card:
        return kit.player_card(
            avatar_image=identity.avatar,
            frame_image=frame_image,
            title1_image=title1_image,
            title2_image=title2_image,
            nickname=identity.nickname,
            level=identity.level or 0,
            current_pt=current_pt,
            description=description,
            width=Fixed(width),
            height=Fixed(height),
        )
    return _generic_player_card(
        kit,
        identity,
        current_pt=current_pt,
        description=description,
        width=width,
        height=height,
    )


def pull_reveal(
    kit: BaseKit,
    pulls: Sequence[PullRevealItem],
    *,
    width: int = INNER_WIDTH,
) -> Component:
    """Gacha reveal grid, bespoke when the kit authored one.

    Args:
        kit: Active kit.
        pulls: Pull results in draw order (1-10 items).
        width: Grid width.

    Returns:
        Reveal component.
    """

    if type(kit).pull_reveal is not BaseKit.pull_reveal:
        return kit.pull_reveal(pulls, width=Fixed(width))
    return _generic_pull_reveal(kit, pulls, width=width)


def avatar_or_initial(
    kit: BaseKit, identity: PlayerIdentity, *, size: int = 56
) -> Component:
    """A circular avatar, or an initial-letter badge when no avatar exists.

    Shared by the generic fallbacks and available to bespoke kit
    implementations that do not want their own fallback treatment.
    """

    if identity.avatar is not None:
        return kit.image(
            identity.avatar,
            width=Fixed(size),
            height=Fixed(size),
            fit="cover",
            radius=size // 2,
        )
    initial = identity.nickname[:1] or "?"
    return badge(kit, initial, width=size, height=size, font_size=max(22, size // 2))


def _generic_game_identity(
    kit: BaseKit,
    identity: PlayerIdentity,
    *,
    width: int,
    detail: str | None,
) -> Component:
    name_lines: list[Component] = [
        kit.text(identity.nickname, font_size=26, wrap=False, max_lines=1)
    ]
    if identity.level is not None:
        name_lines.append(
            kit.text(f"Lv.{identity.level}", font_size=LABEL_SIZE, wrap=False)
        )

    cells: list[Component] = [
        avatar_or_initial(kit, identity, size=56),
        Frame(
            VStack(name_lines, gap=2, align="start"),
            width=Fill(),
            align_x="start",
            align_y="center",
        ),
    ]
    if detail:
        cells.append(
            kit.text(detail, font_size=BODY_SIZE, align="right", wrap=False, max_lines=1)
        )

    return kit.panel(
        HStack(cells, gap=16, align="center"),
        width=Fixed(width),
        height=Fixed(80),
        padding=Insets.only(left=16, top=12, right=20, bottom=12),
    )


def _generic_player_card(
    kit: BaseKit,
    identity: PlayerIdentity,
    *,
    current_pt: int,
    description: str,
    width: int,
    height: int,
) -> Component:
    stats: list[Component] = [
        kit.text(identity.nickname, font_size=32, wrap=False, max_lines=1)
    ]
    if identity.level is not None:
        stats.append(stat_row(kit, "等级", f"Lv.{identity.level}"))
    stats.append(stat_row(kit, "赛季积分", f"{current_pt} Pt"))

    body: list[Component] = [
        HStack(
            [
                avatar_or_initial(kit, identity, size=96),
                Frame(
                    VStack(stats, gap=10, align="stretch"),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
            ],
            gap=24,
            align="center",
        ),
    ]
    if description:
        body.append(kit.separator(length=Fill()))
        body.append(
            kit.text(description, font_size=LABEL_SIZE, max_lines=2, overflow="ellipsis")
        )

    # The generic card fits its content; ``height`` only constrains bespoke
    # implementations, which design against a fixed canvas.
    return kit.panel(
        VStack(body, gap=16, align="stretch"),
        width=Fixed(width),
        padding=Insets.all(PANEL_PADDING),
    )


#: Height of the generic reveal tile's optional art slot (contain-fit thumb).
_REVEAL_ART_HEIGHT = 96

#: Generic reveal tile height without an art slot. Every row is capped by a
#: fixed-height cell, so the budget is exact: 32 (chip) + 60 (two name lines)
#: + 26 (markers) + 26 (note) + 3 × 8 gaps + 12 + 12 padding = 192, plus 4px
#: slack. The former 174 fit only one-line names; the production filler names
#: wrap to two lines and pushed the note over the panel border.
_REVEAL_TILE_HEIGHT = 196


def _generic_pull_reveal(
    kit: BaseKit,
    pulls: Sequence[PullRevealItem],
    *,
    width: int,
) -> Component:
    columns = 5 if len(pulls) > 5 else max(1, len(pulls))
    gap = 12
    tile_width = (width - gap * (columns - 1)) // columns

    # Batch-driven art slot: when any pull carries art, every tile reserves
    # the slot (empty on art-less pulls) so the whole grid stays one uniform
    # tile height; an art-less batch keeps the plain tile height unchanged.
    art_slot = any(pull.image is not None for pull in pulls)
    tiles = [
        _reveal_tile(kit, pull, tile_width, art_slot=art_slot) for pull in pulls
    ]
    return Grid(columns=columns, gap=gap, children=tiles)


def _reveal_tile(
    kit: BaseKit, pull: PullRevealItem, width: int, *, art_slot: bool = False
) -> Component:
    is_top = pull.rarity >= 6
    rarity_chip: Component
    if is_top:
        rarity_chip = badge(kit, f"★{pull.rarity}", width=64, height=32)
    else:
        rarity_chip = kit.text(f"★{pull.rarity}", font_size=LABEL_SIZE, wrap=False)

    # Every row is height-capped so the fixed tile height always fits the
    # content — an uncapped two-line name used to push the note outside the
    # panel border.
    rows: list[Component] = [
        Frame(rarity_chip, height=Fixed(32), align_x="center", align_y="center")
    ]
    if art_slot:
        # Thumb above the name; the slot is reserved even without art so the
        # fixed tile height below keeps mixed batches uniform.
        rows.append(
            Frame(
                kit.image(
                    pull.image,
                    width=Fill(),
                    height=Fixed(_REVEAL_ART_HEIGHT),
                    fit="contain",
                )
                if pull.image is not None
                else None,
                height=Fixed(_REVEAL_ART_HEIGHT),
                align_x="center",
                align_y="center",
            )
        )
    rows.append(
        Frame(
            kit.text(
                pull.name,
                font_size=LABEL_SIZE,
                align="center",
                max_lines=2,
                overflow="ellipsis",
            ),
            width=Fill(),
            height=Fixed(60),
            align_x="center",
            align_y="center",
        )
    )
    markers: list[str] = []
    if pull.is_new:
        markers.append("NEW")
    if pull.featured:
        markers.append("PICK UP")
    # A ten-pull tile is too narrow for 「NEW · PICK UP」; rather than a
    # dangling 「NEW · …」 ellipsis, keep the first marker — NEW is
    # information the tile shows nowhere else. Every kit renders body text
    # with the shared CJK font, so measuring here is kit-agnostic.
    marker_text = " · ".join(markers)
    if markers and _marker_px(marker_text) > width - 16:
        marker_text = markers[0]
    rows.append(
        Frame(
            kit.text(
                marker_text,
                font_size=LABEL_SIZE,
                align="center",
                wrap=False,
                max_lines=1,
            )
            if markers
            else None,
            height=Fixed(26),
            align_x="center",
            align_y="center",
        )
    )
    # The note line is always reserved so every tile in the grid is the same
    # height regardless of which pulls carry annotations.
    rows.append(
        Frame(
            kit.text(
                pull.note,
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                align="center",
                wrap=False,
                max_lines=1,
            )
            if pull.note
            else None,
            height=Fixed(26),
            align_x="center",
            align_y="center",
        )
    )

    # A rarity-6 tile carries a filled chip; the tile surface itself stays the
    # kit's default so bespoke kits keep full control of celebration effects.
    # An art batch adds the slot plus one 8px row gap to every tile.
    tile_height = _REVEAL_TILE_HEIGHT + (_REVEAL_ART_HEIGHT + 8 if art_slot else 0)
    return kit.panel(
        VStack(rows, gap=8, align="stretch"),
        width=Fixed(width),
        height=Fixed(tile_height),
        padding=Insets.only(left=8, top=12, right=8, bottom=12),
    )


def _marker_px(text: str) -> int:
    """Measure a marker line at build time.

    All nine kits draw body text with the shared CJK font from
    ``plugins.render.kits.fonts``, so this measurement is exact for every
    kit that reaches the generic tile.
    """

    from plugins.render.kits.fonts import CHINESE_FONT
    from plugins.render.primitives import load_font
    from plugins.render.text_layout import text_width

    return text_width(text, load_font(LABEL_SIZE, CHINESE_FONT))


def _header(
    kit: BaseKit, title: str, subtitle: str | None, width: int
) -> Component:
    from plugins.render.kits.bangdream import BanGDreamKit

    if isinstance(kit, BanGDreamKit) and subtitle:
        return Frame(
            kit.title_pill(title, subtitle, pill_width=min(width, 500), pill_height=57),
            width=Fixed(width),
            align_x="start",
        )

    lines: list[Component] = [
        kit.text(title, font_size=TITLE_SIZE, wrap=False, max_lines=1)
    ]
    if subtitle:
        lines.append(
            kit.text(
                subtitle,
                font_size=SUBTITLE_SIZE,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            )
        )
    return Frame(
        VStack(lines, gap=6, align="start"),
        width=Fixed(width),
        align_x="start",
        align_y="center",
    )


def _background(kit: BaseKit, source: object | None):
    if source is None:
        return kit.background()
    try:
        return kit.background(source=source)  # type: ignore[call-arg]
    except TypeError:
        # Only BanGDreamKit accepts a source image.
        return kit.background()


def _trim(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"
