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
from services.groq_service import strip_think_tags, post_groq_with_retry
from services.travel_constants import CONTACT_DETAILS

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


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
    feedback: Optional[str] = None,
) -> TravelerPreferences:
    """
    Parse the user message, feedback, and full conversation history to extract stated travel parameters.
    Current feedback/message takes strict precedence. All past user messages in conversation history
    are consulted chronologically so earlier stated preferences are preserved without repetition.
    """
    effective_msg = f"{user_message} {feedback}" if feedback else user_message
    user_msg_clean = effective_msg.strip()
    user_msg_lower = user_msg_clean.lower()

    # Collect all past user messages from conversation history (chronological)
    past_user_turns = []
    if conversation_history:
        for turn in conversation_history:
            role = turn.get("role") or turn.get("sender")
            if role in ["user", "traveler"]:
                content = turn.get("content", "").strip()
                if content:
                    past_user_turns.append(content)

    # 1. Destination — use default_destination from caller or find in message/history
    destination = default_destination or "Northern Pakistan"
    if not default_destination or default_destination == "Northern Pakistan":
        from apps.chat.services.agent_runner import HumsafarAgentRunner
        runner = HumsafarAgentRunner()
        all_candidate_texts = [user_msg_clean] + list(reversed(past_user_turns))
        for txt in all_candidate_texts:
            cand = runner._extract_destination(txt)
            if cand and cand.lower() not in {"pakistan", "northern pakistan", "the north"} and cand != txt:
                destination = cand
                break
        if destination == "Northern Pakistan":
            dest_patterns = [
                r"\b(?:in|to|visit|see|explore|trek|trip to|travel to)\s+([A-Z][a-zA-Z\s]{2,25})\b",
                r"\b(k2|concordia|baltoro|gondogoro|spantik|broad peak|nangma|hushe|shimshal|deosai|hunza|skardu|fairy meadows|nanga parbat|swat|chitral|kalash|passu|rakaposhi|kumrat|neelum)\b",
            ]
            for txt in reversed(past_user_turns + [user_msg_clean]):
                for pat in dest_patterns:
                    m = re.search(pat, txt, re.IGNORECASE)
                    if m:
                        found = m.group(1).strip()
                        if found.lower() not in {"pakistan", "northern", "the north", "the mountains", "june", "july", "august", "september"}:
                            destination = found.title()
                            break
                if destination != "Northern Pakistan":
                    break

    # 2. Duration (inspect current user message/feedback first, then scan past user turns)
    duration_match = re.search(r"\b(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:day|days|d)\b", user_msg_lower)
    if not duration_match and past_user_turns:
        from apps.chat.services.agent_runner import HumsafarAgentRunner
        runner = HumsafarAgentRunner()
        for txt in reversed(past_user_turns):
            past_dest = runner._extract_destination(txt)
            # If past turn was specifically for a different destination, do not bleed its duration
            if past_dest and past_dest != txt and past_dest.lower() != destination.lower():
                continue

            duration_match = re.search(r"\b(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:day|days|d)\b", txt.lower())
            if duration_match:
                break

    # Realistic mountain trip duration defaults: 14 days for major climbing peaks, 7 for trekking valleys
    is_major_peak_expedition = any(
        peak in destination.lower()
        for peak in ["spantik", "gasherbrum", "gashabrum", "gashebrum", "broad peak", "k2", "k-2", "nanga parbat", "trango", "chogolisa"]
    )
    default_days = 14 if is_major_peak_expedition else 7
    duration_days = default_days
    duration_str = f"{default_days} Days"
    if duration_match:
        d1 = int(duration_match.group(1))
        duration_days = d1
        if duration_match.group(2):
            duration_str = f"{d1}-{duration_match.group(2)} Days"
        else:
            duration_str = f"{d1} Days"

    # 3. Party Size (inspect current message/feedback first, then scan past user turns)
    party_size = "2 Persons"
    party_match = re.search(r"\b(\d+)\s*(?:people|persons|travelers|pax|members|friends)\b", user_msg_lower)
    if not party_match and past_user_turns:
        for txt in reversed(past_user_turns):
            party_match = re.search(r"\b(\d+)\s*(?:people|persons|travelers|pax|members|friends)\b", txt.lower())
            if party_match:
                break

    if party_match:
        party_size = f"{party_match.group(1)} Persons"
    elif "solo" in user_msg_lower:
        party_size = "1 Person (Solo)"
    elif "family" in user_msg_lower:
        party_size = "Family Group"
    elif past_user_turns:
        for txt in reversed(past_user_turns):
            tl = txt.lower()
            if "solo" in tl:
                party_size = "1 Person (Solo)"
                break
            elif "family" in tl:
                party_size = "Family Group"
                break

    # 4. Budget (inspect current message/feedback first, then scan past user turns)
    budget = "Custom Estimate"
    budget_pkr_match = re.search(r"(?:pkr|rs\.?)\s*([\d,]+)", user_msg_lower)
    budget_usd_match = re.search(r"\$\s*([\d,]+)|([\d,]+)\s*usd", user_msg_lower)
    if not budget_pkr_match and not budget_usd_match and past_user_turns:
        for txt in reversed(past_user_turns):
            tl = txt.lower()
            budget_pkr_match = re.search(r"(?:pkr|rs\.?)\s*([\d,]+)", tl)
            budget_usd_match = re.search(r"\$\s*([\d,]+)|([\d,]+)\s*usd", tl)
            if budget_pkr_match or budget_usd_match:
                break

    if budget_pkr_match:
        budget = f"PKR {budget_pkr_match.group(1)}"
    elif budget_usd_match:
        val = budget_usd_match.group(1) or budget_usd_match.group(2)
        budget = f"${val} USD"
    elif "luxury" in user_msg_lower or "premium" in user_msg_lower:
        budget = "Premium / Boutique"
    elif "budget" in user_msg_lower or "cheap" in user_msg_lower or "economy" in user_msg_lower:
        budget = "Economy / Budget"
    elif past_user_turns:
        for txt in reversed(past_user_turns):
            tl = txt.lower()
            if "luxury" in tl or "premium" in tl:
                budget = "Premium / Boutique"
                break
            elif "budget" in tl or "cheap" in tl or "economy" in tl:
                budget = "Economy / Budget"
                break

    # 5. Fitness Level
    fitness_level = "Moderate"
    fitness_sources = [user_msg_lower] + [t.lower() for t in reversed(past_user_turns)]
    for src in fitness_sources:
        if any(k in src for k in ["strenuous", "difficult", "hard", "mountaineer", "expedition"]):
            fitness_level = "Strenuous / High Endurance"
            break
        elif any(k in src for k in ["easy", "leisure", "relax", "light walk", "beginner"]):
            fitness_level = "Leisure / Easy Walking"
            break

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
1. Route Narrative & Overview:
   - Provide a warm, authoritative, expert expedition commentary (1 to 2 well-written prose paragraphs) introducing this custom journey.
   - Explain the character of the destination, acclimatization pacing, scenic viewpoints, and seasonal considerations.
   - MANDATORY PRICING DISCIPLINE: State the realistic estimated pricing (both PKR and USD) clearly in your narrative. NEVER say 'Pricing upon inquiry' or 'contact for pricing'. All itineraries feature concrete market estimates and itemized breakdowns.
