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
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


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
        cleaned = "\n".join(content_lines).strip()
    else:
        cleaned = text.strip()

    # Strip any trailing reasoning scratchpad, constraint checklists, or self-corrections
    scratchpad_split_regex = (
        r"\n+(?:[0-9]+\.\s*)?(?:\*{1,2})?\s*(?:Check (?:Against )?Constraints|Constraint Check|Constraints Check|"
        r"Self-Correction|Verification|Thinking Process|Constraint Checklist|Here(?:'s| is) (?:a |the )?thinking process)"
    )
    cleaned = re.split(scratchpad_split_regex, cleaned, flags=re.IGNORECASE)[0]

    return cleaned.strip()


SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion embedded on the Indus Trekking and Tours Pakistan website (itp.7scribes.com).
Company Tagline: "Plan better. Travel farther."

Your primary role is to help travelers discover, explore, and plan mountain expeditions and cultural tours across Pakistan (Karakoram, Himalayas, Hindukush, Gilgit-Baltistan, Hunza, Skardu, Deosai, Swat, Chitral, Fairy Meadows, K2 Base Camp, and beyond).

CORE ARCHITECTURAL RULE: STRUCTURE IS EARNED, NOT DEFAULT.
1. Route Narrative & Commentary:
   - Provide a warm, authoritative, expert expedition commentary (1 to 3 well-written prose paragraphs) introducing the journey.
   - Highlight the route's character, scenic milestones (such as Concordia, Baltoro Glacier, or Trango Towers), terrain, acclimatization pacing, and best seasonal window.
   - MANDATORY CONCRETE PRICING: State the realistic tour investment (both PKR and USD) clearly in your narrative using the official package price or calculated market rate provided in the listing. NEVER say 'Pricing upon inquiry' or 'contact for pricing'. All itineraries feature concrete pricing and itemized cost breakdowns.
2. CRITICAL SEPARATION OF CONCERNS:
   - DO NOT dump a raw markdown schedule table or day-by-day outline into this text reply!
   - The detailed day-by-day stages, itemized prices, inclusions, exclusions, and equipment checklist are delivered directly in the accompanying structured itinerary card payload, which the frontend renders visually as an interactive timeline.
   - Point the traveler to the visual itinerary card below for the complete day-by-day stops and booking options.
3. BULLETED LISTS DISCIPLINE:
   - Use bullet points ONLY for genuinely scannable multi-item lists (>3 items) where order or shared structure matters.
   - Never nest bullets more than one level.
   - For 2 or 3 items, weave them into natural sentences.
4. HEADINGS DISCIPLINE:
   - Reserved exclusively for multi-section content. Never wrap a 1-sentence thought in a heading.
5. TONE & SANITIZATION:
   - Warm, hospitable, respectful of mountain heritage and native Balti/Shina communities.
   - NEVER output internal reasoning tags like <think> or </think>.
   - NEVER output file metadata strings like '• MD' or 'Download Itinerary'.
"""

FACTUAL_SYSTEM_PROMPT = """You are Humsafar, the senior mountain expedition planner for Indus Trekking and Tours Pakistan (itp.7scribes.com).
Tagline: "Plan better. Travel farther."

The traveler is asking a short factual, logistical, or conversational question (such as dates, seasons, weather, permits, elevation, gear advice, or general curiosity).

