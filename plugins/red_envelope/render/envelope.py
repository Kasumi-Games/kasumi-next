"""EnvelopeCard —— 红包的两张卡片：创建公告与抢完结算。

Cost discipline IS the design (consistency review #14/#15): a live envelope
broadcasts exactly twice — once on 发红包 and once on the claim that empties
it. Every individual 抢红包 reply stays text, so a ten-share envelope costs two
images, not eleven near-identical ones. (The on-demand ``/红包列表`` card lives
in :mod:`.listing` and sits outside this budget: it renders only when a player
explicitly asks.)

Both cards render in the CREATOR's kit and carry the ``owner_name`` form of
the theme signature: the envelope is the most social surface in the bot, and
handing people currency inside your own theme is what makes themes visible.
The create card additionally embeds the Tier A ``game_identity`` strip so
bespoke kits get their own treatment of the creator.

The completion summary names both 手气王 and 霉运王 once. The service retains
the full claim-time ledger; the settlement card ranks it by amount descending
and shows only the top three, without repeating those labels in a member row.

No database access in here. The handler resolves the kit, the creator
identity, and every nickname on the event loop thread and passes plain data
in, so the raster can be offloaded via ``await *_page(...).render_async()``.

Envelope titles and nicknames are player-authored, and the bundled CJK font
has no emoji glyphs, so :func:`_clean` strips emoji-range codepoints before
any of those strings reach a text node. ★/☆ (U+2605/U+2606) are present in the
font and deliberately survive.
"""

from typing import Sequence
from dataclasses import dataclass

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import badge
from utils.cards import headline
from utils.cards import stat_row
from utils.cards import card_page
from utils.cards import game_identity
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render import PlayerIdentity
from plugins.render.kits.bangdream import BanGDreamKit

#: 结算榜逐行展示的领取数上限；超出折叠成一行小结（红包最多 10000 份）。
#: 两个金额极值另有 stat 行兜底，所以被折叠也不会丢信息。
MAX_LADDER_ROWS = 3

#: 红包标题在 hero 面板里的字号（页标题 40 之下、正文 24 之上）。
_ENVELOPE_TITLE_SIZE = 34

#: 总金额是创建卡的主角，给它 hero 字号。
_HERO_AMOUNT_SIZE = 48


@dataclass(frozen=True)
class EnvelopeCreateData:
    """Everything the create announcement shows.

    Attributes:
        channel_index: Channel-local id players type to claim this envelope.
        title: Player-authored envelope title.
        total_amount: Total Pt inside.
        total_count: Number of shares.
        creator: Creator identity for the Tier A strip.
        validity_text: Player-facing validity, e.g. ``24 小时``.
    """

    channel_index: int
    title: str
    total_amount: int
    total_count: int
    creator: PlayerIdentity
    validity_text: str = "24 小时"


@dataclass(frozen=True)
class ClaimRow:
    """One row of the completion ledger, in claim order.

    Attributes:
        name: Claimer display name, resolved by the handler.
        amount: Pt this claim got.
        is_lucky_king: Whether this row gets the 手气王 badge. The handler
            marks exactly one row (ties break to the earliest claimer).
    """

    name: str
    amount: int
    is_lucky_king: bool = False


@dataclass(frozen=True)
class EnvelopeCompletionData:
    """Everything the completion card shows.

    Attributes:
        channel_index: Channel-local envelope id.
        title: Player-authored envelope title.
        total_amount: Total Pt that was inside.
        total_count: Number of shares.
        creator_name: Creator display name (also signs the theme footer).
        duration_text: Preformatted race duration, e.g. ``2 分 14 秒``.
        lucky_king_name: Display name of the biggest claim.
        lucky_king_amount: Pt of the biggest claim.
        claims: Full ledger in claim order.
    """

    channel_index: int
    title: str
    total_amount: int
    total_count: int
    creator_name: str
    duration_text: str
    lucky_king_name: str
    lucky_king_amount: int
    claims: tuple[ClaimRow, ...]


