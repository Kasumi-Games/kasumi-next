"""Warehouse plan, expedition account and an exploration ledger."""

from .folio import surface
from .folio import gain_rows
from ..components import ROSE
from ..components import MUTED
from ..components import SURFACE


@surface(1240)
def board(f, field, *, identity=None, detail=None):
    from plugins.mines.models import BlockType

    y = f.title("探险", "WAREHOUSE FLOOR PLAN", "Arisa 的仓库")
    side = f.person(identity, 58, y, 280)
    side = f.text(detail or "", 58, side + 30, 280, 25, ROSE)
    side = f.section("探索指引", 58, side + 34, 280)
    f.text(
        "发送格子编号翻开\n收手：带走当前奖励\n避开藏着 Arisa 的格子",
        58,
        side,
        280,
        24,
        leading=39,
    )
    cols, rows = field.width, field.height
    gap, max_size = 12, 734
    cell = (max_size - gap * (max(cols, rows) - 1)) // max(cols, rows)
    board_w, board_h = cols * cell + (cols - 1) * gap, rows * cell + (rows - 1) * gap
    start_x = 448 + (734 - board_w) // 2
    for r in range(rows):
        for c in range(cols):
            x, top = start_x + c * (cell + gap), y + r * (cell + gap)
            block = field.field[r][c]
            shown = block in (BlockType.EMPTY_SHOWN, BlockType.MINE_SHOWN)
            f.box(
                x,
                top,
                cell,
                cell,
                (221, 195, 198, 255) if block == BlockType.MINE_SHOWN else SURFACE,
                ROSE if shown else MUTED,
            )
            if shown:
                image = (
                    field.arisa_stamps[r][c]
                    if block == BlockType.MINE_SHOWN
                    else field.kasumi_stamps[r][c]
                )
                f.image(image, x + 7, top + 7, cell - 14, cell - 14)
            else:
                font_size = min(48, max(18, round(cell * 0.38)))
                f.text(
                    str(r * cols + c + 1),
                    x + 6,
                    top + (cell - font_size) // 2,
                    cell - 12,
                    font_size,
                    MUTED,
                    align="center",
                )
    f.footer("格子编号从左到右、从上到下排列", y + board_h + 28)


@surface(1120, book=True)
def result(f, data, *, identity=None):
    from plugins.mines.render.result import _HEADLINES

    y = f.title(
        "探险归档",
        "EXPEDITION / SETTLEMENT",
        _HEADLINES.get(data.outcome, str(data.outcome)),
    )
    left = f.person(identity, 58, y, 400)
    left = f.metric("本局净收益", f"{data.net:+,} Pt", 58, left + 42, 400, size=60)
    if data.positive:
        left = f.stamp(
            "撤退结算" if str(data.outcome) == "cashout" else "探索完成",
            58,
            left + 40,
            260,
        )
    right = f.section("探索记录", 524, y, 538)
    rows = [
        ("押注", f"{data.bet_amount:,} Pt"),
        ("结算入账", f"{data.payout:,} Pt"),
        ("结算倍率", f"× {data.multiplier:.2f}"),
        ("已翻开", f"{data.revealed_count}/{data.safe_cells}"),
        ("Arisa 数量", f"{data.mines} 个"),
        ("当前余额", f"{data.balance:,} Pt"),
    ]
    right = f.facts(rows, 524, right, 538)
    gains = gain_rows(data)
    if gains:
        right = f.section("任务与成长", 524, right + 20, 538)
        right = f.facts(gains, 524, right, 538)
    if data.payout_capped:
        right = f.text("本次入账已达到奖励上限", 524, right + 18, 538, 23, ROSE)
    f.gutter(458, 524, y, max(left, right), padding=22)
    f.footer("/探险 开始新的探索 · /探险统计 查看战绩", max(left, right) + 28)


@surface(1160)
def stats(f, data):
    from .blackjack import recent_form

    y = f.title("探索纪要", "EXPEDITION / LEDGER", f"战绩 {data.total_games} 局")
    a = f.metric("净收益", f"{data.net_profit:+,} Pt", 58, y, 390, size=58)
    a = f.metric("胜率", f"{data.win_rate:.1%}", 58, a + 34, 390, size=58)
    a = f.text(
        f"{data.wins} 胜 / {data.losses} 负 / {data.total_games} 局",
        58,
        a + 24,
        390,
        24,
        MUTED,
    )
    b = f.section("探索收支", 524, y, 578)
    b = f.facts(
        (
            ("总投入", f"{data.total_wagered:,} Pt"),
            ("总赢得", f"{data.total_won:,} Pt"),
            ("总输掉", f"{data.total_lost:,} Pt"),
            ("平均下注", f"{data.avg_bet:.1f} Pt"),
            ("平均赢得", f"{data.avg_win:.1f} Pt"),
            ("平均输掉", f"{data.avg_loss:.1f} Pt"),
            ("最高赢", f"{data.biggest_win:,} Pt"),
            ("最高输", f"{data.biggest_loss:,} Pt"),
        ),
        524,
        b,
        578,
    )
    end = recent_form(f, data.recent_games, 58, max(a, b) + 38, 1044)
    f.footer("/探险 开始新的探索", end + 24)
