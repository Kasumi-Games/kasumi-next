"""One mail, as a letter with its rewards underneath.

Today this response is a single string that splices three unrelated blocks
together — metadata, body, and the grant results appended last — so the reward,
which is the emotional payload, arrives at the bottom of a text wall. Here the
letter is one panel and the haul is another, with the quantities as display
numerals.

The reward panel has three states and never renders empty:

``本次领取``
    at least one ``GrantResult.granted`` is positive — this read claimed them.
``之前已发放``
    every result came back ``skipped``. That happens when a previous read
    granted the items but ``read_mail`` then failed, leaving the mail unread
    (see the ordering in the plugin handler). Without this state the player
    would be shown an empty panel and conclude the rewards vanished.
``已领取``
    the mail was already read, so the handler ran no grants at all and passed
    an empty result list.
"""

from typing import Sequence

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
from utils.cards import card_page
from utils.cards import panel_section
from plugins.render import Fixed
from plugins.render import Frame
from plugins.render import VStack
from plugins.render import BaseKit
from plugins.render import AutoPage
from plugins.render import Component
from plugins.render.kits.bangdream import BanGDreamKit

from .inbox import expiry_state
from ..models import ServiceMail
from .rewards import any_granted
from .rewards import reward_grid
from .rewards import section_band
from .rewards import tiles_for_attachments

#: Letter heading. Bigger than the body so the hierarchy survives downscale,
#: smaller than the card title so it does not compete with the header.
LETTER_TITLE_SIZE = 30

#: Mail content is admin-authored and unbounded. At this line height a 24-line
#: cap is about 820px of body, which keeps the page under roughly 1400px.
BODY_LINE_HEIGHT = 34
BODY_MAX_LINES = 24


def render_mail(
    mail: ServiceMail,
    results: Sequence = (),
    kit: BaseKit | None = None,
    *,
    ordinal: int | None = None,
) -> Image.Image:
    """Render one mail and the outcome of claiming it.

    Args:
        mail: The mail being read.
        results: ``GrantResult`` values from ``grant_many``, positionally
            matching ``mail.attachments``. Empty when the mail was already read.
        kit: Active kit. Defaults to the BanG Dream! kit.
        ordinal: The mailbox ordinal the player typed (``/邮件 <编号>``).

    Returns:
        Rendered card.
    """

    return mail_page(mail, results, kit, ordinal=ordinal).render()


def mail_page(
    mail: ServiceMail,
    results: Sequence = (),
    kit: BaseKit | None = None,
    *,
    ordinal: int | None = None,
) -> AutoPage:
    """Build the mail detail page without rendering it.

    The subtitle speaks the player's own numbering: ``第 {ordinal} 封`` is the
    number they just typed. The database id (the old ``#M{id}`` code) never
    renders — live testing showed it reads as a second, contradictory
    numbering that can even run opposite to the mailbox order.

    Args:
        mail: The mail being read.
        results: ``GrantResult`` values from ``grant_many``.
        kit: Active kit. Defaults to the BanG Dream! kit.
        ordinal: The mailbox ordinal the player typed, when known.

    Returns:
        Page ready for ``await render_async()``.
    """

    kit = kit or BanGDreamKit()
    results = list(results)

    sections: list[Component] = [_letter_panel(kit, mail)]
    if mail.attachments:
        sections.append(_reward_panel(kit, mail, results))

    expiry, _ = expiry_state(mail.expire_time)
    subtitle = f"第 {ordinal} 封 · {expiry}" if ordinal else expiry
    return card_page(
        kit,
        title="邮件",
        subtitle=subtitle,
        body=VStack(sections, gap=32, align="stretch"),
        footer=_footer(kit),
    )


def _letter_panel(kit: BaseKit, mail: ServiceMail) -> Component:
    return panel_section(
        kit,
        VStack(
            [
                Frame(
                    kit.text(
                        mail.title,
                        font_size=LETTER_TITLE_SIZE,
                        max_lines=2,
                    ),
                    width=Fixed(INNER_WIDTH),
                    align_x="stretch",
                    align_y="center",
                ),
                kit.separator(length=Fixed(INNER_WIDTH), thickness=2),
                kit.text(
                    _meta_line(mail),
                    font_size=LABEL_SIZE,
                    color=kit.muted_text_color,
                    wrap=False,
                    max_lines=1,
                ),
                Frame(
                    kit.text(
                        mail.content,
                        font_size=BODY_SIZE,
                        line_height=BODY_LINE_HEIGHT,
                        max_lines=BODY_MAX_LINES,
                    ),
                    width=Fixed(INNER_WIDTH),
                    align_x="stretch",
                    align_y="start",
                ),
            ],
            gap=18,
            align="start",
        ),
    )


def _reward_panel(
    kit: BaseKit, mail: ServiceMail, results: Sequence
) -> Component:
    tiles = tiles_for_attachments(kit, mail.attachments, results)
    return panel_section(
        kit,
        VStack(
            [
                section_band(
                    kit,
                    _band_caption(mail, results),
                    # Count the tiles, not the raw rows: legacy mails carry
                    # duplicate attachment rows that collapse to one tile.
                    f"{len(tiles)} 项",
                ),
                reward_grid(kit, tiles),
            ],
            gap=24,
            align="stretch",
        ),
    )


def _band_caption(mail: ServiceMail, results: Sequence) -> str:
    if not results:
        return "已领取"
    if any_granted(results):
        return "本次领取"
    return "之前已发放"


def _meta_line(mail: ServiceMail) -> str:
    # Deliberately no sender segment: real sender ids are opaque platform
    # hashes, and rendering one leaks it onto a shareable image.
    created = mail.created_at.strftime("%Y-%m-%d %H:%M")
    expires = mail.expire_time.strftime("%Y-%m-%d %H:%M")
    return f"{created} 送达 · {expires} 过期"


def _footer(kit: BaseKit) -> Component:
    return Frame(
        kit.text(
            "/邮箱 返回列表 · /邮件 领取 一键领取",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )
