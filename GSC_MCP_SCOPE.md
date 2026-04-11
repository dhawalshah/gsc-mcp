# Google Search Console MCP Server - Build Scope

## Context

You are building a **self-hosted, team-accessible GSC MCP server** to replace the desktop-only mcp-gsc (AminForou/mcp-gsc). This must run on Google Cloud Run with SSE transport, similar to your existing GA4, Google Ads, Meta Ads, and LinkedIn Ads MCPs.

Your team: ~40 people across 4 countries. Goal: all team members can query GSC data via Claude without individual setup.

---

## What the Existing MCP Covers (19 Tools)

Review what mcp-gsc already does so you don't duplicate:

### Search Analytics (Query-based data)
- `get_search_analytics` – queries by dimension, date range, filters
- `get_performance_overview` – summary of clicks/impressions/CTR/position
- `get_search_by_page_query` – queries driving specific pages
- `compare_search_periods` – side-by-side period comparison
- `get_advanced_search_analytics` – mobile-focused or position-filtered queries

### Sites (Property Management)
- `list_properties` – all GSC properties user has access to
- `get_site_details` – details about a specific property
- `add_site` – add new property (destructive, gated)
- `delete_site` – remove property (destructive, gated)

### URL Inspection
- `inspect_url_enhanced` – single URL full inspection
- `batch_url_inspection` – inspect multiple URLs at once
- `check_indexing_issues` – check specific pages for indexing errors

### Sitemaps
- `get_sitemaps` – list all sitemaps for a property
- `list_sitemaps_enhanced` – detailed view with error patterns
- `get_sitemap_details` – fetch status of specific sitemap
- `submit_sitemap` – submit new sitemap
- `delete_sitemap` – remove sitemap (destructive, gated)

### Utility
- `about_creator` – info about Amin Foroutan

---

## What the Full GSC API Offers (Gaps to Fill)

### A. Search Analytics Service – Extended Filtering & Dimensions

**Current coverage:** Basic query, dimensions, date filtering.

**Missing:**
1. **Batch querying** – Multiple queries in single call (reduce round-trips)
2. **Search Type filtering** – Filter by `web`, `image`, `video`, `news`, `discover`, `googleNews` separately
3. **Data freshness control** – `data_state: "all" | "final"` (final = 2–3 day lag, more stable)
4. **Page-level aggregation** – GroupBy `page` with all dimensions simultaneously (top pages + countries + devices at once)
5. **Row limit handling** – API caps at 5,000 rows/query; add tool to paginate/export large datasets (50K+ rows using batch requests)
6. **CTR optimization** – Pre-built tool: "Find pages with high impressions but low CTR" + suggest title/meta improvements
7. **Keyword cannibalization** – Identify multiple pages ranking for same query
8. **Position-band filtering** – Pages ranked 1–3, 4–10, 11–20, 21–30 separately (useful for "rank 2 but should be rank 1" analysis)

**Why it matters:** Your team does optimization work. They need to slice data by device/country/type/position in ways the basic query doesn't expose.

---

### B. URL Inspection Service – Extended Coverage

**Current coverage:** Single URL and batch inspection.

**Missing:**
1. **AMP inspection** – Check AMP status if applicable
2. **Rich Results detection** – Return structured data eligibility (FAQs, Reviews, etc.)
3. **Mobile Usability** – Crawl issues flagged by Google's mobile tester
4. **Core Web Vitals status** – LCP, FID, CLS scores if available
5. **Robots.txt blocking detection** – Flag if user-agent:Googlebot or user-agent:* has disallow rules matching the URL
6. **Crawl depth analysis** – For lists of URLs, identify shallowest/deepest crawled paths
7. **Last crawl time tracking** – Track when Google last crawled each URL (useful for freshness analysis)

**Why it matters:** URL inspection is a bottleneck. Batch inspection exists but should expose all 15+ inspection fields, not just index status.

---

### C. Sitemaps Service – Complete Management

**Current coverage:** List, get, submit, delete.

