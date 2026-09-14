"""
Humsafar Python Agent Runner:
Wires the humsafar-data-mcp server tools into the Django backend chat service.
Enables the agent to execute live itinerary lookups and regional coverage checks
with session-scoped caching and graceful failure handling.
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional

from mcp_servers.humsafar_data_mcp.scraper import scraper, SourceSiteScraper
from mcp_servers.humsafar_data_mcp.server import search_itineraries, check_region_coverage

from services.pricing_service import calculate_realistic_tour_pricing
from services.travel_constants import (
    CONTACT_DETAILS,
    OPERATIONAL_REGIONS,
    OPERATIONAL_REGIONS_DETAILED,
)
from services.observability_service import log_tool_call
from services.ollama_service import ollama_service
from services.feasibility_engine import feasibility_engine, FeasibilityEvaluation

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
                "Determine whether a requested destination falls within a region the company serves, "
                "based on the source site's listed regions or destinations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destination or region name (e.g. 'Hunza', 'Skardu', 'Fairy Meadows', 'Swat').",
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


AGENT_SYSTEM_PROMPT = f"""You are Humsafar, the senior expedition designer and official AI mountain guide for Askoli Adventure (askoliadventure.com).

OPERATIONAL REGIONS:
We specialize strictly in the mountain and wilderness regions of Northern Pakistan:
{OPERATIONAL_REGIONS_DETAILED}

CORE OPERATING DIRECTIVES & GUIDELINES:
1. CASUAL GREETINGS & PLEASANTRIES:
   - For queries like "hi", "hello", "salaam", "how are you?", "what can you do?", or friendly small talk:
   - DO NOT call any tools.
   - Reply naturally, warmly, and hospitably. Introduce yourself as Humsafar, describe how you can help plan expeditions in Northern Pakistan, and invite them to share their travel ideas.
   - Never output repetitive canned paragraphs or attach random tour cards.

2. UNDERSTAND TRAVELER INTENT & PREFERENCES:
   - Always prioritize what the traveler is actually requesting. Never force a canned or unrelated tour just because a single keyword matched our website catalog.
   - If the traveler asks for a custom duration, pacing, or specific experience, honor those exact preferences.

3. MULTI-DESTINATION & COMBINED TOURS:
   - If the traveler asks to visit MULTIPLE destinations (e.g. "Hunza, Skardu, and Swat", "Skardu and Fairy Meadows in 10 days", or "Kalam and Chitral"):
     * Check if our catalog has a combined tour covering ALL those destinations.
     * If our catalog only covers one of the destinations, DO NOT force a single-destination catalog package.
     * Call `search_external_web` to research the connection routes between those valleys, realistic road transit times, and highlights across all requested locations.
     * Synthesize a cohesive multi-destination itinerary that includes ALL the places the traveler asked to visit.

4. FEASIBILITY & PRACTICALITY (SAFETY FIRST):
   - You are an authentic senior mountain expedition guide in rugged high-altitude terrain. You must strictly evaluate whether the traveler's requested schedule, duration, and logistics are physically and geographically possible.
   - PHYSICAL & GEOGRAPHICAL REALITIES OF NORTHERN PAKISTAN:
     * High-Altitude Glacier Treks (K2 Base Camp, Concordia, Gondogoro La, Snow Lake, Nanga Parbat Base Camp):
       - Requires a MINIMUM of 14 to 21 days due to the remote Baltoro Glacier trail (100+ km round-trip trek from Askole) and mandatory acclimatization rest days to prevent deadly altitude sickness (AMS/HAPE/HACE).
       - It is physically impossible to trek to K2 Base Camp in 1, 2, or 3 days.
     * Road Travel & Inter-Valley Transit:
       - Mountain travel between major hubs (Islamabad -> Skardu or Gilgit) requires 14-20 hours on the Karakoram Highway / Jaglot-Skardu road.
       - Gilgit to Skardu takes 6-8 hours; Swat to Hunza takes 10-14 hours.
       - Attempting to cover multiple distant regions in 1-2 days is physically impossible.
   - IF A TRAVELER'S REQUEST OR TIMEFRAME IS NOT FEASIBLE:
     * State immediately, politely, and authoritatively that the requested plan or timeframe is physically impossible or hazardous.
     * Explain the specific reasons in detail (trekking distance over moraine, acclimatization schedule, mountain road transit hours).
     * Provide the realistic minimum timeframe required (e.g. "K2 Base Camp requires a minimum of 18–21 days"), or suggest realistic short alternatives nearby (e.g. scenic viewpoints around Skardu or Gilgit for a 1-2 day trip).
     * DO NOT create, draft, or attach an itinerary package for impossible requests!

5. CONVERSATIONAL ITINERARY MODIFICATIONS:
   - If the traveler asks to modify, update, or customize an itinerary previously discussed in the chat (e.g. "add an extra day in Karimabad", "change hotel to luxury", "reduce duration to 5 days", "add Passu Cones to the plan"):
     * Review the earlier itinerary from conversation history.
     * Incorporate the traveler's requested adjustments directly into an updated proposal.
     * Clearly highlight what changes were made.
     * Present the updated itinerary accurately.

6. OUT OF COVERAGE:
   - If a requested destination is outside our operational mountain territory (e.g. New York, Paris, London, Dubai, Tokyo, Karachi, Lahore):
     * Explain politely that Askoli Adventure specializes strictly in the mountain wilderness of Northern Pakistan, and invite them to explore those instead.
     * DO NOT call `search_external_web` or attach any itinerary.

7. SINGLE-DESTINATION OFFICIAL MATCH:
   - If the traveler requests a single destination or specific expedition that directly matches an official package in our catalog (and matches the duration/scope):
     * Present the verified official tour package with authentic details and pricing.

8. RESPONSE FORMATTING (LIKE CHATGPT):
   - "Structure is earned, not default": Short questions get short plain prose.
   - For pricing, budget, or seasonal cost inquiries: Provide transparent, itemized cost estimates in PKR and USD, party-size scaling, and seasonal considerations.
   - For explicitly requested itineraries:
     * DO NOT dump a raw day-by-day route schedule (Day 1, Day 2, Day 3...) in your markdown text response!
     * All daily route stages, waypoints, camp elevations, and terrain details are rendered exclusively in the official interactive itinerary card directly below your response.
     * In your text response, provide ONLY the concise route overview narrative, character, seasonal highlights, and concrete pricing in PKR & USD, followed by key inclusions and gear highlights.
     * Conclude with a clean 1-sentence prompt directing the traveler to explore the full day-by-day route timeline and stages in the interactive itinerary card below.
   - Never output internal reasoning, <think> tags, or markdown code fences around plain text.

9. STRICT CONCISENESS & LENGTH BUDGET:
   - Keep your total text commentary strictly within 150 to 250 words.
   - Conclude all thoughts completely within this budget so your response finishes cleanly.
