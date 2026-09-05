"""
Groq LLM Service for Humsafar.
Synthesizes high-quality, authentic travel guide responses grounded strictly in live scraped itineraries.
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")


def strip_think_tags(text: str) -> str:
    """
    Remove reasoning model thought blocks (<think>...</think>) from model outputs
    so internal chain-of-thought is never exposed to travelers.
    """
    if not text:
        return ""
    # If there is a closing </think>, strip everything between <think> and </think>
    if "</think>" in text:
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return cleaned.strip()

    # If <think> is unclosed, strip the tag and leading thinking bullets/steps
    if "<think>" in text:
        lines = text.splitlines()
        content_lines = []
        in_think = False
        for line in lines:
            if "<think>" in line:
                in_think = True
                continue
            if in_think:
                stripped_l = line.strip()
                if (
                    stripped_l.startswith(("*", "-", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "#"))
                    or "thinking" in stripped_l.lower()
                    or "analyze" in stripped_l.lower()
                    or not stripped_l
                ):
                    continue
                else:
                    in_think = False
                    content_lines.append(line)
            else:
                content_lines.append(line)
        return "\n".join(content_lines).strip()

    return text.strip()


SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion embedded on the Indus Trekking and Tours Pakistan website (itp.7scribes.com).
Company Tagline: "Plan better. Travel farther."

Your primary role is to help travelers discover, explore, and plan mountain expeditions and cultural tours across Pakistan (Karakoram, Himalayas, Hindukush, Gilgit-Baltistan, Hunza, Skardu, Deosai, Swat, Chitral, Fairy Meadows, K2 Base Camp, and beyond).

CRITICAL DATA INTEGRITY & PRESENTATION RULES:
1. Grounding First: Ground all official package facts on the verified company listings from itp.7scribes.com.
2. Complete, Comprehensive Travel Proposals: When a traveler inquires about an itinerary, destination, or tour, provide a COMPLETE, highly detailed, beautifully structured travel proposal. Never leave details out or tell the traveler merely to 'contact for schedule' without providing the full day-by-day plan and logistics.
3. Required Sections in Every Travel Proposal:
   - ## Overview & Destination Highlights: Engaging narrative of the destination, average elevation/altitude (e.g., Deosai at 4,114m), iconic landmarks (e.g., Sheosar Lake, wildlife, high plateaus), and best travel season.
   - ## Day-by-Day Itinerary: A clear, paced schedule for each day (e.g., **Day 1:** ..., **Day 2:** ..., etc.) detailing routes, transport modes (4x4 jeeps, trekking), and overnight stops.
   - ## Pricing & Budget Breakdown:
     - State the official package status ("Pricing upon inquiry" or exact PKR price verified from itp.7scribes.com).
     - Provide realistic, itemized market pricing estimates in Pakistani Rupees (PKR) and approximate USD (e.g., PKR 180,000 – 260,000 / $650 – $950 USD per person for private groups), explaining what factors influence cost (group size, 4x4 jeep requirements, hotel standard).
   - ## Included Services: Full bulleted list of all inclusions (licensed guide, Balti porters, all camp meals, 4x4 jeeps, park entry permits, twin-sharing hotel stays).
   - ## Excluded Services: Clear bulleted list of exclusions (international flights, personal travel/evacuation insurance, personal gear, tips).
   - ## Essential Mountain Gear Checklist: Specific gear recommendations (sturdy trekking boots, 4-season -15°C sleeping bag, thermal layering, Category 4 UV glacier sunglasses, headlamp, first aid).
   - ## Booking & Operations Advisory: Official booking guidelines for Indus Trekking and Tours Pakistan (itp.7scribes.com), noting required advance reservation lead time (6 to 8 weeks for permits and logistics).
4. Tone & Formatting:
   - Warm, authoritative, authentic, and respectful of mountain heritage and local cultures.
   - Use clear markdown headings (## and ###), clean bold labels (**Day 1:**, **Price:**), and neat bullet points.
   - NEVER output internal reasoning tags like <think> or </think>.
   - NEVER output file metadata strings like '• MD' or 'Download Itinerary'. Present the proposal directly as a seamless, professional travel document.
"""

CONVERSATIONAL_SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion for Indus Trekking and Tours Pakistan (itp.7scribes.com).
Company Tagline: "Plan better. Travel farther."

The traveler sent a greeting, small talk, or a general conversational question.
Provide a warm, hospitable, and concise response. Welcome them to Indus Trekking and Tours, briefly mention the iconic mountain regions and expeditions we specialize in (K2 Base Camp, Concordia, Hunza Valley, Skardu, Deosai, Fairy Meadows, Swat), and invite them to share what trip or valley they would like to explore.
Do NOT generate or invent an unrequested itinerary. Keep it welcoming, authentic, and focused on assisting them.
NO INTERNAL THOUGHT TAGS: Never output <think> tags or your internal thinking process. Output only the final response.
"""


def generate_conversational_reply(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate a warm conversational reply for greetings and general small talk
    without forcing an itinerary match or catalog dump.
    """
    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    active_model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    if not key:
        return (
            "Salam and welcome to Indus Trekking and Tours Pakistan!\n\n"
            "I am Humsafar, your mountain expedition and tour companion. Whether you are dreaming of trekking "
            "to K2 Base Camp and Concordia, exploring the alpine wilderness of Deosai, or planning a private journey "
            "through Hunza and Skardu, I am here to help.\n\n"
            "Where in northern Pakistan would you like to travel, or what kind of experience are you looking for?"
        )

    messages = [{"role": "system", "content": CONVERSATIONAL_SYSTEM_PROMPT}]
    for msg in conversation_history[-4:]:
        role = "user" if msg.get("role") in ["user", "traveler"] else "assistant"
        content = strip_think_tags(msg.get("content", ""))
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": active_model, "messages": messages, "temperature": 0.5, "max_tokens": 1024},
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            result = strip_think_tags(raw_text)
            if result:
                return result
    except Exception as exc:
        logger.error("Groq conversational reply error: %s", exc)

    return (
        "Salam and welcome to Indus Trekking and Tours Pakistan!\n\n"
        "I am Humsafar, your official mountain expedition planner. "
        "Tell me which region or peak you would like to explore—such as K2 Base Camp, Hunza, Skardu, Deosai, or Swat—"
        "and I will help you design the perfect itinerary."
    )



