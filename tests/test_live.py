from __future__ import annotations

import json
import math
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from shapely import from_wkt
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from wfigs_mcp.arcgis import ArcGISClient, JsonObject
from wfigs_mcp.cache import TTLCache
from wfigs_mcp.caveats import Freshness
from wfigs_mcp.config import CURRENT_LAYER_URL, Settings, resolve_ytd_layer_url
from wfigs_mcp.datasets import DatasetService, GroupBy, SearchFilters, SearchResponse
from wfigs_mcp.geo import count_vertices
from wfigs_mcp.normalize import NormalizedFire, Scope
from wfigs_mcp.server import build_app

pytestmark = [
    pytest.mark.live,
    pytest.mark.asyncio(loop_scope="module"),
    pytest.mark.skipif(
        os.getenv("WFIGS_RUN_LIVE") != "1",
        reason="Set WFIGS_RUN_LIVE=1 to call the public NIFC services",
    ),
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def live_service() -> AsyncIterator[DatasetService]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as http:
        ytd_url = await resolve_ytd_layer_url(http)
        client = ArcGISClient(http, TTLCache[JsonObject](300), timeout_seconds=30)
        yield DatasetService(client, CURRENT_LAYER_URL, ytd_url)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def live_fire(live_service: DatasetService) -> NormalizedFire:
    result = await live_service.search_fires(
        SearchFilters(min_acres=1, max_acres=1_000),
        scope=Scope.YEAR_TO_DATE,
        limit=25,
    )
    candidates = [
        fire for fire in result.fires
        if fire.state and fire.discovery_date and fire.incident_type
    ]
    if not candidates:
        pytest.skip("No current-year sample with state, discovery date, and type in 1..1000 acres")
    fire = candidates[0]
    print(f"\nLIVE_SAMPLE {fire.model_dump_json()}")
    return fire


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def live_polygon(live_service: DatasetService, live_fire: NormalizedFire) -> BaseGeometry:
    # Use unsimplified upstream geometry, not a centroid that may fall outside a polygon.
    canonical = str(UUID(live_fire.irwin_id)).upper()
    payload = await live_service.client.request_json(
        f"{live_service.layer_urls[Scope.YEAR_TO_DATE]}/query",
        {
            "f": "geojson",
            "where": f"poly_IRWINID = '{{{canonical}}}'",
            "outFields": "poly_IRWINID",
            "returnGeometry": True,
            "outSR": 4326,
            "resultRecordCount": 2,
        },
    )
    assert len(payload["features"]) == 1, "Sample must have one upstream perimeter"
    polygon = shape(payload["features"][0]["geometry"])
    assert not polygon.is_empty and polygon.is_valid
    assert polygon.geom_type in {"Polygon", "MultiPolygon"}
    return polygon


def assert_freshness(value: Freshness) -> None:
    assert value.data_as_of.tzinfo is not None
    assert value.data_as_of <= datetime.now(UTC)
    assert "not evacuation guidance" in value.caveat
    assert "local emergency officials" in value.caveat
    assert "https://inciweb.wildfire.gov" in value.caveat
    newest, oldest = value.newest_perimeter_age_hours, value.oldest_perimeter_age_hours
    if newest is None:
        assert oldest is None
    else:
        assert oldest is not None and 0 <= newest <= oldest


def assert_search_contract(result: SearchResponse, scope: Scope, limit: int) -> None:
    assert result.dataset is scope
    assert 0 <= len(result.fires) <= limit
    assert result.total_count >= len(result.fires)
    assert result.truncated == (result.total_count > len(result.fires))
    assert_freshness(result.freshness)
    for fire in result.fires:
        assert fire.dataset is scope
        assert str(UUID(fire.irwin_id)).upper() == fire.irwin_id
        assert fire.name
        assert "geometry" not in fire.model_dump()
        assert fire.state is None or (len(fire.state) == 2 and fire.state.isupper())
        if fire.acres is not None:
            assert math.isfinite(fire.acres) and fire.acres >= 0
            assert fire.acres_source in {"poly_Acres_AutoCalc", "poly_GISAcres"}
        assert fire.percent_contained is None or 0 <= fire.percent_contained <= 100
        for timestamp in (fire.discovery_date, fire.perimeter_updated_at):
            assert timestamp is None or timestamp.tzinfo is not None


async def test_live_layer_metadata(live_service: DatasetService) -> None:
    for url in live_service.layer_urls.values():
        metadata = await live_service.client.request_json(url, {"f": "json"})
        assert metadata["geometryType"] == "esriGeometryPolygon"
        assert metadata["maxRecordCount"] > 0
        assert metadata["advancedQueryCapabilities"]["supportsPagination"] is True
        assert "geojson" in metadata["supportedQueryFormats"].lower()
        fields = {field["name"] for field in metadata["fields"]}
        assert {"poly_IRWINID", "poly_Acres_AutoCalc", "poly_PolygonDateTime"} <= fields


async def test_live_active_search(live_service: DatasetService) -> None:
    result = await live_service.search_fires(SearchFilters(), limit=5)
    # Current may legitimately be empty; a well-formed empty response is not an error.
    assert_search_contract(result, Scope.ACTIVE, 5)


async def test_live_ytd_search_sorting_and_size(live_service: DatasetService) -> None:
    result = await live_service.search_fires(SearchFilters(), scope=Scope.YEAR_TO_DATE)
    assert_search_contract(result, Scope.YEAR_TO_DATE, 25)
    acres = [fire.acres for fire in result.fires if fire.acres is not None]
    assert acres == sorted(acres, reverse=True)
    assert len(result.model_dump_json().encode()) < 20_000


async def test_live_combined_filters(
    live_service: DatasetService, live_fire: NormalizedFire
) -> None:
    assert live_fire.discovery_date is not None and live_fire.state is not None
    assert live_fire.acres is not None
    day = live_fire.discovery_date.date()
    result = await live_service.search_fires(
        SearchFilters(
            state=live_fire.state.lower(),
            name_contains=live_fire.name.lower(),
            min_acres=0,
            max_acres=live_fire.acres + 1,
            discovered_after=day,
            discovered_before=day,
            incident_type=live_fire.incident_type,
        ),
        scope=Scope.YEAR_TO_DATE,
        limit=25,
    )
    assert_search_contract(result, Scope.YEAR_TO_DATE, 25)
    assert result.fires, "Sample-based filters should match a live incident"
    for fire in result.fires:
        assert fire.state == live_fire.state
        assert fire.incident_type == live_fire.incident_type
        assert fire.acres is not None and 0 <= fire.acres <= live_fire.acres + 1
        assert fire.discovery_date is not None and fire.discovery_date.date() == day


async def test_live_detail_by_id(
    live_service: DatasetService, live_fire: NormalizedFire
) -> None:
    result = await live_service.get_fire(
        irwin_id="{" + live_fire.irwin_id.lower() + "}", scope=Scope.YEAR_TO_DATE
    )
    assert result.status == "found" and result.fire is not None
    assert result.fire.irwin_id == live_fire.irwin_id
    assert result.dataset is Scope.YEAR_TO_DATE
    assert_freshness(result.freshness)


async def test_live_exact_name_lookup(
    live_service: DatasetService, live_fire: NormalizedFire
) -> None:
    result = await live_service.get_fire(
        name=live_fire.name.lower(), state=live_fire.state, scope=Scope.YEAR_TO_DATE
    )
    assert result.status in {"found", "ambiguous"}
    matches = [result.fire] if result.fire is not None else result.candidates
    assert any(fire.irwin_id == live_fire.irwin_id for fire in matches)
    assert all(fire.state == live_fire.state for fire in matches)
    if result.status == "ambiguous":
        assert len(matches) > 1 and result.fire is None
    assert_freshness(result.freshness)


async def test_live_missing_id(live_service: DatasetService) -> None:
    missing_id = str(uuid4())
    print(f"\nLIVE_MISSING_ID {missing_id}")
    result = await live_service.get_fire(irwin_id=missing_id)
    assert result.status == "not_found"
    assert result.fire is None and result.candidates == []
    assert result.dataset is Scope.YEAR_TO_DATE
    assert "active or year-to-date" in result.message
    assert_freshness(result.freshness)


async def test_live_active_to_ytd_fallback(
    live_service: DatasetService, live_fire: NormalizedFire
) -> None:
    result = await live_service.get_fire(irwin_id=live_fire.irwin_id)
    if result.dataset is Scope.ACTIVE:
        pytest.skip("Selected YearToDate sample is also in Current; positive fallback unavailable")
    assert result.status == "found" and result.fire is not None
    assert result.fire.irwin_id == live_fire.irwin_id
    assert result.dataset is Scope.YEAR_TO_DATE
    assert "Not currently active" in result.message
    assert_freshness(result.freshness)


@pytest.mark.parametrize("format", ["geojson", "wkt", "bbox_only"])
async def test_live_perimeter_formats(
    live_service: DatasetService,
    live_fire: NormalizedFire,
    live_polygon: BaseGeometry,
    format: Literal["geojson", "wkt", "bbox_only"],
) -> None:
    result = await live_service.get_perimeter(
        live_fire.irwin_id, scope=Scope.YEAR_TO_DATE, format=format
    )
    assert result.irwin_id == live_fire.irwin_id and result.format == format
    assert result.dataset is Scope.YEAR_TO_DATE
    assert 0 < result.vertices_after <= result.vertices_before
    assert result.vertices_after <= live_service.vertex_cap
    if format == "wkt":
        assert isinstance(result.geometry, str)
        polygon = from_wkt(result.geometry)
    else:
        assert isinstance(result.geometry, dict)
        polygon = shape(result.geometry)
    assert not polygon.is_empty and polygon.is_valid
    assert polygon.geom_type in {"Polygon", "MultiPolygon"}
    xmin, ymin, xmax, ymax = polygon.bounds
    assert -180 <= xmin <= xmax <= 180 and -90 <= ymin <= ymax <= 90
    if format == "bbox_only":
        assert polygon.bounds == pytest.approx(live_polygon.bounds)
        assert count_vertices(polygon) == 5
    else:
        assert count_vertices(polygon) == result.vertices_after
    assert_freshness(result.freshness)


async def test_live_proximity_inside_and_ordering(
    live_service: DatasetService, live_fire: NormalizedFire, live_polygon: BaseGeometry
) -> None:
    point = live_polygon.representative_point()
    print(f"\nLIVE_PROXIMITY_INPUT lat={point.y} lon={point.x} radius_miles=1 limit=25")
    result = await live_service.fires_near(
        point.y, point.x, radius_miles=1, scope=Scope.YEAR_TO_DATE, limit=25
    )
    assert result.dataset is Scope.YEAR_TO_DATE
    assert result.total_count >= len(result.fires) and len(result.fires) <= 25
    assert result.truncated == (result.total_count > len(result.fires))
    matches = [item for item in result.fires if item.fire.irwin_id == live_fire.irwin_id]
    assert matches, "Sample's interior point must retrieve its perimeter"
    assert matches[0].inside and matches[0].distance_miles == 0
    assert matches[0].bearing_degrees is None
    distances = [item.distance_miles for item in result.fires]
    assert distances == sorted(distances)
    assert all(0 <= distance <= 1 for distance in distances)
    for item in result.fires:
        assert "geometry" not in item.fire.model_dump()
        if not item.inside:
            assert item.bearing_degrees is not None and 0 <= item.bearing_degrees < 360
    assert_freshness(result.freshness)


@pytest.mark.parametrize("group_by", list(GroupBy))
async def test_live_summaries(
    live_service: DatasetService, live_fire: NormalizedFire, group_by: GroupBy
) -> None:
    result = await live_service.summarize_fires(
        group_by,
        SearchFilters(state=live_fire.state, name_contains=live_fire.name),
        scope=Scope.YEAR_TO_DATE,
    )
    assert result.dataset is Scope.YEAR_TO_DATE and result.group_by is group_by
    assert result.groups and sum(group.count for group in result.groups) >= 1
    assert len({group.group for group in result.groups}) == len(result.groups)
    for group in result.groups:
        assert group.count > 0
        assert math.isfinite(group.total_perimeter_acres) and group.total_perimeter_acres >= 0
    if group_by is GroupBy.STATE:
        assert {group.group for group in result.groups} == {live_fire.state}
    elif group_by is GroupBy.INCIDENT_TYPE:
        assert live_fire.incident_type in {group.group for group in result.groups}
    elif group_by is GroupBy.MONTH:
        assert live_fire.discovery_date is not None
        assert live_fire.discovery_date.strftime("%Y-%m") in {
            group.group for group in result.groups
        }
    else:
        assert (live_fire.agency or "unknown") in {group.group for group in result.groups}
    assert "not definitive burned area" in result.note
    assert_freshness(result.freshness)


async def test_live_cache_preserves_fetch_time(
    live_service: DatasetService, live_fire: NormalizedFire
) -> None:
    filters = SearchFilters(state=live_fire.state, name_contains=live_fire.name)
    first = await live_service.search_fires(filters, scope=Scope.YEAR_TO_DATE, limit=1)
    hits = live_service.client.cache_stats.hits
    second = await live_service.search_fires(filters, scope=Scope.YEAR_TO_DATE, limit=1)
    assert live_service.client.cache_stats.hits >= hits + 2
    assert second.model_dump() == first.model_dump()
    assert_freshness(second.freshness)


async def test_live_mcp_search_and_resources(live_service: DatasetService) -> None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as http:
        client = ArcGISClient(http, TTLCache[JsonObject](300), timeout_seconds=30)
        service = DatasetService(
            client, CURRENT_LAYER_URL, live_service.layer_urls[Scope.YEAR_TO_DATE]
        )
        async with Client(build_app(service, Settings.from_env())) as mcp:
            result = await mcp.call_tool("search_fires", {"scope": "year_to_date", "limit": 1})
            assert not result.is_error and result.structured_content is not None
            assert_search_contract(
                SearchResponse.model_validate(result.structured_content), Scope.YEAR_TO_DATE, 1
            )
            for uri in ("wfigs://about", "wfigs://status"):
                contents = await mcp.read_resource(uri)
                assert contents and hasattr(contents[0], "text")
                payload = json.loads(contents[0].text)
                if uri == "wfigs://about":
                    assert "not evacuation guidance" in payload["caveat"]
                else:
                    assert (
                        payload["layers"]["year_to_date"] == service.layer_urls[Scope.YEAR_TO_DATE]
                    )
                    assert payload["last_successful_fetch"] is not None
                    assert payload["cache"]["misses"] >= 2