**Missing:**
1. **Error classification** – Breakdown of `submitted vs. indexed` by error type (parsing, crawl, etc.)
2. **Encoding validation** – Check XML encoding issues
3. **Update frequency tracking** – Note when sitemaps were last processed
4. **Submission history** – When was each sitemap submitted? (API doesn't expose this directly, but log it on submission)

**Why it matters:** Agencies need to audit sitemaps. Add a tool to flag sitemaps with high error rates or never-indexed URLs.

---

### D. Sites Service – Complete Property Management

**Current coverage:** List, get, add, delete.

**Missing:**
1. **Preferred domain** – Which variant (www vs. non-www, http vs. https) does Google prefer?
2. **Verification method** – How was each property verified? (DNS, HTML file, Google Analytics, etc.)
3. **Permission level** – What level does the authenticated user have? (Owner, Full, Restricted)
4. **Verified by user** – Email of the user who verified the property (when available)

**Why it matters:** Team members need to know which properties they own vs. which they can only view.

---

### E. New Cross-Service Tools (Composite Analysis)

**Build these on top of the core API:**

1. **`analyze_site_health`** – One call that returns:
   - Top 10 pages by traffic
   - Indexing status of each
   - CTR vs. average for position band
   - Mobile usability issues (if any)
   - Last crawl date
   - Robots.txt rules affecting these pages

2. **`identify_quick_wins`** – Find pages worth optimizing:
   - High impressions (>100) but CTR <2%
   - Ranked 4–10 (on second page)
   - No indexing issues
   - Returns suggested title/meta improvements

3. **`export_full_dataset`** – Bypass 5K row limit:
   - Loops through all rows using batch queries
   - Returns all queries, pages, countries, devices in one JSON
   - Optionally pipe to BigQuery or save to GCS

4. **`crawl_error_summary`** – Aggregate indexing errors:
   - Broken URLs
   - Soft 404s
   - Mobile usability issues
   - By property

5. **`property_migration_checklist`** – When moving sites:
   - List all indexed pages
   - Verify sitemaps
   - Check 301 redirects are indexed as redirects (not errors)
   - Suggest property settings to update

---

## Architecture Requirements

### Deployment Model
- **Technology:** Python (FastAPI or Flask)
- **Transport:** SSE (Server-Sent Events) — matches your existing stack
- **Hosting:** Google Cloud Run (asia-southeast1)
- **Container:** Dockerfile included
- **Port:** 3001 (or configurable)
- **Endpoint:** `https://gsc-mcp-YOUR-HASH.asia-southeast1.run.app/sse`

### Authentication
- **OAuth 2.0** – Personal Google account (recommended for team)
  - User logs in once per property/account
  - Token stored in Cloud Run environment (or Cloud Secret Manager)
  - Auto-refresh on expiry
- **No service accounts** – GSC API doesn't work well with service accounts; OAuth is required

### Team Access Control
- **Single service account credential** OR **per-user OAuth**
  - Recommended: **per-user OAuth with a shared refresh token in env** (each team member's GSC properties accessible via one shared credential)
  - Alternative: **API key** passed per-request (less secure, but simpler for testing)
- **Audit logging** – Log which tool was called, when, by whom, for which property
- **Rate limiting** – Implement to avoid GSC API quota exhaustion
  - GSC has quota of ~200 queries/day per property, limit to 10/min per user

---

## Implementation Checklist for Claude Code

### Phase 1: Core Tools (Align with existing mcp-gsc)
- [ ] Search Analytics: query with all dimensions + filters (see above)
- [ ] Search Analytics: batch query (multiple date ranges / properties)
- [ ] Sites: list, get, add, delete, get permission level
- [ ] URL Inspection: single, batch, with full field exposure (indexing + AMP + rich results)
- [ ] Sitemaps: list, get, submit, delete + error classification
- [ ] Compare two periods
- [ ] Advanced filtering: CTR optimization, position bands, search type

### Phase 2: Extended Tools (New)
- [ ] `analyze_site_health` – composite tool
- [ ] `identify_quick_wins` – CTR + position analysis
- [ ] `export_full_dataset` – paginate 5K row limit
- [ ] `crawl_error_summary` – aggregate errors across properties
- [ ] `property_migration_checklist` – move site safely

### Phase 3: Deployment & Team Integration
- [ ] Dockerfile + docker-compose (for local dev)
- [ ] Cloud Run deploy script (with gcloud CLI)
- [ ] Environment variables: GSC_OAUTH_CLIENT_ID, GSC_OAUTH_CLIENT_SECRET, GSC_OAUTH_REDIRECT_URI
- [ ] Audit logging to Cloud Logging (who called what, when)
- [ ] Rate limiting per user/property
- [ ] Token refresh logic (auto-renew before expiry)
- [ ] Error handling + retry logic for flaky API calls
- [ ] Unit tests (mock Google API responses, zero real credentials needed)

### Phase 4: Documentation & Claude Integration
- [ ] README with team setup instructions (no per-person setup needed)
- [ ] Example prompts for team use cases
- [ ] Add server.json for official MCP registry
- [ ] Document all 25+ tools with examples
- [ ] Troubleshooting guide

---

## Data Models & API Response Structure

All tools must return **structured JSON** (not formatted text), for LLM reasoning:

```json
{
  "success": true,
  "data": {
    // Tool-specific payload
  },
  "metadata": {
    "property": "https://example.com",
    "date_range": ["2025-01-01", "2025-01-07"],
    "rows_returned": 150,
    "rows_available": 2543,
    "timestamp": "2025-04-10T12:34:56Z"
  },
  "error": null
}
```

For errors:
```json
{
  "success": false,
  "data": null,
  "error": "Property not found: https://typo.com",
  "error_code": "404_NOT_FOUND",
  "timestamp": "2025-04-10T12:34:56Z"
}
```

---

## Key Implementation Notes

1. **Row limit handling:** GSC API caps at 5,000 rows per query. Use `startRow` parameter + batch queries to fetch all data. For big sites, this is essential.

2. **Data freshness:** Google releases GSC data with 2–3 day lag. Add `data_state` parameter: `"all"` (default, includes partial data) vs. `"final"` (confirmed, 2–3 days old).

3. **Search type:** Separate `web`, `image`, `video`, `news`, `discover`, `googleNews` into dedicated filters instead of mixing them.

4. **Device breakdown:** Always support `DESKTOP`, `MOBILE`, `TABLET` filtering.

5. **Country codes:** Use ISO-3166-1 Alpha-3 codes (e.g., `USA`, `GBR`, `SGP`).

6. **URL formats:** Support both URL-prefix (`https://example.com/`) and domain properties (`sc-domain:example.com`).

7. **Batch requests:** Use Google Batch API where available to reduce round-trips.

8. **Caching:** Consider caching property list + property details (changes rarely) for 1 hour to reduce quota usage.

---

## Success Criteria

- [ ] All 19 existing tools + 5 new composite tools working (24 total)
- [ ] Team can use via Claude without per-person setup
- [ ] Handles 50K+ row exports cleanly (pagination transparent to user)
- [ ] Rate limiting prevents quota exhaustion
- [ ] Audit logs show which team member queried what
- [ ] Dockerized & deployable to Cloud Run in <5 min
- [ ] Zero hard-coded credentials in repo
- [ ] Unit test coverage >80%
- [ ] All error messages are actionable (not generic "API error")
- [ ] Documentation includes 3+ example team workflows (SEO audit, rank tracking, migration prep)

---

## Comparison Matrix: Existing vs. Complete

| Feature | Existing MCP | Complete Version |
|---------|--------------|------------------|
| Search Analytics | Basic query | + Batch, search type, data freshness, position bands |
| URL Inspection | Single + batch | + AMP, rich results, mobile usability, robots.txt check |
| Sitemaps | List/submit/delete | + Error breakdown, encoding validation |
| Sites | List/add/delete | + Permission level, verification method |
| Cross-service tools | 0 | + 5 new (health, quick wins, export, errors, migration) |
| Deployment | Local desktop only | Cloud Run + SSE + team auth |
| Row limit handling | None (caps at 5K) | Paginated export (50K+) |
| Audit logging | None | Full audit trail |
| Rate limiting | None | Per-user quota enforcement |

---

## References

- GSC API Docs: https://developers.google.com/webmaster-tools/v1/api_reference_index
- Existing mcp-gsc: https://github.com/AminForou/mcp-gsc
- Your stack: GA4 MCP (asia-southeast1.run.app), Google Ads MCP, LinkedIn MCP
- Rate limits: https://developers.google.com/webmaster-tools/limits-quotas-analytics

---

## Next Steps

1. **You:** Review this scope. Add/remove features as needed. Mark any as "defer to v2".
2. **Claude Code:** Run with this scope to build the MCP server end-to-end.
3. **You:** Test locally with Dockerfile, then deploy to Cloud Run.
4. **Team:** Use immediately with Claude + existing 2Stallions ecosystem.
