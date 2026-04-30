# Google Search Console MCP

A Model Context Protocol (MCP) server for Google Search Console. Connect Claude (or any MCP-compatible AI client) directly to your GSC properties to query search performance, inspect URLs, manage sitemaps, find quick wins, and run composite audits — all in natural language.

The server speaks the [MCP authorization spec (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization), so it works as a remote connector anywhere Claude supports custom MCP servers — claude.ai (personal), Claude Desktop, and Claude Teams. Add **one URL**, click "Connect", sign in with Google, done. For a Teams plan, the org owner adds the URL once and each member individually authenticates on first use.

## What you can do

### Sites & Properties
- List all GSC properties with permission level (owner / full / restricted)
- Get details for a specific property including verification method
- Add or remove properties from GSC

### Search Analytics
- Query by query, page, country, device, search type, and date range
- Performance overviews with clicks, impressions, CTR, average position
- Compare two date ranges side-by-side
- Position-band reports (1–3, 4–10, 11–20, 21–50)
- CTR optimisation reports — pages with high impressions but low CTR
- Keyword cannibalisation detection — multiple pages competing for the same rank
- Batched analytics queries and dataset exports past the 5,000-row API limit

### URL Inspection
- Full URL inspection: indexing status, canonical, mobile usability, rich results, AMP
- Batch inspection of up to 20 URLs at once

### Sitemaps
- List, fetch, submit, and delete sitemaps for a property

### Composite Analysis
- `analyze_site_health` — top pages + indexing + mobile usability + last crawl
- `identify_quick_wins` — high impressions, low CTR, ranked 4–10, no indexing issues
- `crawl_error_summary` — aggregate indexing and mobile errors across sampled pages
- `property_migration_checklist` — pre-migration audit across old and new properties

---

## How auth works

There are **two** modes. Pick one.

### Mode A — Local STDIO (one user, no server)
Use this if you only want it on your own machine. `setup_local_auth.py` runs the Google OAuth flow once and stores your token in `~/.config/google-search-console-mcp/token.json`. Claude Desktop launches `server.py` as a subprocess. No Firestore, no Cloud Run, no public URL.

### Mode B — Remote HTTP server (Claude Teams, claude.ai, multi-user)
The MCP server is also an OAuth 2.1 authorization server. When Claude connects:

1. Claude discovers our metadata at `/.well-known/oauth-protected-resource` and `/.well-known/oauth-authorization-server`.
2. Claude registers itself via Dynamic Client Registration (`POST /oauth/register`).
3. Claude redirects the user to `/oauth/authorize`. We delegate identification to Google OAuth.
4. After Google login, we issue our **own** opaque bearer token to Claude — Google credentials never leave the server.
5. On each `/mcp` request Claude sends our bearer; we map it server-side to the right user's stored Google credentials and call the Search Console APIs.

The `?user=email` query string from older versions is **gone** — there are no per-user URLs to copy around.

---

## Prerequisites

- Python 3.10+
- A Google Search Console property you have access to
- A [Google Cloud](https://console.cloud.google.com/) project

---

## Step 1 — Set up Google Cloud

### 1a. Create a project and enable the Search Console API
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select a project.
3. **APIs & Services → Library**, enable **Google Search Console API**.

### 1b. Create OAuth 2.0 credentials
1. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**.
2. Application type: **Web application**.
3. Add **Authorized redirect URIs**:
   - `http://localhost:8080/auth/callback` *(local dev / setup_local_auth.py)*
   - `https://YOUR-CLOUD-RUN-URL/auth/callback` *(remote deployment — add after deploy)*
4. Click **Create**, then **Download JSON** → save as `client_secret.json` in the project root *(gitignored)*. You can also copy the Client ID / Client Secret straight into env vars.

### 1c. OAuth consent screen
1. **APIs & Services → OAuth consent screen**.
2. Choose **Internal** for a Google Workspace org (recommended for teams), or **External** for personal/individual use.
3. Add scopes:
   - `https://www.googleapis.com/auth/webmasters`
   - `https://www.googleapis.com/auth/webmasters.readonly`
4. If using **External** in Testing mode, add each user's email under **Test users**.

### 1d. Enable Firestore *(Mode B only)*
The server stores OAuth bearer tokens and per-user Google credentials in Firestore.
1. In Cloud Console, **Firestore → Create database → Native mode**, pick a region.
2. Grant the Cloud Run service account **Cloud Datastore User** role under **IAM & Admin → IAM**.

---

## Step 2 — Install

```bash
git clone https://github.com/dhawalshah/google-search-console-mcp
cd google-search-console-mcp
pip install -r requirements.txt
cp .env.example .env       # fill in values
```

---

## Step 3 — Mode A: Local STDIO

```bash
python setup_local_auth.py
```

A browser opens, you sign in with Google, the script writes `~/.config/google-search-console-mcp/token.json`.

Then add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "google-search-console": {
      "command": "python",
      "args": ["/absolute/path/to/google-search-console-mcp/server.py"],
      "env": {
        "OAUTH_CONFIG_PATH": "/absolute/path/to/client_secret.json",
        "MCP_USER_EMAIL": "you@yourcompany.com"
      }
    }
  }
}
```

Restart Claude Desktop. You're done — skip the rest.

---

## Step 3 — Mode B: Remote HTTP server (Claude Teams / claude.ai)

### Deploy to Cloud Run

```bash
gcloud run deploy google-search-console-mcp \
  --source . \
  --region YOUR_REGION \
  --project YOUR_PROJECT_ID \
  --platform managed \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=your-project-id,BASE_URL=https://YOUR-SERVICE-URL.run.app,GOOGLE_CLIENT_ID=...,GOOGLE_CLIENT_SECRET=...,ALLOWED_DOMAINS=yourcompany.com"
