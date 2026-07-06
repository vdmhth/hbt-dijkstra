import json
from pathlib import Path
import osmnx as ox

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.graph_loader import RoadGraph
from backend.snap import resolve_routing_point

DATA_DIR = Path(__file__).resolve().parent
GRAPH = DATA_DIR / "hbt_drive_network.graphml"
PLACE = "Hai Bà Trưng District, Hanoi, Vietnam"
MAX_SNAP_M = 100.0      
MAX_PER_TYPE = 20       
TAGS = {
    "amenity": ["university", "college", "hospital", "marketplace",
                "fuel", "atm", "pharmacy", "cafe", "bank", "fast_food"],
    "leisure": ["park"],
    "shop":    ["mall"],
}
LABEL = {
    "university": "ĐH", "college": "ĐH", "hospital": "BV",
    "marketplace": "Chợ", "park": "Công viên", "mall": "TTTM",
    "fuel": "Cây xăng", "atm": "ATM", "pharmacy": "Nhà thuốc",
    "cafe": "Cafe", "bank": "NH", "fast_food": "Đồ ăn",
}
LANDMARK_TYPES = {"university", "college", "hospital", "marketplace", "mall", "park"}
KEYWORDS = {
    "ĐH": ["đại học", "trường", "học viện", "cao đẳng"],
    "BV": ["bệnh viện", "viện"],
    "TTTM": ["trung tâm", "vincom", "mall"],
    "Công viên": ["công viên", "vườn hoa", "hồ"],
    "Chợ": ["chợ"],
    "Cây xăng": ["xăng", "petrolimex", "petro"],
    "Nhà thuốc": ["nhà thuốc", "pharmacy"],
    "NH": ["ngân hàng", "bank"],
    "Cafe": ["cafe", "coffee", "cà phê"],
}
def display_name(kind, name):
    nm = name.strip()
    pref = LABEL[kind]
    low = nm.lower()
    if any(k in low for k in KEYWORDS.get(pref, [])):
        return nm
    return f"{pref} {nm}"
def main():
    G = RoadGraph.from_graphml(str(GRAPH))
    print(f"Graph: {G.num_nodes()} nodes")
    gdf = ox.features_from_place(PLACE, tags=TAGS)
    gdf = gdf[gdf.geometry.notna()]
    seen, out, counts = set(), [], {}
    for _, row in gdf.iterrows():
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        kind = None
        for col in ("amenity", "leisure", "shop"):
            v = row.get(col)
            if isinstance(v, str) and v in LABEL:
                kind = v
                break
        if kind is None:
            continue
        pt = row.geometry.centroid
        lat, lon = float(pt.y), float(pt.x)
        r = resolve_routing_point(G.adjacency, G.node_coords, lat, lon)
        if r["distance_m"] > MAX_SNAP_M:
            continue
        key = name.strip().lower()
        if key in seen:
            continue
        if kind in LANDMARK_TYPES and counts.get(kind, 0) >= MAX_PER_TYPE:
            continue
        seen.add(key)
        counts[kind] = counts.get(kind, 0) + 1
        out.append({
            "name": display_name(kind, name),
            "lat": round(r["lat"], 5),   
            "lon": round(r["lon"], 5),
            "type": kind,
            "snap_m": round(r["distance_m"], 1),
        })

    out.sort(key=lambda x: (x["type"], x["name"]))
    (DATA_DIR / "places.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved {len(out)} places -> data/places.json")
    by = {}
    for p in out:
        by[p["type"]] = by.get(p["type"], 0) + 1
    print("by type:", by)


if __name__ == "__main__":
    main()