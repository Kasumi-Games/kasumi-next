"""红包列表卡 —— ``/红包列表`` 的按需查询面。

The create/completion cards in :mod:`.envelope` are broadcast surfaces with a
strict cost discipline (each envelope renders exactly twice). This card sits
outside that budget: it renders only when a player explicitly asks for the
list, so it can be an image without inflating per-envelope cost. Claims and
errors stay text, exactly as before.

Layout follows the mailbox inbox idiom, the blessed list-card pattern:

* Each active envelope is one row — a filled index chip (the number the player
  types to claim, so it is content and gets the ``badge`` emphasis), the title
  with the remaining amount/shares under it, and a trailing validity cell.
* Validity mirrors the inbox expiry idiom: a filled badge when the envelope is
  about to expire, muted text otherwise. Urgency is a SHAPE change, never a
  hue, so it survives the monochrome kit.
* The remaining line is content the player reads before deciding to claim, so
  it stays in full text color at :data:`~utils.cards.LABEL_SIZE` (the 22px
  must-read floor).
* No envelopes at all renders the shared :func:`utils.cards.empty_state` card
  rather than falling back to text — an empty answer is still an answer.

No database access in here: the handler resolves the kit and formats validity
on the event loop thread and passes plain data in, so the raster can be
offloaded via ``await list_page(...).render_async()``.
"""

from typing import Sequence
from dataclasses import dataclass

from PIL import Image

from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import SUBTITLE_SIZE
from utils.cards import badge
from utils.cards import card_page
from utils.cards import empty_state
from utils.cards import panel_section
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit

from .envelope import _clean

#: 逐行展示的红包数上限；超出折叠成一行小结。列表按创建时间倒序，被折叠的
#: 是最旧的红包，折叠行本身是内容（少了它列表对不上账），所以全文字色。
MAX_ROWS = 12

ROW_HEIGHT = 76
ROW_GAP = 18

#: 编号是玩家照着输入的领取口令，方形填充徽章，三位数也装得下。
INDEX_CHIP = 56

#: 尾列固定宽度——每行都保留这一列，行中部的标题/余量才对得齐。
VALIDITY_COLUMN = 150
#: 临期徽章要装下最宽的「剩 NN 分钟」（约 118px 文本）再留出圆角端的呼吸位。
VALIDITY_BADGE_WIDTH = 140
VALIDITY_BADGE_HEIGHT = 36


@dataclass(frozen=True)
class EnvelopeListItem:
    """One active envelope, as the list card shows it.

    Attributes:
        channel_index: Channel-local id players type to claim.
        title: Player-authored envelope title.
        remaining_amount: Pt still inside.
        total_amount: Pt it started with.
        remaining_count: Shares still unclaimed.
        total_count: Shares it started with.
        validity_text: Preformatted time left, e.g. ``剩 23 小时``.
        urgent: Whether the envelope is about to expire (renders as a filled
            badge instead of muted text). The handler decides the threshold.
    """

    channel_index: int
    title: str
    remaining_amount: int
    total_amount: int
    remaining_count: int
    total_count: int
    validity_text: str
    urgent: bool = False


def render_list(
    items: Sequence[EnvelopeListItem], kit: BaseKit | None = None
) -> Image.Image:
    """Render the active-envelope list card.

    Args:
        items: Active envelopes, newest first.
        kit: Active kit — the REQUESTER's (this is their query surface, not a
            creator broadcast). Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return list_page(items, kit).render()


def list_page(
    items: Sequence[EnvelopeListItem], kit: BaseKit | None = None
) -> AutoPage:
    """Build the list page without rendering it.

    Args:
        items: Active envelopes, newest first.
        kit: Active kit — the REQUESTER's. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``render()`` / ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    items = list(items)

    if not items:
        return card_page(
            kit,
            title="红包",
            subtitle="0 个",
            body=panel_section(
                kit,
                empty_state(kit, "现在没有可以抢的红包\n发一个就会出现在这里"),
            ),
            footer=_footer(kit),
        )

    shown = items[: MAX_ROWS - 1] if len(items) > MAX_ROWS else items
    rows: list[Component] = [_row(kit, item) for item in shown]
    if len(items) > MAX_ROWS:
        rows.append(_overflow_row(kit, len(items) - len(shown)))

    return card_page(
        kit,
        title="红包",
        subtitle=f"进行中 {len(items)} 个",
        body=panel_section(kit, VStack(rows, gap=ROW_GAP, align="stretch")),
        footer=_footer(kit),
    )


def _row(kit: BaseKit, item: EnvelopeListItem) -> Component:
    remaining = (
        f"剩 {item.remaining_amount}/{item.total_amount} Pt"
        f" · {item.remaining_count}/{item.total_count} 份"
    )
    return Frame(
        HStack(
            [
                badge(
                    kit,
                    str(item.channel_index),
                    width=INDEX_CHIP,
                    height=INDEX_CHIP,
                    font_size=26,
                ),
                Frame(
                    VStack(
                        [
                            kit.text(
                                _clean(item.title, "红包"),
                                font_size=SUBTITLE_SIZE,
                                wrap=False,
                                max_lines=1,
                                overflow="ellipsis",
                            ),
                            # 余量是玩家决定抢不抢的依据——内容，全文字色。
                            kit.text(
                                remaining,
                                font_size=LABEL_SIZE,
                                wrap=False,
                                max_lines=1,
                            ),
                        ],
                        gap=4,
                        align="start",
                    ),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
                Frame(
                    _validity_cell(kit, item),
                    width=Fixed(VALIDITY_COLUMN),
                    align_x="end",
                    align_y="center",
                ),
            ],
            gap=ROW_GAP,
            align="center",
        ),
        width=Fixed(INNER_WIDTH),
        height=Fixed(ROW_HEIGHT),
        align_x="stretch",
        align_y="center",
    )


def _validity_cell(kit: BaseKit, item: EnvelopeListItem) -> Component:
    """A filled badge when expiry is close, plain muted text otherwise."""

    if item.urgent:
        return badge(
            kit,
            item.validity_text,
            width=VALIDITY_BADGE_WIDTH,
            height=VALIDITY_BADGE_HEIGHT,
            font_size=LABEL_SIZE,
        )
    return kit.text(
        item.validity_text,
        font_size=LABEL_SIZE,
        color=kit.muted_text_color,
        align="right",
        wrap=False,
        max_lines=1,
    )


def _overflow_row(kit: BaseKit, hidden: int) -> Component:
    return Frame(
        kit.text(
            f"……还有 {hidden} 个红包",
            font_size=LABEL_SIZE,
            align="center",
            wrap=False,
            max_lines=1,
        ),
        width=Fixed(INNER_WIDTH),
        height=Fixed(40),
        align_x="center",
        align_y="center",
    )


def _footer(kit: BaseKit) -> Component:
    return Frame(
        kit.text(
            "发送「抢红包 编号」领取 · 「发红包 金额 份数」再发一个",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )
