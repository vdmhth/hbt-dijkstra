from .dijkstra import dijkstra_multi_source
from .nearest import haversine_m, nearest_node

def _same_pt(a, b, eps=1e-7):
    return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps
def _branch_coords(adjacency, node_coords, chain):
    coords = []
    for u, v in zip(chain, chain[1:]):
        best = None
        for e in adjacency.get(u, []): # handle MultiDiGraph
            if e["to"] == v and (best is None or e["length"] < best["length"]):
                best = e
        seg = None
        if best is not None and best.get("geometry_coords"):
            seg = [list(p) for p in best["geometry_coords"]]# check for orientation 
            a = node_coords.get(u)
            if a is not None and len(seg) >= 2:
                d0 = haversine_m(seg[0][0], seg[0][1], a[0], a[1])
                d1 = haversine_m(seg[-1][0], seg[-1][1], a[0], a[1])
                if d0 > d1:
                    seg.reverse()
        else:
            cu, cv = node_coords.get(u), node_coords.get(v)
            if cu is not None and cv is not None:
                seg = [list(cu), list(cv)]  # fallback to straight line
        if not seg:
            continue
        if not coords:
            coords.extend(seg) 
        elif _same_pt(coords[-1], seg[0]):
            coords.extend(seg[1:])
        else:
            coords.extend(seg)
    return coords


def _along_map(node_coords, path):
    along, acc, prev_c = {}, 0.0, None
    for n in path:
        c = node_coords.get(n)
        if c is None:
            continue
        if prev_c is not None:
            acc += haversine_m(prev_c[0], prev_c[1], c[0], c[1])
        along[n] = acc
        prev_c = c
    return along


def pois_along_route(graph, places, path, poi_type=None, max_detour_m=200.0):
    adjacency = graph.adjacency
    node_coords = graph.node_coords

    sources = [n for n in path if n in adjacency]
    if not sources:
        return []

    dist, prev, root = dijkstra_multi_source(
        adjacency, sources, weight_key="length", max_dist=max_detour_m
    )
    along = _along_map(node_coords, [n for n in path if n in node_coords])

    hits = []
    for p in places:
        if poi_type and p.get("type") != poi_type:
            continue
        lat, lon = p.get("lat"), p.get("lon")
        if lat is None or lon is None:
            continue

        poi_node = nearest_node(node_coords, lat, lon)
        detour = dist.get(poi_node)
        if detour is None or detour > max_detour_m:
            continue
        chain, cur = [poi_node], poi_node
        while cur in prev:
            cur = prev[cur]
            chain.append(cur)
        chain.reverse()
        turn_in = _branch_coords(adjacency, node_coords, chain)

        attach = root.get(poi_node, poi_node)
        attach_c = node_coords.get(attach, (lat, lon))

        hits.append(
            {
                "name": p.get("name", ""),
                "type": p.get("type", ""),
                "lat": float(lat),
                "lon": float(lon),
                "detour_m": float(detour),
                "along_m": float(along.get(attach, 0.0)),
                "attach_lat": float(attach_c[0]),
                "attach_lon": float(attach_c[1]),
                "turn_in": turn_in,
            }
        )

    hits.sort(key=lambda h: h["along_m"]) 
    return hits