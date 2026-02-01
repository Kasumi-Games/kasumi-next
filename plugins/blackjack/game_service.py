"""
Blackjack game database service for storing and retrieving game records.
"""

import time
from datetime import datetime
from typing import List, Optional

from .database import get_session
from .models import BlackjackGame, GameResult


class BlackjackGameService:
    """Service class for handling blackjack game database operations"""

    @staticmethod
    def has_played_today(user_id: str) -> bool:
        """
        Check if the user has played any game today

        Args:
            user_id: Player's user ID

        Returns:
            True if user has played at least one game today
        """
        session = get_session()

        # 获取今天0点的时间戳
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_timestamp = int(today_start.timestamp())

        # 查询今天是否有游戏记录
        count = (
            session.query(BlackjackGame)
            .filter(BlackjackGame.user_id == user_id)
            .filter(BlackjackGame.timestamp >= today_timestamp)
            .count()
        )

        return count > 0

    @staticmethod
    def record_game(
        user_id: str,
        bet_amount: int,
        result: GameResult,
        winnings: int,
        is_split: bool = False,
    ) -> BlackjackGame:
        """
        Record a completed blackjack game

        Args:
            user_id: Player's user ID
            bet_amount: Total bet amount (including split)
            result: Game result from GameResult enum
            winnings: Net winnings (can be negative for losses)
            is_split: Whether the game involved splitting cards

        Returns:
            The created BlackjackGame record
        """
        session = get_session()

        game = BlackjackGame(
            user_id=user_id,
            bet_amount=bet_amount,
            result=result.value,
            winnings=winnings,
            is_split=1 if is_split else 0,
            timestamp=int(time.time()),
        )

        session.add(game)
        session.commit()

        return game

    @staticmethod
    def get_user_games(
        user_id: str, limit: Optional[int] = None
    ) -> List[BlackjackGame]:
        """
        Get all games for a user, ordered by timestamp (newest first)

        Args:
            user_id: Player's user ID
            limit: Optional limit on number of results

        Returns:
            List of BlackjackGame records
        """
        session = get_session()

        query = (
            session.query(BlackjackGame)
            .filter(BlackjackGame.user_id == user_id)
            .order_by(BlackjackGame.timestamp.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    @staticmethod
    def get_user_stats(user_id: str) -> dict:
        """
        Get comprehensive statistics for a user

        Args:
            user_id: Player's user ID

        Returns:
            Dictionary with complete statistics
        """
        session = get_session()

        games = (
            session.query(BlackjackGame).filter(BlackjackGame.user_id == user_id).all()
        )

        if not games:
            return {
                "total_games": 0,
                "wins": 0,
                "losses": 0,
                "pushes": 0,
                "win_rate": 0.0,
                "total_wagered": 0,
                "total_won": 0,
                "total_lost": 0,
                "net_profit": 0,
                "avg_bet": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "biggest_win": 0,
                "biggest_loss": 0,
            }

        # Basic counts
        total_games = len(games)
        wins = len(
            [
                g
                for g in games
                if g.result in [GameResult.WIN.value, GameResult.BLACKJACK.value]
            ]
        )
        pushes = len([g for g in games if g.result == GameResult.PUSH.value])
        losses = total_games - wins - pushes

        # Win rate
        win_rate = wins / total_games if total_games > 0 else 0.0

        # Financial stats
        total_wagered = sum(game.bet_amount for game in games)
        total_won = sum(game.winnings for game in games if game.winnings > 0)
        total_lost = abs(sum(game.winnings for game in games if game.winnings < 0))
        net_profit = total_won - total_lost

        # Averages
        avg_bet = total_wagered / total_games if total_games > 0 else 0.0
        avg_win = total_won / wins if wins > 0 else 0.0
        avg_loss = total_lost / losses if losses > 0 else 0.0

        # Extremes
        win_amounts = [game.winnings for game in games if game.winnings > 0]
        loss_amounts = [abs(game.winnings) for game in games if game.winnings < 0]

        biggest_win = max(win_amounts) if win_amounts else 0
        biggest_loss = max(loss_amounts) if loss_amounts else 0

        return {
            "total_games": total_games,
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": win_rate,
            "total_wagered": total_wagered,
            "total_won": total_won,
            "total_lost": total_lost,
            "net_profit": net_profit,
            "avg_bet": avg_bet,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "biggest_win": biggest_win,
            "biggest_loss": biggest_loss,
        }