def render_create(
    data: EnvelopeCreateData, kit: BaseKit | None = None
) -> Image.Image:
    """Render the create announcement card.

    Args:
        data: Pre-assembled card data.
        kit: Active kit — the CREATOR's. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return create_page(data, kit).render()


def create_page(data: EnvelopeCreateData, kit: BaseKit | None = None) -> AutoPage:
    """Build the create announcement page without rendering it.

    Args:
        data: Pre-assembled card data.
        kit: Active kit — the CREATOR's. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    title = _clean(data.title, "红包")
    creator = PlayerIdentity(
        nickname=_clean(data.creator.nickname, "玩家"),
        level=data.creator.level,
        avatar=data.creator.avatar,
    )

    hero = VStack(
        [
            game_identity(kit, creator, width=INNER_WIDTH),
            kit.separator(length=Fill()),
            Frame(
                kit.text(
                    title,
                    font_size=_ENVELOPE_TITLE_SIZE,
                    wrap=False,
                    max_lines=1,
                    overflow="ellipsis",
                ),
                width=Fixed(INNER_WIDTH),
                align_x="start",
                align_y="center",
            ),
            # 金额居左、份数靠右贴边（stat_row 的骨架放大版）：两个数字各占
            # 一端，比原来挤在一起的「N Pt 共 M 份」松得多，又不多占一行。
            Frame(
                HStack(
                    [
                        Frame(
                            kit.text(
                                f"{data.total_amount} Pt",
                                font_size=_HERO_AMOUNT_SIZE,
                                wrap=False,
                                max_lines=1,
                            ),
                            width=Fill(),
                            align_x="start",
                            align_y="end",
                        ),
                        kit.text(
                            f"共 {data.total_count} 份",
                            font_size=BODY_SIZE,
                            align="right",
                            wrap=False,
                            max_lines=1,
                        ),
                    ],
                    gap=16,
                    align="end",
                ),
                width=Fixed(INNER_WIDTH),
                align_x="stretch",
                align_y="center",
            ),
            stat_row(kit, "有效期", data.validity_text, width=INNER_WIDTH),
        ],
        gap=20,
        align="stretch",
    )

    # 指令提示是这张卡的行动号召，必读内容：全文字色、居中、单独成板。
    hint = Frame(
        kit.text(
            f"发送「抢红包 {data.channel_index}」领取",
            font_size=30,
            align="center",
            wrap=False,
            max_lines=1,
        ),
        width=Fixed(INNER_WIDTH),
        height=Fixed(72),
        align_x="center",
        align_y="center",
    )

    return card_page(
        kit,
        title="红包",
        subtitle=f"#{data.channel_index}",
        body=VStack(
            [panel_section(kit, hero), panel_section(kit, hint)],
            gap=24,
            align="stretch",
        ),
        owner_name=creator.nickname,
    )


def render_completion(
    data: EnvelopeCompletionData, kit: BaseKit | None = None
) -> Image.Image:
    """Render the completion (settlement) card.

    Args:
        data: Pre-assembled card data.
        kit: Active kit — the CREATOR's. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return completion_page(data, kit).render()


def completion_page(
    data: EnvelopeCompletionData, kit: BaseKit | None = None
) -> AutoPage:
    """Build the completion page without rendering it.

    Args:
        data: Pre-assembled card data.
        kit: Active kit — the CREATOR's. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    title = _clean(data.title, "红包")
    creator_name = _clean(data.creator_name, "玩家")
    lucky_king_name = _clean(data.lucky_king_name, "玩家")
    unluckiest = _unluckiest(data.claims)

    # 两个极值在 stat 行里始终可见——榜单折叠也不丢；可见账本行再用徽章
    # 按形状标记。相同最低金额按领取顺序取最早者。
    summary_rows: list[Component] = [
        stat_row(kit, "来自", creator_name, width=INNER_WIDTH),
        stat_row(
            kit,
            "总金额",
            f"{data.total_amount} Pt · {data.total_count} 份",
            width=INNER_WIDTH,
        ),
        stat_row(kit, "用时", data.duration_text, width=INNER_WIDTH),
        stat_row(
            kit,
            "手气王",
            f"{lucky_king_name} · {data.lucky_king_amount} Pt",
            width=INNER_WIDTH,
        ),
    ]
    if unluckiest is not None:
        _, claim = unluckiest
        summary_rows.append(
            stat_row(
                kit,
                "霉运王",
                f"{_clean(claim.name, '玩家')} · {claim.amount} Pt",
                width=INNER_WIDTH,
            )
        )
    summary_rows.extend(
        [
            kit.separator(length=Fill()),
            _claim_ladder(kit, data.claims),
        ]
    )
    summary = VStack(summary_rows, gap=16, align="stretch")

    return card_page(
        kit,
        title="红包",
        subtitle=f"#{data.channel_index} · {title}",
        body=VStack(
            [headline(kit, "红包已抢完"), panel_section(kit, summary)],
            gap=24,
            align="stretch",
        ),
        owner_name=creator_name,
    )


def _claim_ladder(
    kit: BaseKit, claims: Sequence[ClaimRow], *, width: int = INNER_WIDTH
) -> Component:
    """Amount-descending Top 3, with claim order as the tie-breaker."""

    ranked = sorted(
        enumerate(claims, start=1),
        key=lambda item: (-item[1].amount, item[0]),
    )
    rows: list[Component] = [
        _claim_row(kit, rank, claim, width)
        for rank, (_, claim) in enumerate(ranked[:MAX_LADDER_ROWS], start=1)
    ]
    hidden = len(claims) - MAX_LADDER_ROWS
    if hidden > 0:
        # 折叠行是内容（少了它整份账对不上），所以全文字色而非 muted。
        rows.append(
            Frame(
                kit.text(
                    f"……还有 {hidden} 人已领取",
                    font_size=LABEL_SIZE,
                    align="center",
                    wrap=False,
                    max_lines=1,
                ),
                width=Fixed(width),
                height=Fixed(40),
                align_x="center",
                align_y="center",
            )
        )
    return VStack(rows, gap=12, align="stretch")


