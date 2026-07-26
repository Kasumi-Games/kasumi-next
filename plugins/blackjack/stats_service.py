"""
Blackjack game statistics service for analyzing player game data.

The former ``create_win_loss_chart`` matplotlib figure is gone: ``/黑香澄统计``
now answers with the themed card in ``stats_render``, so this module is pure
data assembly.
"""

from typing import List
from dataclasses import dataclass

from .models import BlackjackGame
from .game_service import BlackjackGameService


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
    blackjacks: int  # BlackJack获胜次数（已计入wins）
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


def _convert_db_games_to_records(
    db_games: List[BlackjackGame],
) -> List[BlackjackGameRecord]:
    """
    将数据库游戏记录转换为BlackjackGameRecord格式

    Args:
        db_games: 数据库游戏记录列表

    Returns:
        BlackjackGameRecord列表
    """
    game_records = []

    for game in db_games:
        is_win = game.result in ["win", "blackjack"]

        game_records.append(
            BlackjackGameRecord(
                time=game.timestamp,
                amount=game.winnings,  # 净收益
                is_win=is_win,
                bet_amount=game.bet_amount,
            )
        )

    return game_records


def get_blackjack_stats(user_id: str) -> BlackjackStats:
    """
    获取用户的blackjack游戏统计数据

    Args:
        user_id: 用户ID

    Returns:
        完整的blackjack统计数据
    """
    # 从数据库获取统计信息
    stats_dict = BlackjackGameService.get_user_stats(user_id)

    if stats_dict["total_games"] == 0:
        # 没有游戏记录，返回空统计
        return BlackjackStats(
            user_id=user_id,
            total_games=0,
            wins=0,
            losses=0,
            pushes=0,
            blackjacks=0,
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

    # 获取最近30次游戏记录
    recent_db_games = BlackjackGameService.get_user_games(user_id, limit=30)
    recent_games = _convert_db_games_to_records(recent_db_games)

    return BlackjackStats(
        user_id=user_id,
        total_games=stats_dict["total_games"],
        wins=stats_dict["wins"],
        losses=stats_dict["losses"],
        pushes=stats_dict["pushes"],
        blackjacks=stats_dict["blackjacks"],
        win_rate=stats_dict["win_rate"],
        total_wagered=stats_dict["total_wagered"],
        total_won=stats_dict["total_won"],
        total_lost=stats_dict["total_lost"],
        net_profit=stats_dict["net_profit"],
        avg_bet=stats_dict["avg_bet"],
        avg_win=stats_dict["avg_win"],
        avg_loss=stats_dict["avg_loss"],
        biggest_win=stats_dict["biggest_win"],
        biggest_loss=stats_dict["biggest_loss"],
        recent_games=recent_games,
    )
