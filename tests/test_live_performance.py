from __future__ import annotations

import asyncio
import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import UTC, datetime

import httpx
import pytest

from wfigs_mcp.arcgis import ArcGISClient, ArcGISError, JsonObject
from wfigs_mcp.cache import TTLCache
from wfigs_mcp.config import CURRENT_LAYER_URL, resolve_ytd_layer_url
from wfigs_mcp.datasets import DatasetService, SearchFilters
from wfigs_mcp.normalize import Scope

pytestmark = [
    pytest.mark.live,
    pytest.mark.performance,
    pytest.mark.skipif(
        os.getenv("WFIGS_RUN_LIVE") != "1" or os.getenv("WFIGS_RUN_PERFORMANCE") != "1",
        reason="Set both WFIGS_RUN_LIVE=1 and WFIGS_RUN_PERFORMANCE=1 for the public benchmark",
    ),
]


@pytest.mark.asyncio
async def test_live_search_latency_throughput_and_resources() -> None:
    if sys.platform not in {"darwin", "linux"}:
        pytest.skip("Process RSS measurement currently supports macOS and Linux only")
    import resource

    request_count, concurrency = 10, 2
    http_attempts = 0

    async def count_request(_: httpx.Request) -> None:
        nonlocal http_attempts
        http_attempts += 1

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=30, event_hooks={"request": [count_request]}
    ) as http:
        ytd_url = await resolve_ytd_layer_url(http)
        client = ArcGISClient(
            http, TTLCache[JsonObject](0), timeout_seconds=30, max_retries=0
        )
        service = DatasetService(client, CURRENT_LAYER_URL, ytd_url)
        semaphore = asyncio.Semaphore(concurrency)

        async def search() -> tuple[float, str | None]:
            async with semaphore:
                start = time.perf_counter()
                error = None
                try:
                    result = await service.search_fires(
                        SearchFilters(state="OR"), scope=Scope.YEAR_TO_DATE, limit=5
                    )
                    assert result.dataset is Scope.YEAR_TO_DATE
                    assert result.total_count >= len(result.fires)
                    assert len(result.fires) <= 5
                    assert all(fire.state == "OR" for fire in result.fires)
                except (ArcGISError, httpx.HTTPError, ValueError, AssertionError) as exc:
                    error = f"{type(exc).__name__}: {exc}"
                return time.perf_counter() - start, error

        http_attempts = 0
        started_at = datetime.now(UTC)
        before = resource.getrusage(resource.RUSAGE_SELF)
        start = time.perf_counter()
        results = await asyncio.gather(*(search() for _ in range(request_count)))
        elapsed = time.perf_counter() - start
        after = resource.getrusage(resource.RUSAGE_SELF)

        latencies = sorted(duration * 1_000 for duration, _ in results)
        errors = [error for _, error in results if error is not None]
        successful = request_count - len(errors)
        cpu_user = after.ru_utime - before.ru_utime
        cpu_system = after.ru_stime - before.ru_stime
        # macOS reports ru_maxrss in bytes; Linux reports KiB. Both are lifetime high-water marks.
        rss_unit = 1 if sys.platform == "darwin" else 1_024
        report = {
            "started_at": started_at.isoformat(),
            "python": platform.python_version(),
            "platform": sys.platform,
            "layer_url": ytd_url,
            "operation": "DatasetService.search_fires",
            "inputs": {"state": "OR", "scope": "year_to_date", "limit": 5},
            "requests": request_count,
            "concurrency": concurrency,
            "cache_ttl_seconds": 0,
            "max_retries": 0,
            "upstream_http_attempts": http_attempts,
            "cache_hits": client.cache_stats.hits,
            "successful_requests": successful,
            "failed_requests": len(errors),
            "errors": errors,
            "elapsed_seconds": elapsed,
            "successful_requests_per_second": successful / elapsed,
            "latency_ms": {
                "samples_sorted": latencies,
                "min": min(latencies),
                "median": statistics.median(latencies),
                "p95_nearest_rank": latencies[math.ceil(0.95 * len(latencies)) - 1],
                "max": max(latencies),
            },
            "cpu_user_seconds": cpu_user,
            "cpu_system_seconds": cpu_system,
            "cpu_one_core_percent": 100 * (cpu_user + cpu_system) / elapsed,
            "process_peak_rss_before_mib": before.ru_maxrss * rss_unit / 1_048_576,
            "process_peak_rss_after_mib": after.ru_maxrss * rss_unit / 1_048_576,
        }
        print("\nWFIGS_LIVE_BENCHMARK " + json.dumps(report, indent=2))
        assert not errors, f"Benchmark request failures: {errors}"
        assert client.cache_stats.hits == 0, "Benchmark must not measure local cache hits"
        assert successful == request_count
