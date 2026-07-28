"""The inbox card — the mailbox's front door and its highest-traffic surface.

This replaces the numbered text list and, deliberately, the idea of paging
through it. The card densifies instead: up to
:data:`SPACIOUS_LIMIT` mails render as two-line rows, beyond that every row
collapses to a single line, and past :data:`MAX_ROWS` the tail becomes one
summary line. ``AutoPage`` grows to fit, so there is never a page two and no
pagination command has to exist.

The sequence number is navigation, not state, so every row uses the same
number chip. State is written explicitly in the meta line: 「待领取」,
「已领取」, 「未读通知」, or 「已读通知」. This avoids making players infer a
second meaning from filled versus bare numerals.

Item names are resolved through the inventory catalog, which reads the
process-global session. Build the page on the event loop thread and only
offload the raster — see :func:`inbox_page`.
"""

import datetime
from typing import Sequence

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import SUBTITLE_SIZE
from utils.cards import badge
from utils.cards import card_page
from utils.cards import empty_state
from utils.cards import panel_section
from utils.clock import bot_now
from plugins.render import Fill
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import HStack
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit

from ..models import ServiceMail
from .rewards import attachment_summary

#: Above this many mails the rows switch to the single-line variant.
SPACIOUS_LIMIT = 8

#: Hard ceiling on rendered rows. Mails expire in at most 30 days and the 3am
#: cleanup deletes them, so the list is naturally bounded; this is the backstop.
MAX_ROWS = 24

SPACIOUS_ROW_HEIGHT = 76
DENSE_ROW_HEIGHT = 52
SPACIOUS_CHIP = 64
DENSE_CHIP = 44
ROW_GAP = 18

EXPIRY_COLUMN = 160
DENSE_EXPIRY_COLUMN = 120
DENSE_ITEMS_COLUMN = 240
EXPIRY_BADGE_WIDTH = 124
EXPIRY_BADGE_HEIGHT = 36


def render_inbox(
    mails: Sequence[ServiceMail], kit: BaseKit | None = None
) -> Image.Image:
    """Render a player's inbox.

    Args:
        mails: Mails newest first, as returned by ``MailService.get_user_mails``.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return inbox_page(mails, kit).render()


def inbox_page(
    mails: Sequence[ServiceMail], kit: BaseKit | None = None
) -> AutoPage:
    """Build the inbox page without rendering it.

    Handlers use this so the tree — which reads the inventory catalog for item
    names — is built on the event loop thread while only the raster is offloaded
    to ``render_async``.

    Args:
        mails: Mails newest first.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    mails = list(mails)

    if not mails:
        return card_page(
            kit,
            title="邮箱",
            subtitle="0 封",
            body=panel_section(
                kit,
                empty_state(kit, "邮箱是空的\n有新邮件时这里会出现提醒"),
            ),
        )

    unclaimed = [mail for mail in mails if _is_claimable(mail)]
    dense = len(mails) > SPACIOUS_LIMIT
    shown = mails[: MAX_ROWS - 1] if len(mails) > MAX_ROWS else mails

    rows: list[Component] = [
        _dense_row(kit, index, mail) if dense else _spacious_row(kit, index, mail)
        for index, mail in enumerate(shown, 1)
    ]
    if len(mails) > MAX_ROWS:
        rows.append(_overflow_row(kit, len(mails) - len(shown)))

    return card_page(
        kit,
        title="邮箱",
        subtitle=_subtitle(mails, unclaimed),
        body=panel_section(kit, VStack(rows, gap=ROW_GAP, align="stretch")),
        footer=_footer(kit, bool(unclaimed)),
    )


def _subtitle(
    mails: Sequence[ServiceMail], unclaimed: Sequence[ServiceMail]
) -> str:
    notices = [
        mail for mail in mails if not mail.is_read and not mail.attachments
    ]
    parts: list[str] = []
    if unclaimed:
        parts.append(f"{len(unclaimed)} 封未领取")
    if notices:
        parts.append(f"{len(notices)} 封通知未读")
    parts.append(f"共 {len(mails)} 封")
    return " · ".join(parts)


