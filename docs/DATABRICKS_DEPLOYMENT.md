# Deploying WFIGS MCP on Databricks Apps

This guide describes how to deploy the WFIGS MCP server as a
[Databricks App](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/).
Databricks Jobs and Model Serving are not appropriate targets because this
server needs a long-running Streamable HTTP endpoint.

## Current compatibility status

The project is close to Databricks-compatible, but **the current code is not deployable as-is**.
Two small runtime adaptations are required before creating the app:

1. Listen on the port assigned in `DATABRICKS_APP_PORT` and bind to
   `0.0.0.0`.
2. Expose Streamable HTTP at `/api/mcp`, because Databricks token
   authentication applies to app API routes under `/api/`.

The rest of the project already fits Databricks Apps:

- The runtime includes Python 3.11 and `uv`.
- Databricks detects `pyproject.toml` and `uv.lock` and runs `uv sync` during
  deployment when no `requirements.txt` is present.
- The server already supports Streamable HTTP.
- NIFC's upstream ArcGIS services require no credentials.

## Architecture

```text
MCP client
    |
    | HTTPS + Databricks OAuth Bearer token
    v
Databricks Apps ingress
    |
    | /api/mcp
    v
WFIGS FastMCP server
    |
    | outbound HTTPS
    v
ArcGIS Online + NIFC FeatureServer
```

Databricks Apps provides ingress authentication and app permissions. The WFIGS
server remains read-only and performs no Databricks data access.

## Prerequisites

- A Databricks workspace with Databricks Apps enabled.
- Permission to create or manage an app.
- Databricks CLI authenticated to the workspace.
- Outbound HTTPS access from the app to:
  - `www.arcgis.com`
  - `services3.arcgis.com`
- An MCP client that can use Streamable HTTP and attach a Databricks OAuth
  Bearer token.

For CLI authentication:

```bash
databricks auth login --host https://<workspace-url> --profile wfigs
```

Do not deploy `.venv`, `dist`, caches, or local environment files. They are
already excluded by this repository's `.gitignore`.

## 1. Add Databricks runtime compatibility

### Use the Databricks-assigned port

Update `Settings.from_env()` in `src/wfigs_mcp/config.py` so Databricks's port
takes precedence over the local default:

```python
databricks_port = os.getenv("DATABRICKS_APP_PORT")

return cls(
    # Existing settings omitted here.
    host=os.getenv(
        "WFIGS_HOST",
        "0.0.0.0" if databricks_port else "127.0.0.1",
    ),
    port=int(os.getenv("WFIGS_PORT", databricks_port or "8000")),
)
```

`WFIGS_PORT` remains an explicit override. Locally, the server continues to use
`127.0.0.1:8000`; inside Databricks Apps it uses `0.0.0.0` and the assigned
port.

### Move the MCP endpoint under `/api/`

Databricks supports token authentication for app endpoints under `/api/`.
FastMCP's default Streamable HTTP path is `/mcp`, so configure it when creating
the app in `src/wfigs_mcp/server.py`:

```python
import os

app = FastMCP(
    "NIFC WFIGS Wildfire Perimeters",
    host=settings.host,
    port=settings.port,
    lifespan=lifespan,
    streamable_http_path=os.getenv("WFIGS_STREAMABLE_HTTP_PATH", "/mcp"),
)
```

This preserves `/mcp` locally and lets Databricks set `/api/mcp` through an
environment variable.

Add tests for both environment behaviors before deployment:

- no Databricks variables: `127.0.0.1:8000` and `/mcp`
- `DATABRICKS_APP_PORT=12345`: `0.0.0.0:12345` and `/api/mcp` when configured

Run the existing checks after editing:

```bash
uv run pytest -m "not live"
uv run ruff check .
uv run mypy
```

## 2. Add `app.yaml`

Create `app.yaml` in the repository root:

```yaml
command:
  - uv
  - run
  - wfigs-mcp
  - --transport
  - streamable-http

env:
  - name: WFIGS_STREAMABLE_HTTP_PATH
    value: /api/mcp
```

The code change above automatically reads `DATABRICKS_APP_PORT`, so do not
hard-code a port in `app.yaml`. Databricks runs command arrays directly rather
than through a shell.

Optional WFIGS settings can be added to `env`, for example:

```yaml
env:
  - name: WFIGS_STREAMABLE_HTTP_PATH
    value: /api/mcp
  - name: WFIGS_CACHE_TTL_SECONDS
    value: "300"
  - name: WFIGS_TIMEOUT_SECONDS
    value: "20"
```

No NIFC API key or secret is required. Only set `WFIGS_YTD_LAYER_URL` when the
automatic current-year ArcGIS discovery needs an operational override.

## 3. Test the Databricks startup contract locally

Test the same host, port, path, and transport used by Databricks:

```bash
DATABRICKS_APP_PORT=8765 \
WFIGS_STREAMABLE_HTTP_PATH=/api/mcp \
uv run wfigs-mcp --transport streamable-http
```

The startup log should report Uvicorn on `0.0.0.0:8765`. The MCP endpoint is:

```text
http://127.0.0.1:8765/api/mcp
```

For environments using a recent Databricks CLI, the app contract can also be
tested with:

```bash
databricks apps run-local --prepare-environment
```

## 4. Create and deploy the app

Databricks Apps supports workspace-folder and Git-backed deployments. Git is
recommended for production because each deployment maps to a commit, branch,
or tag.

### Option A: Workspace-folder deployment

Set names appropriate for your workspace:

```bash
export DATABRICKS_CONFIG_PROFILE=wfigs
export APP_NAME=wfigs-mcp
export WORKSPACE_PATH=/Workspace/Users/<user@example.com>/wfigs-mcp
```

