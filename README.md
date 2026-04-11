# Google Search Console MCP

A Python MCP server that connects Claude (or any MCP-compatible AI client) directly to your Google Search Console properties via OAuth 2.0.

## Features

### Site Management
- **list_properties** - List all GSC properties with permission levels
- **get_site_details** - Get details for a specific GSC property
- **add_site** - Add a new property to GSC
- **delete_site** - Remove a property from GSC

### Search Analytics
- **get_search_analytics** - Query search analytics with dimensions and filters
- **get_performance_overview** - Get clicks/impressions/CTR/position summary
- **compare_periods** - Compare performance between two date periods
- **get_position_band_report** - Filter pages by position band (1-3, 4-10, 11-20)
- **get_ctr_optimization_report** - Find pages with high impressions but low CTR
- **get_keyword_cannibalization** - Identify queries with multiple competing pages
- **batch_search_analytics** - Run multiple analytics queries in one call
- **export_full_dataset** - Export all rows bypassing the 5K row limit

### URL Inspection
- **inspect_url** - Inspect a URL for indexing status, mobile usability, and rich results
- **batch_url_inspection** - Inspect multiple URLs at once

### Sitemaps
- **list_sitemaps** - List sitemaps with health classification
- **get_sitemap** - Get details for a specific sitemap
- **submit_sitemap** - Submit a sitemap to GSC
- **delete_sitemap** - Remove a sitemap from GSC

### Composite / Analysis
- **analyze_site_health** - One-call site health report: traffic + indexing + mobile
- **identify_quick_wins** - Find pages worth optimizing (high impressions, low CTR, ranked 4-10)
- **crawl_error_summary** - Aggregate indexing and mobile errors across a property
- **property_migration_checklist** - Checklist for safely migrating a site

## Quick Start (Team / Cloud Run mode)

1. Clone the repo:
   ```
   git clone https://github.com/dhawalshah/google-search-console-mcp.git
   cd google-search-console-mcp
   ```

2. Get Google OAuth credentials:
   - Go to Google Cloud Console → APIs & Services → Credentials
   - Click "Create Credentials" → OAuth 2.0 Client ID
   - Application type: **Web application**
   - Note your project number

3. Add the redirect URI to your OAuth client:
   ```
   https://gsc-mcp-YOUR_PROJECT_NUMBER.asia-southeast1.run.app/auth/callback
   ```

4. Download the credentials and copy to the project directory:
   ```
   cp ~/Downloads/client_secret_*.json ./client_secret.json
   ```

5. Deploy to Cloud Run:
   ```
   cd /path/to/team-mcp && bash deploy.sh
   ```

6. Authenticate your team members — each person visits:
   ```
   https://gsc-mcp-YOUR_PROJECT_NUMBER.asia-southeast1.run.app/auth/login
   ```

7. Connect Claude Desktop — add to `claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "google-search-console": {
         "url": "https://gsc-mcp-YOUR_PROJECT_NUMBER.asia-southeast1.run.app/mcp"
       }
     }
   }
   ```

## Local Development (STDIO mode)

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Copy your OAuth credentials to the project directory:
   ```
   cp ~/Downloads/client_secret_*.json ./client_secret.json
   ```

3. Run the one-shot local auth setup:
   ```
   python setup_local_auth.py
   ```
   This opens your browser, completes the OAuth flow, and saves a token to `~/.config/google-search-console-mcp/token.json`.

4. Add to Claude Desktop config (`claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "google-search-console": {
         "command": "python",
         "args": ["/path/to/google-search-console-mcp/server.py"],
         "env": {
           "MCP_USER_EMAIL": "you@company.com",
           "OAUTH_CONFIG_PATH": "/path/to/google-search-console-mcp/client_secret.json"
         }
       }
     }
   }
   ```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GCP_PROJECT_ID` | Cloud Run only | Your Google Cloud project ID |
| `OAUTH_CONFIG_PATH` | Yes | Full path to your `client_secret.json` file |
| `MCP_USER_EMAIL` | No (STDIO mode only) | Your Google account email (STDIO local mode only) |
| `ALLOWED_DOMAIN` | Cloud Run only | Restrict logins to a specific Google Workspace domain (e.g. `company.com`) |
| `BASE_URL` | Cloud Run only | Public URL of the deployed service (e.g. `https://gsc-mcp-123.asia-southeast1.run.app`) |
| `SESSION_SECRET_KEY` | Cloud Run only | Random secret key for signing session cookies |

## Example Prompts

**Weekly performance digest:**
> "Give me a performance overview for sc-domain:example.com for the last 28 days, then identify any quick wins."

**SEO audit before a site migration:**
> "Run the property migration checklist for sc-domain:example.com and list all sitemaps with their health status."

**Content gap analysis:**
> "Find keyword cannibalization issues on sc-domain:example.com for the last 90 days, and show me the CTR optimization report for pages ranked between position 4 and 10."

## License

MIT
