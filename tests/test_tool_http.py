from __future__ import annotations

import httpx
import pytest
import respx

from wfigs_mcp.arcgis import ArcGISClient, JsonObject
from wfigs_mcp.cache import TTLCache
from wfigs_mcp.datasets import DatasetService, GroupBy, SearchFilters
from wfigs_mcp.normalize import Scope

ACTIVE = "https://example.test/current/0"
YTD = "https://example.test/ytd/0"
IRWIN_ID = "11111111-1111-1111-1111-111111111111"


def attributes() -> dict[str, object]:
    return {
        "poly_IncidentName": "TEST",
        "poly_Acres_AutoCalc": 10.0,
        "poly_GISAcres": 9.9,
        "poly_CreateDate": 1792600000000,
        "poly_PolygonDateTime": 1792610000000,
        "poly_IRWINID": "{" + IRWIN_ID + "}",
        "attr_IncidentName": "TEST",
        "attr_IncidentSize": 10.0,
        "attr_PercentContained": 25,
        "attr_FireDiscoveryDateTime": 1792000000000,
        "attr_IncidentTypeCategory": "WF",
        "attr_POOState": "US-OR",
        "attr_POOCounty": "Test",
        "attr_POOProtectingAgency": "USFS",
        "attr_POOProtectingUnit": "OR-TEST",
    }


@pytest.mark.asyncio
@respx.mock
async def test_search_tool_behavior_against_mocked_http() -> None:
    count_route = respx.get(f"{ACTIVE}/query", params__contains={"returnCountOnly": "true"})
    count_route.mock(return_value=httpx.Response(200, json={"count": 1}))
    feature_route = respx.get(f"{ACTIVE}/query", params__contains={"resultOffset": "0"})
    feature_route.mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    {
                        "attributes": attributes(),
                        "centroid": {"x": -121, "y": 44},
                        "envelope": {
                            "xmin": -121.1,
                            "ymin": 43.9,
                            "xmax": -120.9,
                            "ymax": 44.1,
                        },
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as http:
        client = ArcGISClient(http, TTLCache[JsonObject](300))
        service = DatasetService(client, ACTIVE, YTD)
        result = await service.search_fires(SearchFilters(state="OR"))

    assert result.total_count == 1
    assert result.fires[0].state == "OR"
    assert result.freshness.caveat.startswith("Wildfire perimeters can lag")


@pytest.mark.asyncio
@respx.mock
async def test_perimeter_falls_back_and_simplifies_mocked_geojson() -> None:
    respx.get(f"{ACTIVE}/query").mock(
        return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": []})
    )
    respx.get(f"{YTD}/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": attributes(),
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[-121, 44], [-120.9, 44], [-120.9, 44.1], [-121, 44.1], [-121, 44]]
                            ],
                        },
                    }
                ],
            },
        )
    )
    async with httpx.AsyncClient() as http:
        client = ArcGISClient(http, TTLCache[JsonObject](300))
        service = DatasetService(client, ACTIVE, YTD)
        result = await service.get_perimeter(IRWIN_ID, simplify_tolerance_m=100)

    assert result.dataset is Scope.YEAR_TO_DATE
    assert result.message.startswith("Not currently active")
    assert result.format == "geojson"
    assert result.vertices_after <= result.vertices_before


@pytest.mark.asyncio
@respx.mock
async def test_fires_near_computes_inside_status_against_mocked_http() -> None:
    response_feature = {
        "attributes": attributes(),
        "centroid": {"x": -120.95, "y": 44.05},
        "envelope": {"xmin": -121, "ymin": 44, "xmax": -120.9, "ymax": 44.1},
        "geometry": {
            "rings": [
                [[-121, 44], [-121, 44.1], [-120.9, 44.1], [-120.9, 44], [-121, 44]]
            ]
        },
    }
    respx.get(f"{ACTIVE}/query").mock(
        return_value=httpx.Response(200, json={"features": [response_feature]})
    )
    async with httpx.AsyncClient() as http:
        client = ArcGISClient(http, TTLCache[JsonObject](300))
        service = DatasetService(client, ACTIVE, YTD)
        result = await service.fires_near(44.05, -120.95, radius_miles=5)

    assert result.total_count == 1
    assert result.fires[0].inside is True
    assert result.fires[0].distance_miles == 0
    assert result.fires[0].fire.centroid is not None


@pytest.mark.asyncio
@respx.mock
async def test_summary_uses_upstream_statistics_and_reports_freshness() -> None:
    respx.get(f"{ACTIVE}/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    {
                        "attributes": {
                            "attr_POOState": "US-OR",
                            "fire_count": 3,
                            "total_acres": 42.5,
                            "newest_perimeter": 1792610000000,
                            "oldest_perimeter": 1792500000000,
                        }
                    }
                ]
            },
        )
    )
    async with httpx.AsyncClient() as http:
        client = ArcGISClient(http, TTLCache[JsonObject](300))
        service = DatasetService(client, ACTIVE, YTD)
        result = await service.summarize_fires(GroupBy.STATE, SearchFilters())

    assert result.groups[0].group == "OR"
    assert result.groups[0].total_perimeter_acres == 42.5
    assert result.freshness.newest_perimeter_age_hours is not None