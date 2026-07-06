
import math

from .nearest import nearest_node_with_distance

EARTH_RADIUS_M = 6371000.0

VERTEX_SNAP_EPS_M = 3.0

def _local_xy(lat, lon, lat0, lon0):
    x = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_RADIUS_M
    return x, y


def _xy_to_latlon(x, y, lat0, lon0):
    lat = lat0 + math.degrees(y / EARTH_RADIUS_M)
    lon = lon0 + math.degrees(x / (EARTH_RADIUS_M * math.cos(math.radians(lat0))))
    return lat, lon


def _project_to_segment(p_lat, p_lon, a_lat, a_lon, b_lat, b_lon): # take origin at a a(0,0)
    bx, by = _local_xy(b_lat, b_lon, a_lat, a_lon)
    px, py = _local_xy(p_lat, p_lon, a_lat, a_lon)
    ab_len2 = bx * bx + by * by

    if ab_len2 == 0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, (px * bx + py * by) / ab_len2)) # project p onto ab, then clamp to [0,1]
    projx, projy = t * bx, t * by
    dist = math.hypot(px - projx, py - projy)
    proj_lat, proj_lon = _xy_to_latlon(projx, projy, a_lat, a_lon)
    return t, proj_lat, proj_lon, dist

def _distance_m(a, b): 
    return math.hypot(*_local_xy(b[0], b[1], a[0], a[1]))


def _orient_geometry(coords, start_coord, end_coord): # check orientation
    if not coords or len(coords) < 2:
        return [list(start_coord), list(end_coord)]

    coords = [list(c) for c in coords]

    forward_score = _distance_m(coords[0], start_coord) + _distance_m(
        coords[-1], end_coord
    )
    reverse_score = _distance_m(coords[-1], start_coord) + _distance_m(
        coords[0], end_coord
    )

    if reverse_score < forward_score:
        coords.reverse()

    return coords


def _edge_geometry(edge, start_coord, end_coord):
    geometry = edge.get("geometry_coords")
    if geometry and len(geometry) >= 2:
        return _orient_geometry(geometry, start_coord, end_coord)
    return [list(start_coord), list(end_coord)]


def _polyline_length_m(coords):
    total = 0.0
    for a, b in zip(coords, coords[1:]):
        total += _distance_m(a, b)
    return total


def _project_to_polyline(p_lat, p_lon, coords): # find the projection along polyline
    if not coords:
        return 0.0, p_lat, p_lon, float("inf")

    if len(coords) == 1:
        return 0.0, coords[0][0], coords[0][1], _distance_m(
            [p_lat, p_lon], coords[0]
        )

    segment_lengths = []
    total_length = 0.0

    for a, b in zip(coords, coords[1:]):
        length = _distance_m(a, b)
        segment_lengths.append(length)
        total_length += length

    best = None
    acc = 0.0

    for i, (a, b) in enumerate(zip(coords, coords[1:])):
        seg_len = segment_lengths[i]
        local_t, proj_lat, proj_lon, dist = _project_to_segment(
            p_lat, p_lon, a[0], a[1], b[0], b[1]
        )
        along = acc + local_t * seg_len
        global_t = 0.0 if total_length <= 0 else along / total_length

        if best is None or dist < best[3]:
            best = (global_t, proj_lat, proj_lon, dist)

        acc += seg_len

    return best
def _nearest_edge_match(adjacency, node_coords, lat, lon): 
    best = None
    for u, edges in adjacency.items():
        start_coord = node_coords.get(u)
        if start_coord is None:
            continue
        for edge in edges:
            v = edge["to"]
            end_coord = node_coords.get(v)
            if end_coord is None:
                continue
            geometry = _edge_geometry(edge, start_coord, end_coord)
            t, proj_lat, proj_lon, dist = _project_to_polyline(lat, lon, geometry)

            if best is None or dist < best["distance_m"]:
                best = {
                    "u": u,
                    "v": v,
                    "edge": edge,
                    "t": t,
                    "lat": proj_lat,
                    "lon": proj_lon,
                    "distance_m": dist,
                    "edge_length": float(
                        edge.get("length", _polyline_length_m(geometry))
                    ),
                    "geometry_coords": geometry,
                }
    return best
def resolve_routing_point(adjacency, node_coords, lat, lon):
    match = _nearest_edge_match(adjacency, node_coords, lat, lon)

    if match is None:
        node_id, dist = nearest_node_with_distance(node_coords, lat, lon)
        n_lat, n_lon = node_coords[node_id]

        return {
            "kind": "vertex",
            "node": node_id,
            "lat": n_lat,
            "lon": n_lon,
            "distance_m": dist,
        }

    u = match["u"]
    v = match["v"]
    t = match["t"]
    edge_length = match["edge_length"]

    dist_to_u = t * edge_length
    dist_to_v = (1.0 - t) * edge_length

    if dist_to_u <= VERTEX_SNAP_EPS_M:
        lat_u, lon_u = node_coords[u]

        return {
            "kind": "vertex",
            "node": u,
            "lat": lat_u,
            "lon": lon_u,
            "distance_m": match["distance_m"],
        }

    if dist_to_v <= VERTEX_SNAP_EPS_M:
        lat_v, lon_v = node_coords[v]

        return {
            "kind": "vertex",
            "node": v,
            "lat": lat_v,
            "lon": lon_v,
            "distance_m": match["distance_m"],
        }

    return {
        "kind": "edge",
        "u": u,
        "v": v,
        "edge": match["edge"],
        "t": t,
        "lat": match["lat"],
        "lon": match["lon"],
        "distance_m": match["distance_m"],
        "geometry_coords": match["geometry_coords"],
    }


