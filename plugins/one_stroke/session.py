from __future__ import annotations

import time
import random
from pathlib import Path
from typing import Dict, Optional, Set
from dataclasses import dataclass, field

from .models import Edge, Graph, MoveResult, Node
from plugins.render_service.primitives import RESOURCES_DIR

BG_PATH = RESOURCES_DIR / "BG"
BGS = list(BG_PATH.glob("bg[0-9][0-9][0-9][0-9][0-9].png"))
DIRECTION_DELTAS = {
    "W": (-1, 0),
    "A": (0, -1),
    "S": (1, 0),
    "D": (0, 1),
}


@dataclass
class GameSession:
    user_id: str
    channel_id: str
    difficulty_name: str
    reward: int
    graph: Graph
    bg_path: Path = field(init=False)
    current_pos: Node = field(init=False)
    drawn_edges: Set[Edge] = field(default_factory=set)
    visited_nodes: Set[Node] = field(default_factory=set)
    move_history: list[str] = field(default_factory=list)
    started_at: float = field(init=False)

    def __post_init__(self) -> None:
        self.started_at = time.monotonic()
        self.bg_path = random.choice(BGS)
        self.current_pos = self.graph.start_node
        self.visited_nodes = {self.graph.start_node}

    @property
    def total_edges(self) -> int:
        return self.graph.total_edges()

    @property
    def drawn_count(self) -> int:
        return len(self.drawn_edges)

    @property
    def is_complete(self) -> bool:
        return self.drawn_count >= self.total_edges

    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def restart_timer(self) -> None:
        self.started_at = time.monotonic()

    def reset(self) -> None:
        self.current_pos = self.graph.start_node
        self.drawn_edges.clear()
        self.visited_nodes = {self.graph.start_node}
        self.move_history.clear()

    def move(self, direction: str) -> MoveResult:
        direction = direction.upper()
        delta = DIRECTION_DELTAS.get(direction)
        if delta is None:
            return MoveResult.NO_EDGE

        nr = self.current_pos[0] + delta[0]
        nc = self.current_pos[1] + delta[1]
        next_node = (nr, nc)

        if not self.graph.in_bounds(next_node):
            return MoveResult.OUT_OF_BOUNDS

        edge = frozenset((self.current_pos, next_node))
        if edge not in self.graph.edges:
            return MoveResult.NO_EDGE

        if edge in self.drawn_edges:
            return MoveResult.ALREADY_DRAWN

        self.drawn_edges.add(edge)
        self.current_pos = next_node
        self.visited_nodes.add(next_node)
        self.move_history.append(direction)
        return MoveResult.SUCCESS


class GameManager:
    def __init__(self):
        self._sessions: Dict[str, GameSession] = {}
        self._active_players: Set[str] = set()

    def is_in_game(self, user_id: str) -> bool:
        return user_id in self._active_players

    def create_session(
        self,
        user_id: str,
        channel_id: str,
        difficulty_name: str,
        reward: int,
        graph: Graph,
    ) -> Optional[GameSession]:
        if user_id in self._active_players:
            return None
        session = GameSession(
            user_id=user_id,
            channel_id=channel_id,
            difficulty_name=difficulty_name,
            reward=reward,
            graph=graph,
        )
        self._sessions[user_id] = session
        self._active_players.add(user_id)
        return session

    def get_session(self, user_id: str) -> Optional[GameSession]:
        return self._sessions.get(user_id)

    def end_game(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)
        self._active_players.discard(user_id)