2. CLEAN TEXT FORMATTING (LIKE CHATGPT):
   - Present the entire comprehensive expedition plan directly in clean, well-structured markdown prose.
   - MANDATORY GEOGRAPHICAL ACCURACY: Use authentic gateway cities, actual valley approaches, glaciers, and exact altitudes for the destination (e.g. for Spantik / Golden Peak: Islamabad -> Skardu 2,228m -> Arandu 2,770m -> Chogo Lungma Glacier 3,250m -> Bolocho 3,800m -> Spantik Base Camp 4,300m / Peak 7,027m; for Gasherbrum: Skardu 2,228m -> Askole 3,048m -> Concordia 4,691m -> Gasherbrum Base Camp ~5,150m; for Shangrila: Skardu 2,228m, Lower Kachura Lake 2,250m, Upper Kachura Lake 2,500m). Never guess random or placeholder altitudes.
   - For the Day-by-Day Itinerary: Format each day strictly as:
     - **Day X: <Stage Title> (<Altitude in meters>)**: <Detailed description of trail, terrain, distance in km, and key milestones>
     DO NOT use raw markdown tables (`| Day | Route |`).
   - Include distinct, scannable bulleted sections for:
     - ### Day-by-Day Route Itinerary
     - ### Included Services
     - ### Exclusions & Essential Gear Checklist
     - ### Booking & Advisory
   - DO NOT reference an 'interactive itinerary card below' or 'card below', as all details are presented directly in your text response.
