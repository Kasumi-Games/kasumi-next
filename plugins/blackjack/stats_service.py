"""
Blackjack game statistics service for analyzing player game data.
"""

from pathlib import Path
from matplotlib.axes import Axes
from dataclasses import dataclass
import matplotlib.font_manager as fm
from typing import List, Optional, cast

from .. import monetary
from ..monetary.models import Transaction, TransactionCategory


font_path = Path(__file__).parent / "recourses" / "old.ttf"
font = fm.FontProperties(fname=font_path)


@dataclass
class BlackjackGameRecord:
    """Single blackjack game record"""

    time: int
    amount: int  # Positive for wins, negative for losses
    is_win: bool
    bet_amount: int  # Original bet amount (always positive)


@dataclass
class BlackjackStats:
    """Comprehensive blackjack statistics for a player"""

    user_id: str
    total_games: int
    wins: int
    losses: int
    pushes: int  # 平局
    win_rate: float
    total_wagered: int  # 总投入
    total_won: int  # 总赢得
    total_lost: int  # 总失去
    net_profit: int  # 净收益 (可能为负)
    avg_bet: float  # 平均每轮赌注
    avg_win: float  # 平均赢得金额
    avg_loss: float  # 平均失去金额
    biggest_win: int  # 最高赢得
    biggest_loss: int  # 最高失去
    recent_games: List[BlackjackGameRecord]  # 最近30次游戏记录


def _analyze_game_records(transactions: List[Transaction]) -> List[BlackjackGameRecord]:
    """
    分析交易记录，提取游戏结果

    Args:
        transactions: blackjack交易记录列表

    Returns:
        游戏记录列表
    """
    game_records = []

    for transaction in transactions:
        if transaction.category == TransactionCategory.INCOME:
            # 赢钱记录
            # 从金额推算原始赌注（考虑1.5倍和生日bonus）
            if transaction.amount % 3 == 0:  # 可能是1.5倍奖励
                bet_amount = int(transaction.amount / 1.5)
            else:
                bet_amount = transaction.amount  # 1:1赔率

            game_records.append(
                BlackjackGameRecord(
                    time=transaction.time,
                    amount=transaction.amount,
                    is_win=True,
                    bet_amount=bet_amount,
                )
            )

        elif transaction.category == TransactionCategory.EXPENSE:
            # 输钱记录
            game_records.append(
                BlackjackGameRecord(
                    time=transaction.time,
                    amount=-transaction.amount,  # 转为负数表示损失
                    is_win=False,
                    bet_amount=transaction.amount,
                )
            )

    return sorted(game_records, key=lambda x: x.time, reverse=True)


def get_blackjack_stats(user_id: str) -> BlackjackStats:
    """
    获取用户的blackjack游戏统计数据

    Args:
        user_id: 用户ID

    Returns:
        完整的blackjack统计数据
    """
    # 使用monetary插件的通用接口获取blackjack交易记录
    all_transactions = monetary.get_user_transactions(user_id, "blackjack")

    if not all_transactions:
        # 没有游戏记录，返回空统计
        return BlackjackStats(
            user_id=user_id,
            total_games=0,
            wins=0,
            losses=0,
            pushes=0,
            win_rate=0.0,
            total_wagered=0,
            total_won=0,
            total_lost=0,
            net_profit=0,
            avg_bet=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            biggest_win=0,
            biggest_loss=0,
            recent_games=[],
        )

    # 分析游戏记录
    game_records = _analyze_game_records(all_transactions)

    # 计算基础统计
    total_games = len(game_records)
    wins = sum(1 for record in game_records if record.is_win)
    losses = total_games - wins
    pushes = 0  # 平局在当前实现中不会产生交易记录

    win_rate = wins / total_games if total_games > 0 else 0.0

    # 计算金额统计
    total_wagered = sum(record.bet_amount for record in game_records)
    total_won = sum(record.amount for record in game_records if record.amount > 0)
    total_lost = abs(sum(record.amount for record in game_records if record.amount < 0))
    net_profit = total_won - total_lost

    # 计算平均值
    avg_bet = total_wagered / total_games if total_games > 0 else 0.0
    avg_win = total_won / wins if wins > 0 else 0.0
    avg_loss = total_lost / losses if losses > 0 else 0.0

    # 计算最值
    win_amounts = [record.amount for record in game_records if record.amount > 0]
    loss_amounts = [abs(record.amount) for record in game_records if record.amount < 0]

    biggest_win = max(win_amounts) if win_amounts else 0
    biggest_loss = max(loss_amounts) if loss_amounts else 0

    # 获取最近30次游戏记录
    recent_games = game_records[:30]

    return BlackjackStats(
        user_id=user_id,
        total_games=total_games,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=win_rate,
        total_wagered=total_wagered,
        total_won=total_won,
        total_lost=total_lost,
        net_profit=int(net_profit),
        avg_bet=avg_bet,
        avg_win=avg_win,
        avg_loss=avg_loss,
        biggest_win=biggest_win,
        biggest_loss=biggest_loss,
        recent_games=recent_games,
    )


