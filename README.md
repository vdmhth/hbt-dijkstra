# Shortest Path Finding in Hai Bà Trưng District (Dijkstra + OpenStreetMap)

A web application that finds the shortest / fastest route between two points in
**Hai Bà Trưng District, Hà Nội** on real OpenStreetMap road data, using a
**Dijkstra implementation written from scratch** (no `networkx.shortest_path`,
no OSRM, no Google Directions). It also **visualizes the algorithm step by
step** for teaching purposes.

> Project I — IT3190E, SoICT, HUST.
> The graph currently bundled in `data/` has **1772 nodes / 4084 directed edges**
> (Hai Bà Trưng + ~1 km buffer).

---

## Features

- Pick **start / end** by clicking the map, typing coordinates, picking a sample
  pair, or choosing a named landmark.
- Two routing criteria: **shortest distance** (`length`) and
  **fastest time** (`travel_time`).
- Two snapping modes:
  - **nearest_node** (default, as required by the assignment) — snap the click to
    the closest graph vertex;
  - **virtual_node** (extension) — project the click onto the nearest road *edge*
    using the edge's real geometry and splice in a temporary node.
- **Step-by-step Dijkstra simulation**: settled / current / updated nodes,
  relaxed edges, the shortest-path tree, a priority-queue preview, a step log,
  highlighted pseudocode, and play / pause / step / reset controls.
- **Extension queries built on the same Dijkstra core**:
  - *Nearest facility* (ATM / fuel / hospital …) — multi-target Dijkstra that
    stops at the first facility node it settles;
  - *POIs along a route* — multi-source Dijkstra seeded on every route node to
    measure the real road detour to each nearby POI.
- Routes are drawn along the **true road geometry**, not straight node-to-node
  lines.

---

## Requirements

- Python 3.10+
- Packages in `requirements.txt` (FastAPI, uvicorn, pydantic, networkx, osmnx,
  shapely is pulled in by osmnx, pytest).

`osmnx` is only needed if you want to **re-download** the map. To just run the
app on the bundled graph you only need: `fastapi`, `uvicorn`, `pydantic`,
`networkx`, `shapely`.

---

## Quick start

```bash
# 1. install
pip install -r requirements.txt

# 2. run (from the project root) — serves both API and frontend
uvicorn backend.main:app --reload

# 3. open
#   http://127.0.0.1:8000
```

The backend loads `data/hbt_drive_network.graphml` on startup (falls back to
`data/demo_network.graphml` if the real one is missing) and serves the frontend
from `frontend/` at `/`.

---

## (Optional) Re-downloading the map data

The app ships with a pre-saved graph so the demo is fast and offline-stable. To
regenerate it from OpenStreetMap:

```bash
# drive network, district boundary + 1 km buffer (default)
python data/data.py

# walking network
python data/data.py --walk

# custom buffer in metres
python data/data.py --buffer 1500
```

This uses OSMnx **only to download and save** the network and to attach
`speed_kph` / `travel_time` edge attributes. It does **not** compute any route.

To (re)generate the sample landmarks file `data/places.json`:

```bash
python data/make_places.py
```

---

## Project structure

```
backend/
  main.py          FastAPI app, endpoints, request/response assembly
  config.py        paths, weight choices, snap threshold
  graph_loader.py  read .graphml -> node_coords + adjacency list (+ travel_time)
  nearest.py       haversine + nearest-node search
  snap.py          virtual-node snapping onto real edge geometry
  dijkstra.py      *** the from-scratch Dijkstra (+ multi-source, multi-target) ***
  pois.py          POIs-along-route (detour) using multi-source Dijkstra
  schemas.py       pydantic models
frontend/
  index.html       panel + map + simulation UI
  css/style.css
  js/api.js        fetch wrappers
  js/map.js        Leaflet map + layers
  js/anim.js       simulation playback
  js/app.js        UI logic, request orchestration, rendering
data/
  hbt_drive_network.graphml   bundled HBT driving graph (1772 nodes / 4084 edges)
  places.json                 landmark / POI samples
  data.py, make_places.py     data-generation scripts
tests/
  test_dijkstra.py           
  check.py
  bench.py
```

---

## API

| Method | Endpoint              | Purpose |
|--------|-----------------------|---------|
| GET    | `/api/meta`           | graph center, bounds, node/edge counts |
| GET    | `/api/nearest`        | snapped coordinate for a clicked point |
| GET    | `/api/places`         | landmark / POI list |
| POST   | `/route`              | run Dijkstra source → target |
| POST   | `/nearest_facility`   | nearest facility of a type (multi-target Dijkstra) |
| POST   | `/pois_along_route`   | POIs within a detour of a route (multi-source Dijkstra) |

Example `/route` body:

```json
{
  "source": { "lat": 21.001, "lon": 105.845 },
  "target": { "lat": 21.008, "lon": 105.857 },
  "weight": "length",
  "snap_mode": "nearest_node",
  "record_steps": true,
  "max_steps": 4000
}
```

---

## Tests

```bash
pytest -q
```
---

## Assignment compliance

- The shortest-path computation is implemented by hand in `backend/dijkstra.py`
  with a binary-heap priority queue (`heapq`) and lazy deletion.
- Forbidden functions (`networkx.shortest_path`, `networkx.dijkstra_path`,
  `osmnx.shortest_path`, OSRM / Google Directions) are **not** used for routing.
- Allowed libraries are used only for: downloading/saving OSM data (osmnx),
  reading GraphML (networkx), the web layer (FastAPI), and the map (Leaflet).
