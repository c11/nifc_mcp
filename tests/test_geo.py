from __future__ import annotations

import pytest
from shapely.geometry import mapping

from wfigs_mcp.geo import geodesic_area_acres, proximity_to_perimeter, simplify_geometry

SQUARE_COORDINATES = [
    [-121.0, 39.0],
    [-120.9, 39.0],
    [-120.9, 39.1],
    [-121.0, 39.1],
    [-121.0, 39.0],
]
SQUARE = {"type": "Polygon", "coordinates": [SQUARE_COORDINATES]}


def test_point_inside_perimeter_has_zero_distance() -> None:
    result = proximity_to_perimeter(39.05, -120.95, SQUARE)

    assert result.inside is True
    assert result.distance_miles == 0
    assert result.bearing_degrees is None


def test_point_outside_uses_nearest_edge_and_bearing() -> None:
    result = proximity_to_perimeter(39.05, -121.1, SQUARE)

    assert result.inside is False
    assert result.distance_miles == pytest.approx(5.37, rel=0.03)
    assert result.bearing_degrees == pytest.approx(90, abs=2)


def test_simplification_enforces_vertex_cap() -> None:
    coordinates = [(-121 + index / 10_000, 39 + (index % 2) / 10_000) for index in range(100)]
    coordinates += [(-120.99, 39.01), (-121, 39.01), coordinates[0]]
    geometry = {"type": "Polygon", "coordinates": [coordinates]}

    result = simplify_geometry(geometry, tolerance_m=0, vertex_cap=20)

    assert result.vertices_before == 103
    assert result.vertices_after <= 20
    assert mapping(result.geometry)["type"] == "Polygon"


def test_geodesic_area_is_plausible() -> None:
    assert geodesic_area_acres(SQUARE) == pytest.approx(23670, rel=0.03)