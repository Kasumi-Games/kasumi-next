from __future__ import annotations

import math
from typing import Dict, List, Set
from collections import defaultdict

from .models import Edge, Graph, Node

DECAY_DELAY_BY_SCALE = {
    3: 3,
    4: 6.5,
    5: 10.5,
}
DECAY_TAU_BY_SCALE = {
    3: 7.21,
    4: 14.42,
    5: 28.84,
}
DEFAULT_DECAY_DELAY_SECONDS = 6.5
DEFAULT_DECAY_TAU_SECONDS = 14.42


def _build_adj(graph: Graph) -> Dict[Node, Set[Node]]:
    adj: Dict[Node, Set[Node]] = defaultdict(set)
    for edge in graph.edges:
        a, b = tuple(edge)
        adj[a].add(b)
        adj[b].add(a)
    return dict(adj)


def _odd_vertices(graph: Graph) -> List[Node]:
    adj = _build_adj(graph)
    return [node for node in graph.nodes if len(adj.get(node, set())) % 2 == 1]


def _find_euler_trail(graph: Graph) -> List[Node]:
    adj = _build_adj(graph)
    odd = _odd_vertices(graph)
    start = graph.start_node
    if len(odd) == 2 and start not in odd:
        start = odd[0]

    stack = [start]
    path: List[Node] = []

    while stack:
        v = stack[-1]
        if adj.get(v):
            u = next(iter(adj[v]))
            adj[v].remove(u)
            adj[u].remove(v)
            stack.append(u)
        else:
            path.append(stack.pop())
    path.reverse()
    return path


def compute_branching_factor(graph: Graph) -> float:
    trail = _find_euler_trail(graph)
    if len(trail) <= 1:
        return 0.0

    remaining: Set[Edge] = set(graph.edges)
    total_choices = 0.0
    step_count = 0
    for i in range(len(trail) - 1):
        cur = trail[i]
        next_node = trail[i + 1]
        choices = 0
        for neighbor in _build_adj(graph).get(cur, set()):
            if frozenset((cur, neighbor)) in remaining:
                choices += 1
        total_choices += max(choices, 1)
        step_count += 1
        remaining.discard(frozenset((cur, next_node)))

    avg_choices = total_choices / max(step_count, 1)
    return 1.0 / max(avg_choices, 1.0)


def compute_bridge_ratio(graph: Graph) -> float:
    adj = _build_adj(graph)
    if not graph.nodes:
        return 0.0

    timer = 0
    tin: Dict[Node, int] = {}
    low: Dict[Node, int] = {}
    bridges = 0

    def dfs(v: Node, parent: Node | None) -> None:
        nonlocal timer, bridges
        timer += 1
        tin[v] = timer
        low[v] = timer
        for to in adj.get(v, set()):
            if to == parent:
                continue
            if to in tin:
                low[v] = min(low[v], tin[to])
            else:
                dfs(to, v)
                low[v] = min(low[v], low[to])
                if low[to] > tin[v]:
                    bridges += 1

    start = next(iter(graph.nodes))
    dfs(start, None)
    return bridges / max(len(graph.edges), 1)


def compute_odd_vertex_distance(graph: Graph) -> float:
    odd = _odd_vertices(graph)
    if len(odd) != 2:
        return 0.0
    (r1, c1), (r2, c2) = odd
    dist = abs(r1 - r2) + abs(c1 - c2)
    max_dist = graph.rows + graph.cols - 2
    return dist / max(max_dist, 1)


def compute_visual_density(graph: Graph) -> float:
    adj = _build_adj(graph)
    if not graph.nodes:
        return 0.0
    degrees = [len(adj.get(node, set())) for node in graph.nodes]
    avg_degree = sum(degrees) / len(degrees)
    max_degree = max(degrees)
    return max_degree / 4.0 + avg_degree / 4.0


def calculate_reward(graph: Graph) -> int:
    base = len(graph.edges)
    branch_score = compute_branching_factor(graph)
    trap_score = compute_bridge_ratio(graph)
    position_score = compute_odd_vertex_distance(graph)
    density_score = compute_visual_density(graph)

    score = (
        base**2 / 300
        + branch_score * 1.5
        + trap_score * 6
        + position_score * 4
        + density_score * 1
    )
    return max(1, int(score))


def calculate_time_decay_factor(
    elapsed_seconds: float,
    delay_seconds: float = DEFAULT_DECAY_DELAY_SECONDS,
    tau_seconds: float = DEFAULT_DECAY_TAU_SECONDS,
) -> float:
    if tau_seconds <= 0:
        return 0.0
    effective_elapsed = max(0.0, elapsed_seconds - delay_seconds)
    return math.exp(-effective_elapsed / tau_seconds)


def apply_time_decay(
    base_reward: int,
    elapsed_seconds: float,
    graph: Graph | None = None,
    delay_seconds: float | None = None,
    tau_seconds: float | None = None,
) -> int:
    if graph is not None:
        scale = max(graph.rows, graph.cols)
        resolved_delay = DECAY_DELAY_BY_SCALE.get(scale, DEFAULT_DECAY_DELAY_SECONDS)
        resolved_tau = DECAY_TAU_BY_SCALE.get(scale, DEFAULT_DECAY_TAU_SECONDS)
    else:
        resolved_delay = DEFAULT_DECAY_DELAY_SECONDS
        resolved_tau = DEFAULT_DECAY_TAU_SECONDS
    if delay_seconds is not None:
        resolved_delay = delay_seconds
    if tau_seconds is not None:
        resolved_tau = tau_seconds

    factor = calculate_time_decay_factor(
        elapsed_seconds=elapsed_seconds,
        delay_seconds=resolved_delay,
        tau_seconds=resolved_tau,
    )
    return max(0, int(round(base_reward * factor)))
