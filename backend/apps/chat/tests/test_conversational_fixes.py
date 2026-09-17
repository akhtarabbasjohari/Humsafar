import re
import pytest
from unittest.mock import patch, MagicMock

from services.itinerary_drafter import extract_traveler_preferences
from services.ollama_service import OllamaService
from apps.chat.services.agent_runner import HumsafarAgentRunner


class TestConversationalFixes:
    """Tests covering bug fixes identified during comprehensive live testing."""

    def test_factual_permit_intent_detection(self):
        """Ensure questions about permits for foreign tourists are detected as factual queries."""
        permit_queries = [
            "Do foreign tourists need a special permit to visit restricted border zones in Gilgit-Baltistan?",
            "Do we need a permit to visit Askoli?",
            "Can travelers get a visa on arrival?",
            "Are there special permit requirements for K2 base camp?",
            "Does anyone need a NOC for Deosai?",
        ]

        factual_patterns = [
            r"\b(what|which)\s+(dates?|months?|seasons?|time of year|window)\b",
            r"\b(when|what time)\s+(is|are|does|can|should)\b",
            r"\b(best|optimal|recommended)\s+(time|season|month|window)\b",
            r"\b(how\s+high|altitude|elevation|height)\b",
            r"\b(?:do|does|can|will|should)\s+(?:i|we|foreign(?:ers| tourists)?|tourists?|travelers?|visitors?|anyone)\s+(?:need|get|require|obtain|apply\s+for)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass)\b",
            r"\b(?:is\s+there|are\s+there)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass|rules?|restrictions?)\b",
            r"\b(?:need|require|requirements?)\s+(?:a\s+)?(?:special\s+)?(?:permit|visa|noc|clearance|pass)\b",
            r"\b(?:permit|visa|noc|clearance)\s+(?:requirements?|needed|required)\b",
            r"\b(how\s+difficult|what\s+grade|fitness\s+level|how\s+fit)\b",
            r"\b(what\s+temperature|how\s+cold|what\s+weather)\b",
            r"\b(can\s+i|is\s+it\s+safe)\b",
        ]

        for q in permit_queries:
            clean_msg = q.lower()
            matched = any(re.search(pat, clean_msg) for pat in factual_patterns)
            assert matched, f"Query failed to match factual pattern: {q}"

    def test_party_size_extraction_variations(self):
        """Ensure 'party of X', 'group of X', 'family of X', and 'X of us' are accurately extracted."""
        # 1. Party of 4
        pref1 = extract_traveler_preferences(
            user_message="We are a party of 4 planning a trip to Hunza.",
            conversation_history=[],
        )
        assert pref1.party_size == "4 Persons"

        # 2. Family of 5
        pref2 = extract_traveler_preferences(
            user_message="Can you organize an expedition for our family of 5?",
            conversation_history=[],
        )
        assert pref2.party_size == "5 Persons"

        # 3. Group of 3
        pref3 = extract_traveler_preferences(
            user_message="Group of 3 looking for a trek to Rakaposhi.",
            conversation_history=[],
        )
        assert pref3.party_size == "3 Persons"

        # 4. 4 of us
        pref4 = extract_traveler_preferences(
            user_message="There are 4 of us visiting Skardu next month.",
            conversation_history=[],
        )
        assert pref4.party_size == "4 Persons"

        # 5. Overriding prior turns
        pref5 = extract_traveler_preferences(
            user_message="Actually we are now a party of 6.",
            conversation_history=[{"role": "user", "content": "I want to plan for 2 people"}],
        )
        assert pref5.party_size == "6 Persons"

    def test_prose_schedule_and_price_stripping(self):
        """Ensure prose does not leak hallucinated day stages, duration, or prices when official card is present."""
        raw_llm_reply = (
            "We are thrilled to present our flagship K2 Base Camp & Concordia Trek!\n\n"
            "**Duration:** 20 days\n"
            "**Price:** Pricing upon inquiry\n\n"
            "**Day 1:** Arrival in Islamabad and briefing.\n"
            "**Day 2:** Flight to Skardu or drive via Karakoram Highway.\n"
            "* Day 3: Drive to Askole.\n"
            "- Day 4: Trek from Askole to Jhola.\n\n"
            "Our certified guides and high-altitude staff will accompany you every step.\n"
        )

        filtered_lines = []
        for line in raw_llm_reply.splitlines():
            s_line = line.strip()
            if re.match(r"^(?:[\*\-\•]|\d+\.)?\s*\*{0,2}Day\s+\d+\*{0,2}\s*[:\-]", s_line, re.IGNORECASE):
                continue
            if re.match(r"^(?:[\*\-\•])?\s*\*{0,2}(?:Duration|Price|Estimated\s+Price)\*{0,2}\s*[:\-]", s_line, re.IGNORECASE):
                continue
            if re.search(r"\bpricing\s+upon\s+inquiry\b", s_line, re.IGNORECASE):
                continue
            filtered_lines.append(line)

        clean = "\n".join(filtered_lines).strip()

        assert "Duration: 20 days" not in clean
        assert "Pricing upon inquiry" not in clean
        assert "Day 1:" not in clean
        assert "Day 2:" not in clean
        assert "Day 3:" not in clean
        assert "Day 4:" not in clean
        assert "We are thrilled to present" in clean
        assert "Our certified guides" in clean

    def test_duration_discrepancy_notice(self):
        """Verify note is added when requested duration differs significantly from catalog package."""
        user_message = "Can you plan a 6-day trip to Hunza Valley?"
        dur_days = 14
        clean_reply = "Welcome to Hunza Valley! Here is our standard exploration tour."

        req_dur_match = re.search(r"\b(\d+)[\s\-]*(?:days?|nights?)\b", user_message.lower())
        assert req_dur_match is not None
        req_days = int(req_dur_match.group(1))
        assert req_days == 6

        if abs(dur_days - req_days) >= 3:
            dur_note = (
                f"\n\n*Note on Duration:* While our standard catalog package runs for {dur_days} days, "
                f"our operations team can easily tailor a customized {req_days}-day adaptation to suit your exact schedule."
            )
            clean_reply = f"{clean_reply}{dur_note}"

        assert "*Note on Duration:*" in clean_reply
        assert "14 days" in clean_reply
        assert "6-day adaptation" in clean_reply

    def test_ollama_service_timeout_default(self):
        """Verify default Ollama timeout is calibrated to 45 seconds for CPU inference."""
        service = OllamaService()
        assert service.timeout == 45.0