def _claim_row(
    kit: BaseKit,
    order: int,
    claim: ClaimRow,
    width: int,
) -> Component:
    """One compact member row: rank, name, and amount.

    The two extrema already live in the completion summary, so duplicating a
    crown in a row makes the short list noisier without adding information.
    """

    cells: list[Component] = [
        Frame(
            kit.text(
                str(order),
                font_size=BODY_SIZE,
                align="center",
                wrap=False,
                max_lines=1,
            ),
            width=Fixed(56),
            align_x="center",
            align_y="center",
        ),
        Frame(
            kit.text(
                _clean(claim.name, "玩家"),
                font_size=BODY_SIZE,
                wrap=False,
                max_lines=1,
                overflow="ellipsis",
            ),
            width=Fill(),
            align_x="start",
            align_y="center",
        ),
        kit.text(
            f"{claim.amount} Pt",
            font_size=BODY_SIZE,
            align="right",
            wrap=False,
            max_lines=1,
        ),
    ]
    return Frame(
        HStack(cells, gap=16, align="center"),
        width=Fixed(width),
        height=Fixed(52),
        align_x="stretch",
        align_y="center",
    )


def _unluckiest(
    claims: Sequence[ClaimRow],
) -> tuple[int, ClaimRow] | None:
    """Return the earliest lowest claim as a one-based ledger position."""

    if len(claims) < 2:
        return None
    index, claim = min(enumerate(claims), key=lambda item: item[1].amount)
    return index + 1, claim


#: The only glyphs the bundled font (``old.ttf``) carries in the
#: Miscellaneous Symbols block U+2600–U+26FF: ★ ☆ ☉ ♀ ♂. Everything else in
#: the block (♥ ♪ ⚡ ☀ ☺ ⚽ …) is absent from its cmap and draws as tofu.
_MISC_SYMBOLS_PRESENT = frozenset({0x2605, 0x2606, 0x2609, 0x2640, 0x2642})

#: Emoji-capable BMP codepoints outside the block rules below that are absent
#: from the font, plus the ZWJ, keycap combiner, and variation selectors.
#: (The emoji-capable arrows the font DOES carry — ↖↗↘↙ — are kept.)
_UNRENDERABLE_SINGLES = frozenset(
    {
        0x00A9,  # ©
        0x00AE,  # ®
        0x200D,  # zero-width joiner
        0x203C,  # ‼
        0x2049,  # ⁉
        0x20E3,  # combining keycap
        0x2122,  # ™
        0x2139,  # ℹ
        0x2194,  # ↔
        0x2195,  # ↕
        0x21A9,  # ↩
        0x21AA,  # ↪
        0x24C2,  # Ⓜ
        0x25AA,  # ▪
        0x25AB,  # ▫
        0x25B6,  # ▶
        0x25C0,  # ◀
        0x25FB,  # ◻
        0x25FC,  # ◼
        0x25FD,  # ◽
        0x25FE,  # ◾
        0x2934,  # ⤴
        0x2935,  # ⤵
        0x3030,  # 〰
        0x303D,  # 〽
        0x3297,  # ㊗
        0x3299,  # ㊙
        0xFE0E,  # text variation selector
        0xFE0F,  # emoji variation selector
    }
)


def _clean(text: str, fallback: str = "") -> str:
    """Strip codepoints the bundled CJK font cannot draw.

    Player-authored titles and nicknames routinely carry emoji, which render
    as empty boxes in every kit. The ranges below were measured against the
    bundled font's cmap, not guessed: stripped are the supplementary emoji
    planes (U+1F000 and up), Miscellaneous Technical U+2300–U+23FF (⌚⏰⏳ —
    only ⌒ U+2312, the kaomoji arc, is present), Miscellaneous Symbols
    U+2600–U+26FF except the five present glyphs (★☆☉♀♂), Dingbats
    U+2700–U+27BF (✂✓✨ — all absent), Miscellaneous Symbols and Arrows
    U+2B00–U+2BFF (⭐⭕⬆ — the font has no glyph in the whole block), and the
    absent emoji-capable singles (‼⁉™©®Ⓜ▶◀⤴〽㊗ …) plus the ZWJ, keycap
    combiner, and variation selectors.

    Args:
        text: Raw player-authored string.
        fallback: Returned when stripping leaves nothing.

    Returns:
        Drawable string.
    """

    cleaned = "".join(ch for ch in text if not _is_unrenderable(ch)).strip()
    return cleaned or fallback


def _is_unrenderable(ch: str) -> bool:
    code = ord(ch)
    if code >= 0x1F000:
        return True
    if 0x2300 <= code <= 0x23FF:
        return code != 0x2312
    if 0x2600 <= code <= 0x26FF:
        return code not in _MISC_SYMBOLS_PRESENT
    if 0x2700 <= code <= 0x27BF:
        return True
    if 0x2B00 <= code <= 0x2BFF:
        return True
    return code in _UNRENDERABLE_SINGLES