def _footer(kit: BaseKit, claimable: bool) -> Component:
    hint = "/邮件 <编号> 查看"
    if claimable:
        hint += " · /邮件 领取 一键领取"
    return Frame(
        kit.text(
            hint,
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )


def _spacious_row(kit: BaseKit, index: int, mail: ServiceMail) -> Component:
    return Frame(
        HStack(
            [
                _index_cell(kit, index, mail, size=SPACIOUS_CHIP, font_size=30),
                Frame(
                    VStack(
                        [
                            kit.text(
                                mail.title,
                                font_size=SUBTITLE_SIZE,
                                wrap=False,
                                max_lines=1,
                            ),
                            _meta_text(kit, mail),
                        ],
                        gap=4,
                        align="start",
                    ),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
                Frame(
                    _expiry_cell(kit, mail),
                    width=Fixed(EXPIRY_COLUMN),
                    align_x="end",
                    align_y="center",
                ),
            ],
            gap=ROW_GAP,
            align="center",
        ),
        width=Fixed(INNER_WIDTH),
        height=Fixed(SPACIOUS_ROW_HEIGHT),
        align_x="stretch",
        align_y="center",
    )


def _dense_row(kit: BaseKit, index: int, mail: ServiceMail) -> Component:
    return Frame(
        HStack(
            [
                _index_cell(
                    kit, index, mail, size=DENSE_CHIP, font_size=LABEL_SIZE
                ),
                Frame(
                    kit.text(
                        mail.title,
                        font_size=BODY_SIZE,
                        wrap=False,
                        max_lines=1,
                    ),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
                Frame(
                    _meta_text(kit, mail, limit=1),
                    width=Fixed(DENSE_ITEMS_COLUMN),
                    align_x="stretch",
                    align_y="center",
                ),
                Frame(
                    _expiry_cell(
                        kit,
                        mail,
                        badge_width=112,
                        badge_height=32,
                        font_size=20,
                    ),
                    width=Fixed(DENSE_EXPIRY_COLUMN),
                    align_x="stretch",
                    align_y="center",
                ),
            ],
            gap=ROW_GAP,
            align="center",
        ),
        width=Fixed(INNER_WIDTH),
        height=Fixed(DENSE_ROW_HEIGHT),
        align_x="stretch",
        align_y="center",
    )


def _overflow_row(kit: BaseKit, remaining: int) -> Component:
    return Frame(
        kit.text(
            f"还有 {remaining} 封 · 已按送达时间排序",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        width=Fixed(INNER_WIDTH),
        height=Fixed(DENSE_ROW_HEIGHT),
        align_x="start",
        align_y="center",
    )


def _index_cell(
    kit: BaseKit,
    index: int,
    mail: ServiceMail,
    *,
    size: int,
    font_size: int,
) -> Component:
    """Stable navigation chip; mail state is written in the meta column."""

    return badge(kit, str(index), width=size, height=size, font_size=font_size)


def _meta_text(
    kit: BaseKit, mail: ServiceMail, *, limit: int | None = None
) -> Component:
    """The attachment line, or the word that replaces it."""

    if mail.is_read and mail.attachments:
        text, muted = "已领取", True
    elif mail.is_read:
        text, muted = "已读通知", True
    elif not mail.attachments:
        text, muted = "未读通知", True
    else:
        text = "待领取 · " + attachment_summary(mail.attachments, limit=limit)
        muted = False
    return kit.text(
        text,
        font_size=LABEL_SIZE,
        color=kit.muted_text_color if muted else None,
        wrap=False,
        max_lines=1,
    )


def _expiry_cell(
    kit: BaseKit,
    mail: ServiceMail,
    *,
    badge_width: int = EXPIRY_BADGE_WIDTH,
    badge_height: int = EXPIRY_BADGE_HEIGHT,
    font_size: int = LABEL_SIZE,
) -> Component:
    """A filled badge when the deadline is close, plain muted text otherwise."""

    text, urgent = expiry_state(mail.expire_time)
    if urgent:
        return badge(
            kit,
            text,
            width=badge_width,
            height=badge_height,
            font_size=font_size,
        )
    return kit.text(
        text,
        font_size=LABEL_SIZE,
        color=kit.muted_text_color,
        align="right",
        wrap=False,
        max_lines=1,
    )

def expiry_state(expire_time: datetime.datetime) -> tuple[str, bool]:
    """Describe how long a mail has left.

    Calendar days rather than elapsed hours, because 「明天到期」 has to mean
    tomorrow's date and not "in 24 hours".

    Args:
        expire_time: When the mail stops being claimable.

    Returns:
        ``(text, urgent)`` where ``urgent`` means today or tomorrow.
    """

    # ``expire_time`` is timezone-aware (utils/clock.py); the comparison base
    # must be aware too, and day math must use the product-timezone calendar.
    now = bot_now()
    if expire_time.tzinfo is None:
        expire_time = expire_time.replace(tzinfo=now.tzinfo)
    if expire_time <= now:
        return "已过期", True
    days = (expire_time.date() - now.date()).days
    if days <= 0:
        return "今天到期", True
    if days == 1:
        return "明天到期", True
    return f"剩 {days} 天", False


def _is_claimable(mail: ServiceMail) -> bool:
    return not mail.is_read and bool(mail.attachments)
