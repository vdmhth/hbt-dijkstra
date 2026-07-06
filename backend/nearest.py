import math

EARTH_RADIUS_M = 6371000.0
def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
def nearest_node(node_coords: dict, lat: float, lon: float):
    if not node_coords:
        raise ValueError("Empty graph")
    cos_lat = math.cos(math.radians(lat))
    best_node = None
    best_d2 = float("inf")
    for node_id, (n_lat, n_lon) in node_coords.items():
        dlat = n_lat - lat
        dlon = (n_lon - lon) * cos_lat
        d2 = dlat * dlat + dlon * dlon
        if d2 < best_d2:
            best_d2 = d2
            best_node = node_id
    return best_node
def nearest_node_with_distance(node_coords: dict, lat: float, lon: float):
    node_id = nearest_node(node_coords, lat, lon)
    n_lat, n_lon = node_coords[node_id]
    distance_m = haversine_m(lat, lon, n_lat, n_lon)
    return node_id, distance_m
