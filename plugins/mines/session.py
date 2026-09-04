import time
import uuid
from math import comb
from typing import Set
from typing import Dict
from typing import Tuple
from typing import Iterable
from typing import Optional
from dataclasses import field as dataclass_field
from dataclasses import dataclass

from .models import Field
from .models import BlockType
from .models import MinesGame
from .models import GameResult
from .database import get_session
from ..inventory import point_hold_service as point_holds

DEFAULT_BOARD_SIZE = 5
MIN_BOARD_SIZE = 2
MAX_BOARD_SIZE = 10
MAX_PAYOUT = 1_000_000_000


def parse_start_args(
    arg_text: str,
) -> Tuple[Optional[int], Optional[int], int]:
    """Parse ``<stake> <mines> [board side length]``."""

    parts = [part for part in arg_text.split() if part]
    if len(parts) > 3:
        raise ValueError("too many arguments")

    bet_amount: Optional[int] = None
    mines: Optional[int] = None
    board_size = DEFAULT_BOARD_SIZE
    if parts:
        try:
            bet_amount = int(parts[0])
        except ValueError:
            bet_amount = None
    if len(parts) >= 2:
        try:
            mines = int(parts[1])
        except ValueError as exc:
            raise ValueError("mine count must be an integer") from exc
    if len(parts) == 3:
        try:
            board_size = int(parts[2])
        except ValueError as exc:
            raise ValueError("board side length must be an integer") from exc

    return bet_amount, mines, board_size


@dataclass(frozen=True)
class RevealBatchResult:
    """Result of revealing one or more cells in input order."""

    opened_indices: Tuple[int, ...]
    already_revealed_indices: Tuple[int, ...]
    hit_mine: bool
    won: bool


def parse_reveal_indices(message: str, total_cells: int) -> Optional[Tuple[int, ...]]:
    """Parse a whitespace-separated, one-based list of board positions."""
    parts = message.split()
    if not parts or any(not part.isdecimal() for part in parts):
        return None

    indices = tuple(int(part) - 1 for part in parts)
    if any(index < 0 or index >= total_cells for index in indices):
        return None
    return indices


@dataclass
class GameSession:
    user_id: str
    channel_id: str
    bet_amount: int
    mines: int
    field: Field
    hold_key: str = ""
    cancelled_reason: str = ""
    revealed_indices: Set[int] = dataclass_field(default_factory=set)
    multiplier: float = 1.0
    house_edge: float = 0.03

    @property
    def revealed_count(self) -> int:
        return len(self.revealed_indices)

    @property
    def safe_cells(self) -> int:
        return self.field.safe_cells()

    @property
    def multiplier_cap(self) -> float:
        """Highest displayed multiplier that still pays at most the cap."""

        return MAX_PAYOUT / self.bet_amount

    @property
    def is_payout_capped(self) -> bool:
        """Whether this round has reached the configured payout ceiling."""

        return (
            self.revealed_count > 0
            and self.multiplier >= self.multiplier_cap
        )

    def update_multiplier(self) -> None:
        if self.revealed_count <= 0:
            self.multiplier = 1.0
            return
        total_tiles = self.field.total_cells()
        total_gems = total_tiles - self.mines
        prob = comb(total_gems, self.revealed_count) / comb(
            total_tiles, self.revealed_count
        )
        uncapped_multiplier = (1 / prob) * (1 - self.house_edge)
        self.multiplier = min(uncapped_multiplier, self.multiplier_cap)

    def get_payout(self) -> int:
        if self.is_payout_capped:
            return MAX_PAYOUT
        return int(self.bet_amount * self.multiplier)

    def reveal_blocks(self, indices: Iterable[int]) -> RevealBatchResult:
        """Reveal cells in order, stopping as soon as the round ends.

        Previously revealed cells are skipped so a mixed batch can still open
        its new cells. A mine and the final safe cell both end processing;
        positions later in the same message are left untouched.
        """
        opened_indices = []
        already_revealed_indices = []
        hit_mine = False
        won = False
        total_cells = self.field.total_cells()

        for index in indices:
            if index < 0 or index >= total_cells:
                raise ValueError(f"cell index out of range: {index}")
            if index in self.revealed_indices:
                already_revealed_indices.append(index)
                continue

            block = self.field.reveal_block(index)
            opened_indices.append(index)
            if block == BlockType.MINE:
                hit_mine = True
                break

            self.revealed_indices.add(index)
            self.update_multiplier()
            if self.revealed_count >= self.safe_cells:
                won = True
                break

        return RevealBatchResult(
            opened_indices=tuple(opened_indices),
            already_revealed_indices=tuple(already_revealed_indices),
            hit_mine=hit_mine,
            won=won,
        )


