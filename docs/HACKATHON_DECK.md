---
marp: true
theme: default
paginate: true
size: 16:9
title: WFIGS MCP - Trustworthy Wildfire Intelligence for AI
description: Hackathon submission deck for the NIFC WFIGS MCP server
style: |
  :root {
    --navy: #102a43;
    --blue: #1565c0;
    --sky: #d9efff;
    --orange: #f05a28;
    --gold: #ffb000;
    --cream: #fffaf2;
    --ink: #243b53;
    --muted: #627d98;
    --green: #177245;
  }
  section {
    background: linear-gradient(135deg, #ffffff 0%, var(--cream) 100%);
    color: var(--ink);
    font-family: "Aptos", "Helvetica Neue", Arial, sans-serif;
    font-size: 27px;
    padding: 52px 66px;
  }
  section::after {
    color: var(--muted);
    font-size: 15px;
  }
  h1, h2, h3 {
    color: var(--navy);
    letter-spacing: -0.02em;
  }
  h1 {
    font-size: 54px;
    line-height: 1.05;
  }
  h2 {
    border-left: 8px solid var(--orange);
    font-size: 40px;
    padding-left: 18px;
  }
  strong {
    color: var(--blue);
  }
  code {
    background: #edf2f7;
    color: var(--navy);
  }
  blockquote {
    background: #ffffff;
    border-left: 7px solid var(--gold);
    box-shadow: 0 8px 24px rgba(16, 42, 67, 0.10);
    margin: 24px 0;
    padding: 18px 28px;
  }
  table {
    font-size: 23px;
  }
  th {
    background: var(--navy);
    color: white;
  }
  .title {
    background:
      radial-gradient(circle at 88% 20%, rgba(255, 176, 0, 0.24) 0 10%, transparent 11%),
      linear-gradient(135deg, var(--navy) 0%, #164e73 62%, var(--blue) 100%);
    color: white;
  }
  .title h1, .title h2, .title strong {
    color: white;
  }
  .title h1 {
    font-size: 62px;
    max-width: 880px;
  }
  .title p {
    color: var(--sky);
    font-size: 30px;
    max-width: 880px;
  }
  .title::after {
    color: var(--sky);
  }
  .eyebrow {
    color: var(--orange);
    font-size: 19px;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }
  .cards {
    display: flex;
    gap: 22px;
    margin-top: 24px;
  }
  .card {
    background: white;
    border-radius: 14px;
    box-shadow: 0 8px 22px rgba(16, 42, 67, 0.10);
    flex: 1;
    padding: 24px;
  }
  .card h3 {
    color: var(--blue);
    font-size: 26px;
    margin: 0 0 12px;
  }
  .metric {
    color: var(--orange);
    font-size: 44px;
    font-weight: 800;
    line-height: 1;
  }
  .small {
    color: var(--muted);
    font-size: 18px;
  }
  .flow {
    align-items: center;
    display: flex;
    gap: 14px;
    justify-content: center;
    margin-top: 44px;
  }
  .node {
    background: white;
    border: 2px solid var(--sky);
    border-radius: 16px;
    box-shadow: 0 8px 20px rgba(16, 42, 67, 0.10);
    padding: 22px 18px;
    text-align: center;
    width: 190px;
  }
  .node strong {
    display: block;
    font-size: 26px;
  }
  .arrow {
    color: var(--orange);
    font-size: 36px;
    font-weight: 800;
  }
  .pill {
    background: var(--sky);
    border-radius: 999px;
    color: var(--navy);
    display: inline-block;
    font-size: 19px;
    font-weight: 700;
    margin: 4px;
    padding: 7px 14px;
  }
  .demo {
    background: #0b1f33;
    border-radius: 16px;
    color: #e6f4ff;
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 21px;
    line-height: 1.5;
    padding: 25px 30px;
  }
  .demo strong {
    color: #7dd3fc;
  }
  .check {
    color: var(--green);
    font-weight: 800;
  }
  .closing {
    background: linear-gradient(135deg, var(--navy), #0c4a6e);
    color: white;
  }
  .closing h1, .closing h2, .closing strong {
    color: white;
  }
  .closing p, .closing li {
    color: #e6f4ff;
  }
---

<!-- _class: title -->

<div class="eyebrow">MCP Hackathon Submission</div>

# WFIGS MCP

## Trustworthy wildfire perimeter intelligence for AI assistants

Natural-language questions in. Safe, normalized, spatially accurate NIFC answers out.

**Python + FastMCP + ArcGIS + Shapely + PyProj**

---

## The problem: public data is not yet AI-ready

NIFC publishes authoritative wildfire perimeter data, but an assistant must still navigate:

<div class="cards">
  <div class="card">
    <h3>Two datasets</h3>
    Active incidents and year-to-date history answer different questions.
  </div>
  <div class="card">
    <h3>Complex GIS schemas</h3>
    118 shared fields, duplicate names, nulls, and competing acreage and date values.
  </div>
  <div class="card">
    <h3>Heavy geometry</h3>
    Raw polygons waste context and centroid distance can be dangerously misleading.
  </div>
</div>

> A generic ArcGIS query tool exposes implementation details. A wildfire assistant needs domain meaning, bounded output, and safety context.

---

## Our solution: a domain-native MCP server

WFIGS MCP converts public NIFC FeatureServers into **five intent-level tools**:

| User intent | MCP tool | What the model receives |
|---|---|---|
| Find matching incidents | `search_fires` | Bounded, normalized records |
| Inspect one incident | `get_fire` | Exact details or honest candidates |
| Ask "what is near me?" | `fires_near` | Edge distance, inside status, bearing |
| Compare or aggregate | `summarize_fires` | Counts and perimeter acres by group |
| Request a shape | `get_perimeter` | Simplified geometry with vertex counts |

<span class="pill">Read-only</span>
<span class="pill">No raw where clauses</span>
<span class="pill">No geometry by default</span>
<span class="pill">Safety caveat on every answer</span>

---

## One question, one safe execution path

<div class="flow">
  <div class="node"><strong>User</strong><span class="small">plain-language wildfire question</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>AI client</strong><span class="small">selects a domain tool</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>WFIGS MCP</strong><span class="small">routes, validates, computes</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>NIFC</strong><span class="small">public ArcGIS services</span></div>
</div>

### Inside the server

- **Dataset router** selects Current or YearToDate and can fall back without hiding it.
- **Normalizer** applies verified precedence for incident ID, acres, timestamps, and agency.
- **Spatial engine** performs point-in-polygon, nearest-edge distance, bearing, and simplification.
- **Guardrails** enforce limits, retries, caching, timeouts, and geometry vertex caps.

---

## Trust is a feature, not a footnote

<div class="cards">
  <div class="card">
    <h3>Freshness is explicit</h3>
    Every response distinguishes fetch time from perimeter capture time and reports perimeter age.
  </div>
  <div class="card">
    <h3>Ambiguity is preserved</h3>
    Duplicate incident names return candidates instead of a confident guess.
  </div>
  <div class="card">
    <h3>Safety is built in</h3>
    Responses state that perimeters can lag and are not evacuation guidance.
  </div>
</div>

### Data choices verified against live metadata

- Prefer polygon IRWIN ID; normalize state codes from `US-OR` to `OR`.
- Prefer geodesic polygon acres; disclose the source field.
- Prefer polygon capture time over record edit time.
- Treat null containment as **unknown**, never zero.

---

## Spatial answers computed where they belong

### Why `fires_near` is different

1. Use an upstream envelope prefilter to reduce transfer.
2. Fetch only candidate polygons.
3. Project locally around the query point.
4. Test whether the point is inside the perimeter.
5. Compute geodesic distance and bearing to the **nearest perimeter edge**.

<div class="cards">
  <div class="card">
    <div class="metric">0 mi</div>
    <strong>Inside means inside</strong><br/>
    Not "near the centroid."
  </div>
  <div class="card">
    <div class="metric">10K</div>
    <strong>Vertex safety cap</strong><br/>
    Large polygons are progressively simplified.
  </div>
  <div class="card">
    <div class="metric">20 KB</div>
    <strong>Default response budget</strong><br/>
    Context stays useful and predictable.
  </div>
</div>

---

## Demo: from question to grounded answer

<div class="demo">
<strong>User</strong>
Are there active fire perimeters within 30 miles of 39.76, -121.62?

<strong>Assistant -> fires_near</strong>
lat=39.76, lon=-121.62, radius_miles=30, scope="active"

<strong>WFIGS MCP returns</strong>
- normalized incident identity
- distance to nearest perimeter edge
- inside status and bearing
- dataset used and data_as_of
- perimeter age
- evacuation-safety caveat
</div>

### Follow-up flow

`get_fire` retrieves incident detail, then `get_perimeter` returns a simplified WGS84 shape only when the user explicitly asks for it.

---

## Built for reliability, not just the happy path

<div class="cards">
  <div class="card">
    <div class="metric">26</div>
    <strong>offline tests passing</strong><br/>
    <span class="small">routing, paging, retries, normalization, geometry, size budget, HTTP</span>
  </div>
  <div class="card">
    <div class="metric">5 min</div>
    <strong>default TTL cache</strong><br/>
    <span class="small">less upstream load without pretending cached data is new</span>
  </div>
  <div class="card">
    <div class="metric">2</div>
    <strong>supported transports</strong><br/>
    <span class="small">stdio for local clients; Streamable HTTP for hosting</span>
  </div>
</div>

- <span class="check">PASS</span> Ruff lint
- <span class="check">PASS</span> strict MyPy
- <span class="check">PASS</span> model-readable timeout and upstream errors
- <span class="check">PASS</span> exponential backoff for HTTP 429 and 5xx
- <span class="check">PASS</span> automatic current-year dataset discovery with fail-closed validation

---

## Designed to move from laptop to shared service

<div class="flow">
  <div class="node"><strong>Local</strong><span class="small">uv + stdio</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>Inspector</strong><span class="small">schemas and resources</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>Hosted</strong><span class="small">Streamable HTTP</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>Scale</strong><span class="small">Databricks Apps ready</span></div>
</div>

### Operational visibility

`wfigs://status` reports resolved layer URLs, last successful fetch, cache hits and misses, and the latest observed perimeter timestamps.

### Zero-secret upstream integration

NIFC services are public. The server needs no upstream API key and performs no write operations.

---

## Impact and next steps

### What this pilot proves

- MCP can turn a complex public geospatial service into a **small, safe, explainable** AI capability.
- Server-side domain logic makes answers more accurate while reducing model context and prompt complexity.
- Explicit freshness, uncertainty, and safety language can be part of the interface contract.

### Next

1. Add Incident Locations enrichment through the existing IRWIN ID extension point.
2. Add hosted observability, rate limiting, and operational dashboards.
3. Pair the MCP server with a map UI and external place-name geocoding.
4. Evaluate tool selection and answer quality on real emergency-management questions.

---

<!-- _class: closing -->

# Better wildfire questions deserve better than raw GIS queries.

## WFIGS MCP makes authoritative perimeter data usable by AI - without hiding uncertainty.

**Five tools. Two resources. One safety-first interface.**

Public data source: NIFC WFIGS via ArcGIS Online  
Project documentation: `README.md`, `docs/USAGE.md`, `docs/DATA_NOTES.md`