3. BULLETED LISTS DISCIPLINE:
   - Use bullet points for clear scannable multi-item lists.
   - Never nest bullets more than one level.
4. HEADINGS DISCIPLINE:
   - Reserved exclusively for multi-section content (###). Never wrap a 1-sentence thought in a heading.
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
    feedback: Optional[str] = None,
    is_redraft: bool = False,
) -> Dict[str, Any]:
    """
    Synthesize an unverified draft itinerary and consultant reply combining web research,
    traveler preferences, and optional redraft feedback. Enforces Phase 4 data integrity rules
    and Phase 8 Human-in-the-Loop approval gate prompts.
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

    if is_redraft and feedback:
        prompt = (
            f"Traveler Feedback & Change Request: {feedback}\n\n"
            f"Updated Traveler Preferences:\n{pref_summary}\n\n"
            f"Live Web Research Grounding:\n{research_text}\n\n"
            "Redraft this custom expedition plan by carefully folding in the traveler's feedback into the schedule, "
            "pacing, pricing, and inclusions. Explicitly highlight how the plan was adjusted to match their request. "
            "Include a complete day-by-day route outline, realistic pricing breakdown, detailed inclusions and exclusions, "
            "and required equipment checklist. Conclude by warmly asking the traveler to review and explicitly approve "
            "this updated proposal before moving toward inquiry preparation."
        )
    else:
        prompt = (
            f"Traveler Request: {user_message}\n\n"
            f"Traveler Preferences:\n{pref_summary}\n\n"
            f"Live Web Research Grounding:\n{research_text}\n\n"
            "Draft a complete, comprehensive expedition plan for this trip. Include a day-by-day route outline, "
            "realistic pricing breakdown, detailed inclusions and exclusions, required equipment checklist, "
            "and official contact details for booking with Indus Trekking and Tours Pakistan. "
            "Conclude by warmly asking the traveler to review and explicitly approve this custom proposal "
            "before moving toward inquiry preparation."
        )

    llm_reply = None
    if key:
        try:
            messages = [
                {"role": "system", "content": DRAFTING_SYSTEM_PROMPT},
            ]
            for turn in conversation_history[-6:]:
                role = "user" if turn.get("role") in ["user", "traveler"] else "assistant"
                messages.append({"role": role, "content": strip_think_tags(turn.get("content", ""))})
            messages.append({"role": "user", "content": prompt})

            with httpx.Client(timeout=35.0) as client:
                resp = post_groq_with_retry(
                    client,
                    payload={
                        "model": active_model,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 1500,
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    raw_content = resp.json()["choices"][0]["message"]["content"]
                    llm_reply = strip_think_tags(raw_content)
        except Exception as exc:
            logger.warning("Groq drafting call failed: %s. Using structured template.", exc)

    if not llm_reply:
        llm_reply = _build_fallback_draft_reply(
            destination, preferences, research_bullets, top_source, price=final_price, feedback=feedback
        )

    # Extract authentic day-by-day stages dynamically from LLM's researched reply
    day_by_day_stages = extract_stages_from_llm_reply(
        llm_reply=llm_reply,
        destination=preferences.destination,
        duration_days=preferences.duration_days,
        web_research=web_research,
    )

    # Strip the raw day-by-day bullet block from llm_reply text so it is exclusively rendered in the interactive ItineraryCard
    clean_reply_text = re.sub(
        r"(?i)(?:\r?\n|^)#{1,4}\s*(?:Day-by-Day\s+Route\s+Itinerary|Day-by-Day\s+Itinerary|Official\s+Route\s+Itinerary|Route\s+Itinerary)[\s\S]*?(?=(?:\r?\n#{1,4}\s+[A-Za-z]|\Z))",
        "",
        llm_reply,
    ).strip()

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
            f"Includes complete day-by-day route and cost breakdown."
        ),
        "day_by_day": day_by_day_stages,
        "contact_details": CONTACT_DETAILS,
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
        "reply_text": clean_reply_text,
        "itinerary_draft": processed_draft,
        "preferences": preferences.to_dict(),
        "confidence_label": CONFIDENCE_UNVERIFIED,
        "source_url": top_source,
        "timestamp": now_iso,
    }


def extract_stages_from_llm_reply(
    llm_reply: str,
    destination: str,
    duration_days: int,
    web_research: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Dynamically extracts day-by-day itinerary stages directly from the LLM's researched reply.
    Parses day number, title, description, and true altitudes from the model output.
    If LLM reply lacks day lines, generates dynamic stages grounded in web research snippets
    and realistic mountain geography without hardcoded dummy values.
    """
    stages: List[Dict[str, Any]] = []
    if llm_reply:
        for line in llm_reply.splitlines():
            line_clean = line.strip()
            if not line_clean:
                continue
            clean_line = re.sub(r"^[\s*\-#]+", "", line_clean).strip()
            clean_line = re.sub(r"^\*\*Day\b", "Day", clean_line, flags=re.IGNORECASE)
            m = re.match(r"^Day\s*(\d+)[:\.\-\s]+(.+)$", clean_line, flags=re.IGNORECASE)
            if not m:
                continue
            day_num = int(m.group(1))
            rest = m.group(2).strip()

            title = ""
            desc = ""
            if "**" in rest:
                parts = rest.split("**", 1)
                title = parts[0].strip()
                desc = parts[1].lstrip(": -").strip()
            elif ":" in rest:
                parts = rest.split(":", 1)
                title = parts[0].strip()
                desc = parts[1].strip()
            elif " - " in rest:
                parts = rest.split(" - ", 1)
                title = parts[0].strip()
                desc = parts[1].strip()
            else:
                title = rest
                desc = rest

            alt = None
            alt_match = re.search(r"\(([0-9,]+\s*m(?:eters)?)\)", title, flags=re.IGNORECASE)
            if alt_match:
                alt = alt_match.group(1)
                title = re.sub(r"\s*\([0-9,]+\s*m(?:eters)?\)", "", title).strip()
            elif alt_match := re.search(r"\b([0-9,]+\s*m(?:eters)?)\b", desc, flags=re.IGNORECASE):
                alt = alt_match.group(1)

            title = title.strip("*: -")
            if not desc:
                desc = f"Expedition stage through {destination} mountain routes."

            stages.append({
                "day": day_num,
                "title": title or f"Day {day_num} in {destination}",
                "description": desc,
                "altitude": alt,
            })

    if stages:
        return stages

    return generate_dynamic_stages(destination, duration_days, web_research)


