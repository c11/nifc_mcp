from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal, cast

import httpx
from mcp.server.fastmcp import FastMCP

from .arcgis import ArcGISClient, JsonObject
from .cache import TTLCache
from .config import Settings, resolve_ytd_layer_url
from .datasets import DatasetService, GroupBy, SearchFilters, SortBy
from .normalize import IncidentType, Scope

LOGGER = logging.getLogger("wfigs_mcp")


def build_app(service: DatasetService, settings: Settings) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await service.client.aclose()

    app = FastMCP(
        "NIFC WFIGS Wildfire Perimeters",
        host=settings.host,
        port=settings.port,
        lifespan=lifespan,
    )

    @app.tool(
        description=(
            "Search and filter fires when you need a bounded list, not one exact incident or "
            "a spatial lookup. Defaults to active fires. Returns normalized records without "
            "polygon geometry; use get_perimeter for geometry."
        )
    )
    async def search_fires(
        state: str | None = None,
        name_contains: str | None = None,
        min_acres: float | None = None,
        max_acres: float | None = None,
        discovered_after: date | None = None,
        discovered_before: date | None = None,
        incident_type: IncidentType | None = None,
        min_percent_contained: float | None = None,
        max_percent_contained: float | None = None,
        scope: Scope = Scope.ACTIVE,
        sort_by: SortBy = SortBy.ACRES,
        limit: int = 25,
    ) -> dict[str, object]:
        result = await service.search_fires(
            SearchFilters(
                state=state,
                name_contains=name_contains,
                min_acres=min_acres,
                max_acres=max_acres,
                discovered_after=discovered_after,
                discovered_before=discovered_before,
                incident_type=incident_type,
                min_percent_contained=min_percent_contained,
                max_percent_contained=max_percent_contained,
            ),
            scope=scope,
            sort_by=sort_by,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @app.tool(
        description=(
            "Get one fire by IRWIN ID or exact name plus state. Use this instead of search for "
            "incident details or to learn whether a named fire is still active. Active lookups "
            "fall back to year-to-date. Returns no polygon geometry; use get_perimeter for it."
        )
    )
    async def get_fire(
        irwin_id: str | None = None,
        name: str | None = None,
        state: str | None = None,
        scope: Scope = Scope.ACTIVE,
    ) -> dict[str, object]:
        result = await service.get_fire(
            scope=scope, irwin_id=irwin_id, name=name, state=state
        )
        return result.model_dump(mode="json")

    @app.tool(
        description=(
            "Find fires near latitude/longitude and calculate nearest-perimeter distance, "
            "inside status, and bearing. Defaults to active fires. Place names must be geocoded "
            "elsewhere first. Returns no polygon geometry; use get_perimeter for geometry."
        )
    )
    async def fires_near(
        lat: float,
        lon: float,
        radius_miles: float = 25,
        scope: Scope = Scope.ACTIVE,
        limit: int = 25,
    ) -> dict[str, object]:
        result = await service.fires_near(
            lat, lon, radius_miles, scope=scope, limit=limit
        )
        return result.model_dump(mode="json")

    @app.tool(
        description=(
            "Aggregate fire counts and perimeter acres by state, incident type, month, or "
            "agency. Use search_fires for individual records. Defaults to active fires and "
            "returns no polygon geometry."
        )
    )
    async def summarize_fires(
        group_by: GroupBy,
        state: str | None = None,
        name_contains: str | None = None,
        min_acres: float | None = None,
        max_acres: float | None = None,
        discovered_after: date | None = None,
        discovered_before: date | None = None,
        incident_type: IncidentType | None = None,
        min_percent_contained: float | None = None,
        max_percent_contained: float | None = None,
        scope: Scope = Scope.ACTIVE,
    ) -> dict[str, object]:
        filters = SearchFilters(
            state=state,
            name_contains=name_contains,
            min_acres=min_acres,
            max_acres=max_acres,
            discovered_after=discovered_after,
            discovered_before=discovered_before,
            incident_type=incident_type,
            min_percent_contained=min_percent_contained,
            max_percent_contained=max_percent_contained,
        )
        result = await service.summarize_fires(group_by, filters, scope=scope)
        return result.model_dump(mode="json")

    @app.tool(
        description=(
            "Return one fire perimeter in WGS84 as GeoJSON, WKT, or only its bounding box. "
            "This is the only tool that returns polygon geometry. Defaults to active fires and "
            "enforces simplification plus a vertex safety cap."
        )
    )
    async def get_perimeter(
        irwin_id: str,
        scope: Scope = Scope.ACTIVE,
        simplify_tolerance_m: float = 100,
        format: Literal["geojson", "wkt", "bbox_only"] = "geojson",
    ) -> dict[str, object]:
        result = await service.get_perimeter(
            irwin_id,
            scope=scope,
            simplify_tolerance_m=simplify_tolerance_m,
            format=format,
        )
        return result.model_dump(mode="json")

    @app.resource(
        "wfigs://about",
        description="Dataset differences, normalized field meanings, and wildfire safety caveats.",
        mime_type="application/json",
    )
    def about() -> str:
        return json.dumps(
            {
                "current": "Recent and ongoing incidents subject to NIFC fall-off rules.",
                "year_to_date": "Qualifying incidents discovered in the current calendar year.",
                "fields": {
                    "acres": "Geodesic polygon acres, with source field disclosed.",
                    "perimeter_updated_at": "Polygon capture time, with labeled fallback.",
                    "percent_contained": "IRWIN reported value; null means unknown, not zero.",
                },
                "details": "See docs/DATA_NOTES.md in the project repository.",
                "caveat": (
                    "Perimeters can lag ground conditions by a day or more and are not evacuation "
                    "guidance. Follow local emergency officials and https://inciweb.wildfire.gov"
                ),
            }
        )

    @app.resource(
        "wfigs://status",
        description="Resolved layer URLs, cache statistics, and observed fetch/freshness status.",
        mime_type="application/json",
    )
    def status() -> str:
        return json.dumps(
            {
                "layers": {key.value: value for key, value in service.layer_urls.items()},
                "last_successful_fetch": (
                    service.client.last_successful_fetch.isoformat()
                    if service.client.last_successful_fetch
                    else None
                ),
                "cache": {
                    "entries": service.client.cache_stats.entries,
                    "hits": service.client.cache_stats.hits,
                    "misses": service.client.cache_stats.misses,
                },
                "latest_perimeter_updated_at": {
                    key.value: value.isoformat() if value else None
                    for key, value in service.latest_perimeter_seen.items()
                },
            },
            default=str,
        )

    return app


async def create_service(settings: Settings) -> DatasetService:
    async with httpx.AsyncClient(follow_redirects=True) as discovery_http:
        ytd_layer_url = await resolve_ytd_layer_url(
            discovery_http, override=settings.ytd_layer_url
        )
    http = httpx.AsyncClient(follow_redirects=True)
    cache: TTLCache[JsonObject] = TTLCache(settings.cache_ttl_seconds)
    client = ArcGISClient(
        http,
        cache,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    service = DatasetService(
        client,
        settings.current_layer_url,
        ytd_layer_url,
        max_limit=settings.max_limit,
        vertex_cap=settings.vertex_cap,
    )
    LOGGER.info("Using Current layer: %s", settings.current_layer_url)
    LOGGER.info("Using YearToDate layer: %s", ytd_layer_url)
    return service


def main() -> None:
    parser = argparse.ArgumentParser(description="NIFC WFIGS MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        help="Override WFIGS_TRANSPORT (default: stdio)",
    )
    args = parser.parse_args()
    settings = Settings.from_env()
    transport = args.transport or settings.transport
    if transport not in {"stdio", "streamable-http"}:
        parser.error("transport must be 'stdio' or 'streamable-http'")
    selected_transport = cast(Literal["stdio", "streamable-http"], transport)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    service = asyncio.run(create_service(settings))
    app = build_app(service, settings)
    app.run(transport=selected_transport)


if __name__ == "__main__":
    main()