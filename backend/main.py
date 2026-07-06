import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from . import config
from .dijkstra import dijkstra, dijkstra_nearest, path_cost
from .snap import resolve_routing_point, splice_virtual_node
from .nearest import nearest_node_with_distance, nearest_node
from .pois import pois_along_route
from .schemas import (
    FrontierEntry,
    MetaResponse,
    NearestResponse,
    NearestFacilityRequest,
    NearestFacilityResponse,
    PoiAlongRouteRequest,
    PoiAlongRouteResponse,
    PoiHit,
    RelaxDetail,
    RouteRequest,
    RouteResponse,
    StepModel,
)
from .graph_loader import RoadGraph
state = {"graph": None, "graph_path": None}
@asynccontextmanager

async def lifespan(app:FastAPI):
    path = config.resolve_graph_path()
    print(f"Reading path from: {path}")
    graph = RoadGraph.from_graphml(path)
    state["graph"] = graph
    state['graph_path']=path
    print(f"Done: {graph.num_nodes()} vertices, {graph.num_edges()} edges.")
    yield
    state.clear()
app = FastAPI(title = "HBT Dijkstra", lifespan = lifespan)
@app.get("/api/meta",response_model = MetaResponse)
def get_meta():
    graph = state["graph"]
    min_lat, min_lon, max_lat, max_lon = graph.bounds()
    return MetaResponse (
        center = list(graph.center()),
        bounds = [min_lat, min_lon, max_lat, max_lon],
        num_nodes = graph.num_nodes(),
        num_edges = graph.num_edges(),
        using_real_data=(state["graph_path"] == config.REAL_GRAPH),
    )
@app.get("/api/nearest", response_model=NearestResponse)
def get_nearest(lat: float, lon: float, snap_mode: str = "nearest_node"):
    graph = state["graph"]

    if snap_mode == "nearest_node":
        node, dist = nearest_node_with_distance(graph.node_coords, lat, lon)
        snap_lat, snap_lon = graph.node_coords[node]

        return NearestResponse(
            lat=snap_lat,
            lon=snap_lon,
            distance_m=dist,
            ok=True,
            max_distance_m=config.MAX_SNAP_DISTANCE_M,
        )

    resolved = resolve_routing_point(graph.adjacency, graph.node_coords, lat, lon)

    return NearestResponse(
        lat=resolved["lat"],
        lon=resolved["lon"],
        distance_m=resolved["distance_m"],
        ok=resolved["distance_m"] <= config.MAX_SNAP_DISTANCE_M,
        max_distance_m=config.MAX_SNAP_DISTANCE_M,
    )
def _load_places():
    path = config.DATA_DIR / "places.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/places")
def get_places():
    return _load_places()


@app.post("/pois_along_route", response_model=PoiAlongRouteResponse)
def get_pois_along_route(req: PoiAlongRouteRequest):
    # Detour-based: how far you must leave the route (on real roads) to
    # reach each POI. Reuses a multi-source Dijkstra seeded at the route.
    graph = state["graph"]
    hits = pois_along_route(graph, _load_places(), req.path, req.type, req.max_detour_m)
    return PoiAlongRouteResponse(
        type=req.type,
        max_detour_m=req.max_detour_m,
        count=len(hits),
        pois=[PoiHit(**h) for h in hits],
    )
SOURCE_VIRTUAL_ID = -1
TARGET_VIRTUAL_ID = -2
FACILITY_VIRTUAL_ID = -10000
def _resolve_endpoint_nearest(graph, lat, lon, label):
    node, node_dist = nearest_node_with_distance(graph.node_coords, lat, lon)
    snapped_lat, snapped_lon = graph.node_coords[node]

    return {
        "node": node,
        "adjacency": graph.adjacency,
        "node_coords": graph.node_coords,
        "snap_distance": node_dist,
        "snapped_coord": [snapped_lat, snapped_lon],
    }

def _resolve_endpoint_virtual(adjacency, node_coords, lat, lon, virtual_id, label):
    resolved = resolve_routing_point(adjacency, node_coords, lat, lon)

    if resolved["distance_m"] > config.MAX_SNAP_DISTANCE_M:
        raise HTTPException(
            status_code=400,
            detail=f"{label} cách đường gần nhất {resolved['distance_m']:.0f}m — quá xa mạng lưới đường.",
        )

    if resolved["kind"] == "vertex":
        node = resolved["node"]
        snapped_lat, snapped_lon = node_coords[node]

        return {
            "node": node,
            "adjacency": adjacency,
            "node_coords": node_coords,
            "snap_distance": resolved["distance_m"],
            "snapped_coord": [snapped_lat, snapped_lon],
        }

    new_adjacency, new_coords = splice_virtual_node(
        adjacency,
        node_coords,
        resolved,
        virtual_id,
    )

    return {
        "node": virtual_id,
        "adjacency": new_adjacency,
        "node_coords": new_coords,
        "snap_distance": resolved["distance_m"],
        "snapped_coord": [resolved["lat"], resolved["lon"]],
    }