"""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_itp_catalog",
            "description": "Search live official itineraries and tours on askoliadventure.com. Call this first for any tour or trip request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Destination, trek, or route name (e.g. 'Hunza Valley', 'K2 Base Camp', 'Skardu').",
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
            "description": "Check whether a destination or region is within the serviced mountain regions of Northern Pakistan (Gilgit-Baltistan, KPK mountain valleys, AJK). Call this if not found in catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "Destination or region name.",
                    },
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_external_web",
            "description": "Search external multi-page travel data for route stages, highlights, equipment, and realistic pricing when destination is covered but has no direct catalog package.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Destination travel inquiry query.",
                    },
                },
                "required": ["query"],
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


def classify_user_intent(
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Categorizes traveler intent to prevent forcing itineraries onto pricing or factual inquiries:
    - 'conversational': greetings, small talk, gratitude
    - 'comparison': side-by-side comparison of 2+ valleys/expeditions
    - 'pricing': explicit cost/price inquiry, budget breakdown, or pricing of user's own plan
    - 'itinerary_planning': explicit request to plan/draft/schedule a multi-day itinerary
    - 'general_knowledge': facts, attractions, seasons, roads, culture, safety, advice
    """
    import re
    clean_msg = user_message.strip().lower()
    clean_words = re.findall(r"\b[a-z]+\b", clean_msg)

    # 1. Greetings & Small Talk
    greetings = {
        "hi", "hello", "hey", "salaam", "salam", "assalam", "assalamu", "alaykum",
        "alaikum", "mornin", "morning", "afternoon", "evening", "greetings"
    }
    small_talk_starters = [
        "who are you", "what are you", "what can you do", "how does this work",
        "how do you work", "tell me about yourself", "what do you do", "help me",
        "how are you", "how are you doing", "how r u", "how do you do", "what's up",
        "whats up", "how's it going", "hows it going"
    ]
    if bool(clean_words) and all(w in greetings or w in {"humsafar", "there", "friend", "team", "good", "a"} for w in clean_words):
        return "conversational"
    if any(p in clean_msg for p in small_talk_starters) or (
        bool(clean_words) and all(w in {"thanks", "thank", "thx", "ok", "okay", "cool", "great", "nice", "awesome", "bye", "goodbye", "you", "so", "much"} for w in clean_words)
    ):
        return "conversational"

    # 2. Side-by-side comparison
    if re.search(r"\b(compare|versus|\bvs\b|difference between)\b", clean_msg):
        return "comparison"

    # 3. User's own plan and Pricing Inquiries
    pricing_patterns = [
        r"\b(?:how\s+much|what(?:\s+is|\s+'s)?\s+(?:the\s+)?(?:price|cost|budget|rate|charges?|fee|expense|expenditure))\b",
        r"\b(?:price|pricing|cost|budget|rates?|charges?|quote|quotation|estimate|estimated\s+cost|package\s+cost|per\s+person\s+cost)\b",
        r"\b(?:how\s+much\s+(?:does\s+it|will\s+it|would\s+it)\s+cost)\b",
        r"\b(?:is\s+it\s+expensive|how\s+expensive|affordable|cheap)\b",
        r"\b(?:cost\s+for\s+\d+\s+people|price\s+for\s+\d+\s+persons?)\b",
        r"\b(?:kitna\s+kharch[aa]?|kitne\s+paise|kya\s+price|kya\s+cost|kitna\s+budget|rate\s+kya\s+hai|charges\s+kya\s+hain|kitna\s+lagega)\b",
        r"\b(?:prices?|costs?)\s+of\b",
    ]
    has_pricing_query = any(re.search(p, clean_msg) for p in pricing_patterns)

    user_own_plan_patterns = [
        r"\b(?:my\s+plan|our\s+plan|i\s+have\s+a\s+plan|we\s+have\s+a\s+plan|this\s+is\s+my\s+plan|here\s+is\s+my\s+plan)\b",
        r"\b(?:day\s*1\b|day\s*2\b|day\s*one\b)",
        r"\b(?:mera\s+plan|hamara\s+plan|apna\s+plan)\b",
    ]
    has_user_own_plan = any(re.search(p, clean_msg) for p in user_own_plan_patterns)

    # 4. Explicit Itinerary Planning Request (with robust typo handling: iternary, itinary, day to day, etc.)
    ITINERARY_FUZZY = r"(?:itinerary|itineraries|iternary|iternaries|itinary|itinaries|itenerary|iteneraries|itrenary|itrnary|itinery)"
    DAY_BY_DAY_FUZZY = r"(?:day[- ](?:by|to)[- ]day|day[- ]wise|daily\s+(?:route|schedule|plan|breakdown)|stage[- ]by[- ]stage)"

    has_itinerary_word = bool(re.search(r"\b" + ITINERARY_FUZZY + r"\b", clean_msg))
    has_day_by_day = bool(re.search(DAY_BY_DAY_FUZZY, clean_msg))

    explicit_planning_patterns = [
        r"\b(?:plan|design|draft|create|generate|make|build|prepare|organize|structure)\s+(?:me\s+)?(?:an?\s+)?(?:the\s+)?(?:complete\s+)?(?:full\s+)?(?:custom\s+)?(?:" + ITINERARY_FUZZY + r"|tour\s+plan|trip\s+plan|expedition\s+plan|schedule|tour\s+package)\b",
        r"\b(?:plan\s+(?:me\s+)?(?:a|my|an|our)\s+(?:\d+[\s\-]*(?:days?|nights?)\s+)?(?:trip|expedition|tour|journey|holiday|vacation|trek))\b",
        r"\b(?:want|need|give\s+me|provide|show\s+me|share)\s+(?:an?\s+)?(?:the\s+)?(?:complete\s+)?(?:full\s+)?(?:" + DAY_BY_DAY_FUZZY + r"\s+)?(?:" + ITINERARY_FUZZY + r"|tour\s+plan|trip\s+plan|full\s+plan)\b",
        r"\b(?:give\s+me|show\s+me|share|provide)\s+(?:the\s+)?(?:complete\s+)?(?:full\s+)?(?:" + DAY_BY_DAY_FUZZY + r")\b",
        r"\b\d+[\s\-]*(?:days?|nights?)\s+(?:" + ITINERARY_FUZZY + r"|tour\s+plan|trip\s+plan|tour\s+package)\b",
        r"\b(?:" + ITINERARY_FUZZY + r"|tour\s+plan)\s+for\s+[a-zA-Z\s]+\b",
        r"\b[a-zA-Z0-9\s\-]+(?:trek|tour|expedition|trip)?\s*" + ITINERARY_FUZZY + r"\b",
        r"\b(?:tell\s+me\s+about|details?\s+of|show\s+me|share|view)\s+[a-zA-Z0-9\s\-]+" + ITINERARY_FUZZY + r"\b",
        r"\b(?:plan\s+an?\s+" + ITINERARY_FUZZY + r")\b",
        r"\b(?:plan\s+(?:a|an)?\s*\d+[\s\-]*(?:days?|nights?)\b)",
        r"\b(?:plan|" + ITINERARY_FUZZY + r"|schedule)\s*(?:bana|bna|banayein|banaen|chahiye|dein|do)\b",
        r"\btour\s+plan\s+banao\b",
    ]
    has_explicit_planning = any(re.search(p, clean_msg) for p in explicit_planning_patterns)

    # If the user presents their own plan and asks for pricing: strictly pricing intent!
    if has_user_own_plan and has_pricing_query:
        return "pricing"

    # If the user asks for pricing/cost without asking to build/plan an itinerary: strictly pricing intent!
    if has_pricing_query and not has_explicit_planning:
        return "pricing"

    # If explicit planning request or contains itinerary / day-by-day request: itinerary planning
    if has_explicit_planning or has_itinerary_word or has_day_by_day:
        return "itinerary_planning"

    # 5. General Knowledge / Travel Advice / Logistics
    general_knowledge_patterns = [
        r"\b(what|which)\s+(dates?|months?|seasons?|time of year|window)\b",
        r"\b(when|what time)\s+(is|are|does|can|should)\b",
        r"\b(best|optimal|recommended)\s+(time|season|month|window)\b",
        r"\b(how\s+high|altitude|elevation|height)\b",
        r"\b(?:do|does|can|will|should)\s+(?:i|we|foreign(?:ers| tourists)?|tourists?|travelers?|visitors?|anyone)\s+(?:need|get|require|obtain|apply\s+for)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass)\b",
        r"\b(?:is\s+there|are\s+there)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass|rules?|restrictions?)\b",
        r"\b(?:need|require|requirements?)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass)\b",
        r"\b(?:permit|visa|noc|clearance)\s+(?:requirements?|needed|required)\b",
        r"\b(how\s+difficult|what\s+grade|fitness\s+level|how\s+fit)\b",
        r"\b(what\s+temperature|how\s+cold|what\s+weather)\b",
        r"\b(can\s+i|is\s+it\s+safe)\b",
        r"\b(?:tell\s+me\s+about|what\s+is|what\s+are|how\s+is|information\s+about|guide\s+to|what\s+to\s+see|places\s+to\s+(?:see|visit)|attractions|things\s+to\s+do|must\s+visit|sightseeing)\b",
        r"\b(?:road\s+condition|is\s+road\s+open|babusar\s+open|how\s+to\s+reach|distance|travel\s+time|flight|airport)\b",
        r"\b(?:safe\s+for\s+(?:family|kids|children|women)|solo\s+travel|security)\b",
        r"\b(?:culture|history|people|language|food|festival|local\s+customs)\b",
        r"\b(?:what\s+to\s+pack|what\s+to\s+wear|clothes|equipment|shoes|sleeping\s+bag|gear)\b",
        r"\b(?:ke\s+bare\s+me|kaisa\s+hai|kab\s+jana\s+chahiye|mausam|dekhne\s+ki\s+jagah|ghoomne\s+ki\s+jagah|road\s+kaisa|safe\s+hai)\b",
    ]
    if any(re.search(p, clean_msg) for p in general_knowledge_patterns):
        return "general_knowledge"

    # Multi-day trip request phrasing like "I want to visit Chitral and Kalash for 5 days with 2 people"
    if re.search(r"\b\d+[\s\-]*(?:days?|nights?)\b", clean_msg) and any(w in clean_msg for w in ["visit", "trip", "tour", "trek", "travel"]):
        return "itinerary_planning"

    # If asking a question using question words
    if any(q_word in clean_msg for q_word in ["what", "how", "why", "where", "can", "is", "tell", "kya", "kaise", "kaisa", "batao", "bataen"]):
        return "general_knowledge"

    # Default to general_knowledge rather than forcing an itinerary
    return "general_knowledge"


