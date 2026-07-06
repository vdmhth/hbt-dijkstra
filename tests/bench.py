import argparse
import csv
import random
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.dijkstra import dijkstra, path_cost       
from backend.graph_loader import RoadGraph                

DEFAULT_GRAPH = PROJECT_ROOT / "data" / "hbt_drive_network.graphml"

DEFAULT_TRACE_SOURCE = 13585289797
DEFAULT_TRACE_TARGET = 13585291174
def _short(node_id) -> str:
    """Abbreviate long OSM ids the way the report does (last 3 digits)."""
    s = str(node_id)
    return "..." + s[-3:] if len(s) > 3 else s


def _random_connected_pair(adjacency, ids, rng, weight_key, min_nodes=2, tries=2000):
    """Return (s, t, result) for a random pair whose route exists and has at
    least `min_nodes` nodes on the path. Returns None if none found in `tries`."""
    for _ in range(tries):
        s, t = rng.choice(ids), rng.choice(ids)
        if s == t:
            continue
        res = dijkstra(adjacency, s, t, weight_key=weight_key, record_steps=False)
        if res.found and len(res.path) >= min_nodes:
            return s, t, res
    return None


def _fmt_table(headers, rows):
    """Render a simple monospaced table."""
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    sep = "  ".join("-" * w for w in widths)
    out = [line, sep]
    for row in rows:
        out.append("  ".join(str(c).ljust(w) for c, w in zip(row, widths)))
    return "\n".join(out)
def perf_table(graph, n_pairs, weight_key, seed, repeat):
    rng = random.Random(seed)
    ids = list(graph.node_coords.keys())
    adjacency = graph.adjacency

    # Warm up once so the first pair does not pay import / branch-prediction cost.
    _random_connected_pair(adjacency, ids, random.Random(seed), weight_key)

    runtimes, settled = [], []
    collected = 0
    while collected < n_pairs:
        s, t = rng.choice(ids), rng.choice(ids)
        if s == t:
            continue
        # time the route; take the fastest of `repeat` runs to cut OS noise
        best_ms = None
        res = None
        for _ in range(repeat):
            t0 = time.perf_counter()
            res = dijkstra(adjacency, s, t, weight_key=weight_key, record_steps=False)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            best_ms = dt_ms if best_ms is None else min(best_ms, dt_ms)
        if not res.found:
            continue
        runtimes.append(best_ms)
        settled.append(res.visited_count)
        collected += 1

    def stats(xs):
        return statistics.mean(xs), statistics.median(xs), max(xs)

    r_mean, r_med, r_max = stats(runtimes)
    s_mean, s_med, s_max = stats(settled)

    rows = [
        ["Runtime (ms)", f"{r_mean:.2f}", f"{r_med:.2f}", f"{r_max:.2f}"],
        ["Settled nodes", f"{s_mean:.0f}", f"{s_med:.0f}", f"{s_max:.0f}"],
    ]
    print(f"Table 6.1 - Performance of the self-implemented Dijkstra")
    print(f"(weight = {weight_key}, {n_pairs} random connected pairs, "
          f"step recording disabled, seed = {seed}, repeat = {repeat})\n")
    print(_fmt_table(["Metric", "Mean", "Median", "Max"], rows))
    return rows
def compare_table(graph, n_pairs, seed, min_nodes):
    rng = random.Random(seed + 1)  # offset so it does not echo the perf pairs
    ids = list(graph.node_coords.keys())
    adjacency = graph.adjacency

    rows = []
    n = 0
    guard = 0
    while n < n_pairs and guard < 100000:
        guard += 1
        s, t = rng.choice(ids), rng.choice(ids)
        if s == t:
            continue
        r_len = dijkstra(adjacency, s, t, weight_key="length", record_steps=False)
        if not r_len.found or len(r_len.path) < min_nodes:
            continue
        r_time = dijkstra(adjacency, s, t, weight_key="travel_time", record_steps=False)
        if not r_time.found:
            continue

        len_dist = path_cost(adjacency, r_len.path, "length")
        len_time = path_cost(adjacency, r_len.path, "travel_time")
        tim_dist = path_cost(adjacency, r_time.path, "length")
        tim_time = path_cost(adjacency, r_time.path, "travel_time")

        differ = "DIFF" if r_len.path != r_time.path else "SAME"
        n += 1
        rows.append([
            n,
            f"{len_dist:.0f}", f"{len_time:.0f}",
            f"{tim_dist:.0f}", f"{tim_time:.0f}",
            differ,
            str(s), str(t),
        ])

    print(f"Table 6.2 - Shortest (length) vs Fastest (travel_time) routing")
    print(f"({n_pairs} representative pairs, min {min_nodes} nodes on path, "
          f"seed = {seed})\n")
    headers = ["#", "length:dist(m)", "length:time(s)",
               "time:dist(m)", "time:time(s)", "Differ?", "source", "target"]
    print(_fmt_table(headers, rows))
    return headers, rows
