from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyproj import CRS, Geod, Transformer
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, transform

WGS84 = CRS.from_epsg(4326)
GEOD = Geod(ellps="WGS84")
METERS_PER_MILE = 1_609.344


@dataclass(frozen=True, slots=True)
class Proximity:
    distance_miles: float
    inside: bool
    bearing_degrees: float | None


@dataclass(frozen=True, slots=True)
class SimplifiedGeometry:
    geometry: BaseGeometry
    vertices_before: int
    vertices_after: int
    tolerance_m: float


def proximity_to_perimeter(
    lat: float,
    lon: float,
    geometry: dict[str, Any],
) -> Proximity:
    polygon = shape(geometry)
    _validate_polygon(polygon)
    forward, inverse = _local_transformers(lat, lon)
    projected = transform(forward.transform, polygon)
    origin = Point(0, 0)
    inside = projected.covers(origin)
    if inside:
        return Proximity(distance_miles=0.0, inside=True, bearing_degrees=None)
    nearest = nearest_points(origin, projected.boundary)[1]
    nearest_wgs84 = transform(inverse.transform, nearest)
    bearing, _, distance_m = GEOD.inv(lon, lat, nearest_wgs84.x, nearest_wgs84.y)
    return Proximity(
        distance_miles=distance_m / METERS_PER_MILE,
        inside=False,
        bearing_degrees=bearing % 360,
    )


def simplify_geometry(
    geometry: dict[str, Any],
    tolerance_m: float,
    vertex_cap: int,
) -> SimplifiedGeometry:
    if tolerance_m < 0:
        raise ValueError("simplify_tolerance_m must be non-negative")
    if vertex_cap < 4:
        raise ValueError("vertex_cap must be at least 4")
    polygon = shape(geometry)
    _validate_polygon(polygon)
    before = count_vertices(polygon)
    centroid = polygon.centroid
    forward, inverse = _local_transformers(centroid.y, centroid.x)
    projected = transform(forward.transform, polygon)

    applied_tolerance = tolerance_m
    simplified = projected.simplify(applied_tolerance, preserve_topology=True)
    while count_vertices(simplified) > vertex_cap and applied_tolerance < 100_000:
        applied_tolerance = max(1.0, applied_tolerance * 2 or 1.0)
        simplified = projected.simplify(applied_tolerance, preserve_topology=True)
    after = count_vertices(simplified)
    if after > vertex_cap:
        raise ValueError(
            f"Perimeter remains above the {vertex_cap}-vertex safety cap after simplification"
        )
    wgs84_geometry = transform(inverse.transform, simplified)
    return SimplifiedGeometry(
        geometry=wgs84_geometry,
        vertices_before=before,
        vertices_after=after,
        tolerance_m=applied_tolerance,
    )


def count_vertices(geometry: BaseGeometry) -> int:
    if isinstance(geometry, Polygon):
        return len(geometry.exterior.coords) + sum(
            len(interior.coords) for interior in geometry.interiors
        )
    if isinstance(geometry, MultiPolygon):
        return sum(count_vertices(polygon) for polygon in geometry.geoms)
    raise ValueError("Expected Polygon or MultiPolygon geometry")


def geodesic_area_acres(geometry: dict[str, Any]) -> float:
    polygon = shape(geometry)
    _validate_polygon(polygon)
    area_m2, _ = GEOD.geometry_area_perimeter(polygon)
    return abs(area_m2) / 4_046.8564224


def _local_transformers(lat: float, lon: float) -> tuple[Transformer, Transformer]:
    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs"
    )
    return (
        Transformer.from_crs(WGS84, local, always_xy=True),
        Transformer.from_crs(local, WGS84, always_xy=True),
    )


def _validate_polygon(geometry: BaseGeometry) -> None:
    if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Expected non-empty Polygon or MultiPolygon geometry")
