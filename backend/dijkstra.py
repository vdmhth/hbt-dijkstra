import heapq
from dataclasses import dataclass, field
from typing import Any, Optional
@dataclass
class RelaxedEdge:
    to: Any
    weight: float
    candidate_dist: float
    improved: bool
@dataclass
class FrontierEntry:
    node: Any
    dist: float
@dataclass
class Step:
    current: Any
    settled: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    relaxed_edges: list = field(default_factory=list)
    relax_details: list = field(default_factory=list)
    frontier_preview: list = field(default_factory=list)
    dist_current: float = 0.0
    frontier_size: int = 0
@dataclass
class DijkstraResult:
    found: bool
    path: list
    total_cost: float
    steps: list
    visited_count: int
def _frontier_preview(pq, settled_set, dist, limit=5, scan=20):
    seen = set()
    preview = []
    for d, node in heapq.nsmallest(scan, pq):
        if node in settled_set or node in seen:
            continue
        seen.add(node)
        preview.append(FrontierEntry(node=node, dist=dist.get(node, d)))
        if len(preview) >= limit:
            break
    return preview
def dijkstra(adjacency: dict, source: Any, target: Any, weight_key: str = "length", record_steps: bool = True, max_steps: Optional[int] = None) -> DijkstraResult:
    dist = {source: 0.0}
    prev = {}
    settled_set = set()
    steps = []
    pq = [(0.0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if u in settled_set:
            continue
        settled_set.add(u)
        relaxed_edges = []
        relax_details = []
        updated = []
        for edge in adjacency.get(u, ()):
            v = edge["to"]
            w = float(edge[weight_key])
            relaxed_edges.append((u, v))
            candidate_dist = d + w
            improved = v not in dist or candidate_dist < dist[v]
            relax_details.append(RelaxedEdge(to=v, weight=w, candidate_dist=candidate_dist, improved=improved))
            if improved:
                dist[v] = candidate_dist
                prev[v] = u
                heapq.heappush(pq, (candidate_dist, v))
                updated.append(v)
        if record_steps and (max_steps is None or len(steps) < max_steps):
            steps.append(
                Step(
                    current=u,
                    settled=[u],
                    updated=updated,
                    relaxed_edges=relaxed_edges,
                    relax_details=relax_details,
                    frontier_preview=_frontier_preview(pq, settled_set, dist),
                    dist_current=d,
                    frontier_size=len(pq),
                )
            )
        if u == target:
            break
    if target not in dist:
        return DijkstraResult(
            found=False,
            path=[],
            total_cost=float("inf"),
            steps=steps,
            visited_count=len(settled_set),
        )
    path = _reconstruct_path(prev, source, target)
    return DijkstraResult(
        found=True,
        path=path,
        total_cost=dist[target],
        steps=steps,
        visited_count=len(settled_set),
    )
def _reconstruct_path(prev: dict, source: Any, target: Any) -> list:
    path = [target]
    node = target
    while node != source:
        node = prev[node]
        path.append(node)
    path.reverse()
    return path


def path_cost(adjacency: dict, path: list, weight_key: str = "weight") -> float:
    total = 0.0
    for u, v in zip(path, path[1:]):
        best = None
        for edge in adjacency.get(u, ()):
            if edge['to'] == v:
                value = float(edge[weight_key])
                if best is None or value < best:
                    best = value
        if best is None:
            raise ValueError(f"Does not exists edge {u}->{v} in the graph")
        total += best
    return total
def dijkstra_multi_source(adjacency: dict, sources, weight_key: str = "length", max_dist=None):
    dist, prev, root = {}, {}, {}
    pq = []
    for s in sources:
        if s in dist:
            continue
        dist[s] = 0.0
        root[s] = s
        heapq.heappush(pq, (0.0, s))
    settled = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in settled:
            continue
        if max_dist is not None and d > max_dist:
            break 
        settled.add(u)
        for edge in adjacency.get(u, ()):
            v = edge["to"]
            nd = d + float(edge[weight_key])
            if max_dist is not None and nd > max_dist:
                continue
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                root[v] = root[u]
                heapq.heappush(pq, (nd, v))
    return dist, prev, root
def dijkstra_nearest(adjacency: dict, source: Any, targets, weight_key: str = "length",
                     record_steps: bool = True, max_steps: Optional[int] = None):
    target_set = set(targets)
    dist = {source: 0.0}
    prev = {}
    settled_set = set()
    steps = []
    pq = [(0.0, source)]
    reached = None
    while pq:
        d, u = heapq.heappop(pq)
        if u in settled_set:
            continue
        settled_set.add(u)
        relaxed_edges = []
        relax_details = []
        updated = []
        for edge in adjacency.get(u, ()):
            v = edge["to"]
            w = float(edge[weight_key])
            relaxed_edges.append((u, v))
            candidate_dist = d + w
            improved = v not in dist or candidate_dist < dist[v]
            relax_details.append(RelaxedEdge(to=v, weight=w, candidate_dist=candidate_dist, improved=improved))
            if improved:
                dist[v] = candidate_dist
                prev[v] = u
                heapq.heappush(pq, (candidate_dist, v))
                updated.append(v)
        if record_steps and (max_steps is None or len(steps) < max_steps):
            steps.append(
                Step(
                    current=u,
                    settled=[u],
                    updated=updated,
                    relaxed_edges=relaxed_edges,
                    relax_details=relax_details,
                    frontier_preview=_frontier_preview(pq, settled_set, dist),
                    dist_current=d,
                    frontier_size=len(pq),
                )
            )
        if u in target_set:
            reached = u
            break
    if reached is None:
        return DijkstraResult(False, [], float("inf"), steps, len(settled_set)), None
    path = _reconstruct_path(prev, source, reached)
    return DijkstraResult(True, path, dist[reached], steps, len(settled_set)), reached