def trace_table(graph, source, target, max_steps_shown):
    adjacency = graph.adjacency
    res = dijkstra(adjacency, source, target, weight_key="length", record_steps=True)

    if not res.found:
        print(f"Table 6.3 - Worked example: NO PATH between {source} and {target}.")
        return None

    total_len = path_cost(adjacency, res.path, "length")
    print("Table 6.3 - Real trace taken from the system's step log")
    print(f"(source {source} -> target {target})\n")
    print(f"summary: total {total_len:.1f} m, {len(res.path)} nodes on the path, "
          f"{res.visited_count} nodes settled in {len(res.steps)} steps\n")

    shown = res.steps[:max_steps_shown]
    for i, step in enumerate(shown):
        n_scanned = len(step.relaxed_edges)
        edge_word = "edge" if n_scanned == 1 else "edges"
        updates = [
            f"{_short(rd.to)}={rd.candidate_dist:.1f}"
            for rd in step.relax_details if rd.improved
        ]
        upd = " ; ".join(updates) if updates else "(no improvement)"
        label = "settle source" if i == 0 else f"settle {_short(step.current)}"
        print(f"step{i}: {label} (d={step.dist_current:.1f}) "
              f"scan {n_scanned} {edge_word} -> {upd}")

    if len(res.steps) > max_steps_shown:
        print("... (each step pops the node with the smallest tentative distance)")
    return res
def _dump_csv(out_dir, perf_rows, compare_pack, trace_res):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "table_6_1_performance.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Mean", "Median", "Max"])
        w.writerows(perf_rows)

    headers, rows = compare_pack
    with (out_dir / "table_6_2_shortest_vs_fastest.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)

    if trace_res is not None:
        with (out_dir / "table_6_3_trace.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["step", "settle_node", "dist", "edges_scanned",
                        "to", "weight", "candidate_dist", "improved"])
            for i, step in enumerate(trace_res.steps):
                if not step.relax_details:
                    w.writerow([i, step.current, f"{step.dist_current:.3f}",
                                len(step.relaxed_edges), "", "", "", ""])
                for rd in step.relax_details:
                    w.writerow([i, step.current, f"{step.dist_current:.3f}",
                                len(step.relaxed_edges), rd.to,
                                f"{rd.weight:.3f}", f"{rd.candidate_dist:.3f}",
                                rd.improved])
    print(f"\nCSV written to {out_dir}/")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Chapter 6 evaluation harness.")
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH),
                    help="Path to the GraphML file.")
    ap.add_argument("--seed", type=int, default=0, help="Random seed.")

    ap.add_argument("--perf-pairs", type=int, default=200,
                    help="Number of random pairs for Table 6.1.")
    ap.add_argument("--perf-weight", default="length",
                    choices=["length", "travel_time"],
                    help="Weight optimised in the performance test.")
    ap.add_argument("--repeat", type=int, default=1,
                    help="Timed runs per pair; the fastest is kept.")

    ap.add_argument("--compare-pairs", type=int, default=6,
                    help="Number of pairs for Table 6.2.")
    ap.add_argument("--compare-min-nodes", type=int, default=8,
                    help="Skip trivial routes shorter than this for Table 6.2.")

    ap.add_argument("--trace-source", type=int, default=DEFAULT_TRACE_SOURCE)
    ap.add_argument("--trace-target", type=int, default=DEFAULT_TRACE_TARGET)
    ap.add_argument("--trace-steps", type=int, default=8,
                    help="How many leading steps to print for Table 6.3.")

    ap.add_argument("--csv", default=None,
                    help="Optional directory to also dump the tables as CSV.")
    ap.add_argument("--skip", nargs="*", default=[],
                    choices=["perf", "compare", "trace"],
                    help="Tables to skip.")
    args = ap.parse_args()

    print(f"Loading graph: {args.graph}")
    graph = RoadGraph.from_graphml(args.graph)
    print(f"Loaded: {graph.num_nodes()} nodes, {graph.num_edges()} directed edges\n")

    perf_rows = compare_pack = trace_res = None

    if "perf" not in args.skip:
        perf_rows = perf_table(graph, args.perf_pairs, args.perf_weight,
                               args.seed, args.repeat)
        print()

    if "compare" not in args.skip:
        compare_pack = compare_table(graph, args.compare_pairs, args.seed,
                                     args.compare_min_nodes)
        print()

    if "trace" not in args.skip:
        trace_res = trace_table(graph, args.trace_source, args.trace_target,
                                args.trace_steps)
        print()

    if args.csv:
        _dump_csv(args.csv,
                  perf_rows or [],
                  compare_pack or (["#"], []),
                  trace_res)


if __name__ == "__main__":
    main()