"""
Groq LLM Service for Humsafar.
Synthesizes high-quality, authentic travel guide responses grounded strictly in live scraped itineraries.
"""

import os
import re
import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple
import httpx
from services.travel_constants import OPERATIONAL_REGIONS, CONTACT_DETAILS
from services.ollama_service import ollama_service

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


class GroqRateLimitExceeded(Exception):
    """Raised when Groq API TPM rate limit is reached and cannot be resolved quickly."""
    pass


def compact_conversation_history(
    history: List[Dict[str, str]],
    max_turns: int = 8,
    max_assistant_chars: int = 350,
) -> List[Dict[str, str]]:
    """
    Compact conversation history to prevent massive token bloat that triggers Groq's
    strict 8,000 TPM limit. Preserves recent user requests while summarizing older
    verbose assistant itinerary outputs.
    """
    if not history:
        return []

    recent = history[-max_turns:]
    compacted = []
    for msg in recent:
        role = "user" if msg.get("role") in ["user", "traveler"] else "assistant"
        raw_text = strip_think_tags(msg.get("content", "")).strip()
        if not raw_text:
            continue

        if role == "assistant" and len(raw_text) > max_assistant_chars:
            # Strip markdown day tables, long gear lists, and keep core summary
            clean = re.sub(r"(?:\n|^)\s*\|[^\n]*\|[^\n]*\n(?:\|[^\n]*\|[^\n]*\n)+", "\n", raw_text)
            clean = re.sub(r"(?i)#{1,4}\s*(?:Included Services|Exclusions|Essential Gear Checklist)[\s\S]*", "", clean)
            paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
            shortened = paragraphs[0] if paragraphs else clean[:max_assistant_chars]
            if len(shortened) > max_assistant_chars:
                shortened = shortened[:max_assistant_chars].rstrip() + "..."
            compacted.append({"role": role, "content": shortened})
        else:
            compacted.append({"role": role, "content": raw_text})

    return compacted


class GroqRateLimiter:
    """
    Sliding-window Token Rate Limiter for Groq API.
    Enforces a safe token budget against Groq's TPM limit (default 6,000 TPM for openai/gpt-oss-120b).
    """
    def __init__(self, tpm_limit: Optional[int] = None, window_seconds: float = 60.0):
        env_limit = os.getenv("GROQ_TPM_LIMIT")
        self.tpm_limit = tpm_limit if tpm_limit is not None else (int(env_limit) if env_limit else 6000)
        self.window_seconds = window_seconds
        self.history: List[Tuple[float, int]] = []
        self.cooldown_until: float = 0.0
        self._lock = threading.Lock()

    def set_cooldown(self, seconds: float):
        """Set a dynamic cooldown window if Groq API reports rate limit backoff."""
        with self._lock:
            self.cooldown_until = max(self.cooldown_until, time.time() + seconds)

    def estimate_tokens(self, payload: Dict[str, Any]) -> int:
        """Estimate token consumption from messages and max_tokens."""
        total_chars = 0
        for m in payload.get("messages", []):
            total_chars += len(m.get("content", ""))
        for t in payload.get("tools", []):
            total_chars += len(json.dumps(t))
        prompt_tokens = total_chars // 3.5
        max_tokens = payload.get("max_tokens", 400)
        expected_output = min(max_tokens, 600)
        return int(prompt_tokens + expected_output)

    def acquire(self, estimated_tokens: int, max_wait: float = 8.0) -> bool:
        """
        Check if request fits within current 60s window. If waiting a short time
        frees enough tokens, sleep and proceed. Otherwise return False to signal fallback.
        """
        if os.getenv("GROQ_BYPASS_RATE_LIMIT", "").lower() in ("true", "1"):
            return True

        with self._lock:
            now = time.time()
            if now < self.cooldown_until:
                logger.info("Groq in active cooldown (%.1fs remaining). Signaling fallback.", self.cooldown_until - now)
                return False

            # Prune events older than window
            self.history = [(t, tok) for t, tok in self.history if now - t < self.window_seconds]
            current_tokens = sum(tok for _, tok in self.history)

            if current_tokens + estimated_tokens <= self.tpm_limit:
                self.history.append((now, estimated_tokens))
                return True

            # Calculate required wait time
            needed = (current_tokens + estimated_tokens) - self.tpm_limit
            accumulated = 0
            wait_time = 0.0
            for t, tok in self.history:
                accumulated += tok
                if accumulated >= needed:
                    wait_time = max(0.0, (t + self.window_seconds) - now)
                    break

            if 0 < wait_time <= max_wait:
                logger.info("Groq TPM budget near limit (%d/%d). Pausing %.2fs...", current_tokens, self.tpm_limit, wait_time)
                time.sleep(wait_time + 0.2)
                now = time.time()
                self.history = [(t, tok) for t, tok in self.history if now - t < self.window_seconds]
                self.history.append((now, estimated_tokens))
                return True

            logger.warning("Groq TPM budget exceeded (%d/%d tokens in last 60s, requested %d). Signaling fallback.", current_tokens, self.tpm_limit, estimated_tokens)
            return False

    def record_actual(self, actual_tokens: int):
        """Update last history record with actual tokens reported by Groq."""
        with self._lock:
            if self.history:
                last_t, _ = self.history[-1]
                self.history[-1] = (last_t, actual_tokens)