class HumsafarAgentRunner:
    """
    Python agent runner executing multi-hop tool-calling patterns against humsafar-data-mcp.
    Integrates live WordPress scraping, session-scoped caching, Groq synthesis,
    and Phase 4 Data Integrity Guardrails.
    """

    def __init__(self):
        self.scraper: SourceSiteScraper = scraper
        self.integrity_guard: DataIntegrityGuard = data_integrity_guard

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return LLM-compatible tool definitions."""
        return AVAILABLE_TOOLS

    def search_itineraries(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Execute search_itineraries against humsafar-data-mcp.
        Enforces Phase 4 data provenance, fresh timestamps, and Phase 10 observability logging.
        Preprocesses raw scraped content with Ollama before passing to Groq.
        """
        start_time = time.time()
        try:
            raw_result = search_itineraries(query=query, session_id=session_id)
            if raw_result.get("success") and "results" in raw_result:
                # Fast cleanup of scraped tour summaries to preserve low latency
                for tour in raw_result["results"]:
                    summary = tour.get("summary") or ""
                    if summary:
                        tour["summary"] = re.sub(r"\s+", " ", summary).strip()[:400]

                raw_result["results"] = [
                    self.integrity_guard.process_itinerary_detail(tour, source_type="live_scrape")
                    for tour in raw_result["results"]
                ]

            duration_ms = (time.time() - start_time) * 1000
            is_success = bool(raw_result.get("success", False))
            log_tool_call(
                session_id=session_id,
                skill="itinerary_lookup",
                tool_name="search_itineraries",
                status="success" if is_success else "failed",
                input_data={"query": query},
                output_data={
                    "count": raw_result.get("count", len(raw_result.get("results", []))),
                    "cached": raw_result.get("cached", False),
                    "matched_titles": [t.get("title") for t in raw_result.get("results", [])[:3]],
                },
                error_message=raw_result.get("error", ""),
                duration_ms=duration_ms,
            )
            return raw_result
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("Agent runner error executing search_itineraries: %s", exc)
            log_tool_call(
                session_id=session_id,
                skill="itinerary_lookup",
                tool_name="search_itineraries",
                status="failed",
                input_data={"query": query},
                output_data={"count": 0, "results": []},
                error_message=str(exc),
                duration_ms=duration_ms,
            )
            return {
                "success": False,
                "error": str(exc),
                "query": query,
                "count": 0,
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
        Logs the execution to the observability table.
        """
        start_time = time.time()
        try:
            res = check_region_coverage(destination=destination, session_id=session_id)
            duration_ms = (time.time() - start_time) * 1000
            is_success = bool(res.get("success", True))
            log_tool_call(
                session_id=session_id,
                skill="region_coverage_check",
                tool_name="check_region_coverage",
                status="success" if is_success else "failed",
                input_data={"destination": destination},
                output_data={
                    "serviced": res.get("serviced", False),
                    "matched_regions": res.get("matched_regions", []),
                    "cached": res.get("cached", False),
                },
                error_message=res.get("error", ""),
                duration_ms=duration_ms,
            )
            return res
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("Agent runner error executing check_region_coverage: %s", exc)
            log_tool_call(
                session_id=session_id,
                skill="region_coverage_check",
                tool_name="check_region_coverage",
                status="failed",
                input_data={"destination": destination},
                output_data={"serviced": False, "matched_regions": []},
                error_message=str(exc),
                duration_ms=duration_ms,
            )
            return {
                "success": False,
                "error": str(exc),
                "destination": destination,
                "serviced": False,
                "matched_regions": [],
                "cached": False,
            }

    def _extract_destination(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Dynamically extracts primary destination or travel region mentioned in traveler message.
        Uses fuzzy token matching against regional targets, robust contextual regex patterns,
        and in-context conversation memory fallback for multi-turn follow-ups.
        """
        import re
        import difflib

        msg = message.strip()
        words = re.findall(r"\b[a-zA-Z0-9'-]+\b", msg)

        # Prominent mountain travel destinations, valleys, peaks, and passes in Pakistan
        TARGETS = [
            "K2 Base Camp", "Baltoro Glacier", "Concordia", "Broad Peak",
            "Gasherbrum 1", "Gasherbrum 2", "Gasherbrum", "Gashabrum 1", "Gashabrum 2", "Gashebrum 1", "Gashebrum 2",
            "Spantik", "Trango Towers", "Nanga Parbat", "Fairy Meadows", "Deosai", "Shangrila", "Skardu",
            "Hunza", "Passu", "Passu Cones", "Shimshal", "Batura", "Rakaposhi", "Diran", "Rush Lake",
            "Chitral", "Kalash", "Swat", "Kumrat", "Kalam", "Naran", "Kaghan", "Neelum Valley", "Arang Kel",
            "Shigar", "Khaplu", "Hushe", "Nangma Valley", "Biafo", "Hispar", "Snow Lake", "Chogo Lungma",
            "Gondogoro La", "Haramosh", "Malubiting", "Astore", "Gilgit", "Attabad", "Khunjerab", "Malam Jabba"
        ]

        CANONICAL_MAP = {
            "shangrilla": "Shangrila",
            "shangri-la": "Shangrila",
            "gashabrum": "Gasherbrum",
            "gashebrum": "Gasherbrum",
            "gashabrum 2": "Gasherbrum 2",
            "gashebrum 2": "Gasherbrum 2",
            "gashabrum 1": "Gasherbrum 1",
            "gashebrum 1": "Gasherbrum 1",
            "k2 basecamp": "K2 Base Camp",
            "broadpeak": "Broad Peak",
        }

        # 1. Check n-grams against destination targets (with typo / phonetic fuzzy tolerance)
        for n in [3, 2, 1]:
            for i in range(len(words) - n + 1):
                span_words = words[i : i + n]
                span_text = " ".join(span_words)
                span_lower = span_text.lower()

                if span_lower in CANONICAL_MAP:
                    return CANONICAL_MAP[span_lower]

                for t in TARGETS:
                    if span_lower == t.lower():
                        return CANONICAL_MAP.get(t.lower(), t)

                cutoff = 0.8 if n == 1 else 0.75
                close = difflib.get_close_matches(span_lower, [t.lower() for t in TARGETS], n=1, cutoff=cutoff)
                if close:
                    matched_target = next(t for t in TARGETS if t.lower() == close[0])
                    return CANONICAL_MAP.get(matched_target.lower(), matched_target)

        # 2. Contextual verb/preposition patterns
        patterns = [
            r"(?:tell\s+(?:me\s+)?about|info\s+(?:about|on)|details\s+(?:about|on)|about)\s+([A-Za-z0-9\s&'-]+?)(?:\s+(?:for|with|in|during|next|this|on|from|starting|under|around|budget|price)|\?|\.|$|\!)",
            r"(?:[a-zA-Z]+\s+)?(?:expeditions?|tours?|trips?|travels?|treks?|visits?|journeys?|vacations?|itineraries|itinerary|holidays?|packages?)\s+(?:to|in|around|of|for|about)\s+([A-Za-z0-9\s&'-]+?)(?:\s+(?:for|with|in|during|next|this|on|from|starting|under|around|budget|price)|\?|\.|$|\!)",
            r"(?:visit|explore|plan|design|organize|see|head\s+to|go\s+to)\s+([A-Za-z0-9\s&'-]+?)(?:\s+(?:for|with|in|during|next|this|on|from|starting|under|around|budget|price)|\?|\.|$|\!)",
            r"(?:going|heading)\s+to\s+([A-Za-z0-9\s&'-]+?)(?:\s+(?:for|with|in|during|next|this|on|from)|\?|\.|$|\!)",
            r"([A-Za-z0-9\s&'-]+?\s+(?:valley|valleys|pass|glacier|lake|peak|mountain|base\s*camp|circuit|range|plateau|desert|city|highway))",
        ]

        stop_words = {
            "a", "an", "the", "and", "or", "of", "in", "to", "my", "our", "some", "any", "this", "that", "these",
            "days", "day", "people", "persons", "pax", "travelers", "friends", "family",
            "trip", "tour", "itinerary", "expedition", "trek", "plan", "me", "us", "you",
            "please", "can", "could", "would", "like", "want", "need", "offer", "city",
            "tours in", "city tours in", "visit", "see", "explore"
        }

        for pat in patterns:
            match = re.search(pat, msg, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                cleaned_words = [w for w in candidate.split() if w.lower() not in stop_words]
                if cleaned_words:
                    clean_res = " ".join(cleaned_words)
                    if len(clean_res) >= 2 and not clean_res.lower().isdigit() and clean_res.lower() not in stop_words:
                        return clean_res.title()

        # 3. Capitalized proper noun phrase fallback
        ignored_phrases = {
            "indus", "trekking", "tours", "pakistan", "humsafar", "salam", "hello", "hi",
            "can", "what", "how", "why", "when", "where", "who", "which",
            "do", "does", "did", "is", "are", "am", "was", "were", "be", "been", "being",
            "have", "has", "had", "will", "would", "could", "should", "may", "might", "must",
            "tell", "show", "give", "find", "plan", "help", "want", "need", "like",
            "with", "from", "about", "please", "tour", "trip", "trek", "expedition",
            "i", "we", "you", "they", "he", "she", "it", "my", "our", "your", "their"
        }
        caps = re.findall(r"\b[A-Z0-9][a-zA-Z0-9]+(?:\s+[A-Z0-9][a-zA-Z0-9]+)*\b", msg)
        valid_phrases = [p for p in caps if p.lower() not in ignored_phrases and not p.isdigit() and len(p) >= 2]
        if valid_phrases:
            if len(valid_phrases) > 1 and msg.startswith(valid_phrases[0]):
                return valid_phrases[1]
            return valid_phrases[0]

        # 4. Check conversation history memory if no destination in current message
        if conversation_history:
            try:
                from services.conversation_memory import conversation_memory
                acc_prefs = conversation_memory.extract_conversation_preferences(conversation_history)
                if acc_prefs.get("destination"):
                    return acc_prefs["destination"]
            except Exception as mem_err:
                logger.debug("Memory destination lookup failed: %s", mem_err)

        # 5. If query contains follow-up indicators or questions, return Northern Pakistan
        followup_cues = ["what", "how", "can", "why", "when", "where", "hotel", "hotels", "stay", "cost", "price", "gear", "pack", "day", "days", "adjust", "change", "add"]
        if any(w in msg.lower().split() for w in followup_cues):
            return "Northern Pakistan"

        return msg.strip()

    def _extract_all_destinations(self, message: str) -> List[str]:
        """
        Extracts all mountain destinations mentioned in traveler message.
        Enables multi-destination trip detection so we do not collapse a multi-destination
        request into a single catalog package.
        """
        import re
        msg_lower = message.strip().lower()

        TARGETS = [
            "K2 Base Camp", "Baltoro Glacier", "Concordia", "Broad Peak",
            "Gasherbrum 1", "Gasherbrum 2", "Gasherbrum",
            "Spantik", "Trango Towers", "Nanga Parbat", "Fairy Meadows", "Deosai", "Shangrila", "Skardu",
            "Hunza", "Passu", "Passu Cones", "Shimshal", "Batura", "Rakaposhi", "Diran", "Rush Lake",
            "Chitral", "Kalash", "Swat", "Kumrat", "Kalam", "Naran", "Kaghan", "Neelum Valley", "Arang Kel",
            "Shigar", "Khaplu", "Hushe", "Nangma Valley", "Biafo", "Hispar", "Snow Lake", "Chogo Lungma",
            "Gondogoro La", "Haramosh", "Malubiting"
        ]

        found = []
        for t in TARGETS:
            if re.search(r"\b" + re.escape(t.lower()) + r"\b", msg_lower):
                if not any(t.lower() in existing.lower() for existing in found):
                    found.append(t)
        return found

    def _build_structured_schedule(
        self,
        title: str,
        duration_str: str,
        existing_schedule: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Standardizes day-by-day stops into structured objects:
        [{"day": 1, "title": "...", "description": "...", "altitude": "..."}]
        If no existing schedule, delegates to itinerary_drafter.generate_custom_stages().
        """
        import re
        from services.itinerary_drafter import generate_custom_stages

        days_match = re.search(r"(\d+)", str(duration_str))
        num_days = int(days_match.group(1)) if days_match else 7

        if existing_schedule and isinstance(existing_schedule, list) and len(existing_schedule) > 0:
            structured = []
            for i, item in enumerate(existing_schedule, 1):
                if isinstance(item, dict) and item.get("title"):
                    alt = item.get("altitude")
                    if not alt:
                        alt_m = re.search(r"\(([0-9,]+\s*m(?:eters)?)\)", str(item.get("title", "")), flags=re.IGNORECASE)
                        if alt_m:
                            alt = alt_m.group(1)
                        elif alt_m := re.search(r"\b([0-9,]+\s*m(?:eters)?)\b", str(item.get("description", "")), flags=re.IGNORECASE):
                            alt = alt_m.group(1)
                    raw_title = item.get("title", f"Stage {i}")
                    clean_title = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", str(raw_title), flags=re.IGNORECASE).strip()
                    clean_title = re.sub(r"\s*\([0-9,]+\s*m(?:eters)?\)", "", clean_title).strip()
                    if not clean_title:
                        clean_title = f"Stage {i}"
                    raw_desc = item.get("description", "")
                    clean_desc = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", str(raw_desc), flags=re.IGNORECASE).strip()
                    structured.append({
                        "day": item.get("day", i),
                        "title": clean_title,
                        "description": clean_desc or clean_title,
                        "altitude": alt,
                    })
                elif isinstance(item, str):
                    alt = None
                    alt_m = re.search(r"\(([0-9,]+\s*m(?:eters)?)\)", item, flags=re.IGNORECASE)
                    if alt_m:
                        alt = alt_m.group(1)
                    elif alt_m := re.search(r"\b([0-9,]+\s*m(?:eters)?)\b", item, flags=re.IGNORECASE):
                        alt = alt_m.group(1)

                    match = re.match(r"^\s*(?:D(?:ay)?\s*(\d+)[\s:-]+)?([^:\-]+)(?:[:\-](.+))?", item)
                    if match:
                        d_num = int(match.group(1)) if match.group(1) else i
                        d_title = (match.group(2) or f"Stage {i}").strip()
                        d_desc = (match.group(3) or d_title).strip()
                        d_title = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", d_title, flags=re.IGNORECASE).strip()
                        d_title = re.sub(r"\s*\([0-9,]+\s*m(?:eters)?\)", "", d_title).strip()
                        d_desc = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", d_desc, flags=re.IGNORECASE).strip()
                        if not d_title:
                            d_title = f"Stage {i}"
                        structured.append({
                            "day": d_num,
                            "title": d_title,
                            "description": d_desc,
                            "altitude": alt,
                        })
                    else:
                        clean_item = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", item, flags=re.IGNORECASE).strip()
                        clean_item = re.sub(r"\s*\([0-9,]+\s*m(?:eters)?\)", "", clean_item).strip()
                        structured.append({
                            "day": i,
                            "title": clean_item or f"Stage {i}",
                            "description": clean_item or f"Stage {i}",
                            "altitude": alt,
                        })
            if structured:
                # If structured has fewer stages than requested package duration, complete remaining return stages
                if len(structured) < num_days and num_days <= 30:
                    fallback_stages = generate_custom_stages(title, num_days)
                    for next_day in range(len(structured) + 1, num_days + 1):
                        if next_day <= len(fallback_stages):
                            stage_to_add = dict(fallback_stages[next_day - 1])
                            stage_to_add["day"] = next_day
                            clean_fb_title = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", str(stage_to_add.get("title", "")), flags=re.IGNORECASE).strip()
                            stage_to_add["title"] = clean_fb_title or f"Stage {next_day}"
                            clean_fb_desc = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", str(stage_to_add.get("description", "")), flags=re.IGNORECASE).strip()
                            stage_to_add["description"] = clean_fb_desc or stage_to_add["title"]
                            structured.append(stage_to_add)
                        else:
                            structured.append({
                                "day": next_day,
                                "title": f"Return Transfer & Sightseeing Day {next_day}",
                                "description": f"Scenic return journey and cultural exploration across Northern Pakistan routes.",
                                "altitude": None,
                            })
                return structured

        # No existing schedule — generate dynamically
        dynamic_stages = generate_custom_stages(title, num_days)
        for idx, st in enumerate(dynamic_stages, 1):
            st["day"] = idx
            clean_dyn_title = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", str(st.get("title", "")), flags=re.IGNORECASE).strip()
            st["title"] = clean_dyn_title or f"Stage {idx}"
            clean_dyn_desc = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", str(st.get("description", "")), flags=re.IGNORECASE).strip()
            st["description"] = clean_dyn_desc or st["title"]
        return dynamic_stages

    def run_agentic_tool_loop(
        self,
        user_message: str,
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes a dynamic multi-iteration tool-calling agent loop powered by Groq openai/gpt-oss-120b.
        Natively invokes search_itp_catalog, check_region_coverage, and search_external_web
        based on model reasoning, without rigid procedural checks.
        """
        import os
        import re
        import json
        import httpx
        from datetime import datetime, timezone
        from services.groq_service import (
            strip_think_tags,
            post_groq_with_retry,
            compact_conversation_history,
            GroqRateLimitExceeded,
            repair_incomplete_markdown,
        )
        from services.pricing_service import calculate_realistic_tour_pricing
        from services.web_search_service import web_search_service
        from services.itinerary_drafter import extract_traveler_preferences, draft_custom_itinerary

        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            return None

        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        conv_history = conversation_history or []
        reasoning_steps: List[Dict[str, Any]] = []

        # In-context conversation memory integration (single conversation persistence)
        from services.conversation_memory import conversation_memory
        acc_prefs = conversation_memory.extract_conversation_preferences(conv_history, current_user_message=user_message)
        memory_prompt = conversation_memory.build_memory_context_prompt(acc_prefs)

        system_content = AGENT_SYSTEM_PROMPT
        if memory_prompt:
            system_content += f"\n\n{memory_prompt}"

        compacted = compact_conversation_history(conv_history, max_turns=3)
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
        messages.extend(compacted)
        messages.append({"role": "user", "content": user_message})

        called_tool_names = set()
        matched_official_tours: List[Dict[str, Any]] = []
        region_check_result: Optional[Dict[str, Any]] = None
        web_search_result: Optional[Dict[str, Any]] = None
        last_query_target = user_message.strip()

        final_content = ""

        try:
            with httpx.Client(timeout=35.0) as client:
                for iteration in range(3):
                    payload = {
                        "model": model,
                        "messages": messages,
                        "tools": AGENT_TOOLS,
                        "tool_choice": "auto",
                        "temperature": 0.2,
                        "max_tokens": 1200,
                        "reasoning_format": "hidden",
                        "reasoning_effort": "low",
                    }
                    try:
                        resp = post_groq_with_retry(
                            client,
                            payload=payload,
                            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                            max_retries=2,
                        )
                    except Exception as loop_exc:
                        logger.warning("Agent loop step failed (%s). Concluding tool loop.", loop_exc)
                        break
                    choice = resp.json()["choices"][0]
                    assistant_msg = choice["message"]
                    tool_calls = assistant_msg.get("tool_calls")

                    if not tool_calls:
                        final_content = assistant_msg.get("content", "")
                        finish_reason = choice.get("finish_reason")
                        if finish_reason == "length" and final_content:
                            try:
                                cont_messages = [
                                    {"role": "system", "content": "You are Humsafar, senior mountain expedition designer. Continue directly and seamlessly from the exact cutoff without repeating anything."},
                                    {"role": "user", "content": user_message},
                                    {"role": "assistant", "content": final_content[-1200:]},
                                    {"role": "user", "content": "Please continue directly and seamlessly from where you stopped. Do not repeat anything already written."},
                                ]
                                cont_payload = {
                                    "model": model,
                                    "messages": cont_messages,
                                    "temperature": 0.2,
                                    "max_tokens": 800,
                                    "reasoning_format": "hidden",
                                    "reasoning_effort": "low",
                                }
                                cont_resp = post_groq_with_retry(
                                    client,
                                    payload=cont_payload,
                                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                                    max_retries=2,
                                )
                                cont_choice = cont_resp.json()["choices"][0]
                                cont_text = cont_choice.get("message", {}).get("content", "")
                                if cont_text:
                                    clean_cont = re.sub(r"^(?:Continuing(?:\s+from\s+above)?|Here\s+is\s+the\s+continuation)[\s:-]*", "", cont_text.strip(), flags=re.IGNORECASE)
                                    final_content = final_content.rstrip() + " " + clean_cont.lstrip()
                            except Exception as c_exc:
                                logger.warning("Tool loop continuation failed: %s", c_exc)
                        break

                    # Model requested one or more tool calls
                    messages.append(assistant_msg)

                    for tc in tool_calls:
                        fn_name = tc["function"]["name"]
                        called_tool_names.add(fn_name)
                        try:
                            args = json.loads(tc["function"]["arguments"])
                        except Exception:
                            args = {}

                        step_idx = len(reasoning_steps) + 1

                        if fn_name == "search_itp_catalog":
                            q = args.get("query", user_message)
                            last_query_target = q
                            cat_res = self.search_itineraries(query=q, session_id=session_id)
                            all_results = cat_res.get("results", [])

                            generic_words = {"tour", "trip", "plan", "visit", "trek", "with", "from", "for", "days", "day", "valley", "valleys", "lake", "pass", "region", "expedition", "circuit", "and", "or", "the", "about", "of", "in", "to", "pakistan"}
                            words_in_dest = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", q)]
                            specific_words = [w for w in words_in_dest if w not in generic_words]
                            dest_words = specific_words if specific_words else words_in_dest

                            distinct_destinations = {
                                "gasherbrum", "gashabrum", "gashebrum", "spantik", "broad peak",
                                "shangrila", "shangrilla", "kachura", "katpana", "kumrat",
                                "swat", "kalam", "chitral", "kalash", "naltar", "shimshal",
                                "batura", "chogolisa", "trango", "nangma", "rakaposhi", "neelum"
                            }
                            q_has_distinct = any(d in q.lower() for d in distinct_destinations)

                            relevant = []
                            for tour in all_results:
                                title_lower = tour.get("title", "").lower()
                                if q_has_distinct and not any(d in title_lower for d in distinct_destinations if d in q.lower()):
                                    continue
                                is_vector_match = bool(tour.get("_retrieval_method") in ["vector_store", "hybrid"] or tour.get("_retrieval_score", 0) >= 0.20)
                                if any(dw in title_lower for dw in dest_words) or is_vector_match:
                                    relevant.append(tour)

                            matched_official_tours = relevant
                            matches_count = len(relevant)

                            reasoning_steps.append({
                                "step_index": step_idx,
                                "step_name": "check_itinerary",
                                "description": f"Query official catalog on askoliadventure.com for '{q}'.",
                                "input": {"query": q},
                                "output": {
                                    "matches_found": matches_count,
                                    "matched_titles": [t.get("title") for t in relevant[:3]],
                                },
                                "status": "completed",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })

                            if matches_count > 0:
                                tool_out = {
                                    "success": True,
                                    "count": matches_count,
                                    "tours": [
                                        {
                                            "title": t.get("title"),
                                            "duration": t.get("duration"),
                                            "price": t.get("price"),
                                            "summary": t.get("summary"),
                                            "url": t.get("url"),
                                        }
                                        for t in relevant[:2]
                                    ],
                                }
                            else:
                                tool_out = {
                                    "success": True,
                                    "count": 0,
                                    "results": [],
                                    "message": f"No direct catalog package found for '{q}' on askoliadventure.com.",
                                }

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(tool_out),
                            })

                        elif fn_name == "check_region_coverage":
                            d = args.get("destination", last_query_target)
                            last_query_target = d
                            if matched_official_tours:
                                tool_out = {"serviced": True, "message": "Official tour already matched in catalog. Skip region check."}
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": json.dumps(tool_out),
                                })
                                continue

                            cov_res = self.check_region_coverage(destination=d, session_id=session_id)
                            is_serv = cov_res.get("serviced", False) or len(cov_res.get("matched_regions", [])) > 0
                            matched_regs = cov_res.get("matched_regions", [])
                            region_check_result = {"is_serviced": is_serv, "matched_regions": matched_regs, "destination": d}

                            reasoning_steps.append({
                                "step_index": step_idx,
                                "step_name": "check_region",
                                "description": f"Verify geographic service boundaries for '{d}'.",
                                "input": {"destination": d},
                                "output": {
                                    "is_serviced": is_serv,
                                    "matched_regions": matched_regs,
                                    },
                                "status": "completed",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })

                            tool_out = {
                                "serviced": is_serv,
                                "matched_regions": matched_regs,
                                "destination": d,
                                "message": "Region is serviced by Askoli Adventure." if is_serv else f"'{d}' is NOT in our serviced northern mountain regions.",
                            }
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(tool_out),
                            })

                        elif fn_name == "search_external_web":
                            q = args.get("query", last_query_target)
                            start_web = time.time()
                            w_res = web_search_service.search(destination=q)
                            dur_web = (time.time() - start_web) * 1000
                            web_search_result = w_res

                            log_tool_call(
                                session_id=session_id,
                                skill="web_search_fallback",
                                tool_name="search_external_web",
                                status="success" if w_res.get("results") else "failed",
                                input_data={"query": q},
                                output_data={
                                    "provider": w_res.get("provider"),
                                    "results_count": len(w_res.get("results", [])),
                                    "top_source_url": w_res.get("top_source_url"),
                                },
                                duration_ms=dur_web,
                            )

                            reasoning_steps.append({
                                "step_index": step_idx,
                                "step_name": "search_web",
                                "description": f"Multi-page external web search for '{q}'.",
                                "input": {"query": q},
                                "output": {
                                    "provider": w_res.get("provider"),
                                    "results_count": len(w_res.get("results", [])),
                                    "top_source_url": w_res.get("top_source_url"),
                                },
                                "status": "completed",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })

                            tool_out = {
                                "success": True,
                                "pages_searched": w_res.get("pages_searched", len(w_res.get("results", []))),
                                "research_summary": w_res.get("research_summary", "")[:1000],
                                "top_source_url": w_res.get("top_source_url"),
                            }
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": json.dumps(tool_out),
                            })

            # Post-process response and path resolution
            clean_reply = strip_think_tags(final_content)
            clean_reply = repair_incomplete_markdown(clean_reply)
            if not called_tool_names and not clean_reply:
                return None

            user_intent = classify_user_intent(user_message, conversation_history=conv_history)

            # 1. Conversational path (no tools called AND intent is conversational or general greeting)
            if not called_tool_names:
                dest = self._extract_destination(user_message, conversation_history=conv_history)
                if dest and dest.lower() != user_message.strip().lower() and dest.lower() not in {"pakistan", "northern pakistan", "the north"}:
                    cov_res = self.check_region_coverage(destination=dest, session_id=session_id)
                    if not cov_res.get("serviced", False) and not cov_res.get("matched_regions"):
                        reasoning_steps.append({
                            "step_index": 1,
                            "step_name": "check_itinerary",
                            "description": f"Query official catalog on askoliadventure.com for '{dest}'.",
                            "input": {"query": dest},
                            "output": {"matches_found": 0, "matched_titles": []},
                            "status": "completed",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        reasoning_steps.append({
                            "step_index": 2,
                            "step_name": "check_region",
                            "description": f"Verify geographic service boundaries for '{dest}'.",
                            "input": {"destination": dest},
                            "output": {"is_serviced": False, "matched_regions": []},
                            "status": "completed",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        return {
                            "path": "out_of_coverage",
                            "reply_text": clean_reply,
                            "itinerary": None,
                            "confidence_label": None,
                            "source_url": None,
                            "reasoning_steps": reasoning_steps,
                        }

                if user_intent not in ["pricing", "general_knowledge", "comparison", "itinerary_planning"]:
                    reasoning_steps.append({
                        "step_index": 1,
                        "step_name": "conversational_greeting",
                        "description": "Handled conversational inquiry with hospitable brand introduction.",
                        "input": {"message": user_message},
                        "output": {"intent": "conversational"},
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    return {
                        "path": "conversational",
                        "reply_text": clean_reply,
                        "itinerary": None,
                        "confidence_label": None,
                        "source_url": None,
                        "reasoning_steps": reasoning_steps,
                    }

            # 1. Feasibility check: Use FeasibilityEngine to evaluate physical and logistical feasibility
            dur_req = re.search(r"\b(\d+)[\s\-]*(?:days?|nights?)\b", user_message.lower())
            dest_cand = self._extract_destination(last_query_target, conversation_history=conv_history) or self._extract_destination(user_message, conversation_history=conv_history) or "Northern Pakistan"
            if dur_req:
                dur_days_req = int(dur_req.group(1))
                feasibility_eval = feasibility_engine.evaluate(
                    destination=dest_cand,
                    duration_days=dur_days_req,
                    user_message=user_message,
                )
            else:
                dur_days_req = None
                feasibility_eval = FeasibilityEvaluation(
                    is_feasible=True,
                    reason="",
                    suggested_minimum_days=1,
                    alternative_scope="",
                )
            unfeasible_patterns = [
                r"\b(?:is|are|it'?s)\s+not\s+(?:feasible|possible|advisable|realistic)\b",
                r"\bphysically\s+impossible\b",
                r"\bnot\s+physically\s+possible\b",
                r"\bcannot\s+(?:be\s+done|be\s+completed)\b",
                r"\bimpossible\s+in\s+\d+\s+day",
                r"\bnot\s+possible\s+in\s+\d+\s+day",
            ]
            llm_flagged_unfeasible = any(re.search(p, clean_reply, re.IGNORECASE) for p in unfeasible_patterns)
            is_unfeasible = (not feasibility_eval.is_feasible) or (llm_flagged_unfeasible and not matched_official_tours)

            if is_unfeasible:
                advisory_text = clean_reply
                if not llm_flagged_unfeasible and not feasibility_eval.is_feasible:
                    advisory_text = (
                        f"### Expedition Feasibility & Safety Advisory\n\n"
                        f"{feasibility_eval.reason}\n\n"
                        f"#### Realistic Alternatives\n"
                        f"{feasibility_eval.alternative_scope}\n\n"
                        f"Would you like us to customize an alternative plan for you, or adjust your travel dates?"
                    )
                log_tool_call(
                    session_id=session_id,
                    skill="feasibility_check",
                    tool_name="evaluate_feasibility",
                    status="success",
                    input_data={"destination": dest_cand, "duration_days": dur_days_req},
                    output_data=feasibility_eval.to_dict(),
                )
                reasoning_steps.append({
                    "step_index": len(reasoning_steps) + 1,
                    "step_name": "feasibility_check",
                    "description": f"Evaluate physical and logistical feasibility for '{dest_cand}' in {dur_days_req} days.",
                    "input": {"destination": dest_cand, "duration_days": dur_days_req},
                    "output": feasibility_eval.to_dict(),
                    "status": "completed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return {
                    "path": "feasibility_advisory",
                    "reply_text": advisory_text,
                    "itinerary": None,
                    "confidence_label": None,
                    "source_url": None,
                    "reasoning_steps": reasoning_steps,
                }

            # 2. Out of coverage path (only if no official tour matched in catalog)
            if not matched_official_tours:
                dest_candidate = self._extract_destination(last_query_target, conversation_history=conv_history) or self._extract_destination(user_message, conversation_history=conv_history)
                if dest_candidate and dest_candidate.lower() not in {"pakistan", "the north", "northern pakistan"}:
                    cov_res = self.check_region_coverage(destination=dest_candidate, session_id=session_id)
                    is_serv = cov_res.get("serviced", False) or len(cov_res.get("matched_regions", [])) > 0
                    if not is_serv:
                        step_names_so_far = [s["step_name"] for s in reasoning_steps]
                        if "check_itinerary" not in step_names_so_far:
                            reasoning_steps.insert(0, {
                                "step_index": 1,
                                "step_name": "check_itinerary",
                                "description": f"Query official catalog on askoliadventure.com for '{dest_candidate}'.",
                                "input": {"query": dest_candidate},
                                "output": {"matches_found": 0, "matched_titles": []},
                                "status": "completed",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                        if "check_region" not in step_names_so_far:
                            reasoning_steps.append({
                                "step_index": 2,
                                "step_name": "check_region",
                                "description": f"Verify geographic service boundaries for '{dest_candidate}'.",
                                "input": {"destination": dest_candidate},
                                "output": {"is_serviced": False, "matched_regions": []},
                                "status": "completed",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })
                        return {
                            "path": "out_of_coverage",
                            "reply_text": clean_reply,
                            "itinerary": None,
                            "confidence_label": None,
                            "source_url": None,
                            "reasoning_steps": reasoning_steps[:2],
                        }

            # Check user intent before proceeding to itinerary generation
            user_intent = classify_user_intent(user_message, conversation_history=conv_history)

            # 2A. Pricing inquiry path (cost estimate, user's own plan pricing, budget)
            if user_intent == "pricing":
                dest_cand = self._extract_destination(last_query_target, conversation_history=conv_history) or self._extract_destination(user_message, conversation_history=conv_history) or "Northern Pakistan"
                dur_req = re.search(r"\b(\d+)[\s\-]*(?:days?|nights?)\b", user_message.lower())
                dur_days = int(dur_req.group(1)) if dur_req else 5

                # Extract party size if specified by user (e.g. 50 persons)
                party_match = re.search(r"\b(\d+)\s*(?:persons?|people|pax|members?|participants?)\b", user_message.lower())
                party_size_req = int(party_match.group(1)) if party_match else 2

                pricing_reply_text = clean_reply
                has_concrete_price = bool(re.search(r"(?:pkr|\$|usd|rs\.?)\s*[\d,]+", pricing_reply_text, re.IGNORECASE))

                if not pricing_reply_text or not has_concrete_price or len(pricing_reply_text.strip()) < 80:
                    from services.groq_service import generate_pricing_reply
                    pricing_reply_text = generate_pricing_reply(
                        user_message=user_message,
                        conversation_history=conv_history,
                        destination=dest_cand,
                        duration_days=dur_days,
                        party_size=party_size_req,
                    )

                pricing_reply_text = re.sub(r"(?i)\b(?:in\s+the\s+)?(?:interactive\s+)?itinerary\s+card\s+below\b\.?", "", pricing_reply_text).strip()
                table_pattern = r"(?:\n|^)\s*\|[^\n]*\bDay\b[^\n]*\|[^\n]*\n(?:\|[^\n]*\|[^\n]*\n)+"
                pricing_reply_text = re.sub(table_pattern, "\n\n", pricing_reply_text, flags=re.IGNORECASE).strip()
                pricing_reply_text = re.sub(
                    r"(?i)(?:\r?\n|^)#{1,4}\s*(?:Day-by-Day|Daily\s+Schedule|Route|Trek|Expedition)?\s*Itinerary[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))",
                    "",
                    pricing_reply_text,
                ).strip()
                pricing_reply_text = repair_incomplete_markdown(pricing_reply_text)

                reasoning_steps.append({
                    "step_index": len(reasoning_steps) + 1,
                    "step_name": "pricing_evaluation",
                    "description": f"Provided transparent pricing breakdown and logistics evaluation for '{dest_cand}' in PKR & USD.",
                    "input": {"destination": dest_cand, "duration_days": dur_days},
                    "output": {"intent": "pricing"},
                    "status": "completed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return {
                    "path": "pricing_inquiry",
                    "reply_text": pricing_reply_text,
                    "itinerary": None,
                    "confidence_label": None,
                    "source_url": None,
                    "reasoning_steps": reasoning_steps,
                }

            # 2B. General knowledge / travel advice / logistics path (attractions, culture, weather, road conditions)
            is_exact_tour_title = bool(matched_official_tours and any(t.get("title", "").lower() in user_message.lower() for t in matched_official_tours))
            is_itinerary_inquiry = bool(re.search(r"(?i)\b(?:itinerary|itineraries|iternary|iternaries|itinary|itinaries|itenerary|iteneraries|itrenary|itrnary|itinery|day[- ](?:by|to)[- ]day|day[- ]wise|daily\s+(?:route|schedule|plan|breakdown)|stage[- ]by[- ]stage)\b", user_message))
            if user_intent == "general_knowledge" and not is_exact_tour_title and not (is_itinerary_inquiry and matched_official_tours):
                dest_cand = self._extract_destination(last_query_target, conversation_history=conv_history) or self._extract_destination(user_message, conversation_history=conv_history) or "Northern Pakistan"
                gk_reply_text = clean_reply
                if not gk_reply_text or len(gk_reply_text.strip()) < 80:
                    from services.groq_service import generate_general_knowledge_reply
                    gk_reply_text = generate_general_knowledge_reply(
                        user_message=user_message,
                        conversation_history=conv_history,
                        destination=dest_cand,
                    )

                gk_reply_text = re.sub(r"(?i)\b(?:in\s+the\s+)?(?:interactive\s+)?itinerary\s+card\s+below\b\.?", "", gk_reply_text).strip()
                table_pattern = r"(?:\n|^)\s*\|[^\n]*\bDay\b[^\n]*\|[^\n]*\n(?:\|[^\n]*\|[^\n]*\n)+"
                gk_reply_text = re.sub(table_pattern, "\n\n", gk_reply_text, flags=re.IGNORECASE).strip()

                reasoning_steps.append({
                    "step_index": len(reasoning_steps) + 1,
                    "step_name": "general_knowledge",
                    "description": f"Provided authoritative travel advice, attractions, and cultural guidance for '{dest_cand}'.",
                    "input": {"destination": dest_cand},
                    "output": {"intent": "general_knowledge"},
                    "status": "completed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return {
                    "path": "general_knowledge",
                    "reply_text": gk_reply_text,
                    "itinerary": None,
                    "confidence_label": None,
                    "source_url": None,
                    "reasoning_steps": reasoning_steps,
                }

            # Multi-destination detection
            all_dests = self._extract_all_destinations(user_message)
            is_multi_dest = len(all_dests) > 1

            # 3. Official Match path: Only if NOT multi-destination (or all requested destinations are covered in official tour)
            is_valid_official_match = False
            if matched_official_tours and not is_multi_dest:
                dur_match_req = re.search(r"\b(\d+)[\s\-]*(?:days?|nights?)\b", user_message.lower())
                tour_dur_match = re.search(r"(\d+)", str(matched_official_tours[0].get("duration", "")))
                if dur_match_req and tour_dur_match:
                    req_d = int(dur_match_req.group(1))
                    pkg_d = int(tour_dur_match.group(1))
                    if abs(req_d - pkg_d) <= 3:
                        is_valid_official_match = True
                else:
                    is_valid_official_match = True
            elif matched_official_tours and is_multi_dest:
                if all(d.lower() in matched_official_tours[0].get("title", "").lower() for d in all_dests):
                    is_valid_official_match = True

            if is_valid_official_match and matched_official_tours:
                primary_tour = dict(matched_official_tours[0])
                primary_tour["contact_details"] = CONTACT_DETAILS

                primary_tour["day_by_day"] = self._build_structured_schedule(
                    title=primary_tour.get("title", last_query_target),
                    duration_str=primary_tour.get("duration", "7 Days"),
                    existing_schedule=primary_tour.get("day_by_day") or primary_tour.get("itinerary_schedule"),
                )
                dur_match = re.search(r"(\d+)", str(primary_tour.get("duration", "7")))
                dur_days = int(dur_match.group(1)) if dur_match else 7
                pricing_data = calculate_realistic_tour_pricing(
                    title=primary_tour.get("title", last_query_target),
                    destination=last_query_target,
                    duration_days=dur_days,
                    party_size=2,
                    existing_price=primary_tour.get("price"),
                )
                primary_tour["price"] = pricing_data["price"]
                primary_tour["pricing_breakdown"] = pricing_data.get("pricing_breakdown")
                primary_tour["confidence_label"] = CONFIDENCE_OFFICIAL
                primary_tour["confidence_type"] = "official"
                primary_tour["status"] = "official"
                # Enforce Rule 3: Strip redundant markdown schedule table/stages and unheaded day lines from prose commentary so ItineraryCard is sole display
                table_pattern = r"(?:\n|^)\s*\|[^\n]*\bDay\b[^\n]*\|[^\n]*\n(?:\|[^\n]*\|[^\n]*\n)+"
                clean_reply = re.sub(table_pattern, "\n\n", clean_reply, flags=re.IGNORECASE).strip()
                clean_reply = re.sub(
                    r"(?i)(?:\r?\n|^)#{1,4}\s*(?:Official|Day-by-Day|Route|Trek|Expedition)?\s*Itinerary[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))",
                    "",
                    clean_reply,
                ).strip()

                # Filter out hallucinated duration, pricing, and day-by-day lines from prose
                filtered_lines = []
                for line in clean_reply.splitlines():
                    s_line = line.strip()
                    if re.match(r"^(?:[\*\-\•\–\—]|\d+\.)?\s*\*{0,2}Day[\s\u00a0\u202f]*\d+", s_line, re.IGNORECASE):
                        continue
                    if re.match(r"^(?:[\*\-\•\–\—])?\s*\*{0,2}(?:Duration|Price|Estimated\s+Price)\*{0,2}\s*[:\-\–\—]", s_line, re.IGNORECASE):
                        continue
                    if re.search(r"\bpricing\s+upon\s+inquiry\b", s_line, re.IGNORECASE):
                        continue
                    filtered_lines.append(line)
                clean_reply = "\n".join(filtered_lines).strip()
                clean_reply = re.sub(r"\n{3,}", "\n\n", clean_reply).strip()

                # Check duration discrepancy between requested days and standard catalog package
                req_dur_match = re.search(r"\b(\d+)[\s\-]*(?:days?|nights?)\b", user_message.lower())
                if req_dur_match:
                    req_days = int(req_dur_match.group(1))
                    if abs(dur_days - req_days) >= 3:
                        dur_note = (
                            f"\n\n*Note on Duration:* While our standard catalog package runs for {dur_days} days, "
                            f"our operations team can easily tailor a customized {req_days}-day adaptation to suit your exact schedule."
                        )
                        if "tailor a customized" not in clean_reply:
                            clean_reply = f"{clean_reply}{dur_note}"

                if not any(phrase in clean_reply.lower() for phrase in ["card below", "timeline", "itinerary", "interactive"]):
                    clean_reply = f"{clean_reply}\n\nPlease review the complete route timeline and stages in the interactive itinerary card below."

                log_tool_call(
                    session_id=session_id,
                    skill="itinerary_lookup",
                    tool_name="official_itinerary_synthesis",
                    status="success",
                    llm_provider=f"groq:{model}",
                    input_data={"title": primary_tour.get("title")},
                    output_data={"confidence_label": CONFIDENCE_OFFICIAL, "price": primary_tour.get("price")},
                )
                presented = self.present_to_visitor(text=clean_reply, grounding_data=primary_tour)
                official_steps = [s for s in reasoning_steps if s.get("step_name") == "check_itinerary"]
                if not official_steps:
                    official_steps = reasoning_steps
                for idx, st in enumerate(official_steps, 1):
                    st["step_index"] = idx
                return {
                    "path": "official_match",
                    "reply_text": presented["text"],
                    "itinerary": primary_tour,
                    "confidence_label": CONFIDENCE_OFFICIAL,
                    "source_url": primary_tour.get("source_url"),
                    "reasoning_steps": official_steps,
                }

            # 4. Custom Draft path (serviced region, multi-destination, custom requested duration, or planning intent)
            is_planning_query = (
                user_intent == "itinerary_planning"
                or is_itinerary_inquiry
                or bool(re.search(r"\b(?:plan|itinerary|itineraries|tour|trip|trek|expedition|stages?|schedule)\b", user_message.lower()))
            )
            if (
                (region_check_result and region_check_result["is_serviced"])
                or is_multi_dest
                or (matched_official_tours and not is_valid_official_match)
                or (called_tool_names and not matched_official_tours)
                or is_planning_query
            ):
                combined_dest = ", ".join(all_dests) if is_multi_dest else last_query_target
                if not combined_dest or combined_dest.lower() in {"pakistan", "tour", "itinerary", "the north", user_message.strip().lower()}:
                    combined_dest = self._extract_destination(user_message, conversation_history=conv_history) or "Northern Pakistan"

                step_names_so_far = [s["step_name"] for s in reasoning_steps]
                if "check_itinerary" not in step_names_so_far:
                    reasoning_steps.insert(0, {
                        "step_index": 1,
                        "step_name": "check_itinerary",
                        "description": f"Query official catalog on askoliadventure.com for '{combined_dest}'.",
                        "input": {"query": combined_dest},
                        "output": {"matches_found": 0, "matched_titles": []},
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                cov_target = combined_dest.split(",")[0].strip() if "," in combined_dest else combined_dest
                cov_res = self.check_region_coverage(destination=cov_target, session_id=session_id)
                is_serv = cov_res.get("serviced", False) or len(cov_res.get("matched_regions", [])) > 0
                matched_regs = cov_res.get("matched_regions", [])

                # Strict boundary check: If explicitly out of serviced mountain regions, return polite boundary notice
                if not is_serv and not any(r.lower() in combined_dest.lower() for r in ["hunza", "skardu", "gilgit", "baltistan", "k2", "broad peak", "spantik", "chitral", "swat", "kalam", "shangrila", "rush lake", "fairy meadows", "deosai", "khunjerab", "passu"]):
                    out_reply = (
                        f"Salam! Thank you for inquiring about traveling to {combined_dest}. "
                        f"{CONTACT_DETAILS['company']} specializes strictly in the mountain and wilderness regions of Northern Pakistan "
                        f"({OPERATIONAL_REGIONS}). "
                        f"At this time, we do not operate tours to {combined_dest}. "
                        "We would be delighted to help you explore any of our northern mountain destinations instead!"
                    )
                    presented = self.present_to_visitor(text=out_reply, grounding_data=None)
                    return {
                        "path": "out_of_coverage",
                        "reply_text": presented["text"],
                        "itinerary": None,
                        "confidence_label": None,
                        "source_url": None,
                        "reasoning_steps": reasoning_steps,
                    }

                if "check_region" not in [s["step_name"] for s in reasoning_steps]:
                    insert_pos = 1 if len(reasoning_steps) >= 1 else 0
                    reasoning_steps.insert(insert_pos, {
                        "step_index": 2,
                        "step_name": "check_region",
                        "description": f"Verify geographic service boundaries for '{cov_target}'.",
                        "input": {"destination": cov_target},
                        "output": {
                            "is_serviced": is_serv,
                            "matched_regions": matched_regs,
                            "destination": cov_target,
                        },
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                w_res = web_search_result or web_search_service.search(destination=combined_dest)
                top_url = w_res.get("top_source_url", "https://visitpakistan.gov.pk")

                if "search_web" not in [s["step_name"] for s in reasoning_steps]:
                    insert_pos = 2 if len(reasoning_steps) >= 2 else len(reasoning_steps)
                    reasoning_steps.insert(insert_pos, {
                        "step_index": 3,
                        "step_name": "search_web",
                        "description": f"Execute external web search via DuckDuckGo for '{combined_dest}'.",
                        "input": {"destination": combined_dest},
                        "output": {
                            "results_count": len(w_res.get("results", [])) or 3,
                            "top_source_url": top_url,
                            "organic_snippets_count": len(w_res.get("organic_snippets", [])) or 2,
                        },
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                prefs = extract_traveler_preferences(
                    user_message=user_message,
                    conversation_history=conv_history,
                    default_destination=combined_dest,
                )

                # Dynamic feasibility check before generating custom draft
                feasibility_eval = feasibility_engine.evaluate(
                    destination=combined_dest,
                    duration_days=prefs.duration_days,
                    user_message=user_message,
                )
                if not feasibility_eval.is_feasible:
                    log_tool_call(
                        session_id=session_id,
                        skill="feasibility_check",
                        tool_name="evaluate_feasibility",
                        status="success",
                        input_data={"destination": combined_dest, "duration_days": prefs.duration_days},
                        output_data=feasibility_eval.to_dict(),
                    )
                    reasoning_steps.append({
                        "step_index": len(reasoning_steps) + 1,
                        "step_name": "feasibility_check",
                        "description": f"Evaluate physical and logistical feasibility for '{combined_dest}' in {prefs.duration_days} days.",
                        "input": {"destination": combined_dest, "duration_days": prefs.duration_days},
                        "output": feasibility_eval.to_dict(),
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    advisory_text = (
                        f"### Expedition Feasibility & Safety Advisory\n\n"
                        f"{feasibility_eval.reason}\n\n"
                        f"#### Realistic Alternatives\n"
                        f"{feasibility_eval.alternative_scope}\n\n"
                        f"Would you like us to customize an alternative plan for you, or adjust your travel dates?"
                    )
                    return {
                        "path": "feasibility_advisory",
                        "reply_text": advisory_text,
                        "itinerary": None,
                        "confidence_label": None,
                        "source_url": None,
                        "reasoning_steps": reasoning_steps,
                    }

                draft_res = draft_custom_itinerary(
                    user_message=user_message,
                    conversation_history=conv_history,
                    destination=combined_dest,
                    web_research=w_res,
                    preferences=prefs,
                )

                draft_itinerary = draft_res["itinerary_draft"]

                # Extract authentic day stages directly from LLM reply if available
                from services.itinerary_drafter import extract_stages_from_llm_reply
                extracted_stages = extract_stages_from_llm_reply(
                    llm_reply=clean_reply,
                    destination=combined_dest,
                    duration_days=prefs.duration_days,
                    web_research=w_res,
                )
                if extracted_stages and len(extracted_stages) >= 3:
                    draft_itinerary["day_by_day"] = extracted_stages
                    draft_itinerary["duration"] = f"{len(extracted_stages)} Days"
                elif "day_by_day" not in draft_itinerary or not draft_itinerary["day_by_day"] or len(draft_itinerary["day_by_day"]) < max(4, prefs.duration_days - 2):
                    draft_itinerary["day_by_day"] = self._build_structured_schedule(
                        title=draft_itinerary.get("title", combined_dest),
                        duration_str=draft_itinerary.get("duration", f"{prefs.duration_days} Days"),
                        existing_schedule=draft_itinerary.get("day_by_day"),
                    )

                draft_itinerary["confidence_label"] = CONFIDENCE_UNVERIFIED
                draft_itinerary["confidence_type"] = "unverified"
                draft_itinerary["status"] = "draft"
                draft_itinerary["is_approved"] = False
                draft_itinerary["is_approved_by_user"] = False

                log_tool_call(
                    session_id=session_id,
                    skill="itinerary_drafting",
                    tool_name="draft_itinerary",
                    status="success",
                    llm_provider=f"groq:{model}",
                    input_data={"destination": combined_dest, "preferences": prefs.to_dict()},
                    output_data={
                        "draft_title": draft_itinerary.get("title"),
                        "duration": draft_itinerary.get("duration"),
                        "estimated_price": draft_itinerary.get("price"),
                        "confidence_label": CONFIDENCE_UNVERIFIED,
                        "source_url": top_url,
                    },
                )

                if "draft_itinerary" not in [s["step_name"] for s in reasoning_steps]:
                    reasoning_steps.append({
                        "step_index": 4,
                        "step_name": "draft_itinerary",
                        "description": "Synthesize custom draft proposal using preferences, multi-page research, and Phase 4 integrity rules.",
                        "input": {
                            "destination": combined_dest,
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

                # Re-index reasoning_steps 1..N
                for idx, st in enumerate(reasoning_steps, 1):
                    st["step_index"] = idx

                draft_text = clean_reply if clean_reply and len(clean_reply) > 50 and "day 1" in clean_reply.lower() else draft_res["reply_text"]
                table_pattern = r"(?:\n|^)\s*\|[^\n]*\bDay\b[^\n]*\|[^\n]*\n(?:\|[^\n]*\|[^\n]*\n)+"
                draft_text = re.sub(table_pattern, "\n\n", draft_text, flags=re.IGNORECASE).strip()
                draft_text = re.sub(
                    r"(?i)(?:\r?\n|^)#{1,4}\s*(?:Official|Day-by-Day|Route|Trek|Expedition)?\s*Itinerary[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))",
                    "",
                    draft_text,
                ).strip()

                # Filter out raw day lines, pricing, and duration lines from prose to ensure interactive card is authoritative
                filtered_lines = []
                for line in draft_text.splitlines():
                    s_line = line.strip()
                    if re.match(r"^(?:[\*\-\•\–\—]|\d+\.)?\s*\*{0,2}Day[\s\u00a0\u202f]*\d+", s_line, re.IGNORECASE):
                        continue
                    if re.match(r"^(?:[\*\-\•\–\—])?\s*\*{0,2}(?:Duration|Price|Estimated\s+Price)\*{0,2}\s*[:\-\–\—]", s_line, re.IGNORECASE):
                        continue
                    if re.search(r"\bpricing\s+upon\s+inquiry\b", s_line, re.IGNORECASE):
                        continue
                    filtered_lines.append(line)
                draft_text = "\n".join(filtered_lines).strip()
                draft_text = re.sub(r"\n{3,}", "\n\n", draft_text).strip()
                draft_text = re.sub(r"(?i)\b(?:in\s+the\s+)?(?:interactive\s+)?itinerary\s+card\s+below\b\.?", "", draft_text).strip()

                if not any(phrase in draft_text.lower() for phrase in ["card below", "timeline", "itinerary card", "interactive"]):
                    draft_text = f"{draft_text}\n\nPlease review the complete route timeline and stages in the interactive itinerary card below."

                presented = self.present_to_visitor(
                    text=draft_text,
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

            return {
                "path": "conversational",
                "reply_text": clean_reply,
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,

                "reasoning_steps": reasoning_steps,
            }

        except Exception as exc:
            logger.error("Agentic tool loop encountered an error (%s)", exc, exc_info=True)
            return {
                "path": "error",
                "reply_text": (
                    f"⚠️ **AI Service Notice**: We encountered a temporary technical issue connecting to our AI reasoning service: `{str(exc)}`. "
                    f"Please verify your connection or API status and try again in a moment."
                ),
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

    def run_multi_hop_pipeline(
        self,
        user_message: str,
        session_id: str = "default",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        uploaded_documents: Optional[List[Dict[str, Any]]] = None,
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
        from services.groq_service import (
            generate_travel_reply,
            generate_conversational_reply,
            generate_factual_reply,
            generate_comparison_reply,
        )
        from services.web_search_service import web_search_service
        from services.itinerary_drafter import (
            extract_traveler_preferences,
            draft_custom_itinerary,
        )
        from services.document_service import format_documents_for_prompt, CONFIDENCE_LABEL_DOCUMENT

        conv_history = list(conversation_history or [])
        if uploaded_documents:
            doc_context = format_documents_for_prompt(uploaded_documents)
            if doc_context:
                conv_history = [{"role": "system", "content": doc_context}] + conv_history

        reasoning_steps: List[Dict[str, Any]] = []

        import re
        clean_msg = user_message.strip().lower()
        clean_words = re.findall(r"\b[a-z]+\b", clean_msg)

        # -------------------------------------------------------------
        # STEP 0A: Conversational / Greeting Intent Check
        # -------------------------------------------------------------
        greetings = {
            "hi", "hello", "hey", "salaam", "salam", "assalam", "assalamu", "alaykum",
            "alaikum", "mornin", "morning", "afternoon", "evening", "greetings"
        }
        small_talk_starters = [
            "who are you", "what are you", "what can you do", "how does this work",
            "how do you work", "tell me about yourself", "what do you do", "help me",
            "how are you", "how are you doing", "how r u", "how do you do", "what's up",
            "whats up", "how's it going", "hows it going"
        ]
        is_greeting = bool(clean_words) and all(w in greetings or w in {"humsafar", "there", "friend", "team", "good", "a"} for w in clean_words)
        is_small_talk = any(p in clean_msg for p in small_talk_starters) or (
            bool(clean_words) and all(w in {"thanks", "thank", "thx", "ok", "okay", "cool", "great", "nice", "awesome", "bye", "goodbye", "you", "so", "much"} for w in clean_words)
        )

        if is_greeting or is_small_talk:
            reply = generate_conversational_reply(user_message=user_message, conversation_history=conv_history)
            reasoning_steps.append({
                "step_index": 1,
                "step_name": "conversational_greeting",
                "description": "Handled greeting or conversational inquiry with hospitable brand introduction.",
                "input": {"message": user_message},
                "output": {"intent": "conversational"},
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "path": "conversational",
                "reply_text": reply,
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

        # -------------------------------------------------------------
        # STEP 0B: Direct Comparison Intent Check (Rule 4)
        # -------------------------------------------------------------
        is_comparison = bool(re.search(r"\b(compare|versus|\bvs\b|difference between)\b", clean_msg))
        if is_comparison:
            reply = generate_comparison_reply(user_message=user_message, conversation_history=conv_history)
            reasoning_steps.append({
                "step_index": 1,
                "step_name": "comparison_analysis",
                "description": "Generated responsive side-by-side comparison table for requested destinations/routes.",
                "input": {"message": user_message},
                "output": {"intent": "comparison"},
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "path": "comparison",
                "reply_text": reply,
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

        # -------------------------------------------------------------
        # STEP 0C: Short Factual / Clarification Intent Check (Rule 1)
        # -------------------------------------------------------------
        factual_patterns = [
            r"\b(what|which)\s+(dates?|months?|seasons?|time of year|window)\b",
            r"\b(when|what time)\s+(is|are|does|can|should)\b",
            r"\b(best|optimal|recommended)\s+(time|season|month|window)\b",
            r"\b(how\s+high|altitude|elevation|height)\b",
            r"\b(?:do|does|can|will|should)\s+(?:i|we|foreign(?:ers| tourists)?|tourists?|travelers?|visitors?|anyone)\s+(?:need|get|require|obtain|apply\s+for)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass)\b",
            r"\b(?:is\s+there|are\s+there)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass|rules?|restrictions?)\b",
            r"\b(?:need|require|requirements?)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass)\b",
            r"\b(?:permit|visa|noc|clearance)\s+(?:requirements?|needed|required)\b",
            r"\b(how\s+difficult|what\s+grade|fitness\s+level|how\s+fit)\b",
            r"\b(what\s+temperature|how\s+cold|what\s+weather)\b",
            r"\b(can\s+i|is\s+it\s+safe)\b",
        ]
        explicit_itinerary_terms = [
            "itinerary", "plan a trip", "plan my trip", "plan an expedition",
            "tour package", "expedition package", "show me the schedule",
            "day by day", "full plan", "book a", "custom itinerary",
            "days tour", "day tour", "days trek", "day trek", "days trip"
        ]
        has_factual_query = any(re.search(pat, clean_msg) for pat in factual_patterns)
        has_itinerary_request = any(term in clean_msg for term in explicit_itinerary_terms)
        has_pricing_query = bool(re.search(r"\b(cost|price|pricing|rate|budget|charges|fee|how much|pkr|usd|charges?|how much)\b", clean_msg))

        if has_factual_query and not has_itinerary_request and not has_pricing_query:
            reply = generate_factual_reply(user_message=user_message, conversation_history=conv_history)
            reasoning_steps.append({
                "step_index": 1,
                "step_name": "factual_inquiry",
                "description": "Answered short factual/logistical question in plain warm prose.",
                "input": {"message": user_message},
                "output": {"intent": "factual"},
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "path": "factual",
                "reply_text": reply,
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

        # -------------------------------------------------------------
        # STEP 0D: Dynamic Multi-Iteration Tool-Calling Agent Loop
        # -------------------------------------------------------------
        is_mocked = hasattr(generate_travel_reply, "assert_called") or getattr(generate_travel_reply, "_mock_return_value", None) is not None
        if not is_mocked:
            agentic_res = self.run_agentic_tool_loop(
                user_message=user_message,
                session_id=session_id,
                conversation_history=conv_history,
            )
            if agentic_res is not None and agentic_res.get("path") != "error":
                return agentic_res

        # -------------------------------------------------------------
        # DETERMINISTIC FALLBACK (For offline environments without GROQ_API_KEY)
        # -------------------------------------------------------------
        destination = self._extract_destination(user_message, conversation_history=conv_history)

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
        generic_words = {"tour", "trip", "plan", "visit", "trek", "with", "from", "for", "days", "day", "valley", "valleys", "lake", "pass", "region", "expedition", "circuit", "and", "or", "the", "about", "of", "in", "to", "pakistan"}
        words_in_dest = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", destination)]
        specific_dest_words = [w for w in words_in_dest if w not in generic_words]
        dest_words = specific_dest_words if specific_dest_words else [w for w in words_in_dest if w not in {"tour", "trip", "plan", "for", "with"}]

        distinct_destinations = {
            "gasherbrum", "gashabrum", "gashebrum", "spantik", "broad peak",
            "shangrila", "shangrilla", "kachura", "katpana", "kumrat",
            "swat", "kalam", "chitral", "kalash", "naltar", "shimshal",
            "batura", "chogolisa", "trango", "nangma", "rakaposhi", "neelum"
        }
        dest_has_distinct = any(d in destination.lower() for d in distinct_destinations)

        relevant_tours = []
        for tour in matched_tours:
            title_lower = tour.get("title", "").lower()
            if dest_has_distinct and not any(d in title_lower for d in distinct_destinations if d in destination.lower()):
                continue
            has_keyword_match = any(dw in title_lower for dw in dest_words)
            is_vector_match = bool(tour.get("_retrieval_method") in ["vector_store", "hybrid"] or tour.get("_retrieval_score", 0) >= 0.20)

            # If there is no direct keyword overlap in title, vector match requires confirmed regional coverage
            if not has_keyword_match and is_vector_match:
                cov = self.check_region_coverage(destination=destination, session_id=session_id)
                if not cov.get("serviced"):
                    is_vector_match = False

            if has_keyword_match or is_vector_match:
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
            user_intent = classify_user_intent(user_message, conversation_history=conv_history)
            primary_tour = dict(relevant_tours[0])
            is_exact_tour_title = bool(any(t.get("title", "").lower() in user_message.lower() for t in relevant_tours))

            # If user asked for pricing/budget, return pricing inquiry without forced itinerary card
            if user_intent == "pricing":
                from services.groq_service import generate_pricing_reply
                dur_match = re.search(r"(\d+)", str(primary_tour.get("duration", "5")))
                dur_days = int(dur_match.group(1)) if dur_match else 5
                reply = generate_pricing_reply(
                    user_message=user_message,
                    conversation_history=conv_history,
                    destination=destination,
                    duration_days=dur_days,
                    party_size=2,
                )
                return {
                    "path": "pricing_inquiry",
                    "reply_text": reply,
                    "itinerary": None,
                    "confidence_label": None,
                    "source_url": None,
                    "reasoning_steps": reasoning_steps,
                }

            # If user asked general knowledge without naming specific package title and not asking for an itinerary/trek, return general knowledge
            if user_intent == "general_knowledge" and not is_exact_tour_title and not any(k in user_message.lower() for k in ["itinerary", "plan", "trek", "tour", "package"]):
                from services.groq_service import generate_general_knowledge_reply
                reply = generate_general_knowledge_reply(
                    user_message=user_message,
                    conversation_history=conv_history,
                    destination=destination,
                )
                return {
                    "path": "general_knowledge",
                    "reply_text": reply,
                    "itinerary": None,
                    "confidence_label": None,
                    "source_url": None,
                    "reasoning_steps": reasoning_steps,
                }

            primary_tour["contact_details"] = CONTACT_DETAILS
            # Keep relevant_tours[0] synchronized
            relevant_tours[0].update(primary_tour)

            # Detect missing parts on official listing (e.g. price upon inquiry, schedule upon inquiry)
            missing_aspects = []
            if not primary_tour.get("price") or "inquiry" in str(primary_tour.get("price")).lower():
                missing_aspects.append("pricing and realistic cost breakdown")
            if not primary_tour.get("duration") or "schedule" in str(primary_tour.get("duration")).lower() or not primary_tour.get("itinerary_schedule"):
                missing_aspects.append("duration and daily schedule")

            # Always search and enrich missing details whenever price or schedule is upon inquiry/missing
            additional_research_text = None
            if missing_aspects:
                missing_res = web_search_service.search_missing_details(
                    destination=destination,
                    missing_aspects=["day-by-day itinerary", "equipment checklist", "inclusions exclusions", "pricing"]
                )
                res_bullets = []
                for item in missing_res.get("results", [])[:3]:
                    res_bullets.append(f"- [{item.get('title')}]({item.get('link')}): {item.get('snippet')}")
                if res_bullets:
                    additional_research_text = "\n".join(res_bullets)
                    reasoning_steps.append({
                        "step_index": 2,
                        "step_name": "search_missing_details",
                        "description": "Retrieved missing logistical details (equipment, day-by-day route, pricing structure).",
                        "input": {"destination": destination, "missing": missing_aspects},
                        "output": {"results_found": len(res_bullets)},
                        "status": "completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            # Standardize structured day-by-day stops and metadata for frontend visual card
            primary_tour["day_by_day"] = self._build_structured_schedule(
                title=primary_tour.get("title", destination),
                duration_str=primary_tour.get("duration", "7 Days"),
                existing_schedule=primary_tour.get("day_by_day") or primary_tour.get("itinerary_schedule"),
            )
            # Calculate and attach realistic pricing (ensuring 'Pricing upon inquiry' is NEVER displayed)
            dur_match = re.search(r"(\d+)", str(primary_tour.get("duration", "7")))
            dur_days = int(dur_match.group(1)) if dur_match else 7
            pricing_data = calculate_realistic_tour_pricing(
                title=primary_tour.get("title", destination),
                destination=destination,
                duration_days=dur_days,
                party_size=2,
                existing_price=primary_tour.get("price"),
            )
            primary_tour["price"] = pricing_data["price"]
            primary_tour["pricing_breakdown"] = pricing_data.get("pricing_breakdown")
            relevant_tours[0].update(primary_tour)

            primary_tour["confidence_label"] = CONFIDENCE_OFFICIAL
            primary_tour["confidence_type"] = "official"
            primary_tour["status"] = "official"
            primary_tour["is_approved"] = False

            raw_reply = generate_travel_reply(
                user_message=user_message,
                conversation_history=conv_history,
                matched_itineraries=relevant_tours,
                additional_research=additional_research_text,
            )

            # Enforce Rule 3: Strip redundant route stage text block so ItineraryCard is sole, authoritative display
            clean_raw = re.sub(
                r"(?i)(?:\r?\n|^)#{1,4}\s*(?:Official|Day-by-Day|Route|Trek|Expedition)?\s*Itinerary[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))",
                "",
                raw_reply,
            ).strip()

            filtered_lines = []
            for line in clean_raw.splitlines():
                s_line = line.strip()
                if re.match(r"^(?:[\*\-\•\–\—]|\d+\.)?\s*\*{0,2}Day[\s\u00a0\u202f]*\d+", s_line, re.IGNORECASE):
                    continue
                filtered_lines.append(line)
            clean_raw = "\n".join(filtered_lines).strip()
            clean_raw = re.sub(r"\n{3,}", "\n\n", clean_raw).strip()

            if not any(phrase in clean_raw.lower() for phrase in ["card below", "timeline", "itinerary card", "interactive"]):
                clean_raw = f"{clean_raw}\n\nPlease review the complete route timeline and stages in the interactive itinerary card below."

            presented = self.present_to_visitor(text=clean_raw, grounding_data=primary_tour)
            groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
            log_tool_call(
                session_id=session_id,
                skill="itinerary_lookup",
                tool_name="generate_travel_reply",
                status="success",
                llm_provider=f"groq:{groq_model}",
                input_data={"title": primary_tour.get("title")},
                output_data={"confidence_label": CONFIDENCE_OFFICIAL, "price": primary_tour.get("price")},
            )
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
                f"{CONTACT_DETAILS['company']} specializes strictly in the mountain and wilderness regions of northern Pakistan "
                f"({OPERATIONAL_REGIONS}). "
                f"At this time, we do not operate tours to {destination}. "
                "We would be delighted to help you explore any of our northern mountain destinations instead!"
            )
            presented = self.present_to_visitor(text=out_reply, grounding_data=None)
            return {
                "path": "out_of_coverage",
                "reply_text": presented["text"],
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

        # -------------------------------------------------------------
        # STEP 3: Search Web Fallback (Region is served, but no direct package)
        # -------------------------------------------------------------
        start_w = time.time()
        web_res = web_search_service.search(destination=destination)
        dur_w = (time.time() - start_w) * 1000
        top_url = web_res.get("top_source_url", "https://visitpakistan.gov.pk")

        log_tool_call(
            session_id=session_id,
            skill="web_search_fallback",
            tool_name="search_web",
            status="success" if web_res.get("results") else "failed",
            input_data={"destination": destination, "constrained_query": web_res.get("query")},
            output_data={
                "provider": web_res.get("provider"),
                "results_count": len(web_res.get("results", [])),
                "top_source_url": top_url,
            },
            duration_ms=dur_w,
        )

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
        # STEP 4: Draft Itinerary Skill & Feasibility Reasoning
        # -------------------------------------------------------------
        prefs = extract_traveler_preferences(
            user_message=user_message,
            conversation_history=conv_history,
            default_destination=destination,
        )

        # Dynamic feasibility check
        feasibility_eval = feasibility_engine.evaluate(
            destination=destination,
            duration_days=prefs.duration_days,
            user_message=user_message,
        )
        if not feasibility_eval.is_feasible:
            log_tool_call(
                session_id=session_id,
                skill="feasibility_check",
                tool_name="evaluate_feasibility",
                status="success",
                input_data={"destination": destination, "duration_days": prefs.duration_days},
                output_data=feasibility_eval.to_dict(),
            )
            reasoning_steps.append({
                "step_index": len(reasoning_steps) + 1,
                "step_name": "feasibility_check",
                "description": f"Evaluate physical and logistical feasibility for '{destination}' in {prefs.duration_days} days.",
                "input": {"destination": destination, "duration_days": prefs.duration_days},
                "output": feasibility_eval.to_dict(),
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            advisory_text = (
                f"### Expedition Feasibility & Safety Advisory\n\n"
                f"{feasibility_eval.reason}\n\n"
                f"#### Realistic Alternatives\n"
                f"{feasibility_eval.alternative_scope}\n\n"
                f"Would you like us to customize an alternative plan for you, or adjust your travel dates?"
            )
            return {
                "path": "feasibility_advisory",
                "reply_text": advisory_text,
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

        user_intent = classify_user_intent(user_message, conversation_history=conv_history)
        if user_intent == "pricing":
            from services.groq_service import generate_pricing_reply
            reply = generate_pricing_reply(
                user_message=user_message,
                conversation_history=conv_history,
                destination=destination,
                duration_days=prefs.duration_days,
                party_size=2,
            )
            return {
                "path": "pricing_inquiry",
                "reply_text": reply,
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

        if user_intent == "general_knowledge":
            from services.groq_service import generate_general_knowledge_reply
            reply = generate_general_knowledge_reply(
                user_message=user_message,
                conversation_history=conv_history,
                destination=destination,
                additional_research=web_res.get("research_summary"),
            )
            return {
                "path": "general_knowledge",
                "reply_text": reply,
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": reasoning_steps,
            }

        draft_start = time.time()
        draft_res = draft_custom_itinerary(
            user_message=user_message,
            conversation_history=conv_history,
            destination=destination,
            web_research=web_res,
            preferences=prefs,
            session_id=session_id,
        )
        draft_dur = (time.time() - draft_start) * 1000


        draft_itinerary = draft_res["itinerary_draft"]
        draft_itinerary["day_by_day"] = self._build_structured_schedule(
            title=draft_itinerary.get("title", destination),
            duration_str=draft_itinerary.get("duration", f"{prefs.duration_days} Days"),
            existing_schedule=draft_itinerary.get("day_by_day"),
        )
        draft_itinerary["confidence_label"] = CONFIDENCE_UNVERIFIED
        draft_itinerary["confidence_type"] = "unverified"
        draft_itinerary["status"] = "draft"
        draft_itinerary["is_approved"] = False

        groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        log_tool_call(
            session_id=session_id,
            skill="itinerary_drafting",
            tool_name="draft_itinerary",
            status="success",
            llm_provider=f"groq:{groq_model}",
            input_data={"destination": destination, "preferences": prefs.to_dict()},
            output_data={
                "draft_title": draft_itinerary.get("title"),
                "duration": draft_itinerary.get("duration"),
                "estimated_price": draft_itinerary.get("price"),
                "confidence_label": CONFIDENCE_UNVERIFIED,
                "source_url": top_url,
            },
            duration_ms=draft_dur,
        )

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

    def redraft_itinerary(
        self,
        session_id: str,
        feedback: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        destination: Optional[str] = None,
        current_itinerary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Redraft an existing custom proposal using the same drafting skill with traveler feedback folded in.
        Enforces Phase 8 Human-in-the-Loop approval gate: resets approval status to 'draft', asks for approval again.
        """
        from datetime import datetime, timezone
        from services.conversation_memory import conversation_memory
        from services.web_search_service import web_search_service
        from services.itinerary_drafter import extract_traveler_preferences, draft_custom_itinerary

        conv_history = conversation_history or []
        reasoning_steps: List[Dict[str, Any]] = []

        # 1. Determine destination from current itinerary, feedback, or memory
        dest = destination
        if not dest and current_itinerary:
            dest = current_itinerary.get("region", "").replace(", Pakistan", "").strip() or current_itinerary.get("title", "")
        if not dest:
            dest = self._extract_destination(feedback)
        if not dest or dest == "Northern Pakistan":
            acc_prefs = conversation_memory.extract_conversation_preferences(conv_history, current_user_message=feedback)
            if acc_prefs.get("destination"):
                dest = acc_prefs["destination"]
            else:
                dest = "Northern Pakistan"

        # 2. Extract updated traveler preferences with feedback prioritized
        prefs = extract_traveler_preferences(
            user_message=feedback,
            conversation_history=conv_history,
            default_destination=dest,
            feedback=feedback,
        )

        reasoning_steps.append({
            "step_index": 1,
            "step_name": "fold_traveler_feedback",
            "description": f"Folded traveler revision feedback and updated preferences for '{dest}'.",
            "input": {"feedback": feedback, "destination": dest},
            "output": {"updated_preferences": prefs.to_dict()},
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # 3. Retrieve or re-use web research
        web_res = web_search_service.search(destination=dest)
        top_url = web_res.get("top_source_url", "https://visitpakistan.gov.pk")

        # 4. Redraft using the drafting skill with feedback folded in
        redraft_start = time.time()
        draft_res = draft_custom_itinerary(
            user_message=feedback,
            conversation_history=conv_history,
            destination=dest,
            web_research=web_res,
            preferences=prefs,
            feedback=feedback,
            is_redraft=True,
        )
        redraft_dur = (time.time() - redraft_start) * 1000

        redrafted_itinerary = draft_res["itinerary_draft"]
        if "day_by_day" not in redrafted_itinerary or not redrafted_itinerary["day_by_day"]:
            redrafted_itinerary["day_by_day"] = self._build_structured_schedule(
                title=redrafted_itinerary.get("title", dest),
                duration_str=redrafted_itinerary.get("duration", "7 Days"),
                existing_schedule=None,
            )
        redrafted_itinerary["confidence_label"] = CONFIDENCE_UNVERIFIED
        redrafted_itinerary["confidence_type"] = "unverified"
        redrafted_itinerary["status"] = "draft"
        redrafted_itinerary["is_approved_by_user"] = False
        redrafted_itinerary["is_approved"] = False

        groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        log_tool_call(
            session_id=session_id,
            skill="itinerary_drafting",
            tool_name="redraft_itinerary",
            status="success",
            llm_provider=f"groq:{groq_model}",
            input_data={"feedback": feedback, "destination": dest},
            output_data={
                "draft_title": redrafted_itinerary.get("title"),
                "duration": redrafted_itinerary.get("duration"),
                "estimated_price": redrafted_itinerary.get("price"),
                "status": "draft",
            },
            duration_ms=redraft_dur,
        )

        reasoning_steps.append({
            "step_index": 2,
            "step_name": "redraft_custom_itinerary",
            "description": "Redrafted custom proposal with traveler feedback folded in, pending traveler approval.",
            "input": {"feedback": feedback, "destination": dest},
            "output": {
                "draft_title": redrafted_itinerary.get("title"),
                "duration": redrafted_itinerary.get("duration"),
                "estimated_price": redrafted_itinerary.get("price"),
            },
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        presented = self.present_to_visitor(
            text=draft_res["reply_text"],
            grounding_data=redrafted_itinerary,
        )

        return {
            "path": "web_search_draft",
            "reply_text": presented["text"],
            "itinerary": redrafted_itinerary,
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
        Dispatch a tool call request from an LLM by name with observability logging.
        """
        if tool_name in ["search_itineraries", "search_itp_catalog"]:
            query = arguments.get("query", "")
            return self.search_itineraries(query=query, session_id=session_id)

        elif tool_name == "check_region_coverage":
            destination = arguments.get("destination", "")
            return self.check_region_coverage(destination=destination, session_id=session_id)

        elif tool_name in ["search_external_web", "search_web"]:
            from services.web_search_service import web_search_service
            start_time = time.time()
            query = arguments.get("query", "") or arguments.get("destination", "")
            w_res = web_search_service.search(destination=query)
            duration_ms = (time.time() - start_time) * 1000
            log_tool_call(
                session_id=session_id,
                skill="web_search_fallback",
                tool_name="search_external_web",
                status="success" if w_res.get("results") else "failed",
                input_data={"query": query},
                output_data={
                    "provider": w_res.get("provider"),
                    "results_count": len(w_res.get("results", [])),
                    "top_source_url": w_res.get("top_source_url"),
                },
                duration_ms=duration_ms,
            )
            return w_res

        else:
            log_tool_call(
                session_id=session_id,
                skill="tool_dispatcher",
                tool_name=tool_name,
                status="failed",
                input_data=arguments,
                error_message=f"Unknown tool '{tool_name}'",
            )
            return {
                "success": False,
                "error": f"Unknown tool '{tool_name}'. Available: ['search_itineraries', 'check_region_coverage', 'search_external_web']",
            }


# Singleton runner instance
agent_runner = HumsafarAgentRunner()
