from __future__ import annotations

import httpx
import pytest
from fastmcp import Client, FastMCP

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
        streamable_http_path="/mcp",
    )


def app_with_client() -> tuple[FastMCP, ArcGISClient]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("returnCountOnly") == "true":
            return httpx.Response(200, json={"count": 0})
        return httpx.Response(200, json={"features": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
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

    async with Client(app) as mcp_client:
        tools = await mcp_client.list_tools()

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
    search_schema = next(tool.input_schema for tool in tools if tool.name == "search_fires")
    assert search_schema["properties"]["limit"]["default"] == 25
    await client.aclose()


@pytest.mark.asyncio
async def test_mcp_lists_about_and_status_resources() -> None:
    app, client = app_with_client()

    async with Client(app) as mcp_client:
        resources = await mcp_client.list_resources()

    assert {str(resource.uri) for resource in resources} == {"wfigs://about", "wfigs://status"}
    await client.aclose()


@pytest.mark.asyncio
async def test_mcp_client_calls_search_tool() -> None:
    app, client = app_with_client()

    async with Client(app) as mcp_client:
        result = await mcp_client.call_tool("search_fires", {"limit": 1})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["total_count"] == 0
    assert result.structured_content["fires"] == []
    await client.aclose()