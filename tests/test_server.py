from __future__ import annotations

import httpx
import pytest

from wfigs_mcp.arcgis import ArcGISClient, JsonObject
from wfigs_mcp.cache import TTLCache
from wfigs_mcp.config import Settings
from wfigs_mcp.datasets import DatasetService
from wfigs_mcp.server import build_app


def settings() -> Settings:
    return Settings(
        current_layer_url="https://example.test/current/0",
        ytd_layer_url="https://example.test/ytd/0",
        cache_ttl_seconds=300,
        timeout_seconds=20,
        max_retries=3,
        max_limit=200,
        vertex_cap=10_000,
        transport="stdio",
        host="127.0.0.1",
        port=8000,
    )


def app_with_client() -> tuple[object, ArcGISClient]:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
    client = ArcGISClient(http, TTLCache[JsonObject](300))
    service = DatasetService(
        client,
        "https://example.test/current/0",
        "https://example.test/ytd/0",
    )
    return build_app(service, settings()), client


@pytest.mark.asyncio
async def test_mcp_lists_domain_tools_with_llm_descriptions() -> None:
    app, client = app_with_client()

    tools = await app.list_tools()  # type: ignore[attr-defined]

    assert {tool.name for tool in tools} == {
        "search_fires",
        "get_fire",
        "fires_near",
        "summarize_fires",
        "get_perimeter",
    }
    descriptions = {tool.name: tool.description or "" for tool in tools}
    assert "Defaults to active" in descriptions["search_fires"]
    assert "geocoded elsewhere" in descriptions["fires_near"]
    assert "only tool that returns polygon geometry" in descriptions["get_perimeter"]
    search_schema = next(tool.inputSchema for tool in tools if tool.name == "search_fires")
    assert search_schema["properties"]["limit"]["default"] == 25
    await client.aclose()


@pytest.mark.asyncio
async def test_mcp_lists_about_and_status_resources() -> None:
    app, client = app_with_client()

    resources = await app.list_resources()  # type: ignore[attr-defined]

    assert {str(resource.uri) for resource in resources} == {"wfigs://about", "wfigs://status"}
    await client.aclose()