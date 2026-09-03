"""
Itinerary Drafting Skill for Humsafar.
Synthesizes structured custom draft itineraries by combining:
1. Live web research snippets and verified URLs.
2. Visitor stated preferences (destination, duration, budget, fitness level, party size).
3. Phase 4 freshness and unverified confidence rules.
"""

import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from services.data_integrity import (
    data_integrity_guard,
    CONFIDENCE_UNVERIFIED,
)

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")


class TravelerPreferences:
    """Represents extracted visitor preferences."""
    def __init__(
        self,
        destination: str = "Northern Pakistan",
        duration: str = "7 Days",
        duration_days: int = 7,
        budget: str = "Standard (PKR 120,000 - 180,000)",
        fitness_level: str = "Moderate",
        party_size: str = "2 Persons",
    ):
        self.destination = destination
        self.duration = duration
        self.duration_days = duration_days
        self.budget = budget
        self.fitness_level = fitness_level
        self.party_size = party_size

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination": self.destination,
            "duration": self.duration,
            "duration_days": self.duration_days,
            "budget": self.budget,
            "fitness_level": self.fitness_level,
            "party_size": self.party_size,
        }


def extract_traveler_preferences(
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    default_destination: str = "Northern Pakistan",
) -> TravelerPreferences:
    """
    Parse the user message and conversation history to extract stated travel parameters.
    """
    combined_text = user_message.lower()
    if conversation_history:
        for turn in conversation_history[-4:]:
            combined_text += " " + turn.get("content", "").lower()

    # 1. Destination
    destination = default_destination
    known_destinations = [
        "chitral", "kalash", "swat", "kalam", "kumrat", "deosai",
        "fairy meadows", "hunza", "skardu", "shimshal", "passu",
        "naran", "kaghan", "astor", "gilgit", "baltistan",
    ]
    for kd in known_destinations:
        if kd in combined_text:
            destination = kd.title()
            if "kalash" in combined_text and kd == "chitral":
                destination = "Chitral & Kalash Valley"
            elif "kalam" in combined_text and kd == "swat":
                destination = "Swat & Kalam Valley"
            break

    # 2. Duration
    duration_match = re.search(r"(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:day|days|d)", combined_text)
    duration_days = 7
    duration_str = "7 Days"
    if duration_match:
        d1 = int(duration_match.group(1))
        duration_days = d1
        if duration_match.group(2):
            duration_str = f"{d1}-{duration_match.group(2)} Days"
        else:
            duration_str = f"{d1} Days"

    # 3. Party Size
    party_size = "2 Persons"
    party_match = re.search(r"(\d+)\s*(?:people|persons|travelers|pax|members|friends)", combined_text)
    if party_match:
        party_size = f"{party_match.group(1)} Persons"
    elif "solo" in combined_text:
        party_size = "1 Person (Solo)"
    elif "family" in combined_text:
        party_size = "Family Group"

    # 4. Budget
    budget = "Custom Estimate"
    budget_pkr_match = re.search(r"(?:pkr|rs\.?)\s*([\d,]+)", combined_text)
    if budget_pkr_match:
        budget = f"PKR {budget_pkr_match.group(1)}"
    elif "luxury" in combined_text or "premium" in combined_text:
        budget = "Premium / Boutique"
    elif "budget" in combined_text or "cheap" in combined_text or "economy" in combined_text:
        budget = "Economy / Budget"

    # 5. Fitness Level
    fitness_level = "Moderate"
    if "strenuous" in combined_text or "difficult" in combined_text or "hard" in combined_text:
        fitness_level = "Strenuous / High Endurance"
    elif "easy" in combined_text or "leisure" in combined_text or "relax" in combined_text:
        fitness_level = "Leisure / Easy Walking"

    return TravelerPreferences(
        destination=destination,
        duration=duration_str,
        duration_days=duration_days,
        budget=budget,
        fitness_level=fitness_level,
        party_size=party_size,
    )


