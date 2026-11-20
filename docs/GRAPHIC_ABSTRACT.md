---
marp: true
theme: default
size: 16:9
title: WFIGS MCP Graphic Abstract
description: From raw wildfire GIS data to trusted AI answers
style: |
  :root {
    --navy: #0d2a42;
    --blue: #1261a0;
    --sky: #dff3ff;
    --orange: #ef5b2a;
    --gold: #ffb000;
    --cream: #fffaf2;
    --ink: #20384c;
    --muted: #60788d;
    --green: #18845a;
    --line: #bed5e5;
  }
  section {
    background:
      radial-gradient(circle at 92% 8%, rgba(255, 176, 0, 0.18) 0 6%, transparent 6.2%),
      linear-gradient(140deg, #ffffff 0%, var(--cream) 100%);
    color: var(--ink);
    font-family: "Aptos", "Helvetica Neue", Arial, sans-serif;
    height: 100%;
    padding: 38px 48px 30px;
  }
  section::after {
    display: none;
  }
  h1 {
    color: var(--navy);
    font-size: 42px;
    letter-spacing: -0.025em;
    line-height: 1.04;
    margin: 0;
  }
  .subtitle {
    color: var(--muted);
    font-size: 20px;
    margin: 8px 0 18px;
  }
  .accent {
    color: var(--orange);
  }
  .canvas {
    align-items: stretch;
    display: grid;
    gap: 16px;
    grid-template-columns: 0.86fr 1.8fr 0.96fr;
    height: 392px;
  }
  .panel {
    background: rgba(255, 255, 255, 0.95);
    border: 1.5px solid var(--line);
    border-radius: 18px;
    box-sizing: border-box;
    box-shadow: 0 9px 24px rgba(13, 42, 66, 0.10);
    overflow: hidden;
    padding: 18px;
    position: relative;
  }
  .panel h2 {
    color: var(--navy);
    font-size: 24px;
    margin: 0 0 13px;
  }
  .label {
    color: var(--orange);
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }
  .source {
    border-left: 6px solid var(--orange);
  }
  .source-card {
    background: var(--cream);
    border-radius: 12px;
    margin: 11px 0;
    padding: 12px 13px;
  }
  .source-card strong {
    color: var(--navy);
    display: block;
    font-size: 18px;
  }
  .source-card span {
    color: var(--muted);
    font-size: 14px;
  }
  .friction {
    color: var(--muted);
    font-size: 14px;
    line-height: 1.35;
    margin-top: 13px;
  }
  .friction b {
    color: var(--orange);
  }
  .engine {
    border-top: 6px solid var(--blue);
    padding-top: 14px;
  }
  .engine-title {
    align-items: center;
    display: flex;
    justify-content: space-between;
  }
  .readonly {
    background: #e6f6ef;
    border-radius: 999px;
    color: var(--green);
    font-size: 13px;
    font-weight: 800;
    padding: 6px 11px;
  }
  .pipeline {
    display: grid;
    gap: 10px;
    grid-template-columns: repeat(4, 1fr);
    margin: 13px 0 15px;
  }
  .stage {
    background: linear-gradient(180deg, var(--sky), #ffffff);
    border: 1px solid #b9ddf2;
    border-radius: 13px;
    min-height: 112px;
    padding: 12px 10px;
    text-align: center;
  }
  .stage-no {
    align-items: center;
    background: var(--blue);
    border-radius: 50%;
    color: white;
    display: inline-flex;
    font-size: 14px;
    font-weight: 800;
    height: 28px;
    justify-content: center;
    margin-bottom: 7px;
    width: 28px;
  }
  .stage strong {
    color: var(--navy);
    display: block;
    font-size: 16px;
    line-height: 1.1;
  }
  .stage span {
    color: var(--muted);
    display: block;
    font-size: 12px;
    line-height: 1.25;
    margin-top: 6px;
  }
  .tools {
    background: #0d2a42;
    border-radius: 13px;
    color: white;
    padding: 13px 14px;
  }
  .tools-title {
    color: #8bd8ff;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.10em;
    margin-bottom: 8px;
    text-transform: uppercase;
  }
  .tool-row {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
  }
  .tool {
    background: rgba(255, 255, 255, 0.11);
    border: 1px solid rgba(255, 255, 255, 0.24);
    border-radius: 999px;
    font-family: "SFMono-Regular", Consolas, monospace;
    font-size: 12px;
    padding: 6px 9px;
  }
  .output {
    border-right: 6px solid var(--gold);
  }
  .answer {
    background: #f7fbfe;
    border: 1px solid #c9deeb;
    border-radius: 12px;
    margin: 7px 0;
    padding: 8px 10px;
  }
  .answer strong {
    color: var(--blue);
    display: block;
    font-size: 15px;
  }
  .answer span {
    color: var(--muted);
    display: block;
    font-size: 13px;
    line-height: 1.15;
    margin-top: 3px;
  }
  .context {
    background: #fff3d9;
    border-radius: 12px;
    color: #7a4a00;
    font-size: 12px;
    line-height: 1.2;
    margin-top: 8px;
    padding: 8px 10px;
  }
  .arrow {
    align-items: center;
    color: var(--orange);
    display: flex;
    font-size: 32px;
    font-weight: 900;
    justify-content: center;
    position: absolute;
    right: -31px;
    top: 168px;
    width: 44px;
    z-index: 4;
  }
  .footer {
    align-items: center;
    display: grid;
    gap: 16px;
    grid-template-columns: 1.55fr 1fr;
    margin-top: 16px;
  }
  .safety {
    background: linear-gradient(90deg, #fff1e9, #fff8e8);
    border-left: 6px solid var(--orange);
    border-radius: 12px;
    color: #6b3b28;
    font-size: 15px;
    line-height: 1.3;
    padding: 11px 15px;
  }
  .proof {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
  .badge {
    background: white;
    border: 1px solid var(--line);
    border-radius: 11px;
    box-shadow: 0 4px 10px rgba(13, 42, 66, 0.07);
    color: var(--navy);
    font-size: 12px;
    font-weight: 700;
    min-width: 82px;
    padding: 8px 9px;
    text-align: center;
  }
  .badge b {
    color: var(--green);
    display: block;
    font-size: 21px;
    line-height: 1;
  }
---

# WFIGS MCP <span class="accent">|</span> From raw wildfire GIS to trusted AI answers

<div class="subtitle">A safety-first Model Context Protocol server for public NIFC wildfire perimeter data</div>

<div class="canvas">
  <div class="panel source">
    <div class="label">Authoritative input</div>
    <h2>NIFC WFIGS</h2>
    <div class="source-card">
      <strong>Current</strong>
      <span>Recent and ongoing incidents</span>
    </div>
    <div class="source-card">
      <strong>YearToDate</strong>
      <span>All qualifying incidents this year</span>
    </div>
    <div class="friction">
      <b>Raw challenge:</b> 118 shared fields, duplicate names, nulls, competing acreage and timestamps, and large polygons.
    </div>
    <div class="arrow">></div>
  </div>

  <div class="panel engine">
    <div class="engine-title">
      <div>
        <div class="label">Domain intelligence layer</div>
        <h2>WFIGS MCP server</h2>
      </div>
      <div class="readonly">READ-ONLY</div>
    </div>
    <div class="pipeline">
      <div class="stage">
        <div class="stage-no">1</div>
        <strong>Route</strong>
        <span>Active vs. year-to-date with explicit fallback</span>
      </div>
      <div class="stage">
        <div class="stage-no">2</div>
        <strong>Normalize</strong>
        <span>Verified IDs, acres, dates, state, and agency</span>
      </div>
      <div class="stage">
        <div class="stage-no">3</div>
        <strong>Compute</strong>
        <span>Nearest edge, inside status, bearing, simplification</span>
      </div>
      <div class="stage">
        <div class="stage-no">4</div>
        <strong>Guard</strong>
        <span>Limits, cache, retries, freshness, vertex cap</span>
      </div>
    </div>
    <div class="tools">
      <div class="tools-title">Five intent-level MCP tools</div>
      <div class="tool-row">
        <div class="tool">search_fires</div>
        <div class="tool">get_fire</div>
        <div class="tool">fires_near</div>
        <div class="tool">summarize_fires</div>
        <div class="tool">get_perimeter</div>
      </div>
    </div>
    <div class="arrow">></div>
  </div>

  <div class="panel output">
    <div class="label">Grounded output</div>
    <h2>AI-ready answers</h2>
    <div class="answer">
      <strong>Compact</strong>
      <span>No polygon geometry unless explicitly requested</span>
    </div>
    <div class="answer">
      <strong>Spatially correct</strong>
      <span>Distance to the perimeter edge, not the centroid</span>
    </div>
    <div class="answer">
      <strong>Transparent</strong>
      <span>Dataset, source fields, data_as_of, and perimeter age</span>
    </div>
    <div class="context">
      Natural-language questions become bounded, model-readable responses with uncertainty preserved.
    </div>
  </div>
</div>

<div class="footer">
  <div class="safety">
    <b>Safety by contract:</b> perimeters can lag ground conditions and are never presented as evacuation guidance; users are directed to local officials and InciWeb.
  </div>
  <div class="proof">
    <div class="badge"><b>26</b>tests pass</div>
    <div class="badge"><b>20 KB</b>response budget</div>
    <div class="badge"><b>2</b>transports</div>
  </div>
</div>
