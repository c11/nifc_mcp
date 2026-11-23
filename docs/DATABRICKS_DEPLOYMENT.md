# Deploying WFIGS MCP on Databricks Apps

Follow this guide from the repository root to deploy the WFIGS MCP server as a
[Databricks App](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/).
Databricks Jobs and Model Serving are not appropriate targets because this
server needs a long-running Streamable HTTP endpoint.

**Result:** an OAuth-protected endpoint at
`https://<your-app-hostname>/api/mcp`, exposing five tools and two resources.

Use the workspace-folder CLI path in steps 0-7 for the first deployment.
Git-backed and UI alternatives are included in step 4. Replace every
`<placeholder>` before running a command; examples use Bash/zsh syntax.

**Verification status (2026-11-22):** these instructions were checked against
the current source and official Databricks documentation. The Databricks CLI
was not installed in the authoring environment, and no app was deployed.
The passing local/live tests in [EVALUATION.md](EVALUATION.md) do not prove
Databricks ingress, OAuth, or deployed transport behavior. Step 7 is required
to verify those after deployment.

## Current compatibility status

The code implements the Databricks Apps runtime contract. Its configuration already:

1. reads the port assigned in `DATABRICKS_APP_PORT` and binds to `0.0.0.0`;
2. accepts `WFIGS_STREAMABLE_HTTP_PATH=/api/mcp`, because Databricks token
  authentication applies to app API routes under `/api/`;
3. maps the public `streamable-http` CLI option to Prefect FastMCP's `http`
  transport.

The deployment uses the project's existing packaging:

- The project requires Python 3.11 or newer and uses Prefect FastMCP.
- Databricks detects `pyproject.toml` and `uv.lock` and runs `uv sync` during
  deployment when no `requirements.txt` is present.
- The server already supports Streamable HTTP.
- NIFC's upstream ArcGIS services require no credentials.

You do **not** need to create `app.py` or `main.py`. The installed command
`wfigs-mcp` invokes `main()` in
[src/wfigs_mcp/server.py](../src/wfigs_mcp/server.py). The configuration file
to add is `app.yaml` in step 2; it is not currently checked into the repository.

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

- A Databricks workspace with Databricks Apps enabled in a supported serverless
  region, and organizational approval for the app's compute cost.
- Permission to create or manage an app.
- A current Databricks CLI authenticated to the workspace. Apps requires at
  least CLI 0.229.0; use the latest supported release for the commands below.
- Python 3.11 or newer and `uv` on your development machine.
- Outbound HTTPS access from the app to:
  - `www.arcgis.com`
  - `services3.arcgis.com`
- Build-time access to your approved Python package repositories.
- An MCP client that can use Streamable HTTP and attach a Databricks OAuth
  Bearer token.

This server needs no SQL warehouse, cluster, Unity Catalog volume, or Databricks
SDK dependency to query NIFC. Do not add data-access grants or app resources
that the server does not use.

## 0. Install tools and authenticate

If the Databricks CLI is missing, on macOS with Homebrew:

```bash
brew install databricks/tap/databricks
```