DRAFTING_SYSTEM_PROMPT = """You are Humsafar, the senior expedition planner for Indus Trekking and Tours Pakistan (itp.7scribes.com).
The traveler has requested a custom itinerary, tour, or expedition plan.
You must synthesize a COMPLETE, professional, ready-to-use expedition proposal based on live regional research and the traveler's stated preferences.

CRITICAL EDITORIAL & COMPLETENESS RULES:
1. Complete Plan Structure: Your plan MUST include:
   - Day-by-Day Route Itinerary (daily destinations, elevation, trekking hours, acclimatization)
   - Pricing & Cost Breakdown (provide a realistic estimated budget range in PKR and USD based on party size, permits, porter logistics, and road transport, clearly labeling it as an estimate)
   - Inclusions (licensed mountain guide, porters, camp cook, all meals on trek, 2-person tents, 4x4 jeeps, CKNP/trekking permits, hotel stays)
   - Exclusions (international flights, personal travel/evacuation insurance, technical personal gear, visa fees, staff tips)
   - Required Equipment & Mountain Gear Checklist (sub-zero sleeping bag, broken-in trekking boots, thermal layers, Gore-Tex shell, Category 4 UV glacier glasses, trekking poles)
   - Official Booking & Reservation Contact Details (Indus Trekking and Tours Pakistan, itp.7scribes.com, advise 6-8 weeks advance lead time for official permits)
2. Grounding & Transparency: Clearly state that this is a custom proposal synthesized from regional travel intelligence, with final dates and permits confirmed by our operations team.
3. Tone: Warm, authoritative, knowledgeable, respectful of mountain communities, and encouraging of responsible wilderness travel.
4. NO INTERNAL THOUGHT TAGS: Never output <think> tags, internal reasoning, or thinking process. Output only the final, polished response directly to the traveler.
"""


