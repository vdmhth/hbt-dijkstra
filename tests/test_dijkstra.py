import random
import sys
from pathlib import Path

import networkx as nx
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from backend.dijkstra import dijkstra, path_cost          
from backend.graph_loader import RoadGraph                  
from backend.nearest import nearest_node                    


def adjacency_to_digraph(adj, weight_key):
    """Build a DiGraph for checking expected shortest-path costs."""
    DG = nx.DiGraph()
    DG.add_nodes_from(adj.keys())
    for u, edges in adj.items():
        for e in edges:
            v, w = e["to"], float(e[weight_key])
            if not DG.has_edge(u, v) or w < DG[u][v]["w"]:
                DG.add_edge(u, v, w=w)
    return DG


@pytest.fixture(scope="module")
def graph():
    path = PROJECT_ROOT / "data" / "hbt_drive_network.graphml"
    return RoadGraph.from_graphml(path)


@pytest.mark.parametrize("weight_key", ["length", "travel_time"])
def test_matches_networkx_on_random_pairs(graph, weight_key):
    DG = adjacency_to_digraph(graph.adjacency, weight_key)
    nodes = list(graph.node_coords.keys())
    rng = random.Random(42)

    checked = 0
    for _ in range(60):
        s, t = rng.choice(nodes), rng.choice(nodes)
        if s == t:
            continue
        res = dijkstra(graph.adjacency, s, t, weight_key=weight_key)
        has_nx_path = nx.has_path(DG, s, t)
        assert res.found == has_nx_path
        if res.found:
            nx_cost = nx.shortest_path_length(DG, s, t, weight="w")
            assert res.total_cost == pytest.approx(nx_cost, abs=1e-6)
            assert res.path[0] == s and res.path[-1] == t
            assert path_cost(graph.adjacency, res.path, weight_key) == pytest.approx(res.total_cost, abs=1e-6)
            checked += 1
    assert checked > 0


def test_no_path_returns_not_found():
    adj = {1: [], 2: []}
    res = dijkstra(adj, 1, 2, weight_key="length")
    assert res.found is False
    assert res.path == []
    assert res.total_cost == float("inf")


def test_trivial_known_graph():
    adj = {
        1: [{"to": 2, "length": 2}, {"to": 3, "length": 10}],
        2: [{"to": 3, "length": 3}],
        3: [],
    }
    res = dijkstra(adj, 1, 3, weight_key="length")
    assert res.found
    assert res.path == [1, 2, 3]
    assert res.total_cost == pytest.approx(5.0)


def test_respects_one_way(graph):
    one_way_pairs = []
    for u, edges in graph.adjacency.items():
        for e in edges:
            if str(e.get("oneway")).lower() in ("true", "1"):
                one_way_pairs.append((u, e["to"]))
    if not one_way_pairs:
        pytest.skip("The graph has no one-way edges to test.")
    u, v = one_way_pairs[0]
    back = any(e["to"] == u for e in graph.adjacency.get(v, []))
    assert not back


def test_nearest_node_snaps(graph):
    nid = nearest_node(graph.node_coords, graph.center()[0], graph.center()[1])
    assert nid in graph.node_coords
