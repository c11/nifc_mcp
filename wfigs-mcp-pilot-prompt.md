# Build a pilot MCP server for NIFC WFIGS fire perimeters

## Goal

Build a pilot Model Context Protocol (MCP) server that lets an AI assistant answer questions about U.S. wildfires this year using two public NIFC datasets. The server should make the data easy and safe for a language model to use:

- route queries to the right dataset
- normalize confusing fields
- keep heavy polygon geometry out of responses unless explicitly requested
- do spatial math on the server
- attach data-freshness caveats to every answer

This is a pilot. Favor a small, correct, well-tested surface over breadth.

## Data sources

Both are public ArcGIS FeatureServer layers published by NIFC. No authentication is required.

| Name in this doc | Hub page | What it contains |
|---|---|---|
| **Current** | https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-current-interagency-fire-perimeters/about | Perimeters for currently active incidents only. Fires drop out once they meet NIFC's removal criteria. |
| **YearToDate** | https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-2026-interagency-fire-perimeters-to-date/about | All perimeters for the current calendar year, including contained and out fires. |

### Step 0: Discover before you code

Do not hard-code field names or service URLs from memory. First:

1. Resolve each Hub page to its underlying FeatureServer layer URL. Use the ArcGIS Hub / ArcGIS Online item metadata (for example the item's `url` property), or the "API" / "View API Resources" link on the Hub page. I believe the service names are similar to `WFIGS_Interagency_Perimeters_Current` and `WFIGS_Interagency_Perimeters_YearToDate`, but verify this.
2. Fetch each layer's metadata (`<layer_url>?f=json`) and record:
   - fields, types, and aliases
   - `maxRecordCount`
   - supported query formats (confirm `geojson`)
   - geometry type and spatial reference
   - `supportsPagination`
   - `supportsStatistics` / `outStatistics`
   - whether `returnCentroid` is supported
3. Run a few sample queries and inspect the real values.
4. Write what you find to `docs/DATA_NOTES.md`. Cover:
   - field meanings
   - which fields come from the GIS polygon (`poly_*`) versus the IRWIN incident record (`attr_*`)
   - which acreage, date, and containment fields to trust
   - how dates are encoded (expect epoch milliseconds, UTC)
   - quirks such as nulls, duplicate incident names, prescribed burns versus wildfires, and complexes
5. Summarize the findings to me before building the tools, and flag anything that changes the design below.

### Year rollover

The YearToDate dataset name and URL include the year and change every January. Do not hard-code "2026" in logic. Resolve the YearToDate layer through configuration, with a documented way to update it:

- an env var override, and
- a discovery helper that searches the NIFC Hub for the current-year item.

Log which layer URL is in use at startup.

## Tech stack

- **Language:** Python 3.11+
- **MCP framework:** the official `mcp` Python SDK (FastMCP)
- **HTTP:** `httpx` (async), with timeouts and retries (exponential backoff on 429/5xx)
- **Geometry:** `shapely` 2.x for simplification, centroids, and intersection; `pyproj` (`Geod`) for geodesic distances and areas
- **Caching:** an in-memory TTL cache, default 5 minutes and configurable. The upstream data does not change faster than this.
- **Packaging:** `uv` with `pyproject.toml`, runnable via `uvx` / `uv run`
- **Transports:** stdio (default) and Streamable HTTP (flag or env var)
- **Testing:** `pytest`, `pytest-asyncio`, `respx` for mocked HTTP

If you have a strong reason to prefer TypeScript, explain why before switching.

## Tool surface

Design the tools around the wildfire domain, not around ArcGIS. The model should never need to write a `where` clause.

### Shared conventions

- **`scope` parameter:** every query tool takes `scope: "active" | "year_to_date"`, default `"active"`.
  - `active` queries Current.
  - `year_to_date` queries YearToDate.
  - Each response states which dataset was used.
  - If an `active` query by name or ID finds nothing, check YearToDate and say so (for example, "not currently active; found in year-to-date as of …").
- **Normalized record:** return the same compact shape from every tool:
  - `irwin_id`, `name`, `state`, `county` (if available)
  - `acres` (state which source field), `percent_contained`
  - `discovery_date`, `perimeter_updated_at` (ISO 8601 UTC)
  - `incident_type` (wildfire / prescribed fire), `unit_id` / agency
  - `centroid` (`lat`, `lon`), `bbox`
  - `dataset`
- **No geometry by default.** Only `get_perimeter` returns polygons.
- **Freshness and safety:** every response includes:
  - a `data_as_of` timestamp
  - the perimeter age
  - a short `caveat` string saying perimeters can lag ground conditions by a day or more and are not evacuation guidance, and pointing people to local emergency officials and InciWeb (https://inciweb.wildfire.gov)
- **Bounded output:** enforce sensible `limit` defaults (for example 25, max 200), page through upstream results internally, and report `total_count` and `truncated`.
- **Errors:** return clear, model-readable errors (invalid state code, upstream timeout, no results) instead of stack traces.

### Tools

1. **`search_fires`**
   - Filters (all optional): `state` (2-letter), `name_contains` (case-insensitive), `min_acres`, `max_acres`, `discovered_after`, `discovered_before`, `incident_type`, `min_percent_contained`, `max_percent_contained`.
   - Also takes `scope`, `sort_by` (`acres` | `discovery_date` | `perimeter_updated_at`), and `limit`.
   - Returns a list of normalized records.

2. **`get_fire`**
   - Takes `irwin_id` or an exact `name` plus `state`.
   - Returns one normalized record with all useful attributes, including fields omitted from search results.
   - If a name matches several incidents, return candidates rather than guessing.

3. **`fires_near`**
   - Takes `lat`, `lon`, `radius_miles` (default 25, max 250), `scope`, and `limit`.
   - Use an upstream envelope prefilter, then compute on the server with geodesic math:
     - the distance from the point to the nearest perimeter edge
     - whether the point is inside a perimeter (distance 0, `inside: true`)
     - the bearing from the point to the fire
   - Sort by distance.
   - This tool is where the safety caveat matters most.

4. **`summarize_fires`**
   - Takes `group_by` (`state` | `incident_type` | `month` | `agency`), `scope`, and optional filters shared with `search_fires`.
   - Returns counts and total acres per group.
   - Use upstream `outStatistics` where supported; otherwise aggregate on the server.

5. **`get_perimeter`**
   - Takes `irwin_id`, `scope`, `simplify_tolerance_m` (default around 100 m), and `format` (`geojson` | `wkt` | `bbox_only`).
   - Returns geometry in WGS84 plus vertex counts before and after simplification.
   - Refuse or force simplification above a configurable vertex cap, so a single huge fire cannot flood the context window.

### Resources

- **`wfigs://about`** describes both datasets, the difference between them, field meanings (from `DATA_NOTES.md`), data freshness, and the caveat.
- **`wfigs://status`** reports the resolved layer URLs, the last successful fetch time, cache stats, and the latest `perimeter_updated_at` seen per dataset.

### Tool descriptions

Write tool descriptions for an LLM reader. Each one should state:

- when to use the tool versus the others
- the default scope
- that geometry is excluded except in `get_perimeter`
- that `fires_near` needs coordinates, so place names must be geocoded elsewhere first

## Non-goals for the pilot

- No write operations of any kind.
- No other NIFC layers. In particular, the WFIGS Incident Locations join is out of scope. Leave a clearly marked extension point for it, keyed on `irwin_id`.
- No authentication, user accounts, or persistence beyond the in-memory cache.
- No built-in geocoding. The server accepts coordinates only.
- No map rendering or UI.

## Suggested project layout

```
wfigs-mcp/
  pyproject.toml
  README.md
  docs/DATA_NOTES.md
  src/wfigs_mcp/
    server.py        # FastMCP app, tool and resource registration, transports
    config.py        # layer URLs, env overrides, year resolution, limits, TTLs
    arcgis.py        # low-level FeatureServer client: query, paging, stats, retries
    datasets.py      # Current vs YearToDate routing, active-to-YTD fallback
    normalize.py     # raw feature -> normalized record; date and acreage handling
    geo.py           # geodesic distance, bearing, simplification, vertex caps
    cache.py
    caveats.py
  tests/
    fixtures/        # recorded real responses (trimmed) for both layers
    test_normalize.py
    test_geo.py
    test_tools.py    # tool behavior against mocked HTTP
    test_live.py     # opt-in live smoke tests (marked, skipped by default)
```

## Testing and acceptance criteria

**Unit tests (mocked, offline)**

- normalization of real recorded features, including nulls and missing fields
- date conversion
- `scope` routing and the active-to-YTD fallback message
- paging past `maxRecordCount`
- geodesic distance and point-in-perimeter on a known polygon
- simplification and vertex caps
- limit and truncation reporting
- the error paths

**Live smoke tests (opt-in, for example `pytest -m live`)**

- each tool returns well-formed results against the real services
- a known large fire from this year can be found by name in `year_to_date`

**MCP Inspector**

- `npx @modelcontextprotocol/inspector` lists all tools and resources with clear descriptions and schemas

**Size budget**

- No tool response other than `get_perimeter` exceeds roughly 20 KB at default settings. Assert this in tests.

**Claude Code / Claude Desktop config**

- The README includes a working MCP config snippet.
- The README includes 5 example questions and which tools they should trigger, for example:
  - "What are the five largest active fires in Oregon?"
  - "Are there any fires within 30 miles of 39.76, -121.62?"
  - "How many acres have burned in each state so far this year?"
  - "Is the Example Fire still active, and when was its perimeter last updated?"
  - "Show me the perimeter of the largest fire in Idaho."

## How to work

1. Do Step 0 (discovery) and share `DATA_NOTES.md` plus any design concerns before writing tool code.
2. Build bottom-up: `arcgis.py`, then `normalize.py` and `geo.py`, then the tools. Write tests alongside each layer.
3. Record trimmed real responses as fixtures early, so tests reflect actual data.
4. Keep the code readable and typed: Pydantic models for tool inputs and outputs, and `ruff` + `mypy` clean.
5. When done, run the full test suite and the live smoke tests, then give me:
   - a short summary of what works
   - known limitations
   - recommended next steps (for example the Incident Locations join, hosting, rate limiting)