def draft_custom_itinerary(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    destination: str,
    web_research: Dict[str, Any],
    preferences: TravelerPreferences,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synthesize an unverified draft itinerary and consultant reply combining web research
    and traveler preferences. Enforces Phase 4 data integrity rules.
    """
    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    active_model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)
    top_source = web_research.get("top_source_url", "https://visitpakistan.gov.pk")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Format web research context
    research_bullets = []
    for item in web_research.get("results", [])[:4]:
        research_bullets.append(
            f"- [{item.get('title')}]({item.get('link')}): {item.get('snippet')}"
        )
    research_text = "\n".join(research_bullets) if research_bullets else "Regional road network and valley access points verified."

    # Estimated benchmark price based on days and party
    base_daily_pkr = 24000
    est_total_pkr = preferences.duration_days * base_daily_pkr
    estimated_price_str = f"{est_total_pkr:,.2f}"

    # Prepare LLM messages
    pref_summary = (
        f"Destination: {preferences.destination}\n"
        f"Duration: {preferences.duration}\n"
        f"Party Size: {preferences.party_size}\n"
        f"Budget Target: {preferences.budget}\n"
        f"Fitness Level: {preferences.fitness_level}"
    )

    prompt = (
        f"Traveler Request: {user_message}\n\n"
        f"Traveler Preferences:\n{pref_summary}\n\n"
        f"Live Web Research Grounding:\n{research_text}\n\n"
        "Draft a complete, comprehensive expedition plan for this trip. Include a day-by-day route outline, "
        "realistic pricing breakdown, detailed inclusions and exclusions, required equipment checklist, "
        "and official contact details for booking with Indus Trekking and Tours Pakistan."
    )

    llm_reply = None
    if key:
        try:
            messages = [
                {"role": "system", "content": DRAFTING_SYSTEM_PROMPT},
            ]
            for turn in conversation_history[-4:]:
                role = "user" if turn.get("role") in ["user", "traveler"] else "assistant"
                messages.append({"role": role, "content": strip_think_tags(turn.get("content", ""))})
            messages.append({"role": "user", "content": prompt})

            with httpx.Client(timeout=35.0) as client:
                resp = client.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": active_model,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 1500,
                    },
                )
                if resp.status_code == 200:
                    raw_content = resp.json()["choices"][0]["message"]["content"]
                    llm_reply = strip_think_tags(raw_content)
        except Exception as exc:
            logger.warning("Groq drafting call failed: %s. Using structured template.", exc)

    if not llm_reply:
        llm_reply = _build_fallback_draft_reply(destination, preferences, research_bullets, top_source)

    # Standard expedition inclusions and exclusions
    standard_inclusions = [
        "Government-licensed mountain expedition guide & English-speaking tour leader",
        "Local Balti / Shina mountain porters (carrying up to 12.5 kg personal baggage)",
        "Expedition cook and all freshly prepared trail meals (breakfast, trail lunch, 3-course dinner)",
        "2-person all-weather expedition tents and shared mess/kitchen/toilet tents",
        "Dedicated 4x4 mountain jeeps for off-road valley transfers",
        "National Park entry permits, trekking fees, and mandatory government environmental bonds",
        "Twin-sharing hotel accommodation during transit cities (Islamabad / Skardu / Gilgit)",
    ]

    standard_exclusions = [
        "International round-trip airfare and Pakistan visa fees",
        "Mandatory high-altitude travel and emergency helicopter evacuation insurance",
        "Personal trekking equipment (-15°C sleeping bag, trekking boots, crampons)",
        "Gratuities/tips for mountain guides, porters, and kitchen crew",
        "Single room hotel supplements and personal laundry/beverages",
    ]

    standard_equipment = [
        "Sturdy, broken-in high-altitude trekking boots and thermal moisture-wicking socks (4-5 pairs)",
        "4-season down sleeping bag with -15°C to -20°C comfort rating and insulated sleeping pad",
        "Layering system: merino wool base layers, fleece mid-layer, wind/waterproof Gore-Tex outer shell, heavy down jacket",
        "Category 4 UV glacier sunglasses (essential for snow and glacier glare), SPF 50+ sunblock, and lip balm",
        "Telescopic trekking poles with snow baskets, headlamp with spare lithium batteries, and 2L insulated thermos",
        "Personal first aid kit including altitude sickness medication (Diamox/Acetazolamide) and water purification tablets",
    ]

    contact_info = {
        "company": "Indus Trekking and Tours Pakistan",
        "website": "https://itp.7scribes.com",
        "email": "info@itp.7scribes.com",
        "advisory": "Permit processing and logistics coordination require 6 to 8 weeks advance booking.",
    }

    # Construct structured draft itinerary object
    draft_title = f"{preferences.duration} {preferences.destination} Custom Expedition"
    raw_draft = {
        "title": draft_title,
        "region": f"{preferences.destination}, Northern Pakistan",
        "duration": preferences.duration,
        "duration_days": preferences.duration_days,
        "price": f"PKR {estimated_price_str} (Estimated)",
        "estimated_price_pkr": estimated_price_str,
        "source_url": top_source,
        "summary": (
            f"Complete {preferences.duration} private expedition through {preferences.destination}. "
            f"Tailored for {preferences.party_size} with {preferences.fitness_level.lower()} activity level. "
            f"Includes complete day-by-day route, equipment checklist, inclusions, exclusions, and cost breakdown."
        ),
        "highlights": [
            f"Private 4x4 mountain transport and scenic valley crossings.",
            f"Dedicated licensed mountain guide and local porters.",
            f"All camping logistics, meals, and park trekking permits covered.",
        ],
        "inclusions": standard_inclusions,
        "exclusions": standard_exclusions,
        "equipment": standard_equipment,
        "contact_details": contact_info,
        "scraped_at": now_iso,
        "is_draft": True,
        "is_approved_by_user": False,
        "status": "draft",
    }

    # Enforce Phase 4 integrity rules
    processed_draft = data_integrity_guard.process_itinerary_detail(
        raw_draft,
        source_type="web_search",
    )

    return {
        "reply_text": llm_reply,
        "itinerary_draft": processed_draft,
        "preferences": preferences.to_dict(),
        "confidence_label": CONFIDENCE_UNVERIFIED,
        "source_url": top_source,
        "timestamp": now_iso,
    }


def _build_fallback_draft_reply(
    destination: str,
    preferences: TravelerPreferences,
    research_bullets: List[str],
    top_source: str,
) -> str:
    """Deterministic fallback draft when LLM API is unavailable."""
    days = preferences.duration_days
    return (
        f"Salam! While we do not currently list a pre-packaged tour for **{destination}** in our static catalog, "
        f"Indus Trekking and Tours Pakistan serves this region with dedicated private logistics.\n\n"
        f"Based on live travel research from {top_source}, I have structured a custom **{preferences.duration}** draft itinerary "
        f"tailored for {preferences.party_size} ({preferences.fitness_level.lower()} pace):\n\n"
        f"• **Day 1**: Islamabad departure, scenic drive via highway & mountain passes.\n"
        f"• **Day 2 to {days - 2}**: Exploration of {destination}, valley villages, viewpoint hikes, and cultural immersion.\n"
        f"• **Day {days - 1}**: Return transit toward staging hub.\n"
        f"• **Day {days}**: Final return journey to Islamabad & expedition wrap-up.\n\n"
        f"> **Note**: This is a custom draft proposal (*unverified estimate*). Our mountain operations team will review hotel availability, "
        "jeep transfers, and guide assignments before confirming final booking details."
    )
