from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

CURRENT_LAYER_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Interagency_Perimeters_Current/FeatureServer/0"
)
ARCGIS_SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"
YTD_TITLE_TEMPLATE = "WFIGS {year} Interagency Fire Perimeters to Date"


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Settings:
    current_layer_url: str
    ytd_layer_url: str | None
    cache_ttl_seconds: float
    timeout_seconds: float
    max_retries: int
    max_limit: int
    vertex_cap: int
    transport: str
    host: str
    port: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            current_layer_url=os.getenv("WFIGS_CURRENT_LAYER_URL", CURRENT_LAYER_URL),
            ytd_layer_url=os.getenv("WFIGS_YTD_LAYER_URL"),
            cache_ttl_seconds=float(os.getenv("WFIGS_CACHE_TTL_SECONDS", "300")),
            timeout_seconds=float(os.getenv("WFIGS_TIMEOUT_SECONDS", "20")),
            max_retries=int(os.getenv("WFIGS_MAX_RETRIES", "3")),
            max_limit=int(os.getenv("WFIGS_MAX_LIMIT", "200")),
            vertex_cap=int(os.getenv("WFIGS_VERTEX_CAP", "10000")),
            transport=os.getenv("WFIGS_TRANSPORT", "stdio"),
            host=os.getenv("WFIGS_HOST", "127.0.0.1"),
            port=int(os.getenv("WFIGS_PORT", "8000")),
        )


async def resolve_ytd_layer_url(
    http: httpx.AsyncClient,
    *,
    override: str | None = None,
    year: int | None = None,
) -> str:
    if override:
        return override.rstrip("/")

    selected_year = year or datetime.now(UTC).year
    title = YTD_TITLE_TEMPLATE.format(year=selected_year)
    query = f'owner:NIFC_Authoritative AND type:"Feature Service" AND title:"{title}"'
    response = await http.get(
        ARCGIS_SEARCH_URL,
        params={"f": "json", "q": query, "num": 10},
    )
    response.raise_for_status()
    payload: Any = response.json()
    results = payload.get("results", []) if isinstance(payload, dict) else []
    candidates = [
        item
        for item in results
        if isinstance(item, dict)
        and item.get("owner") == "NIFC_Authoritative"
        and item.get("type") == "Feature Service"
        and item.get("title") == title
        and isinstance(item.get("url"), str)
        and item["url"].startswith("https://")
    ]
    if len(candidates) != 1:
        raise ConfigurationError(
            f"Expected one authoritative {selected_year} WFIGS YearToDate service; "
            f"found {len(candidates)}. Set WFIGS_YTD_LAYER_URL explicitly."
        )
    layer_url = f"{candidates[0]['url'].rstrip('/')}/0"
    metadata_response = await http.get(layer_url, params={"f": "json"})
    metadata_response.raise_for_status()
    metadata: Any = metadata_response.json()
    if not isinstance(metadata, dict) or metadata.get("geometryType") != "esriGeometryPolygon":
        raise ConfigurationError("Discovered WFIGS YearToDate layer 0 is not a polygon layer.")
    return layer_url
