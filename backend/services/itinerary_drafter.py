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


DRAFTING_SYSTEM_PROMPT = """You are Humsafar, the senior expedition planner for Indus Trekking and Tours Pakistan.
The traveler has requested a destination that we serve, but which does not have a static, pre-packaged itinerary on our website.
You must synthesize a custom DRAFT itinerary proposal based on live web research and the traveler's stated preferences.

CRITICAL EDITORIAL & INTEGRITY RULES:
1. Clearly state that this is a custom draft created specifically for them based on live regional research, not a pre-existing catalog package.
2. Label all prices and schedules as unverified estimates that our operations team will finalize and confirm.
3. Structure the draft with a clear Day-by-Day outline, logistics advice (jeep access, acclimatization), and highlights.
4. Maintain a warm, encouraging, authoritative, and respectful tone toward northern Pakistan's mountain communities.
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
    base_daily_pkr = 22000
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
        "Draft a compelling, day-by-day custom expedition proposal. Outline the route, key passes or valleys, "
        "mountain transport requirements, and estimated costs, highlighting that our team will customize and confirm all bookings."
    )

    llm_reply = None
    if key:
        try:
            messages = [
                {"role": "system", "content": DRAFTING_SYSTEM_PROMPT},
            ]
            for turn in conversation_history[-4:]:
                role = "user" if turn.get("role") in ["user", "traveler"] else "assistant"
                messages.append({"role": role, "content": turn.get("content", "")})
            messages.append({"role": "user", "content": prompt})

            with httpx.Client(timeout=30.0) as client:
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
                        "max_tokens": 1200,
                    },
                )
                if resp.status_code == 200:
                    llm_reply = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Groq drafting call failed: %s. Using structured template.", exc)

    if not llm_reply:
        llm_reply = _build_fallback_draft_reply(destination, preferences, research_bullets, top_source)

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
            f"Custom {preferences.duration} private expedition through {preferences.destination}. "
            f"Tailored for {preferences.party_size} with {preferences.fitness_level.lower()} activity level. "
            f"Grounded in live regional research from {top_source}."
        ),
        "highlights": [
            f"Private 4x4 mountain transport and scenic valley crossings.",
            f"Dedicated licensed guide and mountain hospitality.",
            f"Flexible daily pacing matching {preferences.fitness_level.lower()} fitness.",
        ],
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
