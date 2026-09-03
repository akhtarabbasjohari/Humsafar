"""
Humsafar Python Agent Runner:
Wires the humsafar-data-mcp server tools into the Django backend chat service.
Enables the agent to execute live itinerary lookups and regional coverage checks
with session-scoped caching and graceful failure handling.
"""

import logging
from typing import Dict, Any, List, Optional

from mcp_servers.humsafar_data_mcp.scraper import scraper, SourceSiteScraper
from mcp_servers.humsafar_data_mcp.server import search_itineraries, check_region_coverage

logger = logging.getLogger(__name__)

AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_itineraries",
            "description": (
                "Search live itineraries, routes, and tours on the configured tour operator website "
                "(SOURCE_SITE_URL). Returns durations, prices, schedules, and scrape timestamps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Destination, trek, or route name (e.g. 'Hunza Valley', 'K2 Base Camp', 'Skardu').",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Conversation session ID for session-scoped caching.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_region_coverage",
            "description": (
                "Determine whether a requested mountain valley or destination is within the regions "
                "the tour company serves, based on live destination listings on the source site."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Region or valley name (e.g. 'Swat', 'Baltistan', 'Fairy Meadows').",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Conversation session ID for session-scoped caching.",
                    },
                },
                "required": ["destination"],
            },
        },
    },
]


from services.data_integrity import (
    data_integrity_guard,
    DataIntegrityGuard,
    CONFIDENCE_OFFICIAL,
    CONFIDENCE_UNVERIFIED,
)


class HumsafarAgentRunner:
    """
    Agent Runner responsible for coordinating tool executions against humsafar-data-mcp,
    enforcing data integrity, freshness validation, and confidence labeling.
    """

    def __init__(
        self,
        scraper_instance: Optional[SourceSiteScraper] = None,
        integrity_guard: Optional[DataIntegrityGuard] = None,
    ):
        self.scraper = scraper_instance or scraper
        self.integrity_guard = integrity_guard or data_integrity_guard

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return LLM-compatible tool definitions."""
        return AVAILABLE_TOOLS

    def search_itineraries(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Execute search_itineraries against humsafar-data-mcp and enforce data integrity.
        Attaches source, timestamp, and confidence label to every verified itinerary.
        """
        try:
            raw_result = search_itineraries(query=query, session_id=session_id)
            if raw_result.get("success") and "results" in raw_result:
                raw_result["results"] = [
                    self.integrity_guard.process_itinerary_detail(tour, source_type="live_scrape")
                    for tour in raw_result["results"]
                ]
            return raw_result
        except Exception as exc:
            logger.error("Agent runner error executing search_itineraries: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "query": query,
                "results": [],
                "cached": False,
            }

    def present_to_visitor(
        self,
        text: str,
        grounding_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Enforce presentation integrity: ensure prices, dates, or schedules
        have verified fresh sources and confidence labels attached before showing to a visitor.
        Refuses to present unverified figures as confirmed facts.
        """
        return self.integrity_guard.enforce_presentation_integrity(
            text=text,
            grounding_data=grounding_data,
        )

    def check_region_coverage(self, destination: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Execute check_region_coverage against humsafar-data-mcp.
        """
        try:
            return check_region_coverage(destination=destination, session_id=session_id)
        except Exception as exc:
            logger.error("Agent runner error executing check_region_coverage: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "destination": destination,
                "serviced": False,
                "matched_regions": [],
                "cached": False,
            }

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Dispatch a tool call request from an LLM by name.
        """
        if tool_name == "search_itineraries":
            query = arguments.get("query", "")
            return self.search_itineraries(query=query, session_id=session_id)

        elif tool_name == "check_region_coverage":
            destination = arguments.get("destination", "")
            return self.check_region_coverage(destination=destination, session_id=session_id)

        else:
            return {
                "success": False,
                "error": f"Unknown tool '{tool_name}'. Available: ['search_itineraries', 'check_region_coverage']",
            }


# Singleton runner instance
agent_runner = HumsafarAgentRunner()
