import networkx as nx
from shapely import wkt
def _to_float(value, default = None):
    try:
        return float(value)
    except (TypeError,ValueError):
        return default
def _to_node_id(raw):
    try:
         return int(raw)
    except (TypeError,ValueError):
        return raw
def _parse_geometry(value):
    if not value:
        return None
    try:
        line = wkt.loads(value)
        return [[lat, lon] for lon, lat in line.coords] #reverse for Leaflet 
    except Exception:
        return None
class RoadGraph:
    def __init__(self, node_coords: dict, adjacency:dict):
        self.node_coords =node_coords
        self.adjacency = adjacency
    @classmethod
    def from_graphml(cls,path)->"RoadGraph":
        graph = nx.read_graphml(str(path))
        node_coords = {}
        for raw_id, data in graph.nodes(data =True):
            node_id = _to_node_id(raw_id)
            lat = _to_float(data.get('y'))
            lon = _to_float(data.get('x'))
            if lat is None or lon is None:
                continue
            node_coords[node_id] = (lat,lon)

        adjacency = {node_id: [] for node_id in node_coords}
        for raw_u, raw_v, data in graph.edges(data=True):
            u = _to_node_id(raw_u)
            v = _to_node_id(raw_v)
            length = _to_float(data.get("length"))
            if length is None:
                continue

            travel_time = _to_float(data.get("travel_time"))
            if travel_time is None:
                speed_kmh = _to_float(data.get("speed_kph")) or _to_float(data.get("maxspeed")) or 30.0
                travel_time = length / (speed_kmh * 1000.0 / 3600.0)

            geometry_coords = _parse_geometry(data.get("geometry"))

            adjacency.setdefault(u, []).append(
                {
                    "to": v,
                    "length": length,
                    "travel_time": travel_time,
                    "name": data.get("name", ""),
                    "highway": data.get("highway", ""),
                    "oneway": data.get("oneway", ""),
                    "geometry_coords": geometry_coords,
                }
            )
        return cls(node_coords, adjacency)

    def num_nodes(self) -> int:
        return len(self.node_coords)

    def num_edges(self) -> int:
        return sum(len(edges) for edges in self.adjacency.values())

    def bounds(self):
        lats = [coord[0] for coord in self.node_coords.values()]
        lons = [coord[1] for coord in self.node_coords.values()]
        return min(lats), min(lons), max(lats), max(lons)

    def center(self):
        min_lat, min_lon, max_lat, max_lon = self.bounds()
        return ((min_lat + max_lat) / 2.0, (min_lon + max_lon) / 2.0)