groq_rate_limiter = GroqRateLimiter()


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


SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion embedded on the Askoli Adventure website (askoliadventure.com).
Company Tagline: "Plan better. Travel farther."

Your primary role is to help travelers discover, explore, and plan mountain expeditions and cultural tours across Pakistan (Karakoram, Himalayas, Hindukush, Gilgit-Baltistan, Hunza, Skardu, Deosai, Swat, Chitral, Fairy Meadows, K2 Base Camp, and beyond).

CORE ARCHITECTURAL RULE: STRUCTURE IS EARNED, NOT DEFAULT.
1. MANDATORY SECTION ORDER:
   - Section 1: Route Overview & Narrative (1 to 2 crisp paragraphs introducing the journey, key highlights, acclimatization pacing, best seasonal window, and mandatory pricing in both PKR and USD). State the realistic tour investment clearly. NEVER say 'Pricing upon inquiry' or 'contact for pricing'. All itineraries feature concrete pricing and itemized cost breakdowns.
   - Section 2: `### Day-by-Day Route Itinerary` (IMMEDIATELY following overview: bold day headers and bullet points like `- **Day 1**: ...`, 1–2 crisp sentences per day). Do NOT use rigid markdown tables with `| Day | Route |`.
   - Section 3: `### Included Services & Essential Gear` (at the end: 3–4 bullet points of included services and key gear highlights).
   - Section 4: Conclude with a clean 1-sentence closing remark.
