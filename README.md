# Google Search Console MCP

A self-hosted MCP server that connects Claude (or any MCP-compatible AI client) directly to your Google Search Console data via OAuth 2.0.

Designed for teams: deploy once to Google Cloud Run, each team member authenticates once with their own Google account, and everyone can query GSC data through Claude without per-person setup.

## Features — 22 Tools

### Sites & Properties
| Tool | Description |
|---|---|
| `list_properties` | List all GSC properties with permission level (owner / full / restricted) |
| `get_site_details` | Details for a specific property including verification method |
| `add_site` | Add a new property to GSC |
| `delete_site` | Remove a property from GSC |

### Search Analytics
| Tool | Description |
|---|---|
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
|---|---|
| `inspect_url` | Full inspection: indexing status, crawl date, canonical, mobile usability, rich results, AMP |
| `batch_url_inspection` | Inspect up to 20 URLs at once |

### Sitemaps
| Tool | Description |
|---|---|
| `list_sitemaps` | All sitemaps for a property with submitted vs indexed counts |
| `get_sitemap` | Detailed status for a specific sitemap |
| `submit_sitemap` | Submit a new sitemap |
| `delete_sitemap` | Remove a sitemap |

### Composite Analysis
These tools make multiple API calls and return a comprehensive report in one response.

| Tool | Description |
|---|---|
| `analyze_site_health` | Top pages by traffic + indexing status + mobile usability + last crawl time |
| `identify_quick_wins` | High impressions, low CTR, ranked 4–10, no indexing issues |
| `crawl_error_summary` | Aggregate indexing and mobile errors across a sampled set of pages |
| `property_migration_checklist` | Pre-migration audit: indexed pages, sitemaps, new site GSC status |

---

## Deployment: Google Cloud Run (Team Mode)

### Prerequisites

- Google Cloud project with Firestore and Cloud Run APIs enabled
- Google OAuth 2.0 client credentials (**Web application** type)
- `gcloud` CLI authenticated

### Steps

1. Clone the repo:
   ```bash
   git clone https://github.com/dhawalshah/gsc-mcp.git
   cd gsc-mcp
   ```

2. Create OAuth credentials:
   - Google Cloud Console → APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: **Web application**
   - Download the JSON file and copy it to the project directory as `client_secret.json`

3. Deploy to Cloud Run:
   ```bash
   export PROJECT_ID=your-project-id
   export PROJECT_NUMBER=your-project-number   # found in Cloud Console home
   export REGION=asia-southeast1               # or your preferred region
   export ALLOWED_DOMAIN=yourcompany.com
   export BASE_URL="https://gsc-mcp-${PROJECT_NUMBER}.${REGION}.run.app"
   export SESSION_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

   gcloud run deploy gsc-mcp \
     --source . \
     --region $REGION \
     --allow-unauthenticated \
     --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},OAUTH_CONFIG_PATH=/app/client_secret.json,ALLOWED_DOMAIN=${ALLOWED_DOMAIN},SESSION_SECRET_KEY=${SESSION_SECRET_KEY},BASE_URL=${BASE_URL},OAUTHLIB_RELAX_TOKEN_SCOPE=1"
   ```

4. Add the redirect URI to your OAuth client in Cloud Console:
   ```
   https://gsc-mcp-YOUR_PROJECT_NUMBER.REGION.run.app/auth/callback
   ```

5. Each team member authenticates once:
   ```
   https://gsc-mcp-YOUR_PROJECT_NUMBER.REGION.run.app/auth/login
   ```

6. Connect Claude — add to `claude_desktop_config.json` (replace with your own email):
   ```json
   {
     "mcpServers": {
       "google-search-console": {
         "url": "https://gsc-mcp-YOUR_PROJECT_NUMBER.REGION.run.app/mcp/?user=you@yourcompany.com"
       }
     }
   }
   ```

   Or on Claude.ai (web): Settings → Integrations → Add custom integration, using the same URL.

---

## Local Development (STDIO Mode)

For individual use or local testing without Cloud Run.

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy your OAuth credentials (a **Desktop app** or **Web application** type both work locally):
   ```bash
   cp ~/Downloads/client_secret_*.json ./client_secret.json
   ```

3. Authenticate once:
   ```bash
   python setup_local_auth.py
   ```
   This opens your browser, completes the OAuth flow, and saves a token to `~/.config/google-search-console-mcp/token.json`.

4. Add to Claude Desktop (`claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "google-search-console": {
         "command": "python3",
         "args": ["/path/to/gsc-mcp/server.py"],
         "env": {
           "MCP_USER_EMAIL": "you@yourcompany.com",
           "OAUTH_CONFIG_PATH": "/path/to/gsc-mcp/client_secret.json"
         }
       }
     }
   }
   ```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OAUTH_CONFIG_PATH` | Yes | Full path to `client_secret.json` |
| `GCP_PROJECT_ID` | Cloud Run | Google Cloud project ID (for Firestore token storage) |
| `ALLOWED_DOMAIN` | Cloud Run | Restrict logins to a Google Workspace domain (e.g. `company.com`) — strongly recommended |
| `BASE_URL` | Cloud Run | Public URL of the deployed service |
| `SESSION_SECRET_KEY` | Cloud Run | Strong random secret for signing session cookies — required in production |
| `MCP_USER_EMAIL` | STDIO only | Your Google account email for local single-user mode |

---

## Security Model

- **Authentication:** OAuth 2.0 via Google. Tokens are stored per-user in Firestore, not shared between users.
- **Domain restriction:** Set `ALLOWED_DOMAIN` to your Google Workspace domain. Any Google account outside that domain is rejected at login.
- **`?user=` parameter:** Non-browser MCP clients (Claude Desktop) pass identity via `?user=email`. With `ALLOWED_DOMAIN` set, only emails on your domain are accepted. For maximum security, ensure all team members have logged in before sharing the MCP URL.
- **Session security:** `SESSION_SECRET_KEY` must be set to a strong random value in production. The server refuses to start in Cloud Run without it.
- **Secrets:** `client_secret.json` is excluded from both `.gitignore` and `.dockerignore`. Never commit it.
- **Rate limiting:** 10 requests/minute per user per tool invocation (in-process; for multi-instance Cloud Run deployments, consider moving state to Firestore or Redis).

---

## Example Prompts

**Weekly performance digest:**
> "Give me a performance overview for https://example.com/ for the last 28 days, then identify any quick wins."

**SEO audit before a site migration:**
> "Run the property migration checklist for https://old.example.com/ moving to https://new.example.com/."

**Cannibalization check:**
> "Find keyword cannibalization issues on https://example.com/ for the last 90 days."

**CTR improvement opportunities:**
> "Show me pages on https://example.com/ ranked between position 4 and 10 with impressions above 500 but CTR below 2%."

**Full site health report:**
> "Analyse the site health of https://example.com/ for the last 30 days."

---

## Tech Stack

- **[FastMCP](https://github.com/jlowin/fastmcp)** — MCP server framework
- **FastAPI + uvicorn** — HTTP wrapper and SSE transport
- **Google Auth / google-api-python-client** — OAuth 2.0 and API access
- **Firestore** — Per-user token storage (Cloud Run mode)
- **Google Cloud Run** — Serverless hosting

---

## License

MIT
