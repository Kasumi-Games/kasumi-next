"""The one-command claim receipt.

``/邮件 领取`` claims every unread mail that carries attachments and answers
with this single card instead of one text wall per mail. Beyond the message
count, that removes an index race: ``get_user_mails`` lazily inserts recipient
rows for broadcasts and re-sorts by delivery time on every call, so a broadcast
landing between ``/邮箱`` and ``/邮件 2`` shifts every ordinal. Claim-all takes
no index at all.

The hero is the aggregated haul — a number that did not exist before this card,
because no previous surface ever summed a session. It is capped at
:data:`MAX_HERO_TILES` tiles; anything past that is still listed per mail in the
breakdown panel, so nothing disappears.

Announcement-only mails are deliberately left unread by the claim, and the card
names how many are left. ``is_read`` is the only record that a player saw a
notice, and a bulk claim must not consume it silently.
"""

from PIL import Image

from utils.cards import BODY_SIZE
from utils.cards import LABEL_SIZE
from utils.cards import INNER_WIDTH
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

from ..models import ClaimedMail
from ..models import ClaimOutcome
from .rewards import summarize
from .rewards import reward_grid
from .rewards import reward_tile
from .rewards import section_band
from .rewards import attachment_summary

#: Tiles the hero grid will show. Six fills two rows of three; the rest of the
#: haul is still itemised per mail in the breakdown panel.
MAX_HERO_TILES = 6

DETAIL_ROW_HEIGHT = 44
CODE_COLUMN = 72
TITLE_COLUMN = 232
ROW_GAP = 18


def render_claim_all(
    outcome: ClaimOutcome, kit: BaseKit | None = None
) -> Image.Image:
    """Render the result of claiming every claimable mail.

    Args:
        outcome: Result of ``plugins.mailbox.service.claim_all_mails``.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Rendered card.
    """

    return claim_all_page(outcome, kit).render()


def claim_all_page(
    outcome: ClaimOutcome, kit: BaseKit | None = None
) -> AutoPage:
    """Build the claim-all page without rendering it.

    Args:
        outcome: Result of ``plugins.mailbox.service.claim_all_mails``.
        kit: Active kit. Defaults to the BanG Dream! kit.

    Returns:
        Page ready for ``await render_async()``.
    """

    kit = kit or BanGDreamKit()

    if not outcome.claimed:
        return card_page(
            kit,
            title="邮箱",
            subtitle="一键领取",
            article_title="一键领取",
            show_subtitle=False,
            show_page_title=False,
            body=panel_section(kit, empty_state(kit, _nothing_message(outcome))),
            footer=_footer(kit),
        )

    # Never render an empty hero panel: with nothing to total, the per-mail
    # breakdown is the whole card.
    sections: list[Component] = []
    if outcome.totals:
        sections.append(_hero_panel(kit, outcome))
    sections.append(_detail_panel(kit, outcome))
    return card_page(
        kit,
        title="邮箱",
        subtitle=f"一键领取 · {len(outcome.claimed)} 封",
        article_title="一键领取",
        show_subtitle=False,
        show_page_title=False,
        body=VStack(sections, gap=32, align="stretch"),
        footer=_footer(kit),
    )


def _nothing_message(outcome: ClaimOutcome) -> str:
    if outcome.total_mails == 0:
        return "没有可领取的邮件\n邮箱是空的"
    if outcome.remaining_notices:
        return (
            "没有可领取的邮件\n"
            f"还有 {outcome.remaining_notices} 封通知未读 · /邮箱 查看"
        )
    return f"没有可领取的邮件\n{outcome.total_mails} 封邮件都已领取过了"


def _hero_panel(kit: BaseKit, outcome: ClaimOutcome) -> Component:
    shown = list(outcome.totals[:MAX_HERO_TILES])
    tiles = [
        reward_tile(
            kit,
            total.item_id,
            total.granted if total.granted > 0 else total.already_owned,
            claimed=total.granted > 0,
        )
        for total in shown
    ]
    caption = "合计获得" if any(t.granted > 0 for t in outcome.totals) else "之前已发放"

    children: list[Component] = [
        section_band(kit, caption, f"{len(outcome.totals)} 项"),
        reward_grid(kit, tiles),
    ]
    hidden = len(outcome.totals) - len(shown)
    if hidden > 0:
        children.append(
            kit.text(
                f"另有 {hidden} 项已计入下方明细",
                font_size=LABEL_SIZE,
                color=kit.muted_text_color,
                wrap=False,
                max_lines=1,
            )
        )
    return panel_section(kit, VStack(children, gap=24, align="stretch"))


def _detail_panel(kit: BaseKit, outcome: ClaimOutcome) -> Component:
    children: list[Component] = [section_band(kit, "明细")]
    children.extend(_detail_row(kit, claimed) for claimed in outcome.claimed)

    if outcome.remaining_notices:
        children.append(kit.separator(length=Fixed(INNER_WIDTH), thickness=2))
        children.append(
            kit.text(
                f"还有 {outcome.remaining_notices} 封通知未读 · /邮箱 查看",
                font_size=LABEL_SIZE,
                wrap=False,
                max_lines=1,
            )
        )
    return panel_section(kit, VStack(children, gap=ROW_GAP, align="stretch"))


def _detail_row(kit: BaseKit, claimed: ClaimedMail) -> Component:
    # The leading number is the mailbox ordinal (/邮件 <编号>) — claiming only
    # flips read state and never reorders, so the number still works for
    # rereading. The database id (old M-code) never renders.
    return Frame(
        HStack(
            [
                Frame(
                    kit.text(
                        str(claimed.ordinal),
                        font_size=LABEL_SIZE,
                        color=kit.muted_text_color,
                        wrap=False,
                        max_lines=1,
                    )
                    if claimed.ordinal > 0
                    else None,
                    width=Fixed(CODE_COLUMN),
                    align_x="start",
                    align_y="center",
                ),
                Frame(
                    kit.text(
                        claimed.mail.title,
                        font_size=BODY_SIZE,
                        wrap=False,
                        max_lines=1,
                    ),
                    width=Fixed(TITLE_COLUMN),
                    align_x="stretch",
                    align_y="center",
                ),
                Frame(
                    kit.text(
                        _row_summary(claimed),
                        font_size=LABEL_SIZE,
                        align="right",
                        wrap=False,
                        max_lines=1,
                    ),
                    width=Fill(),
                    align_x="stretch",
                    align_y="center",
                ),
            ],
            gap=ROW_GAP,
            align="center",
        ),
        width=Fixed(INNER_WIDTH),
        height=Fixed(DETAIL_ROW_HEIGHT),
        align_x="stretch",
        align_y="center",
    )


def _row_summary(claimed: ClaimedMail) -> str:
    granted = [result for result in claimed.results if result.granted > 0]
    if granted:
        return summarize(
            [(result.item_id, result.granted) for result in granted], limit=2
        )
    if claimed.results:
        return "之前已发放"
    return attachment_summary(claimed.mail.attachments, limit=2)


def _footer(kit: BaseKit) -> Component:
    return Frame(
        kit.text(
            "/邮箱 查看邮箱 · /邮件 <编号> 查看正文",
            font_size=LABEL_SIZE,
            color=kit.muted_text_color,
            wrap=False,
            max_lines=1,
        ),
        align_x="start",
        align_y="center",
    )
