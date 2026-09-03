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

    def _extract_destination(self, message: str) -> str:
        """Extract primary destination or mountain region mentioned in traveler message."""
        known = [
            "fairy meadows", "k2 base camp", "k2", "concordia", "nanga parbat",
            "chitral", "kalash", "swat", "kalam", "kumrat", "deosai", "hunza",
            "skardu", "shimshal", "passu", "naran", "kaghan", "astor", "gilgit",
            "baltistan", "karakoram", "hindukush", "himalaya", "khunjerab",
            "lahore", "karachi", "islamabad", "paris", "tokyo", "dubai", "london",
        ]
        lower_msg = message.lower()
        for k in known:
            if k in lower_msg:
                return k.title()
        return message.strip()

    def run_multi_hop_pipeline(
        self,
        user_message: str,
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Multi-hop reasoning pipeline enforcing the exact flow:
        1. check_itinerary -> If match found, present official listing (Path 1).
        2. check_region -> If NOT served, return polite boundary reply (Path 3).
        3. search_web -> If served but no direct package, run constrained web search (Step 3).
        4. draft_itinerary -> Synthesize unverified proposal using preferences & Phase 4 rules (Path 2).

        Every hop records structured logs into reasoning_steps for Phase 9 observability hooks.
        """
        from datetime import datetime, timezone
        from services.groq_service import generate_travel_reply
        from services.web_search_service import web_search_service
        from services.itinerary_drafter import (
            extract_traveler_preferences,
            draft_custom_itinerary,
        )

        conv_history = conversation_history or []
        reasoning_steps: List[Dict[str, Any]] = []
        destination = self._extract_destination(user_message)

        # -------------------------------------------------------------
        # STEP 1: Check Itinerary
        # -------------------------------------------------------------
        itinerary_res = self.search_itineraries(query=destination, session_id=session_id)
        matched_tours = itinerary_res.get("results", [])

        if not matched_tours and destination.lower() != user_message.strip().lower():
            second_res = self.search_itineraries(query=user_message, session_id=session_id)
            if second_res.get("results"):
                matched_tours = second_res["results"]

        # Check if any tour returned actually matches the requested destination
        import re
        dest_words = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", destination) if w.lower() not in {"tour", "trip", "plan", "visit", "trek", "with", "from", "for", "days", "day"}]
        relevant_tours = []
        for tour in matched_tours:
            haystack = f"{tour.get('title', '').lower()} {tour.get('summary', '').lower()}"
            if any(dw in haystack for dw in dest_words):
                relevant_tours.append(tour)

        matches_count = len(relevant_tours)

        reasoning_steps.append({
            "step_index": 1,
            "step_name": "check_itinerary",
            "description": "Query humsafar-data-mcp search_itineraries for direct pre-packaged tours.",
            "input": {"query": destination},
            "output": {
                "matches_found": matches_count,
                "matched_titles": [t.get("title") for t in relevant_tours[:3]],
            },
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Path 1: Official Itinerary Match
        if matches_count > 0:
            primary_tour = relevant_tours[0]
            raw_reply = generate_travel_reply(
                user_message=user_message,
                conversation_history=conv_history,
                matched_itineraries=relevant_tours,
            )
            presented = self.present_to_visitor(text=raw_reply, grounding_data=primary_tour)
            return {
                "path": "official_match",
                "reply_text": presented["text"],
                "itinerary": primary_tour,
                "confidence_label": CONFIDENCE_OFFICIAL,
                "source_url": primary_tour.get("source_url"),
                "reasoning_steps": reasoning_steps,
            }

        # -------------------------------------------------------------
        # STEP 2: Check Region Coverage
        # -------------------------------------------------------------
        region_res = self.check_region_coverage(destination=destination, session_id=session_id)
        is_serviced = region_res.get("serviced", False) or len(region_res.get("matched_regions", [])) > 0
        matched_regions = region_res.get("matched_regions", [])

        reasoning_steps.append({
            "step_index": 2,
            "step_name": "check_region",
            "description": "Query humsafar-data-mcp check_region_coverage to verify geographic scope.",
            "input": {"destination": destination},
            "output": {
                "is_serviced": is_serviced,
                "matched_regions": matched_regions,
            },
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Path 3: Destination Not Served (Out of Coverage)
        if not is_serviced:
            out_reply = (
                f"Salam! Thank you for inquiring about traveling to {destination}. "
                "Indus Trekking and Tours Pakistan specializes strictly in the mountain regions of northern Pakistan "
                "(Karakoram, Himalayas, Hindukush, Gilgit-Baltistan, Hunza, Skardu, Swat, Chitral, Fairy Meadows, and surrounding valleys). "
                f"At this time, we do not operate tours to {destination}. "
                "We would be delighted to help you explore any of our mountain destinations instead!"
            )
            presented = self.present_to_visitor(text=out_reply, grounding_data=None)
            return {
                "path": "out_of_coverage",
                "reply_text": presented["text"],
                "itinerary": None,
                "confidence_label": "out_of_coverage",
                "source_url": region_res.get("source_url"),
                "reasoning_steps": reasoning_steps,
            }

        # -------------------------------------------------------------
        # STEP 3: Search Web Fallback (Region is served, but no direct package)
        # -------------------------------------------------------------
        web_res = web_search_service.search(destination=destination)
        top_url = web_res.get("top_source_url", "https://visitpakistan.gov.pk")

        reasoning_steps.append({
            "step_index": 3,
            "step_name": "search_web",
            "description": "Execute constrained web search fallback for destination travel highlights.",
            "input": {
                "destination": destination,
                "constrained_query": web_res.get("query"),
            },
            "output": {
                "provider": web_res.get("provider"),
                "results_count": len(web_res.get("results", [])),
                "top_source_url": top_url,
            },
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # -------------------------------------------------------------
        # STEP 4: Draft Itinerary Skill
        # -------------------------------------------------------------
        prefs = extract_traveler_preferences(
            user_message=user_message,
            conversation_history=conv_history,
            default_destination=destination,
        )

        draft_res = draft_custom_itinerary(
            user_message=user_message,
            conversation_history=conv_history,
            destination=destination,
            web_research=web_res,
            preferences=prefs,
        )

        draft_itinerary = draft_res["itinerary_draft"]

        reasoning_steps.append({
            "step_index": 4,
            "step_name": "draft_itinerary",
            "description": "Synthesize custom draft proposal using preferences, research, and Phase 4 integrity rules.",
            "input": {
                "destination": destination,
                "preferences": prefs.to_dict(),
            },
            "output": {
                "draft_title": draft_itinerary.get("title"),
                "duration": draft_itinerary.get("duration"),
                "estimated_price": draft_itinerary.get("price"),
                "confidence_label": CONFIDENCE_UNVERIFIED,
                "source_url": top_url,
            },
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        presented = self.present_to_visitor(
            text=draft_res["reply_text"],
            grounding_data=draft_itinerary,
        )

        return {
            "path": "web_search_draft",
            "reply_text": presented["text"],
            "itinerary": draft_itinerary,
            "confidence_label": CONFIDENCE_UNVERIFIED,
            "source_url": top_url,
            "reasoning_steps": reasoning_steps,
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
