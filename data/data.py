import argparse
from pathlib import Path
import osmnx as ox
PLACE  = "Hai Bà Trưng District, Hanoi, Vietnam"
DATA_DIR = Path(__file__).resolve().parent
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--walk",action="store_true",help = "Download walk graph")
    parser.add_argument("--buffer",type= int, default = 1000,help = "Extend the boundary")
    args = parser.parse_args()
    network_type = "walk" if args.walk else "drive"
    out_name = "hbt_walk_network.graphml" if args.walk else "hbt_drive_network.graphml"
    out_path = DATA_DIR/out_name
    print(f"Loading {PLACE} (network type = {network_type})")
    if args.buffer >0:
        gdf = ox.geocode_to_gdf(PLACE)
        polygon = gdf.geometry.iloc[0].buffer(args.buffer/111_000)
        G=ox.graph_from_polygon(polygon,network_type = network_type,simplify = True)
    else:
        G = ox.graph_from_place(PLACE, network_type = network_type,simplify = True)
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)
    ox.save_graphml(G, out_path)
    print(f"Saved: {out_path}")
    print(f"Number of vertices: {G.number_of_nodes()} Number of edges: {G.number_of_edges()}")
if __name__ == "__main__":
    main()
    