```

> **Recommended:** store `GOOGLE_CLIENT_SECRET` as a [Cloud Run secret](https://cloud.google.com/run/docs/configuring/services/secrets) rather than a plain env var.

After it's up, go back to **APIs & Services → Credentials → your OAuth client** and add the live callback URL:

```
https://YOUR-SERVICE-URL.run.app/auth/callback
```

### Connect from Claude

**Claude Teams (org owner adds it once for everyone):**
- Settings → Connectors → Add custom connector
- URL: `https://YOUR-SERVICE-URL.run.app/mcp`
- Each member clicks **Connect**, signs in with Google, done.

**claude.ai personal:**
- Settings → Connectors → Add custom connector
- URL: `https://YOUR-SERVICE-URL.run.app/mcp`

**Claude Desktop with a remote server:**
```json
{
  "mcpServers": {
    "google-search-console": {
      "url": "https://YOUR-SERVICE-URL.run.app/mcp"
    }
  }
}
```
Claude Desktop will run the OAuth dance the first time you use it.

---

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `BASE_URL` | Mode B | Public URL of this service. Used for OAuth metadata and as the canonical resource URI tokens are bound to. |
| `GCP_PROJECT_ID` | Mode B | GCP project hosting Firestore. |
| `GOOGLE_CLIENT_ID` | Mode B† | Google OAuth client ID. |
| `GOOGLE_CLIENT_SECRET` | Mode B† | Google OAuth client secret. |
| `OAUTH_CONFIG_PATH` | Mode B† | Alternative to the two above: path to `client_secret.json`. |
| `GOOGLE_REDIRECT_URI` | No | Override the Google callback URL. Defaults to `${BASE_URL}/auth/callback`. |
| `ALLOWED_DOMAINS` | No | Comma-separated email domain allowlist (e.g. `acme.com,beta.com`). Empty = no restriction. |
| `MCP_USER_EMAIL` | Mode A | Your email — set in Claude Desktop config. |
| `PORT` | No | HTTP port (default `8080`). |
| `LOG_LEVEL` | No | Python log level (default `INFO`). |

