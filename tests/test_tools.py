from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from wfigs_mcp.arcgis import QueryResult
from wfigs_mcp.datasets import DatasetService, SearchFilters, SortBy
from wfigs_mcp.normalize import Scope

NOW = datetime(2026, 10, 21, 20, tzinfo=UTC)
ACTIVE_URL = "https://example.test/current/0"
YTD_URL = "https://example.test/ytd/0"


def feature(
    name: str = "TEST",
    irwin_id: str = "{11111111-1111-1111-1111-111111111111}",
) -> dict[str, Any]:
    return {
        "attributes": {
            "poly_IncidentName": name,
            "poly_Acres_AutoCalc": 10.0,
            "poly_GISAcres": 9.9,
            "poly_PolygonDateTime": 1792610000000,
            "poly_IRWINID": irwin_id,
            "attr_IncidentName": name,
            "attr_IncidentSize": 10.0,
            "attr_PercentContained": 25,
            "attr_FireDiscoveryDateTime": 1792000000000,
            "attr_IncidentTypeCategory": "WF",
            "attr_POOState": "US-OR",
            "attr_POOCounty": "Test",
            "attr_POOProtectingAgency": "USFS",
            "attr_POOProtectingUnit": "OR-TEST",
        },
        "centroid": {"x": -121, "y": 44},
        "envelope": {"xmin": -121.1, "ymin": 43.9, "xmax": -120.9, "ymax": 44.1},
    }


class FakeClient:
    def __init__(self, pages: list[list[dict[str, Any]]], counts: list[int] | None = None) -> None:
        self.pages = pages
        self.counts = counts or []
        self.last_successful_fetch = NOW
        self.last_response_as_of = NOW
        self.query_calls: list[tuple[str, dict[str, object]]] = []

    async def query_all(
        self,
        layer_url: str,
        params: dict[str, object],
        *,
        page_size: int = 2_000,
        max_features: int | None = None,
    ) -> QueryResult:
        self.query_calls.append((layer_url, params))
        values = self.pages.pop(0)
        if max_features is not None:
            values = values[:max_features]
        return QueryResult(features=values, fetched_at=NOW)

    async def request_json(self, url: str, params: dict[str, object]) -> dict[str, Any]:
        if params.get("returnCountOnly"):
            return {"count": self.counts.pop(0)}
        raise AssertionError(f"Unexpected request_json call: {url} {params}")


def service(client: FakeClient) -> DatasetService:
    return DatasetService(client, ACTIVE_URL, YTD_URL)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_search_reports_total_and_truncation() -> None:
    client = FakeClient([[feature(), feature("SECOND")]], counts=[7])

    result = await service(client).search_fires(
        SearchFilters(state="or"), scope=Scope.ACTIVE, sort_by=SortBy.ACRES, limit=2
    )

    assert result.total_count == 7
    assert result.truncated is True
    assert len(result.fires) == 2
    assert result.fires[0].dataset is Scope.ACTIVE
    assert "attr_POOState = 'US-OR'" in str(client.query_calls[0][1]["where"])


@pytest.mark.asyncio
async def test_active_lookup_falls_back_to_ytd() -> None:
    client = FakeClient([[], [feature()]])

    result = await service(client).get_fire(
        irwin_id="11111111-1111-1111-1111-111111111111"
    )

    assert result.status == "found"
    assert result.dataset is Scope.YEAR_TO_DATE
    assert result.message.startswith("Not currently active")
    assert [call[0] for call in client.query_calls] == [ACTIVE_URL, YTD_URL]


@pytest.mark.asyncio
async def test_exact_name_ambiguity_returns_candidates() -> None:
    client = FakeClient([[feature(), feature("TEST", "{22222222-2222-2222-2222-222222222222}")]])

    result = await service(client).get_fire(name="test", state="OR")

    assert result.status == "ambiguous"
    assert len(result.candidates) == 2


def test_invalid_filters_are_clear() -> None:
    with pytest.raises(ValueError, match="two-letter"):
        SearchFilters(state="Oregon").where_clause()
    with pytest.raises(ValueError, match="valid two-letter"):
        SearchFilters(state="ZZ").where_clause()
    with pytest.raises(ValidationError):
        SearchFilters(min_percent_contained=101)
    with pytest.raises(ValidationError, match="min_acres cannot exceed"):
        SearchFilters(min_acres=100, max_acres=10)


@pytest.mark.asyncio
async def test_default_search_response_stays_under_size_budget() -> None:
    client = FakeClient([[feature(f"FIRE {index}") for index in range(25)]], counts=[25])

    result = await service(client).search_fires(SearchFilters())

    assert len(result.model_dump_json().encode()) < 20_000