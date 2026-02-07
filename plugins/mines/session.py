from __future__ import annotations

import time
from math import comb
from typing import Dict, Optional, Set
from dataclasses import dataclass, field as dataclass_field

from .. import monetary
from .database import get_session
from .models import Field, GameResult, MinesGame


@dataclass
class GameSession:
    user_id: str
    channel_id: str
    bet_amount: int
    mines: int
    field: Field
    revealed_indices: Set[int] = dataclass_field(default_factory=set)
    multiplier: float = 1.0
    house_edge: float = 0.03

    @property
    def revealed_count(self) -> int:
        return len(self.revealed_indices)

    @property
    def safe_cells(self) -> int:
        return self.field.safe_cells()

    def update_multiplier(self) -> None:
        if self.revealed_count <= 0:
            self.multiplier = 1.0
            return
        total_tiles = self.field.total_cells()
        total_gems = total_tiles - self.mines
        prob = comb(total_gems, self.revealed_count) / comb(
            total_tiles, self.revealed_count
        )
        self.multiplier = (1 / prob) * (1 - self.house_edge)

    def get_payout(self) -> int:
        return int(self.bet_amount * self.multiplier)


class GameManager:
    def __init__(self):
        self._sessions: Dict[str, GameSession] = {}
        self._active_players: Set[str] = set()

    def is_in_game(self, user_id: str) -> bool:
        return user_id in self._active_players

    def start_game(self, user_id: str, bet_amount: int) -> bool:
        if user_id in self._active_players:
            return False
        if monetary.get(user_id) < bet_amount:
            return False
        monetary.cost(user_id, bet_amount, "mines")
        self._active_players.add(user_id)
        return True

    def create_session(
        self, user_id: str, channel_id: str, bet_amount: int, mines: int
    ) -> GameSession:
        field = Field(width=5, height=5, mines=mines)
        session = GameSession(
            user_id=user_id,
            channel_id=channel_id,
            bet_amount=bet_amount,
            mines=mines,
            field=field,
        )
        self._sessions[user_id] = session
        return session

    def get_session(self, user_id: str) -> Optional[GameSession]:
        return self._sessions.get(user_id)

    def remove_session(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)
        self._active_players.discard(user_id)

    def end_game(self, user_id: str, result: GameResult, payout: int) -> None:
        session = self._sessions.get(user_id)
        if session is None:
            return

        if payout > 0:
            monetary.add(user_id, payout, "mines")
            winnings = payout - session.bet_amount
        else:
            winnings = -session.bet_amount

        db_session = get_session()
        db_session.add(
            MinesGame(
                user_id=user_id,
                bet_amount=session.bet_amount,
                mines=session.mines,
                revealed_count=session.revealed_count,
                result=result.value,
                winnings=winnings,
                timestamp=int(time.time()),
            )
        )
        db_session.commit()

        self.remove_session(user_id)

    def refund_game(self, user_id: str) -> None:
        session = self._sessions.get(user_id)
        if session is None:
            return
        monetary.add(user_id, session.bet_amount, "mines_refund")
        self.remove_session(user_id)
