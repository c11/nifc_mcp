# WFIGS MCP

A read-only Model Context Protocol server for public NIFC WFIGS wildfire
perimeters. It routes active and year-to-date queries, normalizes the ArcGIS
schema, performs spatial calculations server-side, and keeps polygon geometry
out of ordinary responses. The MCP application layer uses
[Prefect FastMCP](https://gofastmcp.com/).

For client setup, tool parameters, prompt examples, and troubleshooting, see
[docs/USAGE.md](docs/USAGE.md).

For Databricks Apps architecture, required compatibility changes, deployment,
OAuth, and operations, see
[docs/DATABRICKS_DEPLOYMENT.md](docs/DATABRICKS_DEPLOYMENT.md).

Perimeters can lag ground conditions by a day or more. This server is not a
source of evacuation guidance. Follow local emergency officials and consult
[InciWeb](https://inciweb.wildfire.gov).

## Requirements and setup

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync
uv run wfigs-mcp
```

The default transport is stdio. The server discovers the authoritative
current-year YearToDate ArcGIS item at startup and logs both resolved layer
URLs to stderr.

To run Streamable HTTP at `http://127.0.0.1:8000/mcp`:

```bash
uv run wfigs-mcp --transport streamable-http
```

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `WFIGS_CURRENT_LAYER_URL` | NIFC Current layer | Override the Current FeatureServer layer |
| `WFIGS_YTD_LAYER_URL` | discovered for the UTC year | Override the YearToDate layer, especially during January rollover |
| `WFIGS_CACHE_TTL_SECONDS` | `300` | In-memory query cache lifetime |
| `WFIGS_TIMEOUT_SECONDS` | `20` | Upstream HTTP timeout |
| `WFIGS_MAX_RETRIES` | `3` | Retries for HTTP 429 and 5xx responses |
| `WFIGS_MAX_LIMIT` | `200` | Maximum records returned by bounded tools |
| `WFIGS_VERTEX_CAP` | `10000` | Maximum perimeter vertices after forced simplification |
| `WFIGS_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `WFIGS_HOST` | `127.0.0.1` locally; `0.0.0.0` on Databricks | Streamable HTTP bind address |
| `WFIGS_PORT` | `8000` or `DATABRICKS_APP_PORT` | Streamable HTTP port |
| `WFIGS_STREAMABLE_HTTP_PATH` | `/mcp` | Streamable HTTP endpoint path |

Every January, the discovery helper searches ArcGIS Online for the exact title
`WFIGS <year> Interagency Fire Perimeters to Date`, owned by
`NIFC_Authoritative`, verifies layer 0 is a polygon layer, and fails closed on
zero or multiple matches. Set `WFIGS_YTD_LAYER_URL` to a verified layer URL if
NIFC's rollover is delayed or naming changes.

## MCP client configuration

Claude Desktop configuration, replacing the path with this checkout:

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

Claude Code:

```bash
claude mcp add wfigs -- uv --directory /absolute/path/to/nifc_mcp run wfigs-mcp
```

The package can also be launched from a local checkout without syncing first:

```bash
uvx --from /absolute/path/to/nifc_mcp wfigs-mcp
```

## Tools

- `search_fires`: bounded filtering and sorting of normalized fires.
- `get_fire`: exact ID or name/state lookup with active-to-YTD fallback.
- `fires_near`: point-to-perimeter distance, inside status, and bearing. It
	accepts coordinates only; geocode place names elsewhere.
- `summarize_fires`: counts and perimeter-acre totals by state, incident type,
	month, or agency.
- `get_perimeter`: the only geometry-returning tool; emits simplified WGS84
	GeoJSON, WKT, or a bounding box.

All query tools default to `scope="active"`. Set `scope="year_to_date"` for
contained, out, or otherwise non-current incidents from this calendar year.
Ordinary responses include dataset identity, fetch time, perimeter age, and a
safety caveat. Null containment means unknown, not zero.

The resources `wfigs://about` and `wfigs://status` expose dataset semantics and
runtime layer/cache/freshness status.

## Example questions

| Question | Expected tool |
| --- | --- |
| "What are the five largest active fires in Oregon?" | `search_fires` with `state="OR"`, acreage sorting, and `limit=5` |
| "Are there fires within 30 miles of 39.76, -121.62?" | `fires_near` with those coordinates and `radius_miles=30` |
| "How many perimeter acres are represented in each state so far this year?" | `summarize_fires` grouped by state with `scope="year_to_date"` |
| "Is the Example Fire still active, and when was its perimeter captured?" | `get_fire` by exact name and state, using active fallback |
| "Show me the perimeter of the largest fire in Idaho." | `search_fires`, then `get_perimeter` using its IRWIN ID |

Perimeter-acre totals are not definitive burned area. Parent/child complexes
and overlapping polygons can double-count land, and perimeters may contain
unburned islands.

## Development and verification

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

Live tests are opt-in because they call continuously changing public services:

```bash
WFIGS_RUN_LIVE=1 uv run pytest -m live
```

Inspect the MCP schemas and resources interactively:

```bash
npx @modelcontextprotocol/inspector uv --directory "$PWD" run wfigs-mcp
```

Verified source metadata, field inventory, precedence rules, and observed data
quirks are documented in [docs/DATA_NOTES.md](docs/DATA_NOTES.md).

## Known limitations

- WFIGS does not publish a perimeter for every incident.
- No geocoder, map UI, writes, authentication, or persistent cache is included.
- Proximity uses an upstream envelope prefilter followed by local geodesic
	calculations; broad YearToDate searches can require multiple ArcGIS pages.
- Acreage summaries can double-count overlapping complex/child perimeters.
- Incident Locations data is intentionally out of scope. The typed
	`IncidentLocationEnricher` extension accepts future enrichment keyed only by
	canonical `irwin_id`.