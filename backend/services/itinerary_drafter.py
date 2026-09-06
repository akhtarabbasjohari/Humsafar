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
from services.pricing_service import calculate_realistic_tour_pricing
from services.groq_service import strip_think_tags

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
    User message takes strict precedence. Only user messages in conversation history are
    consulted for missing fields, never assistant responses or external citations.
    """
    user_msg_clean = user_message.strip()
    user_msg_lower = user_msg_clean.lower()

    # 1. Destination
    destination = default_destination
    if "chitral" in user_msg_lower and "kalash" in user_msg_lower:
        destination = "Chitral & Kalash Valley"
    elif "swat" in user_msg_lower and "kalam" in user_msg_lower:
        destination = "Swat & Kalam Valley"
    elif default_destination and default_destination != "Northern Pakistan":
        destination = default_destination
    elif "gilgit" in user_msg_lower and "baltistan" in user_msg_lower:
        destination = "Gilgit-Baltistan"
    else:
        destination = default_destination or "Northern Pakistan"

    # 2. Duration (inspect current user message first)
    duration_match = re.search(r"\b(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:day|days|d)\b", user_msg_lower)
    if not duration_match and conversation_history:
        # Only inspect past USER messages, never assistant responses
        for turn in reversed(conversation_history[-4:]):
            if turn.get("role") in ["user", "traveler"] or turn.get("sender") == "user":
                txt = turn.get("content", "").lower()
                duration_match = re.search(r"\b(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:day|days|d)\b", txt)
                if duration_match:
                    break

    duration_days = 7
    duration_str = "7 Days"
    if duration_match:
        d1 = int(duration_match.group(1))
        duration_days = d1
        if duration_match.group(2):
            duration_str = f"{d1}-{duration_match.group(2)} Days"
        else:
            duration_str = f"{d1} Days"

    # 3. Party Size (inspect current user message first)
    party_size = "2 Persons"
    party_match = re.search(r"\b(\d+)\s*(?:people|persons|travelers|pax|members|friends)\b", user_msg_lower)
    if not party_match and conversation_history:
        for turn in reversed(conversation_history[-4:]):
            if turn.get("role") in ["user", "traveler"] or turn.get("sender") == "user":
                party_match = re.search(r"\b(\d+)\s*(?:people|persons|travelers|pax|members|friends)\b", turn.get("content", "").lower())
                if party_match:
                    break

    if party_match:
        party_size = f"{party_match.group(1)} Persons"
    elif "solo" in user_msg_lower:
        party_size = "1 Person (Solo)"
    elif "family" in user_msg_lower:
        party_size = "Family Group"

    # 4. Budget (inspect current user message first)
    budget = "Custom Estimate"
    budget_pkr_match = re.search(r"(?:pkr|rs\.?)\s*([\d,]+)", user_msg_lower)
    if not budget_pkr_match and conversation_history:
        for turn in reversed(conversation_history[-4:]):
            if turn.get("role") in ["user", "traveler"] or turn.get("sender") == "user":
                budget_pkr_match = re.search(r"(?:pkr|rs\.?)\s*([\d,]+)", turn.get("content", "").lower())
                if budget_pkr_match:
                    break

    if budget_pkr_match:
        budget = f"PKR {budget_pkr_match.group(1)}"
    elif "luxury" in user_msg_lower or "premium" in user_msg_lower:
        budget = "Premium / Boutique"
    elif "budget" in user_msg_lower or "cheap" in user_msg_lower or "economy" in user_msg_lower:
        budget = "Economy / Budget"

    # 5. Fitness Level
    fitness_level = "Moderate"
    if any(k in user_msg_lower for k in ["strenuous", "difficult", "hard", "mountaineer", "expedition"]):
        fitness_level = "Strenuous / High Endurance"
    elif any(k in user_msg_lower for k in ["easy", "leisure", "relax"]):
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
   - MANDATORY PRICING DISCIPLINE: State the realistic estimated pricing (both PKR and USD) clearly in your narrative. NEVER say 'Pricing upon inquiry' or 'contact for pricing'. All itineraries feature concrete market estimates and itemized breakdowns.
2. CRITICAL SEPARATION OF CONCERNS:
   - DO NOT dump a raw markdown schedule table or day-by-day outline into this text reply!
   - The detailed day-by-day stages, estimated prices, itemized cost breakdown, inclusions, exclusions, and equipment checklist are delivered directly in the accompanying structured itinerary card payload, which the frontend renders visually as an interactive timeline.
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

    # Calculate realistic market pricing with dual currency and itemized breakdown
    party_digits = re.search(r"(\d+)", str(preferences.party_size))
    p_size = int(party_digits.group(1)) if party_digits else 2
    draft_title = f"{preferences.duration} {preferences.destination} Custom Expedition"

    pricing_info = calculate_realistic_tour_pricing(
        title=draft_title,
        destination=preferences.destination,
        duration_days=preferences.duration_days,
        party_size=p_size,
    )
    final_price = pricing_info["price"]
    pricing_breakdown = pricing_info["pricing_breakdown"]
    total_pkr_str = pricing_breakdown.get("total_pkr_range", final_price)

    # Prepare LLM messages
    pref_summary = (
        f"Destination: {preferences.destination}\n"
        f"Duration: {preferences.duration}\n"
        f"Party Size: {preferences.party_size}\n"
        f"Budget Target: {preferences.budget}\n"
        f"Fitness Level: {preferences.fitness_level}\n"
        f"Calculated Market Price: {final_price}"
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
        llm_reply = _build_fallback_draft_reply(
            destination, preferences, research_bullets, top_source, price=final_price
        )

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
    clean_region = (
        preferences.destination
        if "pakistan" in preferences.destination.lower()
        else f"{preferences.destination}, Pakistan"
    )
    raw_draft = {
        "title": draft_title,
        "region": clean_region,
        "duration": preferences.duration,
        "duration_days": preferences.duration_days,
        "price": final_price,
        "pricing_breakdown": pricing_breakdown,
        "estimated_price_pkr": total_pkr_str,
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
    """Generate structured, realistic day-by-day stages for a custom drafted trip without repetition."""
    dest_clean = destination.strip()
    stages: List[Dict[str, Any]] = []

    if duration_days <= 1:
        return [{
            "day": 1,
            "title": f"Day Excursion & Highlights of {dest_clean}",
            "description": f"Comprehensive guided exploration of {dest_clean}, visiting key scenic viewpoints, heritage trails, and local artisan markets.",
            "altitude": "1,800m",
        }]

    # Diverse, sequential stage themes for multi-day mountain expeditions
    middle_day_themes = [
        ("Acclimatization Ridge Hike & Panoramic Viewpoints", "Scenic guided hike through pine and birch forests to high panoramic ridge; altitude familiarization and hydration check.", "2,650m"),
        ("Ascent to High Alpine Meadows & Glacial Streams", "Trek along pristine glacial meltwater streams up to alpine pasture meadows beneath granite spires.", "3,150m"),
        ("Glacial Moraine Exploration & Ridge Traverse", "Traverse lateral moraine paths, observing dynamic glacial formations and expansive vistas of surrounding 6,000m-7,000m peaks.", "3,550m"),
        ("High Pass Crossing & Summit Viewpoint Excursion", "Challenging morning ascent to high viewpoint saddle, offering panoramic vistas across Karakoram and Himalayan ranges.", "3,850m"),
        ("Alpine Lakes Discovery & Pristine Wilderness", "Trek to turquoise glacial tarns nestled beneath rocky crags; photography excursion and wilderness rest.", "3,400m"),
        ("Upper Valley Trek & High Camp Experience", "Venture into the remote upper valley cirque with native mountain leaders; stargazing beneath crystal-clear mountain skies.", "3,700m"),
        ("Wilderness Descent along River Gorge", "Gentle descent along rushing river rapids, passing seasonal shepherd hamlets and wild juniper forests.", "3,050m"),
        ("Cultural Immersion in Historic Mountain Village", "Visit traditional stone-and-timber mountain hamlets; engage with local community elders and observe native handicrafts.", "2,450m"),
        ("Hidden Canyon & Cascading Waterfalls", "Day hike into a secluded rocky canyon leading to natural cascading waterfalls and mineral springs.", "2,550m"),
        ("Ancient Fortresses & Valley Heritage Trails", "Explore historic regional towers, ancient petroglyphs, and organic apricot and walnut orchards.", "2,200m"),
        ("Photography Trek & Riverside Rest", "Leisurely day along the riverbank capturing landscape reflections and mountain wildlife; evening tea with local guides.", "2,350m"),
        ("Active Trail Ridge Challenge & Scramble", "Guided scramble up rocky ridge viewpoint with 360-degree amphitheater views of snowcapped peaks.", "3,300m"),
        ("Traditional Woodworking & Carpet Weaving Hamlets", "Visit artisan workshops specializing in Balti woodcarving, handwoven pashmina, and wool carpets.", "2,150m"),
        ("Rest & High-Altitude Wellness Reflection", "Relaxation day at eco-lodge; preparation and packing of expedition equipment with guide team.", "2,250m"),
        ("Scenic Off-Road Valley Excursion", "4x4 jeep exploration of side valleys and remote tributary passes inaccessible by standard vehicles.", "2,800m"),
    ]

    # Day 1: Staging & Departure
    stages.append({
        "day": 1,
        "title": f"Islamabad Briefing & Departure toward {dest_clean} Hub",
        "description": f"Expedition orientation, document checks with Ministry of Tourism, and morning departure along scenic northern highway.",
        "altitude": "540m",
    })

    if duration_days == 2:
        stages.append({
            "day": 2,
            "title": f"Exploration of {dest_clean} & Return Journey",
            "description": f"Morning exploration of {dest_clean}'s primary viewpoints and heritage sites before afternoon transit back.",
            "altitude": "1,800m",
        })
        return stages

    # Day 2: Arrival & Base Hub
    stages.append({
        "day": 2,
        "title": f"Scenic Transit & Arrival in {dest_clean} Base Hub",
        "description": f"Transfer by dedicated 4x4 mountain jeeps into {dest_clean}; check-in at lodge, local briefing, and gentle orientation walk.",
        "altitude": "2,200m",
    })

    # Intermediate days
    remaining_middle_days = duration_days - 3  # leaving last day for return
    for i in range(remaining_middle_days):
        day_num = i + 3
        theme_idx = i % len(middle_day_themes)
        theme_title, theme_desc, theme_alt = middle_day_themes[theme_idx]
        if i >= len(middle_day_themes):
            theme_title = f"{theme_title} - Phase {i // len(middle_day_themes) + 1}"

        stages.append({
            "day": day_num,
            "title": f"{theme_title}",
            "description": theme_desc,
            "altitude": theme_alt,
        })

    # Final Day: Return
    stages.append({
        "day": duration_days,
        "title": "Return Journey to Islamabad & Expedition Wrap-up",
        "description": "Scenic return flight or overland journey back to Islamabad; debriefing with mountain operations team and airport transfers.",
        "altitude": "540m",
    })

    return stages


def _build_fallback_draft_reply(
    destination: str,
    preferences: TravelerPreferences,
    research_bullets: List[str],
    top_source: str,
    price: str = "",
) -> str:
    """Deterministic, clean conversational draft reply."""
    price_clause = f"Estimated pricing for this expedition is **{price}**, with an itemized cost breakdown included. " if price else ""
    return (
        f"Salam! Here is a customized {preferences.duration} expedition proposal for **{destination}** "
        f"designed for {preferences.party_size} at a {preferences.fitness_level.lower()} pace.\n\n"
        f"Our team has grounded this route in current mountain logistics and regional trail information from {top_source}. {price_clause}"
        "Below is the complete day-by-day outline, altitude profile, estimated pricing, and essential gear checklist. "
        "Our mountain operations team will review hotel availability, 4x4 jeep transfers, and licensed guide assignments before finalizing your booking."
    )


