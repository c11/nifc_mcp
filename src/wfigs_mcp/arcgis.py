from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from .cache import CacheStats, TTLCache

JsonObject = dict[str, Any]
Sleep = Callable[[float], Awaitable[None]]


class ArcGISError(RuntimeError):
    """Base error for model-readable upstream failures."""


class ArcGISTimeoutError(ArcGISError):
    pass


class ArcGISResponseError(ArcGISError):
    pass


@dataclass(frozen=True, slots=True)
class QueryResult:
    features: list[JsonObject]
    fetched_at: datetime


class ArcGISClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        cache: TTLCache[JsonObject],
        *,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.25,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._http = http
        self._cache = cache
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self.last_successful_fetch: datetime | None = None
        self.last_response_as_of: datetime | None = None
        self._cache_fetched_at: dict[str, datetime] = {}

    @property
    def cache_stats(self) -> CacheStats:
        return self._cache.stats

    async def aclose(self) -> None:
        await self._http.aclose()

    async def request_json(self, url: str, params: Mapping[str, object]) -> JsonObject:
        normalized = {key: self._serialize(value) for key, value in params.items()}
        cache_key = self._cache_key(url, normalized)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self.last_response_as_of = self._cache_fetched_at.get(cache_key)
            return cached

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.get(
                    url,
                    params=normalized,
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                if attempt == self._max_retries:
                    raise ArcGISTimeoutError(
                        "The NIFC ArcGIS service timed out. Try again shortly."
                    ) from exc
                await self._sleep(self._backoff_seconds * (2**attempt))
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == self._max_retries:
                    raise ArcGISResponseError(
                        f"The NIFC ArcGIS service returned HTTP {response.status_code}."
                    )
                await self._sleep(self._backoff_seconds * (2**attempt))
                continue

            try:
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPStatusError, json.JSONDecodeError) as exc:
                raise ArcGISResponseError(
                    "The NIFC ArcGIS service returned an invalid response."
                ) from exc
            if not isinstance(payload, dict):
                raise ArcGISResponseError(
                    "The NIFC ArcGIS service returned an invalid JSON object."
                )
            if "error" in payload:
                error = payload["error"]
                message = (
                    error.get("message", "ArcGIS query failed")
                    if isinstance(error, dict)
                    else str(error)
                )
                raise ArcGISResponseError(f"The NIFC ArcGIS service rejected the query: {message}")

            result = dict(payload)
            fetched_at = datetime.now(UTC)
            self.last_successful_fetch = fetched_at
            self.last_response_as_of = fetched_at
            self._cache.set(cache_key, result)
            self._cache_fetched_at[cache_key] = fetched_at
            return result

        raise AssertionError("retry loop exited unexpectedly")

    async def query_all(
        self,
        layer_url: str,
        params: Mapping[str, object],
        *,
        page_size: int = 2_000,
        max_features: int | None = None,
    ) -> QueryResult:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        query_url = f"{layer_url.rstrip('/')}/query"
        base_params: dict[str, object] = {"f": "json", "where": "1=1", **params}
        base_params.pop("resultOffset", None)
        base_params.pop("resultRecordCount", None)

        features: list[JsonObject] = []
        offset = 0
        while max_features is None or len(features) < max_features:
            requested = page_size
            if max_features is not None:
                requested = min(requested, max_features - len(features))
            payload = await self.request_json(
                query_url,
                {
                    **base_params,
                    "resultOffset": offset,
                    "resultRecordCount": requested,
                },
            )
            page = payload.get("features")
            if not isinstance(page, list):
                raise ArcGISResponseError("The ArcGIS query response omitted the feature list.")
            typed_page = [feature for feature in page if isinstance(feature, dict)]
            features.extend(typed_page)
            if len(page) < requested:
                break
            offset += len(page)

        fetched_at = self.last_response_as_of or datetime.now(UTC)
        return QueryResult(features=features, fetched_at=fetched_at)

    @staticmethod
    def _serialize(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _cache_key(url: str, params: Mapping[str, str]) -> str:
        return json.dumps([url, sorted(params.items())], separators=(",", ":"))