@app.post("/route", response_model=RouteResponse)
def find_route(req: RouteRequest):
    graph = state["graph"]

    if req.snap_mode == "nearest_node":
        src = _resolve_endpoint_nearest(
            graph,
            req.source.lat,
            req.source.lon,
            "Điểm xuất phát",
        )

        dst = _resolve_endpoint_nearest(
            graph,
            req.target.lat,
            req.target.lon,
            "Điểm kết thúc",
        )

        adjacency = graph.adjacency
        node_coords = graph.node_coords
        source_node = src["node"]
        target_node = dst["node"]

    else:
        adjacency = graph.adjacency
        node_coords = graph.node_coords

        src = _resolve_endpoint_virtual(
            adjacency,
            node_coords,
            req.source.lat,
            req.source.lon,
            SOURCE_VIRTUAL_ID,
            "Điểm xuất phát",
        )

        dst = _resolve_endpoint_virtual(
            src["adjacency"],
            src["node_coords"],
            req.target.lat,
            req.target.lon,
            TARGET_VIRTUAL_ID,
            "Điểm kết thúc",
        )

        adjacency = dst["adjacency"]
        node_coords = dst["node_coords"]
        source_node = src["node"]
        target_node = dst["node"]

    if source_node == target_node:
        raise HTTPException(
            status_code=400,
            detail="Start and End Destinations are the same.",
        )

    result = dijkstra(
        adjacency,
        source_node,
        target_node,
        weight_key=req.weight,
        record_steps=req.record_steps,
        max_steps=req.max_steps,
    )

    steps = [
        StepModel(
            current=int(s.current),
            settled=[int(x) for x in s.settled],
            updated=[int(x) for x in s.updated],
            relaxed_edges=[[int(u), int(v)] for (u, v) in s.relaxed_edges],
            relax_details=[
                RelaxDetail(
                    to=int(r.to),
                    weight=r.weight,
                    candidate_dist=r.candidate_dist,
                    improved=r.improved,
                )
                for r in s.relax_details
            ],
            frontier_preview=[
                FrontierEntry(node=int(f.node), dist=f.dist)
                for f in s.frontier_preview
            ],
            dist_current=s.dist_current,
            frontier_size=s.frontier_size,
        )
        for s in result.steps
    ]

    if not result.found:
        return RouteResponse(
            found=False,
            message="Cannot find a valid path in the current graph.",
            snap_mode=req.snap_mode,
            source_snap_distance=src["snap_distance"],
            target_snap_distance=dst["snap_distance"],
            source_snapped_coord=src["snapped_coord"],
            target_snapped_coord=dst["snapped_coord"],
            source_node=int(source_node),
            target_node=int(target_node),
            steps=steps,
            node_coords=_coords_for(
                node_coords,
                _nodes_in_steps(result.steps) | {source_node, target_node},
            ),
            visited_count=result.visited_count,
        )

    total_length = path_cost(adjacency, result.path, "length")
    total_time = path_cost(adjacency, result.path, "travel_time")
    path_coords = _route_coords(adjacency, node_coords, result.path, req.weight)

    needed = set(result.path) | _nodes_in_steps(result.steps)
    needed.add(source_node)
    needed.add(target_node)

    return RouteResponse(
        found=True,
        message=f"Found path through {len(result.path)} nodes.",
        snap_mode=req.snap_mode,
        source_snap_distance=src["snap_distance"],
        target_snap_distance=dst["snap_distance"],
        source_snapped_coord=src["snapped_coord"],
        target_snapped_coord=dst["snapped_coord"],
        source_node=int(source_node),
        target_node=int(target_node),
        path=[int(n) for n in result.path],
        path_coords=path_coords,
        total_length=total_length,
        total_time=total_time,
        num_nodes=len(result.path),
        node_coords=_coords_for(node_coords, needed),
        steps=steps,
        visited_count=result.visited_count,
    )
