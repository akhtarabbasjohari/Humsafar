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

CORE ARCHITECTURAL RULE: STRUCTURE IS EARNED, NOT DEFAULT.
1. Route Narrative & Commentary:
   - Provide a warm, authoritative, expert expedition commentary (1 to 3 well-written prose paragraphs) introducing this custom journey.
   - Explain the character of the destination, acclimatization pacing, scenic viewpoints, and seasonal considerations.
2. CRITICAL SEPARATION OF CONCERNS:
   - DO NOT dump a raw markdown schedule table or day-by-day outline into this text reply!
   - The detailed day-by-day stages, estimated prices, inclusions, exclusions, and equipment checklist are delivered directly in the accompanying structured itinerary card payload, which the frontend renders visually as an interactive timeline.
   - Point the traveler to the visual itinerary card below for the complete day-by-day route, estimated pricing, and booking options.
3. BULLETED LISTS DISCIPLINE:
   - Use bullet points ONLY for genuinely scannable multi-item lists (>3 items) where order or shared structure matters.
   - Never nest bullets more than one level.
   - For 2 or 3 items, weave them into natural sentences.
4. HEADINGS DISCIPLINE:
   - Reserved exclusively for multi-section content. Never wrap a 1-sentence thought in a heading.
5. TONE & SANITIZATION:
   - Warm, hospitable, respectful of mountain heritage and native Balti/Shina communities.
   - Clearly state that this is a custom proposal synthesized from regional travel intelligence, with final dates and permits confirmed by our operations team.
   - NEVER output internal reasoning tags like <think> or </think>.
   - NEVER output file metadata strings like '• MD' or 'Download Itinerary'.
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

    # Generate structured day-by-day stops
    day_by_day_stages = generate_custom_stages(preferences.destination, preferences.duration_days)

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
        "day_by_day": day_by_day_stages,
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


def generate_custom_stages(destination: str, duration_days: int) -> List[Dict[str, Any]]:
    """Generate structured day-by-day stages for a custom drafted trip."""
    dest_clean = destination.strip()
    stages: List[Dict[str, Any]] = []

    stages.append({
        "day": 1,
        "title": f"Departure from Islamabad to {dest_clean} Staging Area",
        "description": f"Morning departure from Islamabad along the highway toward northern staging hub; expedition orientation and gear check.",
        "altitude": "1,500m",
    })

    if duration_days > 2:
        stages.append({
            "day": 2,
            "title": f"Arrival in {dest_clean} & Acclimatization",
            "description": f"Transfer by dedicated 4x4 mountain jeeps into {dest_clean}; acclimatization walk and heritage exploration.",
            "altitude": "2,400m",
        })

    for d in range(3, duration_days):
        stages.append({
            "day": d,
            "title": f"{dest_clean} Trail Hiking & Wilderness Exploration",
            "description": f"Guided wilderness excursion to alpine meadows, viewpoint passes, and glacial streams with local guides.",
            "altitude": "3,200m",
        })

    if duration_days > 1:
        stages.append({
            "day": duration_days,
            "title": f"Return Journey to Islamabad & Expedition Wrap-up",
            "description": f"Scenic return journey to Islamabad, debriefing with our mountain operations team, and airport transfers.",
            "altitude": "540m",
        })

    return stages


def _build_fallback_draft_reply(
    destination: str,
    preferences: TravelerPreferences,
    research_bullets: List[str],
    top_source: str,
) -> str:
    """Deterministic fallback draft when LLM API is unavailable."""
    return (
        f"Salam! While we do not currently list a pre-packaged tour for **{destination}** in our catalog, "
        f"Indus Trekking and Tours Pakistan operates dedicated private logistics across this region.\n\n"
        f"Based on travel research from {top_source}, I have synthesized a tailored **{preferences.duration}** custom proposal "
        f"for {preferences.party_size} at a {preferences.fitness_level.lower()} pace. "
        f"Please review the complete day-by-day route, estimated pricing, and gear requirements in the interactive itinerary card below. "
        "Our operations team will review hotel availability, 4x4 jeep transfers, and guide assignments before confirming final booking details."
    )

