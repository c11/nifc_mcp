# WFIGS MCP evaluation

## Scope and method

This report describes the automated checks actually present in the repository
and local runs on **2026-11-22**. The project is tested with pytest,
pytest-asyncio, and respx; test and lint/type-check dependencies are declared
in `pyproject.toml`.

The evaluation covers deterministic offline behavior: unit tests, mocked
ArcGIS HTTP interactions, and an in-process MCP client. The normal test command
does **not** make live requests to NIFC, and it does not assess an LLM's tool
selection or generated answer quality.

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
| Live smoke test (`test_live.py`) | Public NIFC services; explicitly opt-in | Exercises search, detail, proximity, summary, and perimeter in YearToDate scope when enabled |

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

The following checks were run locally on **2026-11-22**:

```text
uv run pytest -q
26 passed, 1 skipped in 5.64s

uv run ruff check .
All checks passed!

uv run mypy
Success: no issues found in 10 source files
```

Pytest collected **27 tests**. The single skipped test is the opt-in live NIFC
smoke test in this offline run; the command did not set `WFIGS_RUN_LIVE=1`.
The 26 passing tests use fixtures, fakes, or mocked HTTP.

The live smoke test was then run separately with the opt-in environment
variable:

```text
WFIGS_RUN_LIVE=1 uv run pytest -m live -v
1 passed, 26 deselected in 4.19s
```

It passed on Python 3.12.12. This is one live smoke-test execution, not a
repeated availability or resilience study.

The live test does not hard-code a fire name or incident ID. It searches
YearToDate for one record (`limit=1`), uses the returned IRWIN ID for detail
and bounding-box perimeter lookups, uses the returned centroid as the origin
for a one-mile proximity query, and requests a YearToDate summary grouped by
state. Assertions check that results are present and well-shaped for those
operations; they do not assert specific incident values or counts.

Notable asserted outcomes include:

- `search_fires` with an Oregon filter and limit 2 reports a mocked total of 7
  and marks the result truncated.
- An IRWIN ID absent from Current is found in YearToDate, with the response
  explicitly saying it is not currently active.
- Two matching names produce an ambiguous result with both candidates.
- An inside point returns distance 0; a point west of the square has a
  nearest-edge distance of approximately 5.37 miles (3% relative tolerance)
  and bearing approximately 90 degrees (2-degree tolerance).
- The synthetic perimeter is reduced to no more than 20 vertices.
- A default search response built from 25 mocked records is asserted to be
  under 20,000 serialized bytes.
- MCP discovery exposes the expected five tools and two resources, and a
  client call to `search_fires` returns structured content without an MCP
  error.

The 5.64-second figure is the elapsed time reported for this one local pytest
run; it is **not** a throughput, latency, load, or production performance
benchmark.

## What this evaluation does not establish

- The single live run verifies only the test's selected calls and assertions
  at that time. It does not establish ongoing NIFC availability, resilience
  across service failures, or correctness for all live records. In particular,
  the live smoke test calls the dataset service methods rather than exercising
  an external MCP client session over a deployed transport.
- No benchmark or load test was run; there are no measured latency,
  throughput, concurrency, or resource-usage results.
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

The repository also defines an opt-in live test. It makes requests to public
NIFC services and should only be run when live network access is intended:

```bash
WFIGS_RUN_LIVE=1 uv run pytest -m live
```

The live command was run separately on **2026-11-22** and passed once
(`1 passed, 26 deselected in 4.19s`). Live data can change, so this result is
specific to that execution.
