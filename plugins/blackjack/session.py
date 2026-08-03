from typing import Set
from typing import Dict
from typing import Optional
from collections import defaultdict
from dataclasses import dataclass

from .. import monetary
from .models import Hand
from .models import Shoe
from .models import GameResult
from .game_service import BlackjackGameService


@dataclass
class GameSession:
    user_id: str
    channel_id: str
    bet_amount: int
    player_hand: Hand
    dealer_hand: Hand
    split_hand: Optional[Hand] = None
    split_bet: int = 0
    current_hand_index: int = 0
    # The table renderer belongs to one game, not the process.  Its kit is
    # selected from the player’s equipped theme at game start.
    renderer: object | None = None

    def is_split(self) -> bool:
        return self.split_hand is not None

    def get_current_hand(self) -> Hand:
        if self.current_hand_index == 1 and self.split_hand is not None:
            return self.split_hand
        return self.player_hand

    def advance_to_next_hand(self) -> None:
        if self.is_split() and self.current_hand_index == 0:
            self.current_hand_index = 1


class GameManager:
    def __init__(self, renderer=None):
        self.renderer = renderer
        self.reshuffle_threshold = 52 * 6 * 0.25
        self._sessions: Dict[str, GameSession] = {}
        self._shoes: Dict[str, Shoe] = defaultdict(self._init_shoe)
        self._active_players: Set[str] = set()
        self._player_bets: Dict[str, int] = {}
        self._player_split_state: Dict[str, int] = defaultdict(lambda: 0)

    def set_renderer(self, renderer) -> None:
        self.renderer = renderer

    def _init_shoe(self) -> Shoe:
        shoe = Shoe()
        return shoe

    def get_shoe(self, channel_id: str) -> Shoe:
        return self._shoes[channel_id]

    def create_session(
        self,
        user_id: str,
        channel_id: str,
        bet_amount: int,
        player_hand: Hand,
        dealer_hand: Hand,
        renderer: object | None = None,
    ) -> GameSession:
        session = GameSession(
            user_id=user_id,
            channel_id=channel_id,
            bet_amount=bet_amount,
            player_hand=player_hand,
            dealer_hand=dealer_hand,
            renderer=renderer,
        )
        self._sessions[user_id] = session
        return session

    def get_session(self, user_id: str) -> Optional[GameSession]:
        return self._sessions.get(user_id)

    def renderer_for(self, user_id: str):
        """Return the renderer pinned to a player's game.

        ``self.renderer`` remains the startup renderer and is the fallback for
        legacy callers or a session constructed without a themed renderer.
        Never mutate it per request: two blackjack games can wait for input at
        the same time, and changing a shared kit would make their tables swap
        themes mid-game.
        """

        session = self.get_session(user_id)
        if session is not None and session.renderer is not None:
            return session.renderer
        return self.renderer

    def remove_session(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)

    def is_in_game(self, user_id: str) -> bool:
        return user_id in self._active_players

    def get_active_players(self) -> Set[str]:
        return set(self._active_players)

    def start_game(self, user_id: str, bet_amount: int) -> bool:
        if user_id in self._active_players:
            return False

        if monetary.get(user_id) < bet_amount:
            return False

        monetary.cost(user_id, bet_amount, "blackjack")
        self._active_players.add(user_id)
        self._player_bets[user_id] = bet_amount
        return True

    def end_game(self, user_id: str, result: GameResult, winnings: int = 0) -> int:
        """
        结束游戏并返回实际奖金
        """
        if user_id not in self._active_players:
            return winnings

        bet_amount = self._player_bets.get(user_id, 0)
        is_split = self._player_split_state[user_id] > 0

        total_return = bet_amount + winnings
        if total_return > 0:
            monetary.add(user_id, total_return, "blackjack")

        BlackjackGameService.record_game(
            user_id=user_id,
            bet_amount=bet_amount,
            result=result,
            winnings=winnings,
            is_split=is_split,
        )

        self._active_players.discard(user_id)
        self._player_bets.pop(user_id, None)
        self._player_split_state.pop(user_id, None)
        self.remove_session(user_id)

        return winnings

    def refund_game(self, user_id: str) -> None:
        if user_id not in self._active_players:
            return

        bet_amount = self._player_bets.get(user_id, 0)
        if bet_amount > 0:
            monetary.add(user_id, bet_amount, "blackjack")

        self._active_players.discard(user_id)
        self._player_bets.pop(user_id, None)
        self._player_split_state.pop(user_id, None)
        self.remove_session(user_id)

    def refund_half_game(self, user_id: str) -> None:
        if user_id not in self._active_players:
            return

        bet_amount = self._player_bets.get(user_id, 0)
        if bet_amount > 0:
            monetary.add(user_id, bet_amount // 2, "blackjack")

        self._active_players.discard(user_id)
        self._player_bets.pop(user_id, None)
        self._player_split_state.pop(user_id, None)
        self.remove_session(user_id)

    def get_player_bet(self, user_id: str) -> int:
        return self._player_bets.get(user_id, 0)

    def set_player_bet(self, user_id: str, bet_amount: int) -> None:
        self._player_bets[user_id] = bet_amount

    def get_split_state(self, user_id: str) -> int:
        return self._player_split_state[user_id]

    def set_split_state(self, user_id: str, state: int) -> None:
        self._player_split_state[user_id] = state
