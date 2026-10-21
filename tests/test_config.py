from __future__ import annotations

import httpx
import pytest
import respx

from wfigs_mcp.config import ARCGIS_SEARCH_URL, ConfigurationError, resolve_ytd_layer_url

SERVICE_URL = "https://services.example.test/WFIGS_Interagency_Perimeters_YearToDate/FeatureServer"


@pytest.mark.asyncio
@respx.mock
async def test_discovers_exact_current_year_polygon_service() -> None:
    search = respx.get(ARCGIS_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "item-id",
                        "owner": "NIFC_Authoritative",
                        "type": "Feature Service",
                        "title": "WFIGS 2026 Interagency Fire Perimeters to Date",
                        "url": SERVICE_URL,
                    }
                ]
            },
        )
    )
    respx.get(f"{SERVICE_URL}/0").mock(
        return_value=httpx.Response(200, json={"geometryType": "esriGeometryPolygon"})
    )

    async with httpx.AsyncClient() as http:
        result = await resolve_ytd_layer_url(http, year=2026)

    assert result == f"{SERVICE_URL}/0"
    assert "title%3A%22WFIGS+2026" in str(search.calls[0].request.url)


@pytest.mark.asyncio
@respx.mock
async def test_discovery_fails_closed_on_ambiguity() -> None:
    item = {
        "owner": "NIFC_Authoritative",
        "type": "Feature Service",
        "title": "WFIGS 2026 Interagency Fire Perimeters to Date",
        "url": SERVICE_URL,
    }
    respx.get(ARCGIS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"results": [item, item]})
    )

    async with httpx.AsyncClient() as http:
        with pytest.raises(ConfigurationError, match="found 2"):
            await resolve_ytd_layer_url(http, year=2026)