† Set **either** `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` **or** `OAUTH_CONFIG_PATH`.

---

## Available Tools

### Sites & Properties

| Tool | Description |
| --- | --- |
| `list_properties` | List all GSC properties with permission level (owner / full / restricted) |
| `get_site_details` | Details for a specific property including verification method |
| `add_site` | Add a new property to GSC |
| `delete_site` | Remove a property from GSC |

### Search Analytics

| Tool | Description |
| --- | --- |
| `get_search_analytics` | Query by query, page, country, device, search type, date range |
| `get_performance_overview` | Total clicks, impressions, CTR, average position for a date range |
| `compare_periods` | Side-by-side comparison of two date ranges |
| `get_position_band_report` | Queries by position band: 1–3, 4–10, 11–20, 21–50 |
| `get_ctr_optimization_report` | Pages with high impressions but low CTR — prime optimisation candidates |
| `get_keyword_cannibalization` | Queries where multiple pages compete for the same rank |
| `batch_search_analytics` | Multiple analytics queries in a single call |
| `export_full_dataset` | Paginate past the 5,000-row API limit (up to 100K rows) |

### URL Inspection

| Tool | Description |
| --- | --- |
| `inspect_url` | Full inspection: indexing status, crawl date, canonical, mobile usability, rich results, AMP |
| `batch_url_inspection` | Inspect up to 20 URLs at once |

### Sitemaps

| Tool | Description |
| --- | --- |
| `list_sitemaps` | All sitemaps for a property with submitted vs indexed counts |
| `get_sitemap` | Detailed status for a specific sitemap |
| `submit_sitemap` | Submit a new sitemap |
| `delete_sitemap` | Remove a sitemap |

### Composite Analysis

| Tool | Description |
| --- | --- |
| `analyze_site_health` | Top pages by traffic + indexing status + mobile usability + last crawl time |
| `identify_quick_wins` | High impressions, low CTR, ranked 4–10, no indexing issues |
| `crawl_error_summary` | Aggregate indexing and mobile errors across a sampled set of pages |
| `property_migration_checklist` | Pre-migration audit: indexed pages, sitemaps, new site GSC status |

---

## Example Prompts

```
Give me a performance overview for https://example.com/ for the last 28 days

Identify quick wins — pages ranked 4–10 with low CTR

Find keyword cannibalization issues on https://example.com/ for the last 90 days

Run the property migration checklist for https://old.example.com/ moving to https://new.example.com/

Inspect indexing status for these 10 URLs

Show me the top 20 queries by clicks for last month

Analyse the site health of https://example.com/
```

---

## OAuth endpoint reference (Mode B)

For developers who want to verify the implementation or write their own MCP client.

| Endpoint | Spec | Purpose |
| --- | --- | --- |
| `GET /.well-known/oauth-protected-resource` | RFC 9728 | Advertises the canonical resource URI and authorization server. |
| `GET /.well-known/oauth-authorization-server` | RFC 8414 | Authorization server metadata. |
| `POST /oauth/register` | RFC 7591 | Dynamic Client Registration. |
| `GET /oauth/authorize` | OAuth 2.1 | Starts the auth code flow with PKCE; redirects to Google. |
| `GET /auth/callback` | — | Google redirects here; we mint our authorization code and bounce back to the MCP client. |
| `POST /oauth/token` | OAuth 2.1 | Authorization code + refresh token grants. |

A `GET /mcp` without a valid bearer returns `401` with a `WWW-Authenticate: Bearer resource_metadata="…"` header pointing at the protected-resource metadata document, which is how a standards-compliant MCP client discovers the rest.

---

## Tech Stack

- **[FastMCP](https://github.com/jlowin/fastmcp)** — MCP server framework
- **FastAPI + uvicorn** — HTTP wrapper
- **Google Auth / google-api-python-client** — Google OAuth and API access
- **Firestore** — Per-user token storage and OAuth-server state (Mode B)
- **Google Cloud Run** — Serverless hosting

---

## License

MIT
