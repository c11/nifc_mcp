# Wildfire MCP evaluation

## Scope and method

The project is tested with pytest,
pytest-asyncio, and respx; test and lint/type-check dependencies are declared
in `pyproject.toml`.

The evaluation covers deterministic offline behavior, 18 opt-in live correctness
cases, and a separately opt-in, bounded performance measurement. The normal test
command does **not** make live requests to NIFC. None of these checks assess an
LLM's tool selection or generated answer quality.

## How the server is tested

The tests are arranged in layers:

| Test area | Setup | Behaviors checked |
|---|---|---|
| ArcGIS client (`test_arcgis.py`) | `respx` HTTP mocks and an in-memory TTL cache | Retry after HTTP 429, page through two one-record pages and an empty page, cache repeated requests, and turn an ArcGIS error payload into a readable error |
| Configuration (`test_config.py`) | Environment-variable overrides and mocked ArcGIS Online search/metadata responses | Local and Databricks host/port/path defaults; exact current-year item resolution; rejection of ambiguous discovery results |
| Normalization (`test_normalize.py`) | Recorded current and YearToDate feature JSON plus a synthetic nullable record | ID, name, state, acreage, incident type, UTC date, centroid/bbox, acreage fallback, timestamp fallback, and preference for polygon capture time over a newer edit time |
| Geospatial calculations (`test_geo.py`) | Synthetic WGS84 square polygon and a 103-vertex polygon | Inside status and zero distance; outside nearest-edge distance and bearing; simplification to a vertex cap; plausible geodesic area |
| Dataset/tool behavior (`test_tools.py`) | Fake client, synthetic fire records, and fixed timestamps | State filtering, total/truncation reporting, active-to-YearToDate fallback, duplicate-name candidates, invalid filters, and default search response size |
| HTTP-to-tool integration (`test_tool_http.py`) | Mocked ArcGIS feature, count, GeoJSON, and statistics responses | Search normalization and caveat, perimeter fallback/simplification, proximity for a point inside a mocked polygon, and state summary freshness |
| MCP protocol (`test_server.py`) | In-process FastMCP app, mock HTTP transport, and FastMCP client | Five tool names and descriptions, input default, two resource URIs, and a successful structured `search_fires` call |
| Live correctness ([test_live.py](../tests/test_live.py)) | Public NIFC services, shared 300-second cache, dynamically selected incident | 18 cases covering metadata, both scopes, filters, lookups, geometry, proximity, summaries, caching, and in-process MCP |
| Live performance ([test_live_performance.py](../tests/test_live_performance.py)) | Ten uncached Oregon YearToDate searches, concurrency 2, no retries | Latency samples, achieved throughput, errors, HTTP attempts, CPU time, and process peak RSS |

### Representative inputs

The checked-in normalization fixtures are one Current feature named `ECHO`
(California) and one YearToDate feature named `Spout Springs` / `SPOUT
SPRINGS` (Wyoming). Tests use them to check real-shaped ArcGIS attributes,
including null containment, differing polygon and incident acreage fields,
IRWIN ID formatting, and date fields.

Additional synthetic inputs include:

- A feature named `TEST`, state `US-OR`, polygon acreage `10.0`, source acreage
  `9.9`, 25% containment, and a braced IRWIN ID. This is used with mocked
  search, summary, fallback, and MCP requests.
- Two `TEST` records with different IRWIN IDs to verify ambiguous exact-name
  lookups return candidates.
- A WGS84 square with corners near longitude `-121` to `-120.9` and latitude
  `39` to `39.1`; tests query one point inside and one point west of it.
- A 103-vertex synthetic polygon simplified with zero requested tolerance and
  a 20-vertex cap.
- Mock responses for an Oregon summary (3 records, 42.5 perimeter acres), an
  empty Current lookup followed by a YearToDate GeoJSON perimeter, and an
  ArcGIS discovery result titled `WFIGS 2026 Interagency Fire Perimeters to
  Date`.

These are deterministic test inputs, not a representative sample of all
incidents or a measurement of live-service behavior.

## Results

### Current implementation: verified results

The current suite contains **45 collected cases**: 26 offline cases,
18 live correctness cases, and one live performance case. 

| Command | Observed result |
|---|---|
| `uv run pytest -q` | **26 passed, 19 skipped in 1.20s**; neither live opt-in flag set |
| `WFIGS_RUN_LIVE=1 uv run pytest -m 'live and not performance' -v -s` | **18 passed, 27 deselected in 6.80s**; no live correctness skips |
| `WFIGS_RUN_LIVE=1 WFIGS_RUN_PERFORMANCE=1 uv run pytest tests/test_live_performance.py -v -s` | **1 passed in 1.29s** |
| `uv run ruff check .` | All checks passed |
| `uv run mypy` | No issues in 10 source files |
| `uv run mypy tests/test_live.py tests/test_live_performance.py` | No issues in the two new/expanded test files |