def generate_travel_reply(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    matched_itineraries: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    additional_research: Optional[str] = None,
) -> str:
    """
    Generate a conversational travel reply via Groq LLM grounded on scraped itineraries.
    Strips any <think> tags before returning.
    """
    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    active_model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    if not key:
        logger.warning("GROQ_API_KEY not configured. Falling back to local template response.")
        return _build_fallback_reply(matched_itineraries, user_message)

    # Prepare Context from matched itineraries
    context_blocks = []
    for i, it in enumerate(matched_itineraries[:3], 1):
        block_lines = [
            f"--- Official Listing #{i} ---",
            f"Title: {it.get('title')}",
            f"Duration: {it.get('duration')}",
            f"Price: {it.get('price')}",
            f"Source URL: {it.get('source_url')}",
            f"Confidence: {it.get('confidence_label', 'from our official listing')}",
            f"Scraped At: {it.get('scraped_at')}",
            f"Summary/Highlights: {it.get('summary')}",
        ]
        if it.get("itinerary_schedule"):
            block_lines.append(f"Official Day-by-Day Schedule: {it.get('itinerary_schedule')}")
        if it.get("inclusions"):
            block_lines.append(f"Included Services: {', '.join(it.get('inclusions'))}")
        if it.get("exclusions"):
            block_lines.append(f"Excluded Services: {', '.join(it.get('exclusions'))}")
        if it.get("equipment"):
            block_lines.append(f"Required Mountain Gear: {', '.join(it.get('equipment'))}")
        if it.get("contact_details"):
            cd = it.get("contact_details")
            block_lines.append(f"Official Booking Contact: {cd.get('company')}, Website: {cd.get('website')}, Email: {cd.get('email')}, Advisory: {cd.get('advisory')}")
        context_blocks.append("\n".join(block_lines))

    catalog_context = "\n\n".join(context_blocks) if context_blocks else "No direct package matches found on the website."
    if additional_research:
        catalog_context += f"\n\nADDITIONAL REGIONAL LOGISTICS & MISSING DETAILS RESEARCH:\n{additional_research}"

    # Build messages array
    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCURRENT OFFICIAL LISTINGS GROUND TRUTH:\n{catalog_context}"}
    ]

    # Append recent conversation turns (up to last 6)
    for msg in conversation_history[-6:]:
        role = "user" if msg.get("role") in ["user", "traveler"] else "assistant"
        content = strip_think_tags(msg.get("content", ""))
        if content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})

    try:
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
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return strip_think_tags(raw_text)

    except Exception as exc:
        logger.error("Groq API error during generation: %s. Using local fallback.", exc)
        return _build_fallback_reply(matched_itineraries, user_message)


def _build_fallback_reply(matched_itineraries: List[Dict[str, Any]], query: str) -> str:
    """Deterministic fallback if Groq API is temporarily unreachable."""
    if not matched_itineraries:
        return (
            f"Salam! I checked our live catalog on itp.7scribes.com for '{query}'. "
            "While we regularly operate expeditions across northern Pakistan, I could not locate an exact pre-packaged match for this specific route. "
            "Our operations team at Indus Trekking and Tours Pakistan can customize a dedicated itinerary for you."
        )

    tour = matched_itineraries[0]
    inclusions = "\n".join([f"• {inc}" for inc in tour.get("inclusions", [])[:5]])
    equipment = "\n".join([f"• {eq}" for eq in tour.get("equipment", [])[:5]])

    return (
        f"Salam! Welcome to Indus Trekking and Tours Pakistan.\n\n"
        f"### {tour.get('title')}\n\n"
        f"**Destination & Region:** {tour.get('title')} (Verified from itp.7scribes.com)\n"
        f"**Duration:** {tour.get('duration', '7-9 Days')}\n"
        f"**Official Price:** {tour.get('price', 'Pricing upon inquiry')}\n"
        f"**Estimated Market Budget:** PKR 180,000 – 260,000 / $650 – $950 USD per person (depends on group size, 4x4 transfers, and camp staff).\n\n"
        f"### Overview & Highlights\n"
        f"{tour.get('summary', 'Experience the alpine wilderness, high-altitude plateaus, and mountain hospitality of northern Pakistan with native mountain leaders.')}\n\n"
        f"### Included Services\n"
        f"{inclusions or '• Licensed mountain expedition guide\n• Balti porters & camp staff\n• All trail meals & camping equipment\n• 4x4 mountain jeep transfers\n• National park entry permits'}\n\n"
        f"### Essential Gear Checklist\n"
        f"{equipment or '• Sturdy, broken-in trekking boots\n• 4-season (-15°C) sleeping bag\n• Thermal layering & Gore-Tex outer shell\n• Category 4 UV glacier sunglasses'}\n\n"
        f"### Reservations & Bookings\n"
        f"Coordinated directly by **Indus Trekking and Tours Pakistan** (`itp.7scribes.com`). Permit and logistics clearance requires 6 to 8 weeks advance notice.\n\n"
        f"Would you like us to customize the daily pace or adjust the group size for this expedition?"
    )
