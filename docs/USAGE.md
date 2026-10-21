# Using the WFIGS MCP server

This guide explains how to connect an MCP client to the WFIGS server, ask
wildfire questions, choose the right tool, and interpret the results.

The server is read-only. It queries public NIFC WFIGS perimeter data and does
not modify upstream records.

> Wildfire perimeters can lag ground conditions by a day or more and are not
> evacuation guidance. Follow local emergency officials and consult
> [InciWeb](https://inciweb.wildfire.gov).

## 1. Install and test the server

Requirements:

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

From the project directory:

```bash
uv sync
uv run wfigs-mcp --help
```

The default transport is stdio. Normally an MCP client starts the stdio server
for you, so you do not need to keep it running in a separate terminal.

At startup, the server logs the resolved Current and YearToDate NIFC layer URLs
to stderr. The YearToDate layer is discovered for the current UTC year.

## 2. Connect an MCP client

Replace `/absolute/path/to/nifc_mcp` with this project's absolute path.

### Claude Desktop

Add this entry to the Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "wfigs": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/nifc_mcp",
        "run",
        "wfigs-mcp"
      ]
    }
  }
}
```

Restart Claude Desktop after changing its configuration. The client should
show a server named `wfigs` with five tools and two resources.

### Claude Code

```bash
claude mcp add wfigs -- uv --directory /absolute/path/to/nifc_mcp run wfigs-mcp
```

### Other stdio MCP clients

Use these process settings:

| Setting | Value |
| --- | --- |
| Command | `uv` |
| Arguments | `--directory /absolute/path/to/nifc_mcp run wfigs-mcp` |
| Transport | stdio |

The client must pass each argument separately rather than treating the entire
argument string as one value.

### Streamable HTTP

For clients that connect to an HTTP MCP endpoint:

```bash
uv run wfigs-mcp --transport streamable-http
```

Connect the client to:

```text
http://127.0.0.1:8000/mcp
```

Keep this process running while the client is connected. Change the bind
address and port with `WFIGS_HOST` and `WFIGS_PORT`.

## 3. Choose a dataset scope

Every query tool accepts `scope`:

| Scope | Meaning | Use it when |
| --- | --- | --- |
| `active` | NIFC Current perimeters; this is the default | Asking about recent or ongoing incidents |
| `year_to_date` | All qualifying perimeters for the current calendar year | Asking about contained, out, historical-this-year, or annual totals |

Current membership is not a guarantee that conditions are active on the
ground. NIFC also removes stale records according to size-dependent fall-off
rules.

`get_fire` and `get_perimeter` automatically check YearToDate when an
`active` lookup by name or IRWIN ID finds nothing. Their response says when the
fallback occurred.

## 4. Use the tools

### `search_fires`

Use this tool for a bounded list of fires matching filters. It does not return
polygon geometry.

Parameters:

| Parameter | Type | Notes |
| --- | --- | --- |
| `state` | string | Valid two-letter U.S. state or territory code, such as `OR` |
| `name_contains` | string | Case-insensitive partial incident name |
| `min_acres`, `max_acres` | number | Filter geodesic perimeter acres |
| `discovered_after`, `discovered_before` | date | ISO date such as `2026-07-01` |
| `incident_type` | enum | `wildfire` or `prescribed_fire` |
| `min_percent_contained`, `max_percent_contained` | number | Values from 0 through 100 |
| `scope` | enum | `active` by default; otherwise `year_to_date` |
| `sort_by` | enum | `acres`, `discovery_date`, or `perimeter_updated_at` |
| `limit` | integer | 25 by default; maximum 200 |

Example prompts:

- "What are the five largest active wildfires in Oregon?"
- "Find prescribed fires discovered after 2026-09-01 in California."
- "List year-to-date fires between 1,000 and 10,000 perimeter acres."

Responses report `total_count` and `truncated`. If `truncated` is true, the
tool returned only the requested leading records.

### `get_fire`

Use this tool for one incident's details. Supply exactly one lookup method:

- `irwin_id`, or
- exact `name` together with two-letter `state`.

`scope` defaults to `active`. Name matches are not assumed to be unique. If
several records match, the response returns candidates instead of guessing.

Example prompts:

- "Is the Park Fire in CA still active, and when was its perimeter captured?"
- "Get the incident with IRWIN ID 11111111-1111-1111-1111-111111111111."

Use the returned `irwin_id` for an unambiguous follow-up call to
`get_perimeter`.

### `fires_near`

Use this tool to find perimeters near a coordinate. It requires decimal-degree
WGS84 coordinates; the server does not geocode place names.

| Parameter | Type | Notes |
| --- | --- | --- |
| `lat` | number | Latitude from -90 through 90 |
| `lon` | number | Longitude from -180 through 180 |
| `radius_miles` | number | 25 by default; greater than 0 and at most 250 |
| `scope` | enum | `active` by default |
| `limit` | integer | 25 by default; maximum 200 |

Example prompt:

> Are any active fire perimeters within 30 miles of 39.76, -121.62?

The server first performs an upstream spatial prefilter and then calculates
locally against polygon geometry:

- `distance_miles`: geodesic distance to the nearest perimeter edge
- `inside`: true when the point is inside or on the perimeter
- `bearing_degrees`: direction from the supplied point to the nearest edge;
  null when the point is inside

Distance is to the perimeter, not to the fire's centroid or ignition point.

### `summarize_fires`

Use this tool for grouped counts and perimeter-acre totals. Set `group_by` to:

- `state`
- `incident_type`
- `month`
- `agency`

It accepts the same optional filters as `search_fires` and defaults to active
data.

Example prompts:

- "How many fires and perimeter acres are represented in each state this year?"
- "Group active incidents by wildfire versus prescribed fire."
- "Summarize year-to-date fires by discovery month in Washington."

The returned acreage is summed from perimeter polygons. It is not a definitive
amount burned: overlapping complex and child perimeters can be double-counted,
and polygons can contain unburned islands.

### `get_perimeter`

This is the only tool that returns polygon geometry. It requires an `irwin_id`.

| Parameter | Type | Notes |
| --- | --- | --- |
| `irwin_id` | string | UUID returned by another tool |
| `scope` | enum | `active` by default, with YearToDate fallback |
| `simplify_tolerance_m` | number | 100 meters by default |
| `format` | enum | `geojson`, `wkt`, or `bbox_only` |

Use `bbox_only` when the full shape is unnecessary. Use `geojson` for mapping
software and `wkt` for systems that consume Well-Known Text.

The response reports:

- vertex counts before and after simplification
- the actual simplification tolerance applied
- WGS84 geometry

The server can increase the requested tolerance to enforce its configured
vertex cap. This prevents a large perimeter from flooding the model context.

## 5. Read the resources

The server exposes two JSON resources:

| Resource | Contents |
| --- | --- |
| `wfigs://about` | Dataset differences, normalized field meanings, and the safety caveat |
| `wfigs://status` | Resolved layer URLs, last successful fetch, cache counters, and latest observed perimeter timestamps |