Create the app:

```bash
databricks apps create "$APP_NAME" \
  --description "Read-only MCP server for NIFC WFIGS fire perimeters"
```

Upload or sync the repository source to `WORKSPACE_PATH`. Do not upload `.venv`
or build artifacts. Then deploy:

```bash
databricks apps deploy "$APP_NAME" \
  --source-code-path "$WORKSPACE_PATH" \
  --mode SNAPSHOT
```

The equivalent UI flow is:

1. Upload the source to a Databricks workspace folder.
2. Open **Apps** and create a custom app.
3. Select **Deploy** and choose that workspace folder.
4. Wait for the deployment and app status to become active.

### Option B: Git-backed deployment

Create or configure a custom app with the repository URL and Git provider,
then deploy a branch, tag, or commit from the Apps UI. For private repositories,
configure a Git credential on the app's service principal.

Databricks recommends Git deployment for production and supports automatic
deployment from watched GitHub or Azure DevOps branches.

## 5. Configure permissions and egress

Grant intended users or service principals `CAN USE` on the app. For example,
permissions can be inspected with:

```bash
databricks apps get-permissions "$APP_NAME"
```

If the workspace restricts Databricks Apps egress, allow HTTPS to:

```text
www.arcgis.com
services3.arcgis.com
```

The first domain resolves the current-year YearToDate item. The second serves
layer metadata and query results. A blocked domain causes startup discovery or
tool calls to fail.

## 6. Get the endpoint and authenticate

Inspect the deployed app:

```bash
databricks apps get "$APP_NAME" --output json
```

The remote MCP endpoint is the app URL plus `/api/mcp`:

```text
https://<app-name>-<id>.<region>.databricksapps.com/api/mcp
```

The caller must have `CAN USE` permission and send a valid OAuth 2.0 Bearer
token. For local OAuth user-to-machine (U2M) access:

```bash
databricks auth token --profile wfigs
```

Do not paste or commit the resulting token. Configure the MCP client to refresh
and send it as:

```http
Authorization: Bearer <access-token>
```

For unattended external clients, use Databricks OAuth machine-to-machine (M2M)
authentication with a service principal. The service principal also needs
`CAN USE` on the app.

### MCP client compatibility

Not every MCP client supports arbitrary OAuth-protected Streamable HTTP
servers. Before choosing this hosting model, verify that the client can:

1. connect to a remote Streamable HTTP endpoint;
2. attach or obtain a Databricks Bearer token;
3. refresh the token when it expires.

If the client cannot do these things, use an authentication-aware MCP gateway
or proxy. Do not make the Databricks App anonymous merely to work around a
client limitation.

## 7. Validate the deployment

Check recent logs:

```bash
databricks apps logs "$APP_NAME" --tail-lines 200
```

Expected startup evidence:

- Current and YearToDate layer URLs are logged.
- The app listens on the assigned Databricks port.
- The process starts with the `streamable-http` transport.
- ArcGIS discovery requests return HTTP 200.

Using an authenticated MCP client, verify:

1. `tools/list` returns all five tools.
2. `resources/list` returns `wfigs://about` and `wfigs://status`.
3. `search_fires` returns a bounded active result.
4. `summarize_fires` works with `scope="year_to_date"`.
5. `get_perimeter` returns `bbox_only` for a known IRWIN ID.

The app URL opened in a browser may show no user interface or a not-found page
at `/`. This is expected: the application exposes an MCP API at `/api/mcp`, not
a website.

## Operations and limitations

- The cache is process-local and in memory. It is empty after app restarts and
  is not shared across multiple app processes.
- YearToDate discovery happens on every process start unless
  `WFIGS_YTD_LAYER_URL` is set.
- Databricks Apps compute is billed while the app is running.
- WFIGS does not provide a perimeter for every incident.
- The server is not evacuation guidance; continue to direct users to local
  emergency officials and InciWeb.
- Pin deployments to Git commits or tags for repeatable rollback.

Useful commands:

```bash
databricks apps logs "$APP_NAME" --follow
databricks apps list-deployments "$APP_NAME"
databricks apps stop "$APP_NAME"
databricks apps start "$APP_NAME"
```

## Troubleshooting

| Symptom | Likely cause and resolution |
| --- | --- |
| App starts locally but fails in Databricks | Confirm the code reads `DATABRICKS_APP_PORT` and binds to `0.0.0.0` |
| 404 at `/mcp` | Use `/api/mcp`; the Databricks configuration intentionally changes the route |
| 401 response | Refresh the OAuth token and verify its scopes |
| 403 response | Grant the caller `CAN USE` and verify OAuth scopes |
| Startup fails during YearToDate discovery | Allow egress to `www.arcgis.com`, or set a verified `WFIGS_YTD_LAYER_URL` |
| Tools time out | Allow egress to `services3.arcgis.com` and inspect app logs |
| App deploy cannot resolve dependencies | Confirm both `pyproject.toml` and `uv.lock` are in the deployment root |
| Client connects but cannot keep a session | Confirm it supports MCP Streamable HTTP and preserves the session headers returned by the server |

## Official Databricks references

- [Databricks Apps overview](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
- [Apps runtime and `app.yaml`](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/app-runtime)
- [Apps environment](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/system-env)
- [Deploy an app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy)
- [Connect with token authentication](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/connect-local)
- [Databricks CLI `apps` commands](https://docs.databricks.com/aws/en/dev-tools/cli/reference/apps-commands)

For MCP tool usage after deployment, see [USAGE.md](USAGE.md).