def create_win_loss_chart(stats: BlackjackStats) -> Optional[bytes]:
    """
    创建最近30次游戏的输赢图表

    Args:
        stats: blackjack统计数据

    Returns:
        图表的PNG字节数据，如果没有足够数据则返回None
    """
    try:
        import matplotlib

        matplotlib.use("Agg")  # 使用非交互式后端
        import matplotlib.pyplot as plt
        from io import BytesIO
        import numpy as np
    except ImportError:
        # matplotlib未安装，返回None
        return None

    if len(stats.recent_games) < 2:
        return None

    plt.rcParams["font.family"] = font.get_name()
    plt.rcParams["axes.unicode_minus"] = False

    # 准备数据
    games = stats.recent_games[::-1]  # 反转以按时间正序显示
    game_numbers = list(range(1, len(games) + 1))
    profits = [game.amount for game in games]

    # 计算累计收益
    cumulative_profit = np.cumsum(profits)

    # 创建图表
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    ax1 = cast(Axes, ax1)
    ax2 = cast(Axes, ax2)

    # 第一个子图：单次游戏输赢
    colors = ["green" if p > 0 else "red" if p < 0 else "gray" for p in profits]
    bars = ax1.bar(game_numbers, profits, color=colors, alpha=0.7)
    ax1.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax1.set_title(
        f"最近 {len(games)} 次黑香澄游戏单次输赢",
        fontsize=14,
        fontweight="bold",
        fontproperties=font,
    )
    ax1.set_xlabel("游戏局数", fontproperties=font)
    ax1.set_ylabel("输赢金额 (碎片)", fontproperties=font)
    ax1.grid(True, alpha=0.3)

    # 添加数值标签
    for _, (bar, profit) in enumerate(zip(bars, profits)):
        if profit != 0:
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (5 if profit > 0 else -15),
                str(profit),
                ha="center",
                va="bottom" if profit > 0 else "top",
                fontsize=8,
                fontproperties=font,
            )

    # 第二个子图：累计收益曲线
    ax2.plot(
        game_numbers, cumulative_profit, "b-", linewidth=2, marker="o", markersize=4
    )
    ax2.axhline(y=0, color="gray", linestyle="--", alpha=0.7)

    # 先填充整个区域为浅灰色作为基础
    ax2.fill_between(game_numbers, cumulative_profit, 0, alpha=0.1, color="gray")

    # 然后分别填充正负区域，使用interpolate确保连续性
    ax2.fill_between(
        game_numbers,
        cumulative_profit,
        0,
        where=np.array(cumulative_profit) >= 0,
        color="green",
        alpha=0.3,
        interpolate=True,
        label="盈利区域",
    )
    ax2.fill_between(
        game_numbers,
        cumulative_profit,
        0,
        where=np.array(cumulative_profit) < 0,
        color="red",
        alpha=0.3,
        interpolate=True,
        label="亏损区域",
    )
    ax2.set_title("累计收益趋势", fontsize=14, fontweight="bold", fontproperties=font)
    ax2.set_xlabel("游戏局数", fontproperties=font)
    ax2.set_ylabel("累计收益 (碎片)", fontproperties=font)
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # 添加统计信息
    info_text = f"胜率: {stats.win_rate:.1%} | 净收益: {stats.net_profit} | 平均赌注: {stats.avg_bet:.1f}"
    fig.suptitle(info_text, fontsize=11, y=0.95, fontproperties=font)

    # 调整子图间距和边距
    plt.subplots_adjust(top=0.88, bottom=0.12, hspace=0.35, left=0.08, right=0.95)

    # 保存到字节流
    buffer = BytesIO()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches=None)
    buffer.seek(0)
    chart_bytes = buffer.getvalue()
    plt.close()

    return chart_bytes