Notable offline assertions include:

- `search_fires` with an Oregon filter and limit 2 reports a mocked total of 7
  and marks the result truncated.
- An IRWIN ID absent from Current is found in YearToDate, with the response
  explicitly saying it is not currently active.
- Two matching names produce an ambiguous result with both candidates.
- A point inside the test polygon returns distance 0; a point west of the
  square has a nearest-edge distance of approximately 5.37 miles (3% relative
  tolerance) and bearing approximately 90 degrees (2-degree tolerance).
- A synthetic perimeter is reduced to no more than 20 vertices.
- A default search response built from 25 mocked records is asserted to be
  under 20,000 serialized bytes.
- MCP discovery exposes the expected five tools and two resources, and a
  client call to `search_fires` returns structured content without an MCP
  error.

#### Live correctness design and inputs

The module-scoped service resolves the current-year authoritative YearToDate
layer, uses a 30-second HTTP timeout, and shares a 300-second local cache to
avoid repeatedly downloading the same live geometry. It uses the real public
services, not respx mocks. Cached responses can be reused between cases.

The fixture requests up to 25 YearToDate records between 1 and 1,000 perimeter
acres and selects a record with state, discovery date, and incident type.
This limits geometry size without hard-coding a historical incident. If no
suitable sample exists, dependent cases explicitly skip; HTTP or discovery
failures are not converted to skips. The positive-fallback test also explicitly
skips if the selected record is still in Current.

| # | Case | Input and actual assertion |
|---|---|---|
| 1 | Layer metadata | Both resolved layers: polygon type, positive record limit, pagination, GeoJSON, and required ID/acreage/capture-time fields |
| 2 | Current search | Default active scope, limit 5: bounded normalized records, truncation and safety/freshness contract; an empty Current layer is allowed |
| 3 | YearToDate search | Default limit 25: descending acreage order, normalized IDs/fields, no geometry, and serialized response **below 20,000 bytes** |
| 4 | Combined filters | Sample's lowercase state/name, type, discovery day, and acreage range: nonempty response and matching state/type/date/acreage |
| 5 | Detail by ID | Lowercase, braced sample IRWIN ID: canonical ID returned, `found`, YearToDate identity and freshness |
| 6 | Exact name | Lowercase sample name plus state: found or ambiguous, sample ID among results, no silent selection of a different incident |
| 7 | Missing ID | Generated UUID, default active lookup: `not_found` after both scopes, no candidates, explicit message and caveat |
| 8 | Positive fallback | Sample ID through active lookup: YearToDate match with disclosed fallback, unless sample is also in Current |
| 9 | GeoJSON perimeter | Sample ID: valid nonempty WGS84 polygon, actual vertex count agrees with response and stays within configured cap |
| 10 | WKT perimeter | Same ID: parseable valid polygon with matching vertex count and WGS84 coordinate bounds |
| 11 | Bounding box | Same ID: five-vertex envelope whose bounds match separately fetched unsimplified upstream geometry |
| 12 | Proximity | Interior representative point from raw upstream geometry, radius 1 mile, limit 25: includes sample with inside=true/distance=0/no bearing; results sorted and within radius |
| 13 | State summary | Sample state/name filter: nonempty positive counts, finite nonnegative acreage, expected state, freshness and acreage caveat |
| 14 | Incident-type summary | Same filter: expected sample type present, valid counts/acreage and caveats |
| 15 | Month summary | Same filter: sample discovery month present, valid counts/acreage and caveats |
| 16 | Agency summary | Same filter: sample agency (or explicit unknown) present, valid counts/acreage and caveats |
| 17 | Cache behavior | Repeat identical sample-based search: at least two new cache hits and unchanged response/fetch time |
| 18 | MCP integration | In-process FastMCP client calls YearToDate search against live NIFC and reads both resources; validates structured response, caveat, resolved layer and fetch/cache status |

The recorded fixture for this execution was **Avocado, FL**, IRWIN ID
`631068D8-5EB9-4691-AC75-8DE060A1763C`, wildfire, **999.638448212376**
perimeter acres, discovered **2026-07-07T19:34:00Z**, agency **NPS**. Reported
containment was null; the tests did not reinterpret it as zero.

The raw polygon's interior test point was **25.4199855520001,
-80.93577514744953**. The generated missing ID was
`6a8cceaa-fda9-499e-8fb8-bdb457247083`. These inputs are printed under `-s`
so later runs can be audited without assuming that the same fire remains in
the changing dataset.