def _interpolate_point(a, b, ratio):
    return [
        a[0] + (b[0] - a[0]) * ratio,
        a[1] + (b[1] - a[1]) * ratio,
    ]


def _split_geometry(coords, t): # u->v => u->virtual, virtual->v
    if not coords or len(coords) < 2:
        return None, None

    coords = [list(c) for c in coords]
    t = max(0.0, min(1.0, t))

    segment_lengths = []
    total = 0.0

    for a, b in zip(coords, coords[1:]):
        length = _distance_m(a, b)
        segment_lengths.append(length)
        total += length

    if total <= 0:
        return [coords[0]], [coords[-1]]

    target = total * t
    acc = 0.0

    for i, seg_len in enumerate(segment_lengths):
        a = coords[i]
        b = coords[i + 1]

        if acc + seg_len >= target:
            ratio = 0.0 if seg_len == 0 else (target - acc) / seg_len
            split_point = _interpolate_point(a, b, ratio)

            head = coords[: i + 1] + [split_point]
            tail = [split_point] + coords[i + 1 :]
            return head, tail

        acc += seg_len

    return coords[:], [coords[-1]]


def _split_edge(edge, t_from_origin, geometry_coords=None): #split attributes
    t_from_origin = max(0.0, min(1.0, t_from_origin))

    head = dict(edge)
    tail = dict(edge)

    head["length"] = float(edge["length"]) * t_from_origin
    tail["length"] = float(edge["length"]) * (1.0 - t_from_origin)

    if edge.get("travel_time") is not None:
        head["travel_time"] = float(edge["travel_time"]) * t_from_origin
        tail["travel_time"] = float(edge["travel_time"]) * (1.0 - t_from_origin)

    if geometry_coords is not None:
        head_geo, tail_geo = _split_geometry(geometry_coords, t_from_origin)
        head["geometry_coords"] = head_geo
        tail["geometry_coords"] = tail_geo

    return head, tail


def _find_reverse_edge(adjacency, node_coords, u, v):
    v_edges = adjacency.get(v, [])
    u_coord = node_coords.get(u)
    v_coord = node_coords.get(v)

    candidates = [edge for edge in v_edges if edge.get("to") == u]

    if not candidates:
        return None

    if u_coord is None or v_coord is None:
        return candidates[0]

    best_edge = None
    best_score = float("inf")

    for edge in candidates:
        geom = edge.get("geometry_coords")

        if not geom or len(geom) < 2:
            score = 0.0
        else:
            score = _distance_m(geom[0], v_coord) + _distance_m(geom[-1], u_coord)
            reverse_score = _distance_m(geom[-1], v_coord) + _distance_m(
                geom[0], u_coord
            )
            score = min(score, reverse_score)

        if score < best_score:
            best_score = score
            best_edge = edge

    return best_edge


def splice_virtual_node(adjacency, node_coords, resolved, virtual_id): # case resolved kind is edge
    u = resolved["u"]
    v = resolved["v"]
    t = resolved["t"]

    new_adjacency = dict(adjacency)
    new_coords = dict(node_coords)
    new_coords[virtual_id] = (resolved["lat"], resolved["lon"])

    u_edges = list(adjacency.get(u, []))
    v_edges = list(adjacency.get(v, []))

    edge_uv = resolved.get("edge")

    if edge_uv not in u_edges:
        edge_uv = next((edge for edge in u_edges if edge.get("to") == v), None)

    edge_vu = _find_reverse_edge(adjacency, node_coords, u, v)

    virtual_out = []

    # Split u -> v into u -> virtual and virtual -> v.
    if edge_uv is not None:
        u_coord = node_coords[u]
        v_coord = node_coords[v]
        geom_uv = _edge_geometry(edge_uv, u_coord, v_coord)

        u_part, v_part = _split_edge(edge_uv, t, geom_uv)
        u_part["to"] = virtual_id
        v_part["to"] = v

        new_adjacency[u] = [edge for edge in u_edges if edge is not edge_uv] + [u_part] #remove edge uv, append edge u-virtual
        virtual_out.append(v_part)

    # Split v -> u into v -> virtual and virtual -> u.
    if edge_vu is not None:
        v_coord = node_coords[v]
        u_coord = node_coords[u]
        geom_vu = _edge_geometry(edge_vu, v_coord, u_coord)

        v_part, u_part = _split_edge(edge_vu, 1.0 - t, geom_vu)
        v_part["to"] = virtual_id
        u_part["to"] = u

        new_adjacency[v] = [edge for edge in v_edges if edge is not edge_vu] + [
            v_part
        ]
        virtual_out.append(u_part)

    new_adjacency[virtual_id] = virtual_out
    return new_adjacency, new_coords