---
marp: true
theme: default
paginate: true
size: 16:9
title: Wildfire MCP - Trustworthy Wildfire Intelligence for AI
description: Expanded hackathon submission deck for the NIFC Wildfire MCP server
style: |
  :root {
    --navy: #102a43;
    --blue: #1565c0;
    --sky: #d9efff;
    --orange: #015d31;
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
    font-size: 26px;
    padding: 50px 64px;
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
    font-size: 39px;
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
    margin: 22px 0;
    padding: 16px 26px;
  }
  table {
    font-size: 21px;
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
    max-width: 900px;
  }
  .title p {
    color: var(--sky);
    font-size: 29px;
    max-width: 900px;
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
  .section {
    align-items: center;
    background: linear-gradient(135deg, var(--navy), #0c4a6e);
    color: white;
    display: flex;
    flex-direction: column;
    justify-content: center;
    text-align: center;
  }
  .section h1, .section h2, .section strong {
    color: white;
  }
  .section h1 {
    font-size: 58px;
    max-width: 900px;
  }
  .section p {
    color: var(--sky);
    font-size: 27px;
    max-width: 850px;
  }
  .cards {
    display: flex;
    gap: 20px;
    margin-top: 22px;
  }
  .card {
    background: white;
    border-radius: 14px;
    box-shadow: 0 8px 22px rgba(16, 42, 67, 0.10);
    flex: 1;
    padding: 22px;
  }
  .card h3 {
    color: var(--blue);
    font-size: 24px;
    margin: 0 0 10px;
  }
  .metric {
    color: var(--orange);
    font-size: 42px;
    font-weight: 800;
    line-height: 1;
  }
  .small {
    color: var(--muted);
    font-size: 17px;
  }
  .flow {
    align-items: center;
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 38px;
  }
  .node {
    background: white;
    border: 2px solid var(--sky);
    border-radius: 16px;
    box-shadow: 0 8px 20px rgba(16, 42, 67, 0.10);
    padding: 20px 16px;
    text-align: center;
    width: 190px;
  }
  .node strong {
    display: block;
    font-size: 24px;
  }
  .arrow {
    color: var(--orange);
    font-size: 34px;
    font-weight: 800;
  }
  .pill-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.5rem 1rem;
    margin-top: 1rem;
  }
  .pill {
    background: var(--sky);
    border-radius: 999px;
    color: var(--navy);
    display: inline-block;
    font-size: 18px;
    font-weight: 700;
    margin: 4px;
    padding: 7px 13px;
  }
  .decision {
    align-items: flex-start;
    background: white;
    border-left: 6px solid var(--orange);
    border-radius: 12px;
    box-shadow: 0 7px 18px rgba(16, 42, 67, 0.09);
    display: grid;
    gap: 14px;
    grid-template-columns: 0.7fr 1.3fr;
    margin: 12px 0;
    padding: 14px 18px;
  }
  .decision strong {
    color: var(--navy);
  }
  .decision span {
    color: var(--muted);
    font-size: 21px;
  }
  .demo {
    background: #0b1f33;
    border-radius: 16px;
    color: #e6f4ff;
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 20px;
    line-height: 1.45;
    padding: 23px 28px;
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

  .author {
    display: inline-block;
    color: #031fef;
    padding: 0.15em 0.45em;
    border-radius: 4px;
    font-weight: 1000;
    margin-right: 0.4em;
  }
  .author2 {
    display: inline-block;
    color: #4a4a4ba8;
    padding: 0.15em 0.45em;
    border-radius: 4px;
    font-weight: 1000;
    margin-right: 0.4em;
  }
---

<!-- _class: title -->

<div class="eyebrow">MCP Hackathon Submission</div>

# Wild Fire MCP

## Trustworthy wildfire perimeter intelligence for AI assistants

Natural-language questions in. Safe, normalized, spatially accurate NIFC answers out.

<br>

<span class="author">Zhiqiang Yang, USFS</span>
<span class="author2">with github copilot</span>

---

<!-- _class: section -->

<div class="eyebrow">Section 1</div>

# Problem statement

How can an AI assistant use authoritative wildfire perimeter data without exposing users to GIS complexity, stale context, or misleading spatial answers?

---

## Problem statement: public does not mean AI-ready

NIFC publishes authoritative wildfire perimeter data, but an assistant must still resolve:

<div class="cards">
  <div class="card">
    <h3>Which dataset?</h3>
    Active incidents and year-to-date history answer different questions and have different membership rules.
  </div>
  <div class="card">
    <h3>Which fields?</h3>
    118 shared fields include competing IDs, acreage values, timestamps, nulls, and duplicate names.
  </div>
  <div class="card">
    <h3>Which geometry?</h3>
    Raw polygons are large, and centroid distance does not represent distance to a fire perimeter.
  </div>
</div>

> The challenge is not merely accessing ArcGIS. It is turning dynamic GIS records into bounded, transparent, safety-aware answers an AI model can use correctly.

---

## What goes wrong with a generic data connector?

| Failure mode | User impact |
|---|---|
| Model constructs raw ArcGIS `where` clauses | Fragile queries and an unnecessarily large attack surface |
| Active data is treated as annual history | Missing incidents or incorrect "still active" conclusions |
| Record edit time is treated as perimeter time | Old geometry can appear fresh |
| Centroid is used for proximity | Distance can be wrong for large or irregular fires |
| Full polygons are returned by default | Context flooding, latency, and poor tool reliability |
| Duplicate names are silently resolved | Confident answer about the wrong incident |

**Need:** a domain-native interface that encodes wildfire and geospatial semantics before data reaches the model.

---

<!-- _class: section -->

<div class="eyebrow">Section 2</div>

# Solution overview

A read-only MCP server that converts NIFC FeatureServers into a small set of safe wildfire squeries.

---

## Solution overview: domain tools, not GIS primitives

| User intent | MCP tool | Model-ready result |
|---|---|---|
| Find matching incidents | `search_fires` | Bounded, normalized records |
| Inspect one incident | `get_fire` | Exact detail or honest candidate list |
| Ask "what is near me?" | `fires_near` | Edge distance, inside status, bearing |
| Compare or aggregate | `summarize_fires` | Counts and perimeter acres by group |
| Request a shape | `get_perimeter` | Simplified WGS84 geometry and vertex counts |

<div class="pill-grid">
<span class="pill">Read-only</span>
<span class="pill">No raw query language</span>
<span class="pill">No geometry by default</span>
<span class="pill">Bounded output</span>
<span class="pill">Freshness disclosed</span>
<span class="pill">Safety caveat included</span>
</div>

---

## One question, one controlled execution path

<div class="flow">
  <div class="node"><strong>User</strong><span class="small">plain-language wildfire question</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>AI client</strong><span class="small">selects one domain tool</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>Wildfire MCP</strong><span class="small">routes, validates, computes</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>NIFC</strong><span class="small">public ArcGIS services</span></div>
</div>

### Consistent response contract

- Normalized incident identity, acreage, containment, dates, agency, centroid, and bounding box
- Dataset identity, fetch time, perimeter capture time, and perimeter age
- Clear truncation, ambiguity, fallback, and upstream error messages
- Safety language directing urgent decisions to local officials and InciWeb

---

<!-- _class: section -->

<div class="eyebrow">Section 3</div>

# Technical approach and key decisions

Push domain logic and spatial computation into the server so the model receives answers, not implementation details.

---

## Technical approach: layered and testable

<div class="flow">
  <div class="node"><strong>FastMCP</strong><span class="small">tools, resources, stdio, HTTP</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>Dataset service</strong><span class="small">routing, fallback, limits</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>Domain core</strong><span class="small">normalization and spatial math</span></div>
  <div class="arrow">></div>
  <div class="node"><strong>ArcGIS client</strong><span class="small">paging, cache, retries</span></div>
</div>

<div class="cards">
  <div class="card">
    <h3>Async I/O</h3>
    `httpx` with explicit timeouts and exponential backoff for 429 and 5xx responses.
  </div>
  <div class="card">
    <h3>Typed contracts</h3>
    Pydantic inputs and outputs plus strict MyPy keep tool behavior explicit.
  </div>
  <div class="card">
    <h3>Verified semantics</h3>
    Live metadata discovery and recorded fixtures ground field precedence in actual NIFC data.
  </div>
</div>

---

## Key decisions: route and normalize before answering

<div class="decision">
  <strong>Current vs. YearToDate</strong>
  <span>Every query has an explicit scope. Exact active lookups fall back to YearToDate and disclose the fallback instead of returning a false absence.</span>
</div>

<div class="decision">
  <strong>Current-year discovery</strong>
  <span>The YearToDate item is resolved at startup for the UTC year and validated by owner, exact title, service type, HTTPS URL, and polygon layer.</span>
</div>

<div class="decision">
  <strong>Field precedence</strong>
  <span>Prefer polygon IRWIN ID, geodesic polygon acres, and polygon capture time; disclose source fields rather than silently mixing values.</span>
</div>

<div class="decision">
  <strong>Ambiguity preservation</strong>
  <span>Duplicate incident names return candidates. Null containment remains unknown rather than being converted to zero.</span>
</div>

---

## Key decisions: compute spatial truth on the server

### `fires_near`

1. Apply an upstream envelope prefilter and fetch only candidate polygons.
1. Project around the query point with a local azimuthal equidistant CRS.
1. Compute geodesic distance and bearing to the **nearest perimeter edge**.

### `get_perimeter`

- Geometry is opt-in and returned in WGS84 as GeoJSON, WKT, or bounding box.
- Simplification occurs in a metric local projection.
- The server progressively increases tolerance until the geometry fits the configured vertex cap.

<div class="cards">
  <div class="card"><div class="metric">0 mi</div><strong>Inside means inside</strong></div>
  <div class="card"><div class="metric">10K</div><strong>Default vertex cap</strong></div>
  <div class="card"><div class="metric">20 KB</div><strong>Default response budget</strong></div>
</div>

---

## Key decisions: freshness, safety, and resilience

<div class="cards">
  <div class="card">
    <h3>Freshness is two timestamps</h3>
    `data_as_of` reports fetch time; `perimeter_updated_at` reports polygon capture time with its source field.
  </div>
  <div class="card">
    <h3>Safety is part of the schema</h3>
    Every answer states that perimeters can lag and are not evacuation guidance.
  </div>
  <div class="card">
    <h3>Failures stay model-readable</h3>
    Invalid input, timeouts, no results, and upstream rejection do not leak stack traces.
  </div>
</div>

### Operational choices

- Five-minute configurable in-memory TTL cache
- Internal pagination beyond ArcGIS record limits
- Configurable timeouts, retries, result limits, and vertex caps
- `wfigs://status` for layer URLs, fetch status, cache metrics, and observed freshness

---

## Demo: from question to grounded answer

<div class="demo">
<strong>User</strong>
Are there active fire perimeters within 30 miles of 39.76, -121.62?

<strong>Assistant -> fires_near</strong>
lat=39.76, lon=-121.62, radius_miles=30, scope="active"

<strong>Wildfire MCP returns</strong>
- normalized incident identity
- distance to nearest perimeter edge
- inside status and bearing
- dataset used and data_as_of
- perimeter capture time and age
- evacuation-safety caveat
</div>

**Follow-up:** `get_fire` retrieves detail, then `get_perimeter` returns a simplified shape only if the user explicitly requests geometry.

---

## Engineering evidence

<div class="cards">
  <div class="card">
    <div class="metric">26</div>
    <strong>offline tests passing</strong><br/>
    <span class="small">mocked HTTP, normalization, geometry, routing, and MCP contracts</span>
  </div>
  <div class="card">
    <div class="metric">18</div>
    <strong>live correctness cases passed</strong><br/>
    <span class="small">real NIFC data across tools, resources, and both datasets</span>
  </div>
  <div class="card">
    <div class="metric">2</div>
    <strong>supported transports</strong><br/>
    <span class="small">stdio locally and Streamable HTTP for hosting</span>
  </div>
</div>

- <span class="check">PASS</span> Ruff lint
- <span class="check">PASS</span> strict MyPy
- <span class="check">PASS</span> default non-geometry response size assertion
- <span class="check">PASS</span> automatic current-year discovery with fail-closed validation
- <span class="check">PASS</span> live tool, metadata, fallback, geometry, freshness, and MCP checks
- <span class="check">READY</span> Databricks Apps deployment contract

---

## Live evaluation: correctness and measured performance

<div class="cards">
  <div class="card">
    <div class="metric">18 / 18</div>
    <strong>live correctness checks</strong><br/>
    <span class="small">metadata, Current/YTD search, filters, ID/name lookup, fallback, 3 geometry formats, proximity, 4 summaries, cache, MCP resources</span>
  </div>
  <div class="card">
    <div class="metric">33 ms</div>
    <strong>median search latency</strong><br/>
    <span class="small">10 uncached YearToDate searches; at most 2 concurrent</span>
  </div>
  <div class="card">
    <div class="metric">10.5/s</div>
    <strong>observed throughput</strong><br/>
    <span class="small">20 upstream HTTP attempts; 0 failed searches; no local cache hits</span>
  </div>
</div>

### One bounded benchmark run · 2026-11-22

| Tail latency | Local CPU time | Process peak RSS |
|---:|---:|---:|
| **820 ms p95** | **0.041 s** | **78.8 MiB** |

<span class="small">p95 is nearest-rank over only 10 samples (equal to the max). Single run—not sustained capacity, an SLA, or NIFC server resource usage.</span>

---

## What's learned and next steps

### What this pilot proves

- MCP can turn a complex public geospatial service into a **small, safe, explainable** AI capability.
- Server-side domain logic improves accuracy while reducing prompt complexity and model context.
- Freshness, uncertainty, and safety can be enforced by the interface instead of relying on prompting.

### Next

1. Augment logic for wildfire queries, e.g. geocoding and map UI.
1. Similar logic can be applied to other geospatial data services.
2. Add hosted observability, rate limiting, and operational dashboards.
4. Evaluate tool selection and answer quality on emergency-management question sets.

---

<!-- _class: closing -->

# Better wildfire questions deserve better than raw GIS queries.

## Wildfire MCP makes authoritative perimeter data usable by AI without hiding uncertainty.

**Five tools. Two resources. One safety-first interface.**

Public data source: NIFC WFIGS via ArcGIS Online  

