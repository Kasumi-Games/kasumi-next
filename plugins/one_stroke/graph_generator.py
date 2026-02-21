from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List

from .models import Edge, Graph, Node


@dataclass(frozen=True)
class DifficultyConfig:
    key: str
    label: str
    rows: int
    cols: int
    min_edges: int
    max_edges: int


DIFFICULTY_CONFIGS = {
    "easy": DifficultyConfig("easy", "简单", 3, 3, 8, 11),
    "normal": DifficultyConfig("normal", "普通", 4, 4, 18, 23),
    "hard": DifficultyConfig("hard", "困难", 5, 5, 28, 36),
}

DIFFICULTY_ALIASES = {
    "简单": "easy",
    "easy": "easy",
    "e": "easy",
    "ez": "easy",
    "普通": "normal",
    "normal": "normal",
    "nm": "normal",
    "n": "normal",
    "困难": "hard",
    "hard": "hard",
    "hd": "hard",
}


def parse_difficulty(text: str | None) -> DifficultyConfig:
    if not text:
        return DIFFICULTY_CONFIGS["normal"]
    key = DIFFICULTY_ALIASES.get(text.strip().lower(), "normal")
    return DIFFICULTY_CONFIGS[key]


def _neighbors(node: Node, rows: int, cols: int) -> Iterable[Node]:
    r, c = node
    deltas = ((-1, 0), (1, 0), (0, -1), (0, 1))
    for dr, dc in deltas:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            yield (nr, nc)


def _edge(a: Node, b: Node) -> Edge:
    return frozenset((a, b))


def _frontier_score(node: Node, edges: set[Edge], rows: int, cols: int) -> int:
    """Higher score means this node can still expand to more unused edges."""
    score = 0
    for nxt in _neighbors(node, rows, cols):
        if _edge(node, nxt) not in edges:
            score += 1
    return score


def generate_graph(config: DifficultyConfig, max_retries: int = 100) -> Graph:
    for _ in range(max_retries):
        start = (random.randint(0, config.rows - 1), random.randint(0, config.cols - 1))
        current = start
        nodes = {start}
        edges: set[Edge] = set()
        target_edges = random.randint(config.min_edges, config.max_edges)

        for _ in range(target_edges):
            candidates: List[Node] = []
            for nxt in _neighbors(current, config.rows, config.cols):
                if _edge(current, nxt) not in edges:
                    candidates.append(nxt)

            if not candidates:
                break

            # Prefer neighbors that keep more future options, to avoid sparse clumping.
            weighted: List[tuple[Node, int]] = []
            for nxt in candidates:
                weight = max(1, _frontier_score(nxt, edges, config.rows, config.cols))
                weighted.append((nxt, weight))

            total = sum(weight for _, weight in weighted)
            pick = random.randint(1, total)
            acc = 0
            nxt = weighted[0][0]
            for node, weight in weighted:
                acc += weight
                if pick <= acc:
                    nxt = node
                    break

            edges.add(_edge(current, nxt))
            nodes.add(nxt)
            current = nxt

        if len(edges) >= config.min_edges:
            return Graph(
                rows=config.rows,
                cols=config.cols,
                nodes=nodes,
                edges=edges,
                start_node=start,
            )

    raise RuntimeError("无法生成满足条件的一笔画图，请重试")
