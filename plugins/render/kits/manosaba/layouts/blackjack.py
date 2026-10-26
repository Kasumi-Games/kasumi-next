"""An ink gaming table, rules spread and a player's hand ledger."""

from .folio import surface
from ..components import INK
from ..components import ROSE
from ..components import MUTED
from ..components import SURFACE


@surface(1380, book=True)
def table(
    f, renderer, dealer, player=None, *, hidden=False, identity=None, detail=None
):
    y = f.title("黑香澄", "THE CARD TABLE")
    side = f.person(identity, 58, y, 280)
    side = f.text(detail or "", 58, side + 30, 280, 25, ROSE)
    side = f.section("回合指令", 58, max(side + 38, y + 210), 280)
    f.text("h  补牌\ns  停牌\nd  双倍\nq  投降", 58, side, 280, 25, leading=48)
    cursor = y
    hands = [("庄家 / Kasumi", dealer, hidden)]
    if player is not None:
        hands.append(("你的手牌", player, False))
    for label, hand, hide in hands:
        score = (
            f"{hand.cards[0].get_value()} + ?"
            if hide and hand.cards
            else str(hand.value)
        )
        f.box(390, cursor, 932, 52, INK)
        f.text(label, 410, cursor + 12, 650, 24, SURFACE)
        f.text(f"{score} 点", 1090, cursor + 12, 208, 24, SURFACE, align="right")
        cursor += 78
        # Wrap large hands instead of shrinking the cards below legibility.
        for start in range(0, len(hand.cards), 5):
            for index, card in enumerate(hand.cards[start : start + 5], start):
                image = renderer._render_card_with_text(card, hide and index == 1)
                f.image(image, 390 + (index - start) * 186, cursor, 166, 233)
            cursor += 260
        cursor += 14
    f.gutter(338, 390, y, max(cursor, y + 480), padding=16)
    f.footer("/黑香澄 -h 查看规则 · 牌面与点数沿用当前对局", max(cursor, y + 480) + 24)


@surface(1240, book=True)
def help_page(f):
    from plugins.blackjack.help_content import RULE_SECTIONS

    from .help import rulebook

    rulebook(f, "黑香澄", "CARD TABLE / RULE BOOK", RULE_SECTIONS)


def recent_form(f, records, x, y, width):
    records = list(reversed(records))[-30:]
    if not records:
        return y
    y = f.section("近期战绩", x, y, width)
    f.line(x, y + 34, width, MUTED)
    step = min(28, width // max(1, len(records)))
    for i, record in enumerate(records):
        if record.amount:
            f.box(
                x + i * step,
                y + (6 if record.amount > 0 else 42),
                max(5, step - 7),
                25,
                ROSE if record.amount > 0 else INK,
            )
    return f.text(
        f"最近 {len(records)} 局 · 上为胜，下为负，空为平 · 右端最新",
        x,
        y + 84,
        width,
        20,
        MUTED,
    )


@surface(1160, book=True)
def stats(f, data):
    y = f.title("牌桌战绩", "CARD TABLE / LEDGER", f"共 {data.total_games} 局")
    a = f.person(data.identity, 58, y, 390)
    a = f.metric("净收益", f"{data.net_profit:+,} Pt", 58, a + 38, 390, size=52)
    a = f.metric("胜率", f"{data.win_rate:.1%}", 58, a + 30, 390, size=52)
    a = f.facts(
        (
            ("胜 / 负 / 平", f"{data.wins} / {data.losses} / {data.pushes}"),
            ("BlackJack", f"{data.blackjacks} 次"),
        ),
        58,
        a + 26,
        390,
    )
    b = f.section("收支明细", 524, y, 578)
    b = f.facts(
        (
            ("总投入", f"{data.total_wagered:,} Pt"),
            ("总赢得", f"{data.total_won:,} Pt"),
            ("总输掉", f"{data.total_lost:,} Pt"),
            ("平均下注", f"{data.avg_bet:.1f} Pt"),
            ("平均赢得", f"{data.avg_win:.1f} Pt"),
            ("平均输掉", f"{data.avg_loss:.1f} Pt"),
            ("单局最高赢得", f"{data.biggest_win:,} Pt"),
            ("单局最高输掉", f"{data.biggest_loss:,} Pt"),
        ),
        524,
        b,
        578,
    )
    f.gutter(448, 524, y, max(a, b))
    end = recent_form(f, data.recent_games, 58, max(a, b) + 36, 1044)
    f.footer("/黑香澄 <下注 Pt> 再来一局", end + 24)
