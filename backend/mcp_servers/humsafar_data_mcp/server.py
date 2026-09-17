"""
humsafar-data-mcp server: Custom MCP Server for live itinerary and regional data scraping.
Exposes tools for reading live ground truth data from SOURCE_SITE_URL.
"""

import sys
import logging
from typing import Dict, Any

from mcp.server.mcpserver import MCPServer
from .scraper import scraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("humsafar-data-mcp")

# Initialize MCP Server
mcp_server = MCPServer("humsafar-data-mcp")


@mcp_server.tool()
def search_itineraries(query: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Search live itineraries using retrieval-augmented semantic matching and live catalog scraping
    from the configured source site (SOURCE_SITE_URL).
    Combines dense FAISS embedding retrieval with keyword relevance to resolve nicknames,
    landmarks, and loosely-worded queries (e.g. 'K2 base camp' matching 'Concordia Trek').

    Args:
        query: Destination, circuit, landmark, or tour nickname (e.g., 'Hunza', 'K2 Base Camp', 'Golden Peak').
        session_id: Optional conversation session identifier for session-scoped caching.

    Returns:
        Structured dictionary containing matched itineraries, pricing, duration, highlights,
        source URL, and the ISO 8601 scraping timestamp.
    """
    logger.info("search_itineraries called: query='%s', session_id='%s'", query, session_id)
    return scraper.search_itineraries(query=query, session_id=session_id)


@mcp_server.tool()
def check_region_coverage(destination: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Determine whether a requested destination falls within a region the company serves,
    even when there is no exact pre-packaged itinerary match, based on the source site's
    own listed regions or destinations catalog.

    Args:
        destination: Name of the region, valley, or landmark (e.g., 'Swat', 'Baltistan', 'Skardu').
        session_id: Optional conversation session identifier for session-scoped caching.

    Returns:
        Structured dictionary confirming coverage status (serviced: bool), matched regions,
        source URL, and scrape timestamp.
    """
    logger.info("check_region_coverage called: destination='%s', session_id='%s'", destination, session_id)
    return scraper.check_region_coverage(destination=destination, session_id=session_id)


def main():
    """Run the MCP server over stdio transport."""
    logger.info("Starting humsafar-data-mcp server over stdio transport...")
    mcp_server.run()


if __name__ == "__main__":
    main()