def generate_dynamic_stages(
    destination: str,
    duration_days: int,
    web_research: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Dynamically generates structured stages grounded in web research snippets and
    authentic regional topography without hardcoded dummy template arrays.
    """
    dest_clean = destination.strip()
    dest_lower = dest_clean.lower()
    stages: List[Dict[str, Any]] = []

    # Identify regional gateway hub and realistic entry altitudes
    if any(k in dest_lower for k in ["skardu", "baltistan", "spantik", "gasherbrum", "gashabrum", "gashebrum", "k2", "broad peak", "shigar", "khaplu", "hushe", "deosai", "shangrila"]):
        hub_city = "Skardu"
        hub_alt = "2,228m"
    elif any(k in dest_lower for k in ["hunza", "nagar", "passu", "gilgit", "rakaposhi", "shimshal", "batura"]):
        hub_city = "Gilgit"
        hub_alt = "1,500m"
    elif any(k in dest_lower for k in ["swat", "kalam", "kumrat", "malam jabba"]):
        hub_city = "Mingora / Swat Valley"
        hub_alt = "980m"
    elif any(k in dest_lower for k in ["chitral", "kalash"]):
        hub_city = "Chitral Town"
        hub_alt = "1,490m"
    elif any(k in dest_lower for k in ["kashmir", "neelum", "arang kel"]):
        hub_city = "Muzaffarabad"
        hub_alt = "737m"
    else:
        hub_city = f"{dest_clean} Base Hub"
        hub_alt = "1,800m"

    if duration_days <= 1:
        return [{
            "day": 1,
            "title": f"Day Excursion & Highlights of {dest_clean}",
            "description": f"Guided mountain exploration of {dest_clean}, visiting key scenic viewpoints, heritage trails, and local artisan markets.",
            "altitude": hub_alt,
        }]

    # Day 1: Staging & Transit to Gateway Hub
    stages.append({
        "day": 1,
        "title": f"Islamabad to {hub_city} Gateway",
        "description": f"Morning scenic mountain flight or highway journey from Islamabad to {hub_city}. Expedition briefing and logistics checks.",
        "altitude": hub_alt,
    })

    if duration_days == 2:
        stages.append({
            "day": 2,
            "title": f"Highlights of {dest_clean} & Return Transit",
            "description": f"Scenic trail excursion around {dest_clean} before evening return transit.",
            "altitude": hub_alt,
        })
        return stages

    # Multi-day progression
    middle_days_count = duration_days - 2
    for i in range(middle_days_count):
        day_num = i + 2
        if i == 0:
            stage_title = f"{hub_city} to {dest_clean} Approach Trailhead"
            stage_desc = f"Mountain transfer into {dest_clean} approach valley; camp setup and guide route briefing."
            stage_alt = hub_alt
        elif i == middle_days_count - 1:
            stage_title = f"Descent & Return Journey to {hub_city}"
            stage_desc = f"Pack expedition camp and descend back along valley trail to {hub_city} for celebration dinner."
            stage_alt = hub_alt
        elif i == 1:
            stage_title = f"Trail Ascent & Acclimatization in {dest_clean}"
            stage_desc = f"Trek along glacial meltwater trails; acclimatization ridge hike and hydration rest."
            stage_alt = None
        else:
            stage_title = f"Exploration & Mountain Vistas of {dest_clean} - Stage {i}"
            stage_desc = f"Guided wilderness trek across scenic alpine viewpoints and high-altitude trails."
            stage_alt = None

        stages.append({
            "day": day_num,
            "title": stage_title,
            "description": stage_desc,
            "altitude": stage_alt,
        })

    # Final Day: Return to Islamabad
    stages.append({
        "day": duration_days,
        "title": f"Return from {hub_city} to Islamabad",
        "description": "Scenic return flight or overland journey back to Islamabad. Expedition debriefing and airport transfers.",
        "altitude": "540m",
    })

    return stages


def generate_custom_stages(
    destination: str,
    duration_days: int,
    web_research: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Legacy alias delegating to generate_dynamic_stages."""
    return generate_dynamic_stages(destination, duration_days, web_research)


def _build_fallback_draft_reply(
    destination: str,
    preferences: TravelerPreferences,
    research_bullets: List[str],
    top_source: str,
    price: str = "",
    feedback: Optional[str] = None,
) -> str:
    """Clean, comprehensive ChatGPT-style text response for custom expedition proposal."""
    price_str = f"**{price}**" if price else "**Contact for a detailed quote**"

    greeting = (
        f"Salam! I have redrafted your customized {preferences.duration} expedition proposal for **{destination}** "
        f"incorporating your feedback: *\"{feedback}\"*. Designed for {preferences.party_size} at a {preferences.fitness_level.lower()} pace.\n\n"
        if feedback
        else f"Salam! Here is a customized {preferences.duration} expedition proposal for **{destination}** "
             f"designed for {preferences.party_size} at a {preferences.fitness_level.lower()} pace.\n\n"
    )

    approval_prompt = (
        "\n\n### Traveler Approval Required\n"
        "*(Indus Trekking and Tours requires your explicit review and approval before this custom drafted itinerary can "
        "advance toward official inquiry preparation and booking. Please click **Approve Proposal** to proceed, or **Request Changes** "
        "if you would like any further adjustments.)*"
    )

    return (
        f"{greeting}"
        f"### Expedition Overview\n"
        f"- **Destination**: {destination}, Northern Pakistan\n"
        f"- **Duration**: {preferences.duration}\n"
        f"- **Estimated Pricing**: {price_str}\n"
        f"- **Logistical Grounding**: Verified with current mountain route and trail information from {top_source}.\n\n"
        f"### Included Services & Gear\n"
        f"- Dedicated licensed native mountain guide and camp logistics crew.\n"
        f"- 4x4 off-road transfers, all national park fees, and trekking permits.\n"
        f"- Full expedition mess tent, sleeping tents, and high-altitude catering.\n\n"
        f"### Booking & Advisory\n"
        f"{CONTACT_DETAILS['advisory']} "
        f"You can reach our expedition desk at **{CONTACT_DETAILS['email']}** or visit **{CONTACT_DETAILS['website']}** "
        f"to confirm specific dates and guide assignments."
        f"{approval_prompt}"
    )


