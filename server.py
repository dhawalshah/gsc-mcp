"""Google Search Console MCP Server — tool registrations."""
from fastmcp import FastMCP
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

mcp = FastMCP("Google Search Console Tools")

# --- Sites ---
from gsc.sites import list_properties, get_site_details, add_site, delete_site
mcp.tool(list_properties)
mcp.tool(get_site_details)
mcp.tool(add_site)
mcp.tool(delete_site)

# --- Search Analytics ---
from gsc.search_analytics import (
    get_search_analytics,
    get_performance_overview,
    compare_periods,
    get_position_band_report,
    get_ctr_optimization_report,
    get_keyword_cannibalization,
    batch_search_analytics,
    export_full_dataset,
)
mcp.tool(get_search_analytics)
mcp.tool(get_performance_overview)
mcp.tool(compare_periods)
mcp.tool(get_position_band_report)
mcp.tool(get_ctr_optimization_report)
mcp.tool(get_keyword_cannibalization)
mcp.tool(batch_search_analytics)
mcp.tool(export_full_dataset)

# --- URL Inspection ---
from gsc.url_inspection import inspect_url, batch_url_inspection
mcp.tool(inspect_url)
mcp.tool(batch_url_inspection)

# --- Sitemaps ---
from gsc.sitemaps import list_sitemaps, get_sitemap, submit_sitemap, delete_sitemap
mcp.tool(list_sitemaps)
mcp.tool(get_sitemap)
mcp.tool(submit_sitemap)
mcp.tool(delete_sitemap)

# --- Composite ---
from gsc.composite import (
    analyze_site_health,
    identify_quick_wins,
    crawl_error_summary,
    property_migration_checklist,
)
mcp.tool(analyze_site_health)
mcp.tool(identify_quick_wins)
mcp.tool(crawl_error_summary)
mcp.tool(property_migration_checklist)

if __name__ == "__main__":
    mcp.run()