CORE ARCHITECTURAL RULE: STRUCTURE IS EARNED, NOT DEFAULT.
1. Answer in 1 to 3 sentences of plain, warm, authoritative natural prose.
2. NO HEADINGS (do not use #, ##, or ###). If you wrap a short answer in a heading, it is considered a defect.
3. NO BULLET POINTS. Do not create a bulleted list for 2 or 3 items—weave them into natural flowing sentences.
4. NO UNNECESSARY BOLDING on every other word. Use bold strictly if emphasizing a single critical safety or permit detail.
5. DO NOT dump an unrequested itinerary or timeline card. Answer the specific question directly.
6. NO INTERNAL THOUGHT TAGS: Never output <think> tags or your internal thinking process. Output only the final response.
"""

COMPARISON_SYSTEM_PROMPT = """You are Humsafar, the senior mountain expedition planner for Indus Trekking and Tours Pakistan (itp.7scribes.com).
Tagline: "Plan better. Travel farther."

The traveler is asking for a direct side-by-side comparison between two or more expeditions, tours, or travel destinations.

CORE ARCHITECTURAL RULE: STRUCTURE IS EARNED, NOT DEFAULT.
1. Begin with 1–2 sentences of warm conversational context framing the decision.
2. Use a single, clean markdown comparison table with uniform columns across all compared options:
   | Expedition / Region | Duration | Difficulty / Grade | Max Altitude | Best Season | Key Character / Highlights |
3. Follow the table with a brief 1–2 sentence recommendation clarifying which option best fits different traveler profiles (e.g. first-time trekker vs experienced mountaineer).
4. No unearned headings or nested bullet points.
5. NO INTERNAL THOUGHT TAGS: Never output <think> tags or your internal thinking process. Output only the final response.
"""

CONVERSATIONAL_SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion for Indus Trekking and Tours Pakistan (itp.7scribes.com).
Company Tagline: "Plan better. Travel farther."

The traveler sent a greeting, small talk, or a general conversational question.
Provide a warm, hospitable, and concise response. Welcome them to Indus Trekking and Tours, briefly mention the iconic mountain regions and expeditions we specialize in (K2 Base Camp, Concordia, Hunza Valley, Skardu, Deosai, Fairy Meadows, Swat), and invite them to share what trip or valley they would like to explore.
Do NOT generate or invent an unrequested itinerary. Keep it welcoming, authentic, and focused on assisting them.
NO INTERNAL THOUGHT TAGS: Never output <think> tags or your internal thinking process. Output only the final response.
"""


def post_groq_with_retry(
    client: httpx.Client,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    max_retries: int = 3,
) -> httpx.Response:
    """Post chat completion to Groq API with exponential backoff on 429 rate limit."""
    import time
    resp = None
    for attempt in range(max_retries):
        resp = client.post(GROQ_API_URL, headers=headers, json=payload)
        if resp.status_code == 429 and attempt < max_retries - 1:
            time.sleep(1.5 * (attempt + 1))
            continue
        resp.raise_for_status()
        break
    return resp


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
            resp = post_groq_with_retry(
                client,
                payload={"model": active_model, "messages": messages, "temperature": 0.5, "max_tokens": 1024},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
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


def generate_factual_reply(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    context_notes: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate a plain, warm conversational reply for factual and logistical inquiries
    without headings or bullet points.
    """
    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    active_model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    sys_content = FACTUAL_SYSTEM_PROMPT
    if context_notes:
        sys_content += f"\n\nFACTUAL CONTEXT:\n{context_notes}"

    if not key:
        return _build_factual_fallback(user_message)

    messages = [{"role": "system", "content": sys_content}]
    for msg in conversation_history[-4:]:
        role = "user" if msg.get("role") in ["user", "traveler"] else "assistant"
        content = strip_think_tags(msg.get("content", ""))
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=25.0) as client:
            resp = post_groq_with_retry(
                client,
                payload={"model": active_model, "messages": messages, "temperature": 0.3, "max_tokens": 512},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            cleaned = strip_think_tags(raw_text)
            if cleaned:
                return cleaned
    except Exception as exc:
        logger.error("Groq factual reply error: %s", exc)

    return _build_factual_fallback(user_message)


def generate_comparison_reply(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    comparison_context: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate a direct side-by-side comparison reply using a clean markdown comparison table.
    """
    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    active_model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    sys_content = COMPARISON_SYSTEM_PROMPT
    if comparison_context:
        sys_content += f"\n\nCOMPARISON CONTEXT DATA:\n{comparison_context}"

    if not key:
        return _build_comparison_fallback(user_message)

    messages = [{"role": "system", "content": sys_content}]
    for msg in conversation_history[-4:]:
        role = "user" if msg.get("role") in ["user", "traveler"] else "assistant"
        content = strip_think_tags(msg.get("content", ""))
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = post_groq_with_retry(
                client,
                payload={"model": active_model, "messages": messages, "temperature": 0.3, "max_tokens": 1200},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            cleaned = strip_think_tags(raw_text)
            if cleaned:
                return cleaned
    except Exception as exc:
        logger.error("Groq comparison reply error: %s", exc)

    return _build_comparison_fallback(user_message)


def _build_factual_fallback(user_message: str) -> str:
    """Plain conversational prose fallback for factual queries."""
    msg = user_message.lower()
    if any(k in msg for k in ["date", "when", "season", "window", "month", "time"]):
        if any(k in msg for k in ["k2", "concordia", "baltoro", "karakoram"]):
            return "The optimal trekking window for K2 Base Camp and Concordia runs from mid-June through late August, when the Baltoro Glacier is most accessible and mountain passes are clear of heavy winter snow."
        if any(k in msg for k in ["deosai"]):
            return "The Deosai Plains are accessible from late June through September, with July and August offering the peak wildflower bloom across the alpine plateau."
        if any(k in msg for k in ["hunza", "skardu"]):
            return "The best season to visit Hunza and Skardu spans from April to October, with spring blossoms in April and comfortable trekking weather throughout summer and autumn."
        return "The primary trekking season across northern Pakistan runs from June through September, when high mountain roads and trails are free of snow."

    if any(k in msg for k in ["permit", "visa", "document"]):
        return "Trekking in restricted zones such as the Baltoro Glacier and K2 Base Camp requires a government permit issued through a licensed operator, which typically takes 6 to 8 weeks to process."

    if any(k in msg for k in ["high", "altitude", "elevation"]):
        if "k2" in msg:
            return "K2 Base Camp sits at approximately 5,150 meters (16,896 feet), while Concordia is at 4,650 meters, requiring deliberate gradual acclimatization along the Baltoro route."
        if "deosai" in msg:
            return "The Deosai Plains average an elevation of 4,114 meters (13,497 feet), making it one of the highest alpine plateaus in the world."

    return "Our mountain operations team at Indus Trekking and Tours Pakistan coordinates all regional permits, guide assignments, and seasonal logistics across northern Pakistan."


def _build_comparison_fallback(user_message: str) -> str:
    """Side-by-side comparison fallback table with responsive attributes."""
    return (
        "Both routes represent world-class Karakoram expeditions, but they cater to different endurance levels and mountaineering aspirations.\n\n"
        "| Expedition | Duration | Difficulty | Max Altitude | Best Season | Key Highlight |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| **K2 Base Camp & Concordia** | 14–18 Days | Strenuous Trekking | 5,150m (Base Camp) | Mid-June to Late August | Panoramic amphitheater of four 8,000m peaks at Concordia |\n"
        "| **Gondogoro La Circuit** | 18–22 Days | Technical High Pass | 5,650m (Gondogoro Pass) | July to Mid-August | Dramatic crossing with fixed ropes and view of K2, Broad Peak, and Gasherbrums |\n\n"
        "If you are seeking a classic non-technical glacier trek, K2 Base Camp via Baltoro is the proven choice; if you have crampon experience and want a demanding technical pass crossing, the Gondogoro La circuit offers an unparalleled traverse."
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
            resp = post_groq_with_retry(
                client,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                payload={
                    "model": active_model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            cleaned = strip_think_tags(raw_text)
            if cleaned:
                return cleaned

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
    title = tour.get("title", "Expedition Package")
    summary = tour.get(
        "summary",
        "Experience northern Pakistan's premier alpine wilderness, high-altitude plateaus, and mountain hospitality with native mountain leaders.",
    )
    duration = tour.get("duration", "7–14 Days")
    price = tour.get("price")
    price_clause = f" Estimated investment is **{price}** with an itemized cost breakdown." if price else ""

    return (
        f"Salam and welcome to Indus Trekking and Tours Pakistan!\n\n"
        f"I have retrieved our official expedition listing for **{title}** ({duration}). {summary}{price_clause}\n\n"
        "Please review the complete day-by-day route, pricing details, included services, and mountain gear checklist in the interactive itinerary card below. "
        "Our operations team is available to customize the daily pace or adjust logistics to your party's preferences."
    )


