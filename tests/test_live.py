from __future__ import annotations

import os

import httpx
import pytest

from wfigs_mcp.arcgis import ArcGISClient, JsonObject
from wfigs_mcp.cache import TTLCache
from wfigs_mcp.config import CURRENT_LAYER_URL, resolve_ytd_layer_url
from wfigs_mcp.datasets import DatasetService, GroupBy, SearchFilters
from wfigs_mcp.normalize import Scope

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("WFIGS_RUN_LIVE") != "1",
        reason="Set WFIGS_RUN_LIVE=1 to call the public NIFC services",
    ),
]


@pytest.mark.asyncio
async def test_all_tools_against_live_services() -> None:
    async with httpx.AsyncClient(follow_redirects=True) as http:
        ytd_url = await resolve_ytd_layer_url(http)
        client = ArcGISClient(http, TTLCache[JsonObject](0), timeout_seconds=30)
        service = DatasetService(client, CURRENT_LAYER_URL, ytd_url)

        largest = await service.search_fires(
            SearchFilters(), scope=Scope.YEAR_TO_DATE, limit=1
        )
        assert largest.fires
        fire = largest.fires[0]

        detail = await service.get_fire(irwin_id=fire.irwin_id, scope=Scope.YEAR_TO_DATE)
        assert detail.status == "found"

        assert fire.centroid is not None
        nearby = await service.fires_near(
            fire.centroid.lat,
            fire.centroid.lon,
            radius_miles=1,
            scope=Scope.YEAR_TO_DATE,
            limit=5,
        )
        assert nearby.fires

        summary = await service.summarize_fires(
            GroupBy.STATE, SearchFilters(), scope=Scope.YEAR_TO_DATE
        )
        assert summary.groups

        perimeter = await service.get_perimeter(
            fire.irwin_id,
            scope=Scope.YEAR_TO_DATE,
            format="bbox_only",
        )
        assert perimeter.vertices_before >= perimeter.vertices_after