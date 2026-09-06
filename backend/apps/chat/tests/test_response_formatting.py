"""
Automated unit tests for Response Formatting & Rendering Discipline.
Verifies the core principle: Structure is earned, not default.
- Plain conversational replies for short factual/clarifying questions.
- Comparison tables strictly for comparisons.
- Structured itinerary payload with day_by_day stages without markdown schedule dumps in prose.
"""

import pytest
import re
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatSession
from services.agent_runner import agent_runner
from services.data_integrity import CONFIDENCE_OFFICIAL, CONFIDENCE_UNVERIFIED


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def member_user(db):
    return User.objects.create_user(
        username="tariq_explorer",
        email="tariq@example.com",
        password="Password123!",
    )


@pytest.fixture
def chat_session(db, member_user):
    return ChatSession.objects.create(
        user=member_user,
        title="Karakoram Inquiry",
        is_guest=False,
    )


@pytest.mark.django_db
class TestResponseFormattingDiscipline:
    def test_rule1_plain_factual_query_returns_plain_prose_without_itinerary(self):
        """
        Rule 1: Plain conversational reply for short factual/clarifying queries.
        Query: 'what dates work for K2 base camp'
        Should return 1-2 plain, warm sentences without unearned headings, bullets,
        or an unrequested itinerary card.
        """
        result = agent_runner.run_multi_hop_pipeline(
            user_message="what dates work for K2 base camp",
            session_id="test-formatting-1",
        )
        assert result["path"] == "factual"
        assert result["itinerary"] is None
        reply = result["reply_text"]
        assert len(reply) > 0
        assert "<think>" not in reply

        # Structure is earned: No markdown headings (###) or bullet lists (* or -)
        assert not re.search(r"^#{1,6}\s+", reply, re.MULTILINE), f"Factual reply had unearned headings:\n{reply}"
        assert not re.search(r"^\s*[-*]\s+", reply, re.MULTILINE), f"Factual reply had unearned bullets:\n{reply}"
        # Mentions prime trekking season (summer / June-August)
        assert any(term in reply.lower() for term in ["june", "july", "august", "summer", "season"])

    def test_rule1_altitude_factual_query_returns_plain_prose(self):
        """Another factual query: 'what is the elevation of k2 base camp'."""
        result = agent_runner.run_multi_hop_pipeline(
            user_message="what is the elevation of k2 base camp",
            session_id="test-formatting-2",
        )
        assert result["path"] == "factual"
        assert result["itinerary"] is None
        reply = result["reply_text"]
        assert not re.search(r"^#{1,6}\s+", reply, re.MULTILINE)
        assert any(term in reply for term in ["5,150", "5150", "5,100", "5100", "meters", "m"])

    def test_rule4_comparison_query_returns_table_without_itinerary_card(self):
        """
        Rule 4: Comparison tables used strictly for side-by-side comparisons of 2+ items.
        Query: 'compare K2 base camp and Gondogoro La'
        Should return a markdown table and NO itinerary card.
        """
        result = agent_runner.run_multi_hop_pipeline(
            user_message="compare K2 base camp and Gondogoro La",
            session_id="test-formatting-3",
        )
        assert result["path"] == "comparison"
        assert result["itinerary"] is None
        reply = result["reply_text"]
        assert "<think>" not in reply
        # Must contain markdown table structure
        assert "|" in reply
        assert re.search(r"\|.+\|.+\|", reply), "Comparison response did not include a markdown table"
        # Must compare attributes like Altitude or Duration or Difficulty
        assert any(header in reply.lower() for header in ["altitude", "difficulty", "duration", "feature", "attribute"])

    def test_rule3_official_itinerary_returns_structured_payload_without_schedule_table_in_prose(self):
        """
        Rule 3: No markdown itinerary dumps in prose.
        The backend emits structured itinerary payload (title, duration, price, day_by_day stops array);
        the prose reply provides narrative commentary, and does NOT dump raw markdown schedule tables.
        """
        result = agent_runner.run_multi_hop_pipeline(
            user_message="plan an itinerary for k2 basecamp",
            session_id="test-formatting-4",
        )
        assert result["path"] == "official_match"
        itinerary = result["itinerary"]
        assert itinerary is not None
        assert "K2 Base Camp" in itinerary["title"]
        assert itinerary["status"] == "official"
        assert itinerary["confidence_label"] == CONFIDENCE_OFFICIAL

        # Check structured day_by_day array
        assert "day_by_day" in itinerary
        stages = itinerary["day_by_day"]
        assert isinstance(stages, list)
        assert len(stages) >= 3
        first_stage = stages[0]
        assert "day" in first_stage
        assert "title" in first_stage
        assert "description" in first_stage

        # Verify prose reply does NOT dump a markdown schedule table
        reply = result["reply_text"]
        assert "<think>" not in reply
        # Should not have table header for day-by-day in text
        assert not re.search(r"\|\s*Day\s*\|\s*Route", reply, re.IGNORECASE)
        # Should mention the interactive itinerary card below
        assert any(phrase in reply.lower() for phrase in ["card below", "timeline", "itinerary", "interactive"])

    def test_rule3_drafted_itinerary_returns_structured_payload_with_unverified_confidence(self):
        """
        Rule 3 & Multi-hop: When drafting a covered region, backend emits structured day_by_day stages
        and unverified confidence badge for frontend rendering.
        """
        result = agent_runner.run_multi_hop_pipeline(
            user_message="Plan a 7 day trekking trip to Chitral and Kalash Valley for 2 people",
            session_id="test-formatting-5",
        )
        assert result["path"] == "web_search_draft"
        itinerary = result["itinerary"]
        assert itinerary is not None
        assert "Chitral" in itinerary["title"]
        assert itinerary["status"] == "draft"
        assert itinerary["confidence_label"] == CONFIDENCE_UNVERIFIED
        assert itinerary["is_approved_by_user"] is False

        # day_by_day stages present
        assert "day_by_day" in itinerary
        assert len(itinerary["day_by_day"]) >= 5

        # Prose commentary does not dump markdown schedule tables
        reply = result["reply_text"]
        assert not re.search(r"\|\s*Day\s*\|\s*Route", reply, re.IGNORECASE)

    def test_send_api_endpoint_payload_structure(self, api_client, member_user, chat_session):
        """
        Integration test: /api/chat/sessions/<id>/send/ returns structured day_by_day in itinerary payload.
        """
        api_client.force_authenticate(user=member_user)
        res = api_client.post(
            f"/api/chat/sessions/{chat_session.id}/send/",
            {"message": "tell me about k2 basecamp trek itinerary"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        itinerary = data.get("itinerary")
        assert itinerary is not None
        assert "day_by_day" in itinerary
        assert len(itinerary["day_by_day"]) > 0