Ask an MCP client to read them directly, for example:

- "Read `wfigs://about` and explain which acreage field the server uses."
- "Read `wfigs://status` and show the current layer URLs and cache status."

## 6. Interpret a normalized fire record

Common fields returned by search, detail, and proximity tools:

| Field | Meaning |
| --- | --- |
| `irwin_id` | Canonical incident identifier used for follow-up calls |
| `name`, `state`, `county` | Incident identity and point-of-origin geography |
| `acres` | Selected perimeter area |
| `acres_source` | Upstream field that supplied `acres` |
| `percent_contained` | Reported IRWIN value; null means unknown, not zero |
| `discovery_date` | Incident discovery time in ISO 8601 UTC |
| `perimeter_updated_at` | Polygon capture time, or a labeled fallback timestamp |
| `perimeter_updated_source` | Upstream timestamp field used for freshness |
| `incident_type` | `wildfire` or `prescribed_fire` |
| `unit_id`, `agency` | Protecting unit/agency with jurisdictional fallback |
| `centroid`, `bbox` | Compact location information, not the full polygon |
| `dataset` | `active` or `year_to_date` |

Every response includes a `data_as_of` timestamp, perimeter age information,
and a safety caveat. `data_as_of` describes when the server fetched the data;
it is not the same as the time the perimeter was captured.

## 7. Inspect and troubleshoot

List tools and resources with MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uv --directory "$PWD" run wfigs-mcp
```

Common problems:

| Symptom | Resolution |
| --- | --- |
| Client cannot start `uv` | Configure the absolute path returned by `command -v uv` |
| Client starts in the wrong directory | Include `--directory /absolute/path/to/nifc_mcp` in the arguments |
| YearToDate discovery finds zero or multiple services | Set `WFIGS_YTD_LAYER_URL` to a verified current-year layer URL |
| Invalid state error | Use a valid two-letter code such as `CA`, not a full state name |
| Name lookup is ambiguous | Select a returned candidate and retry with its `irwin_id` |
| No results in active scope | Retry with `scope="year_to_date"`; exact lookups do this automatically |
| Place name cannot be used with `fires_near` | Geocode it elsewhere and pass decimal `lat` and `lon` |
| Upstream timeout or HTTP error | Retry shortly; the server already retries 429 and 5xx responses with backoff |
| Geometry is more simplified than requested | The server increased tolerance to satisfy the vertex safety cap |

For verified source metadata and field precedence details, see
[DATA_NOTES.md](DATA_NOTES.md).