2. CLEAN TEXT FORMATTING (LIKE CHATGPT):
   - Present the complete expedition plan directly in clean, well-structured markdown prose.
   - DO NOT reference an 'interactive itinerary card below' or 'card below'.
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
6. STRICT CONCISENESS & LENGTH BUDGET (CRITICAL TO PREVENT CUTOFFS):
   - Total response length must be strictly between 300 and 450 words.
   - Day-by-day itinerary: Write at most 1–2 crisp, informative sentences per day (highlighting the day's route, camp elevation, and main highlight). Never generate lengthy multi-paragraph descriptions per day.
   - Bulleted sections (Services, Gear): Keep to 3–4 bullet points maximum.
   - Always conclude with a neat 1-sentence closing remark so the response finishes cleanly without stopping in the middle.
"""

FACTUAL_SYSTEM_PROMPT = """You are Humsafar, the senior mountain expedition planner for Askoli Adventure (askoliadventure.com).
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

COMPARISON_SYSTEM_PROMPT = """You are Humsafar, the senior mountain expedition planner for Askoli Adventure (askoliadventure.com).
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

CONVERSATIONAL_SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion for Askoli Adventure (askoliadventure.com).
Company Tagline: "Plan better. Travel farther."

The traveler sent a greeting, small talk, or a general conversational question.
Provide a warm, hospitable, and concise response. Welcome them to Askoli Adventure, briefly mention the iconic mountain regions and expeditions we specialize in, and invite them to share what trip or valley they would like to explore.
Do NOT generate or invent an unrequested itinerary. Keep it welcoming, authentic, and focused on assisting them.
NO INTERNAL THOUGHT TAGS: Never output <think> tags or your internal thinking process. Output only the final response.
"""

PRICING_SYSTEM_PROMPT = """You are Humsafar, the senior mountain expedition planner and budgeting expert for Askoli Adventure (askoliadventure.com).
Company Tagline: "Plan better. Travel farther."

The traveler is asking about trip costs, pricing estimates, budget breakdowns, or asking for the estimated cost of their own proposed trip plan.

CORE ARCHITECTURAL RULES:
1. FOCUS STRICTLY ON PRICING & LOGISTICS:
   - Provide an authoritative, transparent, and realistic cost breakdown in BOTH Pakistani Rupees (PKR) and US Dollars (USD).
   - If the traveler shared their own plan/itinerary (e.g. "I have a 4-day plan for Swat: Mingora, Kalam, Mahodand... how much will it cost?"), directly evaluate the realistic cost for their exact proposed plan and duration.
   - Include realistic itemized estimates:
     * Private 4x4 Transport (e.g. Prado / Land Cruiser / Hiace Cabin with dedicated mountain driver and fuel)
     * Hotel / Guesthouse Accommodation (typical rates per night for standard 3-star vs deluxe/boutique tiers)
     * Licensed Local Mountain Guide & Driver allowances
     * Entry Tickets, National Park fees (e.g. Deosai), and Bridge Tolls
     * Daily Meal Allowance
2. DO NOT GENERATE AN UNREQUESTED ITINERARY:
   - DO NOT dump a day-by-day route schedule (e.g. Day 1, Day 2, Day 3...). The traveler only asked about pricing, NOT for an itinerary plan!
   - DO NOT reference an 'interactive itinerary card below' or attach an itinerary.
3. CLEAR FORMATTING & COST FACTORS:
   - State total estimated cost and per-person estimate clearly.
   - Mention key factors that can adjust the budget (party size, travel season, choice of vehicle and hotel tier).
   - Conclude warmly by asking if this fits their budget, and offer to prepare a full, customized day-by-day itinerary whenever they are ready.
4. NO INTERNAL THOUGHT TAGS: Never output <think> tags or your internal thinking process. Output only the final response.
"""

GENERAL_KNOWLEDGE_SYSTEM_PROMPT = """You are Humsafar, the official AI travel planning companion and mountain guide for Askoli Adventure (askoliadventure.com).
Company Tagline: "Plan better. Travel farther."

The traveler is asking general questions, travel advice, recommendations, cultural context, road conditions, weather, safety, permits, or tourist highlights about northern Pakistan.

CORE ARCHITECTURAL RULES:
1. ANSWER THE INQUIRY DIRECTLY & COMPREHENSIVELY:
   - Provide authentic, expert mountain insight and local knowledge in warm, hospitable prose.
   - If asking about attractions/sightseeing: Highlight the iconic must-see places, scenic viewpoints, and cultural spots.
   - If asking about roads/logistics: Give realistic travel hours, transit conditions (e.g. Karakoram Highway, Jaglot-Skardu road, Babusar Pass), and seasonal accessibility.
   - If asking about seasons/weather: Explain the best months to visit, temperature expectations, and what to pack.
   - If asking about safety/family/culture: Provide reassuring, honest guidance respectful of local Balti, Shina, and Wakhi customs.
   - If asking about mountain history (e.g. K2, Nanga Parbat, Karakoram exploration): Provide the top 3–4 defining historical milestones concisely in 1–2 paragraphs. DO NOT generate sprawling tables or endless chronologies.
2. STRUCTURE IS EARNED, NOT DEFAULT:
   - Keep your entire answer concise and focused (strictly between 200 and 350 words).
   - Use natural bullet points only when listing distinct attractions or tips (>3 items). Never generate multi-column markdown tables unless explicitly asked for a side-by-side comparison.
   - Never refuse or state that you cannot provide an itinerary or travel advice.
   - DO NOT reference an 'itinerary card below'.
3. WARM CLOSING:
   - Conclude warmly with a 1-sentence wrap-up, inviting them to ask more or offer to prepare a full, customized itinerary whenever they are ready.
4. NO INTERNAL THOUGHT TAGS: Never output <think> tags or your internal thinking process. Output only the final response.
"""



def post_groq_with_retry(
    client: httpx.Client,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    max_retries: int = 3,
) -> httpx.Response:
    """
    Post chat completion to Groq API with client-side rate limiting and smart backoff.
    Parses Retry-After headers and rate limit error bodies, preventing 429 thrashing.
    """
    # Auto-inject reasoning parameters for reasoning models (e.g. gpt-oss)
    # to avoid burning output tokens on internal thinking.
    model_str = str(payload.get("model", "")).lower()
    if "gpt-oss" in model_str:
        if "reasoning_format" not in payload:
            payload["reasoning_format"] = "hidden"
        if "reasoning_effort" not in payload:
            payload["reasoning_effort"] = "low"

    est_tokens = groq_rate_limiter.estimate_tokens(payload)
    if not groq_rate_limiter.acquire(est_tokens):
        raise GroqRateLimitExceeded(f"Client-side TPM rate limit safety budget reached (requested ~{est_tokens} tokens).")

    resp = None
    for attempt in range(max_retries):
        resp = client.post(GROQ_API_URL, headers=headers, json=payload)
        if resp.status_code == 429:
            wait_seconds = 0.0
            retry_after_hdr = resp.headers.get("retry-after")
            if retry_after_hdr:
                try:
                    wait_seconds = float(retry_after_hdr)
                except ValueError:
                    pass

            if wait_seconds == 0.0:
                try:
                    err_text = resp.text
                    match = re.search(r"Please try again in\s+(\d+(?:\.\d+)?)(?:s|ms)?", err_text, re.IGNORECASE)
                    if match:
                        num = float(match.group(1))
                        wait_seconds = num / 1000.0 if "ms" in match.group(0).lower() else num
                except Exception:
                    pass

            if 0 < wait_seconds <= 10.0 and attempt < max_retries - 1:
                logger.warning("Groq 429 rate limit hit. Backing off %.2fs as requested by API...", wait_seconds + 0.5)
                time.sleep(wait_seconds + 0.5)
                continue
            elif wait_seconds > 10.0:
                logger.warning("Groq 429 requires %.2fs wait. Signaling immediate secondary LLM fallback.", wait_seconds)
                groq_rate_limiter.set_cooldown(min(wait_seconds, 60.0))
                raise GroqRateLimitExceeded(f"Rate limit exceeded. Wait time: {wait_seconds:.1f}s")
            elif attempt < max_retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue

        resp.raise_for_status()
        try:
            usage = resp.json().get("usage", {})
            if usage.get("total_tokens"):
                groq_rate_limiter.record_actual(usage["total_tokens"])
        except Exception:
            pass
        break

    return resp


def repair_incomplete_markdown(text: str) -> str:
    """
    Repairs text that was cut off at token limits, including:
    1. Unclosed markdown tables (incomplete row missing closing pipes or cells).
    2. Unbalanced bold/italic markers (** or *).
    3. Trailing dangling punctuation or incomplete rows.
    4. Trims incomplete trailing sentences cleanly so responses never end mid-sentence.
    """
    if not text:
        return ""

    lines = text.split("\n")
    if lines:
        last_line = lines[-1].strip()
        # Drop empty heading line at the end (e.g. "### ")
        if re.match(r"^#{1,6}\s*$", last_line):
            lines.pop()
        elif last_line.startswith("|") and not last_line.endswith("|"):
            pipes = last_line.count("|")
            if pipes >= 2:
                lines[-1] = last_line + " |"
            else:
                lines.pop()

    repaired = "\n".join(lines).rstrip()

    # Repair unclosed bold **
    bold_count = repaired.count("**")
    if bold_count % 2 != 0:
        if re.search(r"\*\*[A-Za-z0-9\s\-]+$", repaired):
            repaired += "**"
        else:
            repaired = re.sub(r"\*\*[^\*]*$", "", repaired).rstrip()

    # Repair unclosed italic * (ignoring **)
    clean_no_bold = re.sub(r"\*\*", "", repaired)
    if clean_no_bold.count("*") % 2 != 0:
        repaired = re.sub(r"\*[^\*]*$", "", repaired).rstrip()

    # Repair unclosed parentheses if cut off
    open_paren = repaired.count("(")
    close_paren = repaired.count(")")
    if open_paren > close_paren:
        repaired += ")" * (open_paren - close_paren)

    # Strip dangling trailing conjunctions/prepositions at the end of the text (e.g. "and", "the", "with")
    repaired = re.sub(
        r"\s+\b(?:and|or|the|where|to|with|in|on|at|for|of|by|a|an|is|are|will|from|as|that|which|into)\s*$",
        "",
        repaired,
        flags=re.IGNORECASE,
    ).rstrip()

    # Strip dangling trailing commas, semicolons, hyphens
    repaired = re.sub(r"[,;\-\s]+$", "", repaired).rstrip()

    # If the text ends without punctuation and is not a heading, table, or bold closure, complete the sentence cleanly
    if repaired:
        last_clean_line = [ln.strip() for ln in repaired.split("\n") if ln.strip()][-1] if repaired.split("\n") else ""
        if (
            not last_clean_line.startswith("#")
            and not last_clean_line.startswith("|")
            and repaired[-1] not in ('.', '!', '?', '|', '*', ':', '`', "'", '"', '”', ')', ']', '>')
        ):
            repaired += "."

    return repaired.strip()


def execute_groq_with_continuation(
    client: httpx.Client,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    max_retries: int = 3,
    max_continuations: int = 1,
) -> str:
    """
    Execute chat completion with retry and seamless continuation if finish_reason == 'length'.
    Returns cleaned, complete text without think tags and with repaired markdown.
    """
    resp = post_groq_with_retry(client, payload=payload, headers=headers, max_retries=max_retries)
    data = resp.json()
    choice = data["choices"][0]
    raw_content = choice.get("message", {}).get("content", "")

    if choice.get("finish_reason") == "length" and max_continuations > 0 and raw_content:
        logger.info("Groq response reached token limit. Requesting seamless continuation...")
        try:
            user_msg = ""
            for m in reversed(payload.get("messages", [])):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")
                    break
            cont_messages = [
                {"role": "system", "content": "You are an expert mountain expedition assistant. Continue directly and seamlessly from the exact cutoff without repeating anything."},
                {"role": "user", "content": user_msg or "Continue"},
                {"role": "assistant", "content": raw_content[-1200:]},
                {"role": "user", "content": "Please continue seamlessly from where you stopped. Do not repeat anything already written."},
            ]
            cont_payload = {
                "model": payload.get("model", DEFAULT_MODEL),
                "messages": cont_messages,
                "temperature": payload.get("temperature", 0.2),
                "max_tokens": min(payload.get("max_tokens", 1500), 800),
                "reasoning_format": "hidden",
                "reasoning_effort": "low",
            }
            cont_resp = post_groq_with_retry(client, payload=cont_payload, headers=headers, max_retries=max_retries)
            cont_choice = cont_resp.json()["choices"][0]
            cont_text = cont_choice.get("message", {}).get("content", "")
            if cont_text:
                clean_cont = re.sub(r"^(?:Continuing(?:\s+from\s+above)?|Here\s+is\s+the\s+continuation)[\s:-]*", "", cont_text.strip(), flags=re.IGNORECASE)
                raw_content = raw_content.rstrip() + " " + clean_cont.lstrip()
        except Exception as cont_exc:
            logger.warning("Groq continuation call failed (%s). Returning available content.", cont_exc)

    cleaned = strip_think_tags(raw_content)
    return repair_incomplete_markdown(cleaned)


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
            f"Salam and welcome to {CONTACT_DETAILS['company']}!\n\n"
            "I am Humsafar, your mountain expedition and tour companion. We specialize in "
            f"the mountain wilderness of northern Pakistan ({OPERATIONAL_REGIONS}). "
            "I am here to help you plan your perfect expedition.\n\n"
            "Where in northern Pakistan would you like to travel, or what kind of experience are you looking for?"
        )

    sys_content = CONVERSATIONAL_SYSTEM_PROMPT
    try:
        from services.conversation_memory import conversation_memory
        acc_prefs = conversation_memory.extract_conversation_preferences(conversation_history, current_user_message=user_message)
        mem_prompt = conversation_memory.build_memory_context_prompt(acc_prefs)
        if mem_prompt:
            sys_content = f"{CONVERSATIONAL_SYSTEM_PROMPT}\n\n{mem_prompt}"
    except Exception:
        pass

    compacted = compact_conversation_history(conversation_history, max_turns=8)
    messages = [{"role": "system", "content": sys_content}]
    messages.extend(compacted)
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=30.0) as client:
            result = execute_groq_with_continuation(
                client,
                payload={"model": active_model, "messages": messages, "temperature": 0.5, "max_tokens": 600},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            if result:
                return result
    except Exception as exc:
        logger.warning("Groq conversational reply failed (%s). Attempting secondary Ollama LLM.", exc)
        if ollama_service.is_available():
            ollama_reply = ollama_service.generate_completion(
                prompt=user_message,
                system_prompt=CONVERSATIONAL_SYSTEM_PROMPT,
                max_tokens=300,
                session_id="conversational_reply",
            )
            if ollama_reply:
                return strip_think_tags(ollama_reply)

    return (
        f"Salam and welcome to {CONTACT_DETAILS['company']}!\n\n"
        "I am Humsafar, your official mountain expedition planner. "
        "Tell me which region or peak you would like to explore "
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
        sys_content += f"\n\nFACTUAL CONTEXT:\n{context_notes[:600]}"

    try:
        from services.conversation_memory import conversation_memory
        acc_prefs = conversation_memory.extract_conversation_preferences(conversation_history, current_user_message=user_message)
        mem_prompt = conversation_memory.build_memory_context_prompt(acc_prefs)
        if mem_prompt:
            sys_content += f"\n\n{mem_prompt}"
    except Exception:
        pass

    if not key:
        return _build_factual_fallback(user_message)

    compacted = compact_conversation_history(conversation_history, max_turns=8)
    messages = [{"role": "system", "content": sys_content}]
    messages.extend(compacted)
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=30.0) as client:
            cleaned = execute_groq_with_continuation(
                client,
                payload={"model": active_model, "messages": messages, "temperature": 0.3, "max_tokens": 800},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            if cleaned:
                return cleaned
    except Exception as exc:
        logger.warning("Groq factual reply failed (%s). Attempting secondary Ollama LLM.", exc)
        if ollama_service.is_available():
            ollama_reply = ollama_service.generate_completion(
                prompt=user_message,
                system_prompt=sys_content,
                max_tokens=250,
                session_id="factual_reply",
            )
            if ollama_reply:
                return strip_think_tags(ollama_reply)

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
        sys_content += f"\n\nCOMPARISON CONTEXT DATA:\n{comparison_context[:1000]}"

    try:
        from services.conversation_memory import conversation_memory
        acc_prefs = conversation_memory.extract_conversation_preferences(conversation_history, current_user_message=user_message)
        mem_prompt = conversation_memory.build_memory_context_prompt(acc_prefs)
        if mem_prompt:
            sys_content += f"\n\n{mem_prompt}"
    except Exception:
        pass

    if not key:
        return _build_comparison_fallback(user_message)

    compacted = compact_conversation_history(conversation_history, max_turns=8)
    messages = [{"role": "system", "content": sys_content}]
    messages.extend(compacted)
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=30.0) as client:
            cleaned = execute_groq_with_continuation(
                client,
                payload={"model": active_model, "messages": messages, "temperature": 0.3, "max_tokens": 1200},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            if cleaned:
                return cleaned
    except Exception as exc:
        logger.warning("Groq comparison reply failed (%s). Attempting secondary Ollama LLM.", exc)
        if ollama_service.is_available():
            ollama_reply = ollama_service.generate_completion(
                prompt=user_message,
                system_prompt=sys_content,
                max_tokens=350,
                session_id="comparison_reply",
            )
            if ollama_reply:
                return strip_think_tags(ollama_reply)

    return _build_comparison_fallback(user_message)


def _build_factual_fallback(user_message: str) -> str:
    """Plain conversational prose fallback for factual queries when no API key is available."""
    msg = user_message.lower()
    if any(k in msg for k in ["date", "when", "season", "window", "month", "time"]):
        if any(k in msg for k in ["k2", "concordia", "baltoro", "karakoram"]):
            return "The optimal trekking window for K2 Base Camp and Concordia runs from mid-June through late August, when the Baltoro Glacier is most accessible and mountain passes are clear of heavy winter snow."
        return "The primary trekking season across northern Pakistan runs from June through September, when high mountain roads and trails are free of snow."

    if any(k in msg for k in ["permit", "visa", "document"]):
        return "Trekking in restricted zones requires a government permit issued through a licensed operator, which typically takes 6 to 8 weeks to process."

    if any(k in msg for k in ["high", "altitude", "elevation"]):
        if "k2" in msg:
            return "K2 Base Camp sits at approximately 5,150 meters (16,896 feet), while Concordia is at 4,650 meters, requiring deliberate gradual acclimatization along the Baltoro route."

    return f"Our mountain operations team at {CONTACT_DETAILS['company']} coordinates all regional permits, guide assignments, and seasonal logistics across northern Pakistan."


def _build_comparison_fallback(user_message: str) -> str:
    """Side-by-side comparison fallback table."""
    return (
        "Both options represent premier expedition experiences in northern Pakistan. "
        "Here is a high-level comparison based on our operational knowledge:\n\n"
        "| Attribute | Option A | Option B |\n"
        "| :--- | :--- | :--- |\n"
        "| Duration | Varies | Varies |\n"
        "| Difficulty | Moderate to Strenuous | Moderate to Strenuous |\n"
        "| Best Season | June – September | June – September |\n\n"
        f"For a detailed comparison with exact durations, altitudes, and pricing, "
        f"please contact our expedition desk at {CONTACT_DETAILS['email']}."
    )


def _build_pricing_fallback(user_message: str, pricing_data: Dict[str, Any]) -> str:
    price_str = pricing_data.get("price", "PKR 145,000 / $520 USD")
    breakdown = pricing_data.get("pricing_breakdown", {})
    items = breakdown.get("items", [])
    item_lines = []
    for it in items:
        cat = it.get("category", "Service")
        cost = it.get("cost", "")
        usd = it.get("usd", "")
        item_lines.append(f"- **{cat}**: {cost} ({usd})")
    items_text = "\n".join(item_lines) if item_lines else "- **4x4 Private Transport & Fuel**: PKR 75,000 ($270)\n- **Standard Hotel Accommodation**: PKR 45,000 ($160)\n- **Licensed Mountain Guide**: PKR 25,000 ($90)"

    return (
        f"Salam! Here is an estimated cost breakdown based on current operational rates in northern Pakistan:\n\n"
        f"### Estimated Trip Investment\n"
        f"**Estimated Total:** {price_str}\n\n"
        f"#### Itemized Cost Estimates:\n"
        f"{items_text}\n\n"
        f"*Note:* Final pricing varies based on party size, travel season (peak summer vs autumn/spring), choice of vehicle (Prado vs Hiace vs Jeep), and hotel tiers (standard vs boutique luxury). "
        f"Whenever you would like to proceed, our team at {CONTACT_DETAILS['company']} can prepare a complete custom itinerary tailored to your exact budget!"
    )


def generate_pricing_reply(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    destination: Optional[str] = None,
    duration_days: Optional[int] = None,
    party_size: int = 2,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate an authoritative, transparent pricing & budget breakdown in PKR and USD.
    Does NOT force or attach a day-by-day itinerary schedule.
    """
    from services.pricing_service import calculate_realistic_tour_pricing

    dest = destination or "Northern Pakistan"
    days = duration_days or 5
    pricing_data = calculate_realistic_tour_pricing(
        title=f"{dest} Journey",
        destination=dest,
        duration_days=days,
        party_size=party_size,
    )

    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    active_model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    if not key:
        return _build_pricing_fallback(user_message, pricing_data)

    breakdown = pricing_data.get("pricing_breakdown", {})
    grounding_info = (
        f"Destination: {dest}\n"
        f"Estimated Duration: {days} Days\n"
        f"Party Size: {party_size} Persons\n"
        f"Total Price Estimate: {pricing_data.get('price')}\n"
        f"Itemized Breakdown: {json.dumps(breakdown.get('items', []))}"
    )

    sys_content = f"{PRICING_SYSTEM_PROMPT}\n\nGROUNDED BASELINE PRICING DATA:\n{grounding_info}"
    try:
        from services.conversation_memory import conversation_memory
        acc_prefs = conversation_memory.extract_conversation_preferences(conversation_history, current_user_message=user_message)
        mem_prompt = conversation_memory.build_memory_context_prompt(acc_prefs)
        if mem_prompt:
            sys_content = f"{sys_content}\n\n{mem_prompt}"
    except Exception:
        pass

    compacted = compact_conversation_history(conversation_history, max_turns=8)
    messages = [{"role": "system", "content": sys_content}]
    messages.extend(compacted)
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=35.0) as client:
            cleaned = execute_groq_with_continuation(
                client,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                payload={"model": active_model, "messages": messages, "temperature": 0.2, "max_tokens": 1800},
            )
            if cleaned:
                return cleaned
    except Exception as exc:
        logger.warning("Groq pricing reply failed (%s). Attempting secondary Ollama LLM.", exc)
        if ollama_service.is_available():
            ollama_reply = ollama_service.generate_completion(
                prompt=user_message,
                system_prompt=sys_content,
                max_tokens=600,
                session_id="pricing_reply",
            )
            if ollama_reply:
                return strip_think_tags(ollama_reply)

    return _build_pricing_fallback(user_message, pricing_data)


def _build_general_knowledge_fallback(user_message: str, destination: Optional[str] = None) -> str:
    dest = destination or "Northern Pakistan"
    return (
        f"Salam! {dest} is one of northern Pakistan's most spectacular travel regions, known for its majestic alpine landscapes, rich heritage, and hospitable communities.\n\n"
        f"The best season to explore is typically from May to October, when high mountain passes are open and weather is favorable. "
        f"Road access is via the Karakoram Highway, and regional flights operate between Islamabad, Gilgit, and Skardu (weather permitting).\n\n"
        f"Feel free to ask any specific questions regarding local attractions, culture, weather, or road conditions. "
        f"Whenever you're ready to plan a trip, our team at {CONTACT_DETAILS['company']} would be delighted to design a personalized itinerary for you!"
    )


def generate_general_knowledge_reply(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    destination: Optional[str] = None,
    additional_research: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate an informative, expert mountain guide response for general knowledge,
    sightseeing recommendations, weather/season advice, road access, and culture.
    Does NOT force or attach a day-by-day itinerary schedule.
    """
    key = api_key or os.getenv("GROQ_API_KEY", "").strip()
    active_model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    if not key:
        return _build_general_knowledge_fallback(user_message, destination)

    sys_content = GENERAL_KNOWLEDGE_SYSTEM_PROMPT
    if destination:
        sys_content += f"\n\nTARGET REGION: {destination}"
    if additional_research:
        sys_content += f"\n\nRESEARCH CONTEXT:\n{additional_research[:800]}"

    try:
        from services.conversation_memory import conversation_memory
        acc_prefs = conversation_memory.extract_conversation_preferences(conversation_history, current_user_message=user_message)
        mem_prompt = conversation_memory.build_memory_context_prompt(acc_prefs)
        if mem_prompt:
            sys_content = f"{sys_content}\n\n{mem_prompt}"
    except Exception:
        pass

    compacted = compact_conversation_history(conversation_history, max_turns=8)
    messages = [{"role": "system", "content": sys_content}]
    messages.extend(compacted)
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=35.0) as client:
            cleaned = execute_groq_with_continuation(
                client,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                payload={"model": active_model, "messages": messages, "temperature": 0.25, "max_tokens": 1800},
            )
            if cleaned:
                return cleaned
    except Exception as exc:
        logger.warning("Groq general knowledge reply failed (%s). Attempting secondary Ollama LLM.", exc)
        if ollama_service.is_available():
            ollama_reply = ollama_service.generate_completion(
                prompt=user_message,
                system_prompt=sys_content,
                max_tokens=450,
                session_id="general_knowledge_reply",
            )
            if ollama_reply:
                return strip_think_tags(ollama_reply)

    return _build_general_knowledge_fallback(user_message, destination)


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

    # Prepare Context from matched itineraries (compacted to top 2 to preserve tokens)
    context_blocks = []
    for i, it in enumerate(matched_itineraries[:2], 1):
        block_lines = [
            f"--- Official Listing #{i} ---",
            f"Title: {it.get('title')}",
            f"Duration: {it.get('duration')}",
            f"Price: {it.get('price')}",
            f"Source URL: {it.get('source_url')}",
            f"Summary: {it.get('summary', '')[:250]}",
        ]
        if it.get("itinerary_schedule"):
            block_lines.append(f"Day-by-Day Schedule: {str(it.get('itinerary_schedule'))[:500]}")
        if it.get("inclusions"):
            block_lines.append(f"Inclusions: {', '.join(it.get('inclusions')[:6])}")
        if it.get("contact_details"):
            cd = it.get("contact_details")
            block_lines.append(f"Contact: {cd.get('company')}, Email: {cd.get('email')}")
        context_blocks.append("\n".join(block_lines))

    catalog_context = "\n\n".join(context_blocks) if context_blocks else "No direct package matches found on the website."
    if additional_research:
        catalog_context += f"\n\nREGIONAL RESEARCH:\n{additional_research[:800]}"

    # Compact recent conversation turns & inject in-context memory
    sys_content = f"{SYSTEM_PROMPT}\n\nCURRENT OFFICIAL LISTINGS GROUND TRUTH:\n{catalog_context}"
    try:
        from services.conversation_memory import conversation_memory
        acc_prefs = conversation_memory.extract_conversation_preferences(conversation_history, current_user_message=user_message)
        mem_prompt = conversation_memory.build_memory_context_prompt(acc_prefs)
        if mem_prompt:
            sys_content = f"{sys_content}\n\n{mem_prompt}"
    except Exception:
        pass

    compacted = compact_conversation_history(conversation_history, max_turns=8)
    messages = [
        {"role": "system", "content": sys_content}
    ]
    messages.extend(compacted)
    messages.append({"role": "user", "content": user_message})

    try:
        with httpx.Client(timeout=35.0) as client:
            cleaned = execute_groq_with_continuation(
                client,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                payload={
                    "model": active_model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1800,
                },
            )
            if cleaned:
                return cleaned

    except Exception as exc:
        logger.warning("Groq travel reply failed (%s). Attempting secondary Ollama LLM.", exc)
        if ollama_service.is_available():
            ollama_reply = ollama_service.generate_completion(
                prompt=f"Traveler Inquiry: {user_message}\n\nAvailable Tours:\n{catalog_context[:600]}",
                system_prompt=SYSTEM_PROMPT,
                max_tokens=600,
                session_id="travel_reply",
            )
            if ollama_reply:
                return strip_think_tags(ollama_reply)

        return _build_fallback_reply(matched_itineraries, user_message)


def _build_fallback_reply(matched_itineraries: List[Dict[str, Any]], query: str) -> str:
    """Deterministic fallback if Groq API is temporarily unreachable."""
    if not matched_itineraries:
        return (
            f"Salam! I checked our live catalog on askoliadventure.com for '{query}'. "
            "While we regularly operate expeditions across northern Pakistan, I could not locate an exact pre-packaged match for this specific route. "
            f"Our operations team at {CONTACT_DETAILS['company']} can customize a dedicated itinerary for you."
        )

    tour = matched_itineraries[0]
    title = tour.get("title", "Expedition Package")
    summary = tour.get(
        "summary",
        "Experience northern Pakistan's premier alpine wilderness with native mountain leaders.",
    )
    duration = tour.get("duration", "7–14 Days")
    price = tour.get("price")
    price_clause = f" Estimated investment is **{price}** with an itemized cost breakdown." if price else ""

    return (
        f"Salam and welcome to {CONTACT_DETAILS['company']}!\n\n"
        f"I have retrieved our official expedition listing for **{title}** ({duration}). {summary}{price_clause}\n\n"
        "Please review the verified itinerary, complete day-by-day route stages, and pricing details. "
        "Our operations team is available to customize the daily pace or adjust logistics to your party's preferences."
    )