For other platforms or managed installations, follow the
[official CLI installation instructions](https://docs.databricks.com/aws/en/dev-tools/cli/install).
Do not install the legacy Python `databricks-cli` package into this project.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed,
then verify:

```bash
databricks version
uv --version
```

Set these values in the terminal used for subsequent steps:

```bash
export DATABRICKS_CONFIG_PROFILE="wfigs"
export DATABRICKS_HOST="https://<workspace-url>"
export APP_NAME="mcp-wfigs"
export WORKSPACE_PATH="/Workspace/Users/<your-workspace-user>/mcp-wfigs"

databricks auth login \
  --host "$DATABRICKS_HOST" \
  --profile "$DATABRICKS_CONFIG_PROFILE"
```

Complete the browser sign-in to the intended workspace. Use the workspace
hostname, not an account-console URL or an app URL. Subsequent CLI commands
use `DATABRICKS_CONFIG_PROFILE`.

`mcp-wfigs` is the Databricks app name, distinct from the Python command
`wfigs-mcp`. The `mcp-` prefix follows Databricks' MCP naming guidance for
discovery by AI Playground. Choose another unique name if it is already used.

Choose a **new, dedicated** workspace folder. Later syncs can update or remove
files there; do not point `WORKSPACE_PATH` at a shared folder containing other
projects.

## 1. Verify the source and runtime compatibility

Open a terminal in the local checkout:

```bash
cd /absolute/path/to/nifc_mcp
uv sync --locked
uv run wfigs-mcp --help
uv run pytest -m "not live"
uv run ruff check .
uv run mypy
```

**Checkpoint:** the command help appears and all offline checks pass.
These steps do not enable the opt-in live benchmark.

Do not deploy `.venv`, `dist`, caches, or local environment files. They are
excluded by this repository's [.gitignore](../.gitignore); step 4 explicitly
uses it for sync exclusions.

### Use the Databricks-assigned port

`Settings.from_env()` in `src/wfigs_mcp/config.py` gives Databricks's assigned
port precedence over the local default:

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

### Place the MCP endpoint under `/api/`

Databricks supports token authentication for app endpoints under `/api/`.
Prefect FastMCP's default HTTP path is `/mcp`; the server passes the configured
path when starting the standalone FastMCP HTTP transport:

```python
app.run(
    transport="http",
    host=settings.host,
    port=settings.port,
    path=settings.streamable_http_path,
)
```

The default remains `/mcp` locally. The `app.yaml` setting below changes it to
`/api/mcp` on Databricks.

The test suite covers both environment behaviors:

- no Databricks variables: `127.0.0.1:8000` and `/mcp`
- `DATABRICKS_APP_PORT=12345`: `0.0.0.0:12345` and `/api/mcp` when configured

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

The server automatically reads `DATABRICKS_APP_PORT`, so do not hard-code a
port in `app.yaml`. Databricks runs command arrays directly rather than through
a shell.

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

Keep `pyproject.toml`, `uv.lock`, `README.md`, `app.yaml`, and `src/wfigs_mcp/`
in the deployed root. `README.md` is referenced by the package build metadata.
Do not add `requirements.txt`: it takes precedence over `pyproject.toml` and
would switch Databricks to the pip installation path.

Do not configure a `/health` deployment health check unless you implement that
route first. This server does not define one, and a plain GET on an MCP
endpoint is not equivalent to a successful MCP session.

## 3. Test the Databricks startup contract locally

In **terminal A**, run the same host, path, and transport contract used by
Databricks. This opens a local server and queries public ArcGIS metadata:

```bash
DATABRICKS_APP_PORT=8765 \
WFIGS_STREAMABLE_HTTP_PATH=/api/mcp \
uv run wfigs-mcp --transport streamable-http
```

The startup log should report the resolved Current/YearToDate URLs and
listening on `0.0.0.0:8765`. This binds all network interfaces; use a trusted
development machine/network and stop the process when finished. The endpoint is:

```text
http://127.0.0.1:8765/api/mcp
```

In **terminal B**, from the same checkout, verify the HTTP MCP handshake and
an actual tool call using the already installed FastMCP client:

```bash
uv run python - <<'PY'
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8765/api/mcp", timeout=60) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        print("Tools:", sorted(tool.name for tool in tools))
        print("Resources:", sorted(str(resource.uri) for resource in resources))
        result = await client.call_tool(
            "search_fires", {"scope": "year_to_date", "limit": 1}
        )
        if result.is_error or result.structured_content is None:
            raise RuntimeError("Local MCP search did not return structured data")
        print("Search total_count:", result.structured_content["total_count"])

asyncio.run(main())
PY
```

**Checkpoint:** five tools, two resource URIs, and structured search output.
Press **Ctrl+C in terminal A** to stop the local server. No Databricks
authentication is involved in this local check.

Optional CLI-assisted local execution:

```bash
databricks apps run-local --prepare-environment --entry-point app.yaml
```

Use the proxy/app ports that this command reports; they differ from the direct
8765 example above.

## 4. Create and deploy the app

Databricks Apps supports workspace-folder and Git-backed deployments. Git is
recommended for production because each deployment maps to a commit, branch,
or tag.

### Option A: Workspace-folder deployment

Use the environment variables from step 0. Creating the app can start billable
compute; confirm your workspace and budget first. For a new app:

```bash
databricks apps create "$APP_NAME" \
  --description "Read-only MCP server for NIFC WFIGS fire perimeters"
```

Creation alone does not deploy this repository. If the name already exists,
stop and verify that it is your intended app instead of overwriting another
deployment.

Create the dedicated source directory and **preview** a one-time sync:

```bash
databricks workspace mkdirs "$WORKSPACE_PATH"
databricks sync . "$WORKSPACE_PATH" \
  --exclude-from .gitignore \
  --exclude '.git/**' \
  --exclude '.databricks/**' \
  --dry-run
```

Inspect the preview before continuing. It must include `app.yaml`,
`pyproject.toml`, `uv.lock`, `README.md`, and `src/wfigs_mcp/`, and must exclude
credentials, `.venv/`, caches, and `dist/` submission artifacts. Stop if it
would upload a secret or modify/delete unrelated remote files. Databricks
also limits individual app files to 10 MB.

Then upload using the same exclusions:

```bash
databricks sync . "$WORKSPACE_PATH" \
  --exclude-from .gitignore \
  --exclude '.git/**' \
  --exclude '.databricks/**'
```

In the app's **Overview** page, identify its assigned service principal.
Verify that it has read access to the source folder. If needed, use the
workspace folder's **Share/Permissions** dialog to grant that principal
**CAN READ** on this app's folder, not on unrelated workspace data.

Deploy the uploaded snapshot:

```bash
databricks apps deploy "$APP_NAME" \
  --source-code-path "$WORKSPACE_PATH" \
  --mode SNAPSHOT
```

**Checkpoint:** the deployment reaches `SUCCEEDED`. If it fails, inspect
deployment/build logs before changing dependencies or rerunning it.
The platform starts the command from `app.yaml` after installing dependencies
with `uv`. A successful deployment status alone is not the final acceptance
check; continue through step 7.

The equivalent UI flow is:

1. Upload the source to a Databricks workspace folder.
2. Open **Databricks Apps** from the app switcher and create a custom app named
   `mcp-wfigs` (or your chosen unique name).
3. Select **Deploy** and choose that workspace folder.
4. Wait for the deployment and app status to become active.

### Option B: Git-backed deployment

Instead of uploading workspace files, create/configure a custom app with the
repository URL and Git provider, then select **Deploy > From Git** and choose
the reference. Include the `app.yaml` from step 2 in the chosen commit and use
the repository root as the source path.

For private repositories, configure a Git credential on the app's service
principal. A developer's personal Git connection is not a substitute for the
app principal's access. Prefer a specific commit or release tag for repeatable
deployments; automatic Git deployments are optional and have additional
provider/permission requirements. See the
[official Git deployment guide](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy#deploy-git).

## 5. Configure permissions and egress

In **Databricks Apps > your app > Permissions**, grant intended users, groups,
or calling service principals **CAN USE**. Keep **CAN MANAGE** limited to
maintainers. Permissions can be inspected with:

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
token. **Databricks personal access tokens (PATs) are not supported for calling
the MCP app.** Use OAuth user-to-machine (U2M) access for interactive local
clients or machine-to-machine (M2M) access for unattended callers.

Set the full endpoint URL copied from the app's Overview/get output:

```bash
export WFIGS_MCP_URL="https://<actual-app-hostname>/api/mcp"
```

Do not substitute the workspace hostname here. The verification script in
step 7 obtains an OAuth token from `databricks auth token` using your logged-in
CLI profile and keeps it in memory. A client must send the token as:

```http
Authorization: Bearer <access-token>
```

For unattended external clients, use Databricks OAuth machine-to-machine (M2M)
authentication with a service principal. The service principal also needs
`CAN USE` on the app.

This server does not call Databricks APIs on behalf of the user, so it does
not need additional SQL/catalog user-authorization scopes. If you later add
such access, review the app's requested scopes and the caller token together.
Never place tokens or client secrets in `app.yaml`, source control, screenshots,
or logs.

### MCP client compatibility

Not every MCP client supports arbitrary OAuth-protected Streamable HTTP
servers. Before choosing this hosting model, verify that the client can:

1. connect to a remote Streamable HTTP endpoint;
2. attach or obtain a Databricks Bearer token;
3. refresh the token when it expires.

If the client cannot do these things, use an authentication-aware MCP gateway
or proxy. Do not make the Databricks App anonymous merely to work around a
client limitation.

Use the **full `/api/mcp` URL** in client configuration. Examples for Databricks
starter templates may use `/mcp`; that is a different server configuration.
For clients using automatic OAuth rather than a supplied token, follow the
[custom MCP client registration guidance](https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp#connect-your-agent).

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

From the local checkout and the authenticated terminal used in step 0, run
the following. It uses the project's existing FastMCP dependency; no
Databricks Python SDK installation is necessary:

```bash
uv run python - <<'PY'
import asyncio
import json
import os
import subprocess

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

async def call(client, name, arguments):
    result = await client.call_tool(name, arguments)
    if result.is_error or result.structured_content is None:
        raise RuntimeError(f"{name} did not return successful structured content")
    print(f"PASS {name}")
    return result.structured_content

async def main():
    token_output = subprocess.run(
        [
            "databricks", "auth", "token",
            "--profile", os.environ["DATABRICKS_CONFIG_PROFILE"],
        ],
        check=True, capture_output=True, text=True, timeout=30,
    )
    token = json.loads(token_output.stdout)["access_token"]
    if not isinstance(token, str) or not token:
        raise RuntimeError("CLI did not return an OAuth access token")
    transport = StreamableHttpTransport(
        os.environ["WFIGS_MCP_URL"],
        headers={"Authorization": f"Bearer {token}"},
    )
    async with Client(transport, timeout=60) as client:
        tools = {tool.name for tool in await client.list_tools()}
        assert tools == {
            "search_fires", "get_fire", "fires_near",
            "summarize_fires", "get_perimeter",
        }, tools
        resources = {str(item.uri) for item in await client.list_resources()}
        assert resources == {"wfigs://about", "wfigs://status"}, resources
        for uri in sorted(resources):
            assert await client.read_resource(uri), f"Empty resource: {uri}"
        print("PASS tool discovery and resource reads")

        search = await call(client, "search_fires", {
            "scope": "year_to_date", "min_acres": 1, "max_acres": 1000, "limit": 1,
        })
        if not search["fires"]:
            raise RuntimeError(
                "No YearToDate sample in 1..1000 acres; choose another sample filter"
            )
        irwin_id = search["fires"][0]["irwin_id"]
        detail = await call(client, "get_fire", {
            "scope": "year_to_date", "irwin_id": irwin_id,
        })
        assert detail["status"] == "found"
        perimeter = await call(client, "get_perimeter", {
            "scope": "year_to_date", "irwin_id": irwin_id, "format": "bbox_only",
        })
        assert perimeter["format"] == "bbox_only"
        summary = await call(client, "summarize_fires", {
            "scope": "year_to_date", "group_by": "state",
        })
        assert summary["groups"], "No YearToDate summary groups"
        nearby = await call(client, "fires_near", {
            "lat": 39.76, "lon": -121.62, "radius_miles": 1, "limit": 5,
        })
        assert isinstance(nearby["fires"], list)
        print("DEPLOYMENT CHECK PASSED: remote MCP session and all five tools")

asyncio.run(main())
PY
```

**Checkpoint:** the script exits successfully with `DEPLOYMENT CHECK PASSED`.
Do not treat an HTTP 200 from a browser or a successful dependency build as
equivalent to this check. A proximity search can legitimately return an empty
list; an unavailable YearToDate sample prevents this particular smoke check
from completing and is reported explicitly.

The script checks one remote session, not token refresh, sustained load, or
horizontal scaling. Configure your long-running client to refresh OAuth
tokens; the one-shot script deliberately does not implement a refresh loop.

The app URL opened in a browser may show no user interface or a not-found page
at `/`. This is expected: the application exposes an MCP API at `/api/mcp`, not
a website.

## Operations and limitations

- To update a workspace-based deployment, review `databricks sync --dry-run`
  with the same source, target, and exclusions from step 4, sync, redeploy with
  `--mode SNAPSHOT`, then repeat step 7. Editing the local files does not update
  a running snapshot automatically.
- The cache is process-local and in memory. It is empty after app restarts and
  is not shared across multiple app processes.
- YearToDate discovery happens on every process start unless
  `WFIGS_YTD_LAYER_URL` is set.
- Databricks Apps compute is billed while the app is running.
- WFIGS does not provide a perimeter for every incident.
- The server is not evacuation guidance; continue to direct users to local
  emergency officials and InciWeb.
- Pin deployments to Git commits or tags for repeatable rollback.
- Start with a single app instance/process. Multi-instance deployments require
  separate verification of MCP session routing and cache behavior; they were
  not covered by this project's local benchmarks.

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
| `wfigs-mcp` not found or package build fails | Check that `src/wfigs_mcp/` and `README.md` were uploaded, the `uv` install succeeded, and `app.yaml` uses `uv run wfigs-mcp` |
| Source folder permission error | Grant the app's assigned service principal read access to that specific folder |
| Deployment succeeds but a browser shows 404/405/406 | Root `/` is not a UI; test `/api/mcp` with an MCP client, not an ordinary browser GET |
| Local smoke test cannot connect | Verify terminal A is still running, port 8765 is free, and no `WFIGS_HOST`/`WFIGS_PORT` overrides changed the listener |
| Client connects but cannot keep a session | Confirm it supports MCP Streamable HTTP and preserves the session headers returned by the server |

## Official Databricks references

- [Databricks Apps overview](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
- [Host an existing MCP server on Databricks Apps](https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp#existing-server)
- [Workspace and development prerequisites](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/configure-env)
- [Manage dependencies with `uv`](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/dependencies#uv-dependencies)
- [Apps runtime and `app.yaml`](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/app-runtime)
- [Apps environment](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/system-env)
- [Deploy an app](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/deploy)
- [Connect with token authentication](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/connect-local)
- [Databricks CLI `apps` commands](https://docs.databricks.com/aws/en/dev-tools/cli/reference/apps-commands)
- [Databricks CLI `sync` commands](https://docs.databricks.com/aws/en/dev-tools/cli/reference/sync-commands)

For MCP tool usage after deployment, see [USAGE.md](USAGE.md).