from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR/ "data"
FRONTEND_DIR = BASE_DIR / "frontend"
REAL_GRAPH = DATA_DIR / "hbt_drive_network.graphml"
def resolve_graph_path()-> Path:
    if REAL_GRAPH.exists():
        return REAL_GRAPH
    raise FileNotFoundError("Cannot find .graphml file.")
PLACE_NAME = "Hai Bà Trưng District, Hanoi, Vietnam"
MAX_SNAP_DISTANCE_M = 70.0
