"""
In-Context Conversation Memory Service for Humsafar.
Maintains and extracts persistent traveler preferences within a single conversation
for every visitor (both guest sessions and logged-in users).

Enables the agent to remember earlier stated preferences (destination, duration,
party size, budget, fitness level, logistical requests) without requiring the visitor
to repeat them.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ConversationMemoryService:
    """
    Extracts, accumulates, and formats in-context traveler preferences
    across the entire conversation history within a single session.
    """

    @staticmethod
    def extract_conversation_preferences(
        messages: List[Dict[str, Any]],
        current_user_message: str = "",
    ) -> Dict[str, Any]:
        """
        Scan all conversation turns chronologically to build an accumulated profile
        of visitor preferences. Newer statements update earlier ones for specific
        fields while preserving previously stated fields that were not touched.
        """
        preferences: Dict[str, Any] = {
            "destination": None,
            "duration": None,
            "duration_days": None,
            "party_size": None,
            "budget": None,
            "fitness_level": None,
            "special_requests": [],
            "last_drafted_itinerary": None,
        }

        # Normalize and filter user turns
        user_texts: List[str] = []
        for msg in messages:
            role = msg.get("role") or msg.get("sender")
            if role in ["user", "traveler"]:
                content = msg.get("content", "").strip()
                if content:
                    user_texts.append(content)

        if current_user_message and current_user_message.strip():
            user_texts.append(current_user_message.strip())

        # Inspect messages chronologically
        for text in user_texts:
            t_lower = text.lower()

            # 1. Duration extraction
            dur_match = re.search(r"\b(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:day|days|d)\b", t_lower)
            if dur_match:
                d1 = int(dur_match.group(1))
                preferences["duration_days"] = d1
                if dur_match.group(2):
                    preferences["duration"] = f"{d1}-{dur_match.group(2)} Days"
                else:
                    preferences["duration"] = f"{d1} Days"

            # 2. Party size extraction
            party_match = re.search(r"\b(\d+)\s*(?:people|persons|travelers|pax|members|friends)\b", t_lower)
            if party_match:
                count = int(party_match.group(1))
                preferences["party_size"] = f"{count} Person{'s' if count > 1 else ''}"
            elif re.search(r"\b(?:solo|just me|by myself|alone)\b", t_lower):
                preferences["party_size"] = "1 Person (Solo)"
            elif re.search(r"\b(?:couple|my wife|my husband|two of us)\b", t_lower):
                preferences["party_size"] = "2 Persons (Couple)"
            elif re.search(r"\b(?:family|with kids|with children)\b", t_lower):
                preferences["party_size"] = "Family Group"

            # 3. Budget extraction
            budget_pkr = re.search(r"(?:pkr|rs\.?)\s*([\d,]+)", t_lower)
            budget_usd = re.search(r"\$\s*([\d,]+)|([\d,]+)\s*usd", t_lower)
            if budget_pkr:
                preferences["budget"] = f"PKR {budget_pkr.group(1)}"
            elif budget_usd:
                val = budget_usd.group(1) or budget_usd.group(2)
                preferences["budget"] = f"${val} USD"
            elif any(w in t_lower for w in ["luxury", "boutique", "premium", "5-star", "5 star"]):
                preferences["budget"] = "Premium / Boutique"
            elif any(w in t_lower for w in ["economy", "budget", "cheap", "backpack", "backpacker"]):
                preferences["budget"] = "Economy / Budget"

            # 4. Fitness / Difficulty level
            if any(w in t_lower for w in ["strenuous", "hard", "difficult", "mountaineer", "technical", "challenging", "high endurance"]):
                preferences["fitness_level"] = "Strenuous / High Endurance"
            elif any(w in t_lower for w in ["moderate", "medium", "regular hiker"]):
                preferences["fitness_level"] = "Moderate"
            elif any(w in t_lower for w in ["easy", "leisure", "relax", "beginner", "light walking"]):
                preferences["fitness_level"] = "Leisure / Easy Walking"

            # 5. Destination detection
            known_destinations = [
                "k2", "concordia", "baltoro", "gondogoro", "spantik", "broad peak",
                "gasherbrum", "trango", "chogolisa", "nangma", "hushe", "shimshal",
                "deosai", "hunza", "skardu", "fairy meadows", "nanga parbat", "swat",
                "chitral", "kalash", "passu", "rakaposhi", "kumrat", "kalam", "neelum",
                "haramosh", "shigar", "khaplu", "naran", "kaghan", "astore", "gilgit",
                "attabad", "khunjerab", "shangrila", "katpana", "kachura", "malam jabba",
                "batura", "biafo", "hispar", "snow lake", "rush lake"
            ]
            matched_dest = None
            for dest_kw in known_destinations:
                if re.search(rf"\b{re.escape(dest_kw)}\b", t_lower):
                    matched_dest = dest_kw.title()
                    break

            if matched_dest:
                preferences["destination"] = matched_dest
            else:
                dest_patterns = [
                    r"\b(?:in|to|visit|see|explore|trek|trip to|travel to)\s+([A-Za-z][a-zA-Z\s]{2,20})\b",
                ]
                excluded_dest_words = {
                    "pakistan", "northern", "the north", "the mountains", "june", "july", "august",
                    "september", "hotel", "hotels", "flight", "flights", "jeep", "food", "guide",
                    "porter", "itinerary", "day", "days", "person", "people", "usd", "pkr"
                }
                for pat in dest_patterns:
                    m = re.search(pat, text, flags=re.IGNORECASE)
                    if m:
                        found = m.group(1).strip()
                        found_clean = re.split(r"\b(for|with|in|on|during|next|and)\b", found, flags=re.IGNORECASE)[0].strip()
                        if found_clean.lower() not in excluded_dest_words and len(found_clean) >= 3:
                            preferences["destination"] = found_clean.title()
                            break

            # 6. Special requests / constraints
            special_keywords = [
                ("rest day", "Wants dedicated rest/acclimatization days"),
                ("acclimat", "Prioritizes gradual acclimatization"),
                ("photography", "Focus on photography and scenic viewpoints"),
                ("jeep", "Prefers 4x4 jeep safari/transit where available"),
                ("camp", "Interested in wilderness camping"),
                ("hotel", "Prefers comfortable hotel/lodge stays"),
                ("culture", "Interested in local culture and heritage"),
                ("women", "Women-only or female-friendly group"),
                ("vegetarian", "Vegetarian food preferences"),
                ("halal", "Strict halal meal requirements"),
            ]
            for kw, desc in special_keywords:
                if kw in t_lower and desc not in preferences["special_requests"]:
                    preferences["special_requests"].append(desc)

        return preferences

    @staticmethod
    def build_memory_context_prompt(preferences: Dict[str, Any]) -> str:
        """
        Format the extracted memory into an explicit markdown context section
        for injection into LLM system prompts.
        """
        items: List[str] = []
        if preferences.get("destination"):
            items.append(f"- Preferred Destination/Region: {preferences['destination']}")
        if preferences.get("duration"):
            items.append(f"- Trip Duration: {preferences['duration']}")
        if preferences.get("party_size"):
            items.append(f"- Party Size: {preferences['party_size']}")
        if preferences.get("budget"):
            items.append(f"- Stated Budget: {preferences['budget']}")
        if preferences.get("fitness_level"):
            items.append(f"- Fitness / Activity Level: {preferences['fitness_level']}")
        if preferences.get("special_requests"):
            items.append(f"- Stated Preferences & Notes: {', '.join(preferences['special_requests'])}")

        if not items:
            return ""

        memory_body = "\n".join(items)
        return (
            "\n[IN-CONTEXT MEMORY — REMEMBERED TRAVELER PREFERENCES]\n"
            "The traveler previously established the following preferences in this conversation:\n"
            f"{memory_body}\n"
            "MANDATORY RULE: Honor, preserve, and integrate these stated preferences into your recommendations "
            "and itinerary proposals. Do NOT prompt the visitor to repeat them unless they explicitly ask to change them.\n"
        )


# Global singleton instance
conversation_memory = ConversationMemoryService()