def _nodes_in_steps(steps) -> set:
    nodes = set()
    for s in steps:
        nodes.add(s.current)
        nodes.update(s.settled)
        nodes.update(s.updated)
        for u, v in s.relaxed_edges:
            nodes.add(u)
            nodes.add(v)
    return nodes


def _coords_for(node_coords: dict, nodes) -> dict:
    out = {}
    for n in nodes:
        if n in node_coords:
            out[str(int(n))] = list(node_coords[n])
    return out
def _best_edge(adjacency: dict, u, v, weight_key: str): # choose best weight (multigraph)
    best = None
    best_weight = float("inf")

    for edge in adjacency.get(u, ()):
        if edge.get("to") != v:
            continue

        weight = float(edge.get(weight_key, float("inf")))
        if weight < best_weight:
            best = edge
            best_weight = weight

    return best


def _same_point(a, b, eps=1e-7):
    return abs(a[0] - b[0]) < eps and abs(a[1] - b[1]) < eps


def _route_coords(adjacency: dict, node_coords: dict, path: list, weight_key: str):
    # create a list of coordinates along the path, using geometry_coords if available
    coords = []

    for u, v in zip(path, path[1:]):
        edge = _best_edge(adjacency, u, v, weight_key)

        if edge is not None and edge.get("geometry_coords"):
            segment = edge["geometry_coords"]
        else:
            segment = [list(node_coords[u]), list(node_coords[v])]

        if not segment:
            continue

        # Đảm bảo geometry đi đúng chiều u -> v
        u_coord = list(node_coords[u])
        v_coord = list(node_coords[v])

        if _same_point(segment[-1], u_coord) or _same_point(segment[0], v_coord):
            segment = list(reversed(segment))

        if not coords:
            coords.extend(segment)
        else:
            # Tránh duplicate điểm nối giữa 2 edge
            if _same_point(coords[-1], segment[0]):
                coords.extend(segment[1:])
            else:
                coords.extend(segment)

    return coords


def _serialize_steps(result_steps):
    """Convert internal Step objects to StepModel for JSON responses."""
    return [
        StepModel(
            current=int(s.current),
            settled=[int(x) for x in s.settled],
            updated=[int(x) for x in s.updated],
            relaxed_edges=[[int(u), int(v)] for (u, v) in s.relaxed_edges],
            relax_details=[
                RelaxDetail(to=int(r.to), weight=r.weight,
                            candidate_dist=r.candidate_dist, improved=r.improved)
                for r in s.relax_details
            ],
            frontier_preview=[
                FrontierEntry(node=int(f.node), dist=f.dist) for f in s.frontier_preview
            ],
            dist_current=s.dist_current,
            frontier_size=s.frontier_size,
        )
        for s in result_steps
    ]


