"""
Mines game statistics service for analyzing player game data.
"""

from typing import List
from dataclasses import dataclass

from .models import MinesGame
from .database import get_session


@dataclass
class MinesGameRecord:
    """Single mines game record"""

    time: int
    amount: int  # Positive for wins, negative for losses
    is_win: bool
    bet_amount: int  # Original bet amount (always positive)
    mines: int  # Number of mines in the game
    revealed_count: int  # Number of cells revealed


@dataclass
class MinesStats:
    """Comprehensive mines statistics for a player"""

    user_id: str
    total_games: int
    wins: int
    losses: int
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
    recent_games: List[MinesGameRecord]  # 最近30次游戏记录


def _convert_db_games_to_records(
    db_games: List[MinesGame],
) -> List[MinesGameRecord]:
    """
    将数据库游戏记录转换为MinesGameRecord格式

    Args:
        db_games: 数据库游戏记录列表

    Returns:
        MinesGameRecord列表
    """
    game_records = []

    for game in db_games:
        is_win = game.winnings > 0

        game_records.append(
            MinesGameRecord(
                time=game.timestamp,
                amount=game.winnings,  # 净收益
                is_win=is_win,
                bet_amount=game.bet_amount,
                mines=game.mines,
                revealed_count=game.revealed_count,
            )
        )

    return game_records


def get_mines_stats(
    user_id: str, *, start_time: int | None = None, end_time: int | None = None
) -> MinesStats:
    """
    获取用户的mines游戏统计数据

    Args:
        user_id: 用户ID

    Returns:
        完整的mines统计数据
    """
    db_session = get_session()

    try:
        games_query = db_session.query(MinesGame).filter(MinesGame.user_id == user_id)
        if start_time is not None:
            games_query = games_query.filter(MinesGame.timestamp >= start_time)
        if end_time is not None:
            games_query = games_query.filter(MinesGame.timestamp < end_time)
        games = games_query.all()

        if not games:
            return MinesStats(
                user_id=user_id,
                total_games=0,
                wins=0,
                losses=0,
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

        total_games = len(games)
        total_wagered = sum(game.bet_amount for game in games)
        total_won = sum(game.winnings for game in games if game.winnings > 0)
        total_lost = abs(sum(game.winnings for game in games if game.winnings < 0))
        net_profit = total_won - total_lost
        wins = len([g for g in games if g.winnings > 0])
        losses = len([g for g in games if g.winnings < 0])
        win_rate = wins / total_games if total_games > 0 else 0.0

        avg_bet = total_wagered / total_games if total_games else 0.0
        win_amounts = [g.winnings for g in games if g.winnings > 0]
        loss_amounts = [abs(g.winnings) for g in games if g.winnings < 0]
        biggest_win = max(win_amounts) if win_amounts else 0
        biggest_loss = max(loss_amounts) if loss_amounts else 0
        avg_win = sum(win_amounts) / len(win_amounts) if win_amounts else 0.0
        avg_loss = sum(loss_amounts) / len(loss_amounts) if loss_amounts else 0.0

        # 获取最近30次游戏记录（按时间倒序）
        recent_query = db_session.query(MinesGame).filter(MinesGame.user_id == user_id)
        if start_time is not None:
            recent_query = recent_query.filter(MinesGame.timestamp >= start_time)
        if end_time is not None:
            recent_query = recent_query.filter(MinesGame.timestamp < end_time)
        recent_db_games = recent_query.order_by(MinesGame.timestamp.desc()).limit(30).all()
        recent_games = _convert_db_games_to_records(recent_db_games)

        return MinesStats(
            user_id=user_id,
            total_games=total_games,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_wagered=total_wagered,
            total_won=total_won,
            total_lost=total_lost,
            net_profit=net_profit,
            avg_bet=avg_bet,
            avg_win=avg_win,
            avg_loss=avg_loss,
            biggest_win=biggest_win,
            biggest_loss=biggest_loss,
            recent_games=recent_games,
        )
    finally:
        db_session.close()
