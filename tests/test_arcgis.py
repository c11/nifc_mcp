from __future__ import annotations

import httpx
import pytest
import respx

from wfigs_mcp.arcgis import ArcGISClient, ArcGISResponseError
from wfigs_mcp.cache import TTLCache

LAYER_URL = "https://example.test/FeatureServer/0"


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
def client() -> ArcGISClient:
    return ArcGISClient(
        httpx.AsyncClient(),
        TTLCache(ttl_seconds=300),
        sleep=no_sleep,
    )


@pytest.mark.asyncio
@respx.mock
async def test_query_all_retries_and_pages(client: ArcGISClient) -> None:
    route = respx.get(f"{LAYER_URL}/query").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json={"features": [{"attributes": {"OBJECTID": 1}}]}),
            httpx.Response(200, json={"features": [{"attributes": {"OBJECTID": 2}}]}),
            httpx.Response(200, json={"features": []}),
        ]
    )

    result = await client.query_all(LAYER_URL, {"outFields": "OBJECTID"}, page_size=1)

    assert [feature["attributes"]["OBJECTID"] for feature in result.features] == [1, 2]
    assert route.call_count == 4
    await client._http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_request_json_uses_cache(client: ArcGISClient) -> None:
    route = respx.get(f"{LAYER_URL}/query").mock(
        return_value=httpx.Response(200, json={"features": []})
    )

    await client.request_json(f"{LAYER_URL}/query", {"f": "json"})
    await client.request_json(f"{LAYER_URL}/query", {"f": "json"})

    assert route.call_count == 1
    assert client._cache.stats.hits == 1
    await client._http.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_arcgis_error_is_model_readable(client: ArcGISClient) -> None:
    respx.get(f"{LAYER_URL}/query").mock(
        return_value=httpx.Response(200, json={"error": {"message": "Bad where clause"}})
    )

    with pytest.raises(ArcGISResponseError, match="rejected the query: Bad where clause"):
        await client.request_json(f"{LAYER_URL}/query", {"f": "json"})

    await client._http.aclose()