@app.post("/nearest_facility", response_model=NearestFacilityResponse)
def find_nearest_facility(req: NearestFacilityRequest):

    graph = state["graph"]
    if req.snap_mode == "nearest_node":
        adjacency = graph.adjacency
        node_coords = graph.node_coords

        src_node, _ = nearest_node_with_distance(node_coords, req.source.lat, req.source.lon)

        # candidate facilities of this type -> their nearest graph nodes
        targets = {}  # node -> poi dict
        for p in _load_places():
            if p.get("type") != req.type:
                continue
            la, lo = p.get("lat"), p.get("lon")
            if la is None or lo is None:
                continue
            targets.setdefault(nearest_node(node_coords, la, lo), p)

        if not targets:
            return NearestFacilityResponse(
                found=False,
                message=f"No '{req.type}' in the dataset. Re-run make_places.py with this type.",
                source_node=int(src_node),
            )

        result, reached = dijkstra_nearest(
            adjacency, src_node, set(targets), weight_key=req.weight,
            record_steps=req.record_steps, max_steps=req.max_steps,
        )
        steps = _serialize_steps(result.steps)

        if not result.found or reached is None:
            return NearestFacilityResponse(
                found=False,
                message=f"No reachable '{req.type}' from this point.",
                source_node=int(src_node),
                steps=steps,
                node_coords=_coords_for(node_coords, _nodes_in_steps(result.steps) | {src_node}),
                visited_count=result.visited_count,
            )

        poi = targets[reached]
        total_length = path_cost(adjacency, result.path, "length")
        total_time = path_cost(adjacency, result.path, "travel_time")
        path_coords = _route_coords(adjacency, node_coords, result.path, req.weight)
        needed = set(result.path) | _nodes_in_steps(result.steps) | {src_node, reached}

        return NearestFacilityResponse(
            found=True,
            message=f"Nearest {req.type}: {poi.get('name', '')} ({round(total_length)} m).",
            poi_name=poi.get("name", ""),
            poi_type=poi.get("type", ""),
            poi_lat=float(poi.get("lat")),
            poi_lon=float(poi.get("lon")),
            source_node=int(src_node),
            target_node=int(reached),
            path=[int(n) for n in result.path],
            path_coords=path_coords,
            total_length=total_length,
            total_time=total_time,
            num_nodes=len(result.path),
            node_coords=_coords_for(node_coords, needed),
            steps=steps,
            visited_count=result.visited_count,
        )
    base_adjacency = graph.adjacency
    base_node_coords = graph.node_coords
    src = _resolve_endpoint_virtual(
        base_adjacency,
        base_node_coords,
        req.source.lat,
        req.source.lon,
        SOURCE_VIRTUAL_ID,
        "Điểm xuất phát",
    )
    aug_adjacency = src["adjacency"]
    aug_node_coords = src["node_coords"]
    source_node = src["node"]
    places = [p for p in _load_places() if p.get("type") == req.type and p.get("lat") is not None and p.get("lon") is not None]
    if not places:
        return NearestFacilityResponse(
            found=False,
            message=f"No '{req.type}' in the dataset. Re-run make_places.py with this type.",
            snap_mode = req.snap_mode,
            source_node=int(source_node),
            source_snap_distance=src["snap_distance"],
            source_snapped_coord=src["snapped_coord"],
        )
    targets = {}
   
    for idx, poi in enumerate(places):
        la = float(poi.get("lat"))
        lo = float(poi.get("lon"))
        virtual_id = FACILITY_VIRTUAL_ID - idx
        try:
            dst = _resolve_endpoint_virtual(
                aug_adjacency,
                aug_node_coords,
                la,
                lo,
                virtual_id,
                f"POI {poi.get('name', '')}",
            )
        except HTTPException:
            continue
        aug_adjacency = dst["adjacency"]
        aug_node_coords = dst["node_coords"]
        targets.setdefault(
            dst['node'],
            {
                "poi": poi,
                "snap": dst,
            }
        )
    
    if not targets:
        return NearestFacilityResponse(
            found=False,
            message=f"No reachable '{req.type}' from this point.",
            snap_mode = req.snap_mode,
            source_node=int(source_node),
            source_snap_distance=src["snap_distance"],
            source_snapped_coord=src["snapped_coord"],
            node_coords=_coords_for(aug_node_coords, {source_node}),
            
        )
    result, reached = dijkstra_nearest(
        aug_adjacency,
        source_node,
        set(targets),
        weight_key=req.weight,
        record_steps=req.record_steps,
        max_steps=req.max_steps,
    )

    steps = _serialize_steps(result.steps)

    if not result.found or reached is None:

        return NearestFacilityResponse(
            found=False,
            message=f"No reachable '{req.type}' from this point.",
            snap_mode=req.snap_mode,
            source_node=int(source_node),
            source_snap_distance=src["snap_distance"],
            source_snapped_coord=src["snapped_coord"],
            steps=steps,
            node_coords=_coords_for(
                aug_node_coords,
                _nodes_in_steps(result.steps) | {source_node},
            ),
            visited_count=result.visited_count,
        )

    hit = targets[reached]
    poi = hit["poi"]
    dst = hit["snap"]

    total_length = path_cost(aug_adjacency, result.path, "length")
    total_time = path_cost(aug_adjacency, result.path, "travel_time")
    path_coords = _route_coords(aug_adjacency, aug_node_coords, result.path, req.weight)

    needed = set(result.path) | _nodes_in_steps(result.steps) | {source_node, reached}

    return NearestFacilityResponse(
        found=True,
        message=f"Nearest {req.type}: {poi.get('name', '')} ({round(total_length)} m).",
        snap_mode=req.snap_mode,
        source_snap_distance=src["snap_distance"],
        target_snap_distance=dst["snap_distance"],
        source_snapped_coord=src["snapped_coord"],
        target_snapped_coord=dst["snapped_coord"],
        poi_name=poi.get("name", ""),
        poi_type=poi.get("type", ""),
        poi_lat=float(poi.get("lat")),
        poi_lon=float(poi.get("lon")),
        source_node=int(source_node),
        target_node=int(reached),
        path=[int(n) for n in result.path],
        path_coords=path_coords,
        total_length=total_length,
        total_time=total_time,
        num_nodes=len(result.path),
        node_coords=_coords_for(aug_node_coords, needed),
        steps=steps,
        visited_count=result.visited_count,
    )


app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")