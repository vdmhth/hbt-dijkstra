from typing import Literal

from pydantic import BaseModel, Field

class Point(BaseModel):
    lat: float
    lon: float

class RouteRequest(BaseModel):
    source: Point
    target: Point
    weight: Literal["length", "travel_time"] = "length"
    snap_mode: Literal["nearest_node","virtual_node"] = "nearest_node"
    record_steps: bool = True
    max_steps: int | None = Field(default=4000, ge=1)

class RelaxDetail(BaseModel):
    to: int
    weight: float
    candidate_dist: float
    improved: bool


class FrontierEntry(BaseModel):
    node: int
    dist: float


class StepModel(BaseModel):
    current: int
    settled: list[int]
    updated: list[int]
    relaxed_edges: list[list[int]]
    relax_details: list[RelaxDetail] = Field(default_factory=list)
    frontier_preview: list[FrontierEntry] = Field(default_factory=list)
    dist_current: float
    frontier_size: int

class RouteResponse(BaseModel):
    found: bool
    message: str = ""
    snap_mode: str = "nearest_node"
    source_snap_distance: float = 0.0
    target_snap_distance: float = 0.0
    source_snapped_coord: list[float] = Field(default_factory= list)
    target_snapped_coord: list[float] = Field(default_factory=list)

    source_node: int | None = None
    target_node: int | None = None

    path: list[int] = Field(default_factory=list)
    path_coords: list[list[float]] = Field(default_factory=list)
    total_length: float = 0.0
    total_time: float = 0.0
    num_nodes: int = 0

    node_coords: dict[str, list[float]] = Field(default_factory=dict)
    steps: list[StepModel] = Field(default_factory=list)
    visited_count: int = 0

class MetaResponse(BaseModel):
    center: list[float]
    bounds: list[float]
    num_nodes: int
    num_edges: int
    using_real_data: bool


class PoiAlongRouteRequest(BaseModel):
    path: list[int]
    type: str | None = None
    max_detour_m: float = Field(default=200.0, gt=0, le=2000)


class PoiHit(BaseModel):
    name: str
    type: str
    lat: float
    lon: float
    detour_m: float
    along_m: float
    attach_lat: float
    attach_lon: float
    turn_in: list[list[float]] = Field(default_factory=list)


class PoiAlongRouteResponse(BaseModel):
    type: str | None = None
    max_detour_m: float = 200.0
    count: int = 0
    pois: list[PoiHit] = Field(default_factory=list)

class NearestResponse(BaseModel):
    lat: float
    lon: float
    distance_m: float
    ok: bool
    max_distance_m: float

class NearestFacilityRequest(BaseModel):
    source: Point
    type: str  
    weight: Literal["length", "travel_time"] = "length"
    snap_mode: Literal["nearest_node","virtual_node"] = "nearest_node"
    record_steps: bool = True
    max_steps: int | None = 4000


class NearestFacilityResponse(BaseModel):
    found: bool
    message: str
    snap_mode: str = "nearest_node"
    source_snap_distance: float = 0.0
    target_snap_distance: float = 0.0
    source_snapped_coord: list[float] = Field(default_factory=list)
    target_snapped_coord: list[float] = Field(default_factory=list)

    poi_name: str = ""
    poi_type: str = ""
    poi_lat: float = 0.0
    poi_lon: float = 0.0
    source_node: int = 0
    target_node: int = 0
    path: list[int] = Field(default_factory=list)
    path_coords: list[list[float]] = Field(default_factory=list)
    total_length: float = 0.0
    total_time: float = 0.0
    num_nodes: int = 0
    node_coords: dict = Field(default_factory=dict)
    steps: list[StepModel] = Field(default_factory=list)
    visited_count: int = 0