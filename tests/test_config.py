from __future__ import annotations

import httpx
import pytest
import respx

from wfigs_mcp.config import (
    ARCGIS_SEARCH_URL,
    ConfigurationError,
    Settings,
    resolve_ytd_layer_url,
)

SERVICE_URL = "https://services.example.test/WFIGS_Interagency_Perimeters_YearToDate/FeatureServer"


def test_settings_use_local_http_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABRICKS_APP_PORT", raising=False)
    monkeypatch.delenv("WFIGS_HOST", raising=False)
    monkeypatch.delenv("WFIGS_PORT", raising=False)
    monkeypatch.delenv("WFIGS_STREAMABLE_HTTP_PATH", raising=False)

    settings = Settings.from_env()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.streamable_http_path == "/mcp"


def test_settings_use_databricks_runtime_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABRICKS_APP_PORT", "12345")
    monkeypatch.delenv("WFIGS_HOST", raising=False)
    monkeypatch.delenv("WFIGS_PORT", raising=False)
    monkeypatch.setenv("WFIGS_STREAMABLE_HTTP_PATH", "/api/mcp")

    settings = Settings.from_env()

    assert settings.host == "0.0.0.0"
    assert settings.port == 12345
    assert settings.streamable_http_path == "/api/mcp"


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