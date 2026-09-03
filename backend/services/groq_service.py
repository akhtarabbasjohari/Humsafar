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

Your primary role is to help travelers discover, explore, and plan mountain expeditions and cultural tours across Pakistan (Karakoram, Himalayas, Hindukush, Gilgit-Baltistan, Hunza, Skardu, Swat, Chitral, Fairy Meadows, and beyond).

CRITICAL DATA INTEGRITY & EDITORIAL RULES:
1. Grounding First: Base your itinerary details, daily highlights, duration, and pricing STRICTLY on the official listing provided below. Never fabricate prices or departure dates.
2. Tone: Warm, knowledgeable, authoritative, respectful of local cultures, and encouraging of responsible mountain travel.
3. Pricing & Verification: Always present the official price in Pakistani Rupees (PKR) as found in the listing, citing that it is verified live from our official catalog on itp.7scribes.com. If the official listing states "Pricing upon inquiry", explain that pricing is customized based on group size and dates, and provide realistic market benchmark ranges if requested, clearly labeling them as estimates.
4. Structure: Keep responses engaging and clean. Use concise paragraphs or clear bullet points for highlights.
5. Simple Matching Flow: When presenting a matched tour, summarize the route, state the duration and price clearly, and invite the traveler to ask questions or customize the schedule.
6. NO INTERNAL THOUGHT TAGS: Never output <think> tags, internal reasoning, or thinking process. Output only the final, polished response directly to the traveler.
"""

CONVERSATIONAL_SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion for Indus Trekking and Tours Pakistan (itp.7scribes.com).
Company Tagline: "Plan better. Travel farther."

The traveler sent a greeting, small talk, or a general conversational question.
Provide a warm, hospitable, and concise response. Welcome them to Indus Trekking and Tours, briefly mention the iconic mountain regions and expeditions we specialize in (K2 Base Camp, Concordia, Hunza Valley, Skardu, Fairy Meadows, Swat), and invite them to share what trip or valley they would like to explore.
Do NOT generate or invent a full itinerary card. Keep it welcoming, authentic, and focused on assisting them.
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
            "to K2 Base Camp and Concordia, exploring the golden apricot orchards of Hunza, or planning a private journey "
            "through Skardu and Swat, I am here to help.\n\n"
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
        "Tell me which region or peak you would like to explore—such as K2 Base Camp, Hunza, Skardu, or Swat—"
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
        context_blocks.append(
            f"--- Official Listing #{i} ---\n"
            f"Title: {it.get('title')}\n"
            f"Duration: {it.get('duration')}\n"
            f"Price: {it.get('price')}\n"
            f"Source URL: {it.get('source_url')}\n"
            f"Confidence: {it.get('confidence_label', 'from our official listing')}\n"
            f"Scraped At: {it.get('scraped_at')}\n"
            f"Summary/Highlights: {it.get('summary')}\n"
        )
    catalog_context = "\n".join(context_blocks) if context_blocks else "No direct package matches found on the website."
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
                    "max_tokens": 1500,
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
            "Our team can customize a dedicated itinerary for you."
        )

    tour = matched_itineraries[0]
    return (
        f"Salam! Here is the official verified package from our catalog for your trip:\n\n"
        f"**{tour.get('title')}**\n"
        f"• **Duration**: {tour.get('duration')}\n"
        f"• **Price**: {tour.get('price')}\n"
        f"• **Summary**: {tour.get('summary')}\n\n"
        f"All logistics, mountain transport, and guide services are coordinated by Indus Trekking and Tours Pakistan. "
        "Would you like to review the full day-by-day schedule or customize any of the stops?"
    )
