from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass
from typing import Dict, FrozenSet, Set, Tuple

from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Node = Tuple[int, int]
Edge = FrozenSet[Node]
Base = declarative_base()


class MoveResult(StrEnum):
    SUCCESS = "success"
    NO_EDGE = "no_edge"
    ALREADY_DRAWN = "already_drawn"
    OUT_OF_BOUNDS = "out_of_bounds"


@dataclass
class Graph:
    rows: int
    cols: int
    nodes: Set[Node]
    edges: Set[Edge]
    start_node: Node

    def in_bounds(self, node: Node) -> bool:
        r, c = node
        return 0 <= r < self.rows and 0 <= c < self.cols

    def has_node(self, node: Node) -> bool:
        return node in self.nodes

    def has_edge(self, a: Node, b: Node) -> bool:
        return frozenset((a, b)) in self.edges

    def total_edges(self) -> int:
        return len(self.edges)

    def adjacency(self) -> Dict[Node, Set[Node]]:
        graph: Dict[Node, Set[Node]] = {node: set() for node in self.nodes}
        for edge in self.edges:
            a, b = tuple(edge)
            graph[a].add(b)
            graph[b].add(a)
        return graph


class OneStrokeGame(Base):
    __tablename__ = "one_stroke_games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    elapsed_seconds = Column(Float, nullable=False)
    reward = Column(Integer, nullable=False)
    base_reward = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=False)
