"""
Groq LLM Service for Humsafar.
Synthesizes high-quality, authentic travel guide responses grounded strictly in live scraped itineraries.
"""

import os
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")


SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion embedded on the Indus Trekking and Tours Pakistan website (itp.7scribes.com).
Company Tagline: "Plan better. Travel farther."

Your primary role is to help travelers discover, explore, and plan mountain expeditions and cultural tours across Pakistan (Karakoram, Himalayas, Hindukush, Gilgit-Baltistan, Hunza, Skardu, Swat, Chitral, Fairy Meadows, and beyond).

CRITICAL DATA INTEGRITY & EDITORIAL RULES:
1. Grounding First: Base your itinerary details, daily highlights, duration, and pricing STRICTLY on the official listing provided below. Never fabricate prices or departure dates.
2. Tone: Warm, knowledgeable, authoritative, respectful of local cultures, and encouraging of responsible mountain travel.
3. Pricing & Verification: Always present the official price in Pakistani Rupees (PKR) as found in the listing, citing that it is verified live from our official catalog on itp.7scribes.com.
4. Structure: Keep responses engaging and clean. Use concise paragraphs or clear bullet points for highlights.
5. Simple Matching Flow: When presenting a matched tour, summarize the route, state the duration and price clearly, and invite the traveler to ask questions or customize the schedule.
"""


def generate_travel_reply(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    matched_itineraries: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate a conversational travel reply via Groq LLM grounded on scraped itineraries.
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

    # Build messages array
    messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCURRENT OFFICIAL LISTINGS GROUND TRUTH:\n{catalog_context}"}
    ]

    # Append recent conversation turns (up to last 6)
    for msg in conversation_history[-6:]:
        role = "user" if msg.get("role") in ["user", "traveler"] else "assistant"
        content = msg.get("content", "")
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
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

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
