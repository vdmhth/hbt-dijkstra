from pathlib import Path
from collections import Counter
import networkx as nx
ROOT_DIR = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT_DIR / "data" / "hbt_drive_network.graphml"
def main():
    if not GRAPH_PATH.exists():
        raise FileNotFoundError(f"GraphML file not found: {GRAPH_PATH}")

    G = nx.read_graphml(GRAPH_PATH)

    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()

    is_directed = G.is_directed()
    is_multigraph = G.is_multigraph()

    directed_pairs = set()
    reciprocal_edge_entries = 0
    one_way_edge_entries = 0

    if is_multigraph:
        edge_iter = G.edges(keys=True, data=True)
        for u, v, key, data in edge_iter:
            directed_pairs.add((u, v))
            if G.has_edge(v, u):
                reciprocal_edge_entries += 1
            else:
                one_way_edge_entries += 1
    else:
        edge_iter = G.edges(data=True)
        for u, v, data in edge_iter:
            directed_pairs.add((u, v))
            if G.has_edge(v, u):
                reciprocal_edge_entries += 1
            else:
                one_way_edge_entries += 1

    reciprocal_directed_pairs = sum(
        1 for u, v in directed_pairs if (v, u) in directed_pairs
    )
    one_way_directed_pairs = sum(
        1 for u, v in directed_pairs if (v, u) not in directed_pairs
    )

    edge_weights = set()
    missing_length = 0
    missing_travel_time = 0
    oneway_attr_counter = Counter()

    if is_multigraph:
        edges_data = (data for _, _, _, data in G.edges(keys=True, data=True))
    else:
        edges_data = (data for _, _, data in G.edges(data=True))

    for data in edges_data:
        if "length" in data:
            edge_weights.add("length")
        else:
            missing_length += 1

        if "travel_time" in data:
            edge_weights.add("travel_time")
        else:
            missing_travel_time += 1

        oneway_attr_counter[str(data.get("oneway"))] += 1

    graph_type = []
    graph_type.append("Directed" if is_directed else "Undirected")
    graph_type.append("weighted")
    graph_type.append("MultiDiGraph" if is_multigraph else type(G).__name__)

    print("=== Graph Statistics ===")
    print(f"Graph file: {GRAPH_PATH.name}")
    print(f"Number of nodes: {num_nodes}")
    print(f"Number of directed edges: {num_edges}")
    print(f"Reciprocal directed edges: {reciprocal_edge_entries}")
    print(f"One-way directed edges: {one_way_edge_entries}")
    print(f"Reciprocal unique directed pairs: {reciprocal_directed_pairs}")
    print(f"One-way unique directed pairs: {one_way_directed_pairs}")
    print(f"Graph type: {' '.join(graph_type)}")
    print(f"Edge weights found: {', '.join(sorted(edge_weights))}")
    print(f"Missing length: {missing_length}")
    print(f"Missing travel_time: {missing_travel_time}")
    print(f"Oneway attribute count: {dict(oneway_attr_counter)}")

    if num_edges > 0:
        print(
            f"One-way ratio by edge entries: "
            f"{one_way_edge_entries / num_edges * 100:.2f}%"
        )
        print(
            f"One-way ratio by unique directed pairs: "
            f"{one_way_directed_pairs / len(directed_pairs) * 100:.2f}%"
        )


if __name__ == "__main__":
    main()