#### Performance setup

The benchmark runs in a **separate pytest process** from live correctness tests.
It measures `DatasetService.search_fires`, not a deployed HTTP MCP endpoint:

- **10 total operations**, at most **2 concurrent**; no automatic load ramp.
- Fixed inputs: `state="OR"`, `scope="year_to_date"`, `limit=5`.
- Local cache TTL **0**, retries **0**, timeout **30 seconds**.
- Discovery and environment setup happen before the measured interval.
- Each search normally makes two upstream requests (count and feature query).
- A shared HTTP connection pool is reused; connections are not reset between
  operations. NIFC or intermediary caching is outside the test's control.
- Latency is measured with `time.perf_counter()` after semaphore acquisition,
  so it includes the service call but excludes waiting for a concurrency slot.
- Throughput is successful searches divided by wall time for the entire batch.
- All operation latency samples, failures, HTTP attempts, and cache hits are
  emitted as JSON. Recognized request/validation failures are reported and then
  fail the test; they are not counted as successes.
- There is **no latency, throughput, or resource pass/fail target**. The test
  checks successful operations and zero local cache hits, rather than claiming
  an unapproved service-level objective.

#### Measured performance and resource usage

| Metric | Observed value |
|---|---:|
| Successful / failed searches | **10 / 0** |
| Upstream HTTP attempts | **20** |
| Local cache hits | **0** |
| Measured batch wall time | **0.952618 seconds** |
| Achieved successful search throughput | **10.4974 searches/second** |
| Minimum latency | **30.2730 ms** |
| Median latency | **33.1657 ms** |
| p95 latency, nearest-rank | **819.8705 ms** |
| Maximum latency | **819.8705 ms** |
| Local process user CPU time during batch | **0.034020 seconds** |
| Local process system CPU time during batch | **0.006652 seconds** |
| CPU utilization relative to one core | **4.2695%** |
| Process lifetime peak RSS before batch | **78.0000 MiB** |
| Process lifetime peak RSS after batch | **78.7656 MiB** |

Sorted latency samples (ms, rounded):
`30.2730, 31.9083, 32.2113, 32.6541, 33.0997, 33.2317, 34.0957, 35.6761, 817.4610, 819.8705`.

CPU is measured with `resource.getrusage(RUSAGE_SELF)` deltas. Peak RSS is
`ru_maxrss`, converted from bytes on macOS or KiB on Linux. These measurements
belong to the local pytest process containing the service and client; they are
**not NIFC server measurements**. RSS is a process-lifetime high-water mark,
including imports and setup, not current memory, an allocation delta, or a
memory-leak test. The benchmark explicitly skips resource measurement on
platforms other than macOS/Linux.

With only ten samples, nearest-rank p95 equals the maximum. This sub-second
batch is an observed workload result, **not sustained capacity or a reliable
tail-latency estimate**. The run did not isolate DNS/TLS/connection setup from
upstream response time, so causes of the two slower samples were not measured.

## What this evaluation does not establish

- Live checks establish the selected assertions at execution time, not ongoing
  availability or correctness for every record. Changes between related
  upstream calls can cause assertion failures; the suite does not mask those
  with a retry-until-pass strategy.
- Most cases call dataset service methods. One also uses an in-process MCP
  client with real upstream data; none tests an external stdio process or
  deployed Streamable HTTP transport, ingress, authentication, or network proxy.
- The bounded search benchmark does not measure other tools, sustained load,
  maximum capacity, production resource consumption, or network transfer volume.
- Summary cases validate shape, grouping and caveats for filtered data, not an
  independent recomputation of all nationwide acreage/counts.
- No LLM evaluation was run; tool choice, answer correctness, and safety
  behavior across model-generated conversations were not measured.
- The tests cover selected examples and branches, not exhaustive geographic
  edge cases, all upstream schema changes, or every possible malformed
  response.
- A passing static type and lint check does not prove deployment reliability
  or operational readiness.

## Reproduce

From the repository root, install/sync the declared project environment and
run the same offline and static checks:

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run mypy
```

Run live correctness only when access to public NIFC services is intended:

```bash
WFIGS_RUN_LIVE=1 uv run pytest -m 'live and not performance' -v -s
```

Run the separately approved, bounded benchmark in a fresh process:

```bash
WFIGS_RUN_LIVE=1 WFIGS_RUN_PERFORMANCE=1 \
  uv run pytest tests/test_live_performance.py -v -s
```

`-s` shows the chosen correctness inputs and the JSON benchmark measurements.
The second flag prevents routine live correctness runs from accidentally
benchmarking the public service. Do not parallelize correctness and performance
runs when interpreting process CPU/RSS measurements.