class GameManager:
    def __init__(self):
        self._sessions: Dict[str, GameSession] = {}
        self._active_players: Set[str] = set()
        self._pending_hold_keys: Dict[str, str] = {}

    def is_in_game(self, user_id: str) -> bool:
        return user_id in self._active_players

    def start_game(self, user_id: str, bet_amount: int) -> bool:
        if bet_amount > MAX_PAYOUT or user_id in self._active_players:
            return False
        hold_key = f"mines:{uuid.uuid4().hex}"
        try:
            point_holds.reserve_points(
                user_id,
                bet_amount,
                hold_key,
                "mines",
                operation_key=f"{hold_key}:start",
            )
        except point_holds.PointHoldError:
            return False
        self._active_players.add(user_id)
        self._pending_hold_keys[user_id] = hold_key
        return True

    def create_session(
        self,
        user_id: str,
        channel_id: str,
        bet_amount: int,
        mines: int,
        board_size: int = DEFAULT_BOARD_SIZE,
    ) -> GameSession:
        if bet_amount <= 0 or bet_amount > MAX_PAYOUT:
            raise ValueError(f"bet amount must be between 1 and {MAX_PAYOUT}")
        if not MIN_BOARD_SIZE <= board_size <= MAX_BOARD_SIZE:
            raise ValueError(f"unsupported board size: {board_size}")
        if mines <= 0 or mines >= board_size * board_size:
            raise ValueError("mine count must leave at least one safe cell")

        field = Field(width=board_size, height=board_size, mines=mines)
        session = GameSession(
            user_id=user_id,
            channel_id=channel_id,
            bet_amount=bet_amount,
            mines=mines,
            field=field,
            hold_key=self._pending_hold_keys.pop(user_id),
        )
        self._sessions[user_id] = session
        return session

    def get_session(self, user_id: str) -> Optional[GameSession]:
        return self._sessions.get(user_id)

    def remove_session(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)
        self._active_players.discard(user_id)
        self._pending_hold_keys.pop(user_id, None)

    def ensure_active(self, session: GameSession) -> None:
        if session.cancelled_reason:
            self.remove_session(session.user_id)
            raise point_holds.PointHoldScopeClosed(session.cancelled_reason)

    def end_game(self, user_id: str, result: GameResult, payout: int) -> None:
        session = self._sessions.get(user_id)
        if session is None:
            return

        self.ensure_active(session)

        try:
            point_holds.settle_point_hold(
                session.hold_key,
                payout,
                operation_key=f"{session.hold_key}:settle",
            )
        except point_holds.PointHoldScopeClosed:
            point_holds.refund_point_hold(
                session.hold_key,
                operation_key=f"{session.hold_key}:season_cancel",
            )
            session.cancelled_reason = "赛季已结束"
            self.remove_session(user_id)
            raise

        if payout > 0:
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
        hold_key = (
            session.hold_key
            if session is not None
            else self._pending_hold_keys.get(user_id)
        )
        if hold_key is None:
            return
        point_holds.refund_point_hold(
            hold_key, operation_key=f"{hold_key}:refund"
        )
        self.remove_session(user_id)

    def close_scope(self, scope_type: str, scope_id: str, cutoff: int) -> None:
        del cutoff
        for session in list(self._sessions.values()):
            hold = point_holds.get_point_hold(session.hold_key)
            if (
                hold is None
                or hold.scope_type != scope_type
                or hold.scope_id != scope_id
                or hold.status != point_holds.HOLD_OPEN
            ):
                continue
            point_holds.refund_point_hold(
                session.hold_key,
                operation_key=f"{session.hold_key}:season_cancel",
            )
            session.cancelled_reason = "赛季已结束"
