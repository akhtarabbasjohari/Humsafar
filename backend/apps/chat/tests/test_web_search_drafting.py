"""
Unit tests for Phase 6: Multi-Hop Reasoning Pipeline, Web Search Fallback,
Itinerary Drafting, and Unverified Confidence Labeling.
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatMessage, ChatSession
from services.agent_runner import agent_runner
from services.data_integrity import CONFIDENCE_OFFICIAL, CONFIDENCE_UNVERIFIED
from services.itinerary_drafter import extract_traveler_preferences


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def member_user(db):
    return User.objects.create_user(
        username="rashid_mountaineer",
        email="rashid@example.com",
        password="Password123!",
    )


@pytest.fixture
def chat_session(db, member_user):
    return ChatSession.objects.create(
        user=member_user,
        title="Expedition Inquiry",
        is_guest=False,
    )


@pytest.mark.django_db
class TestMultiHopWebSearchDrafting:
    def test_preference_extraction(self):
        """Test extraction of traveler duration, budget, party size, and fitness."""
        msg = "I want to plan a 6 day trip to Chitral and Kalash for 4 people with moderate budget PKR 140,000."
        prefs = extract_traveler_preferences(msg, default_destination="Chitral")
        assert prefs.destination == "Chitral & Kalash Valley"
        assert prefs.duration_days == 6
        assert "4 Persons" in prefs.party_size
        assert "PKR 140,000" in prefs.budget

    def test_path1_direct_match_skips_web_search(self):
        """When an official tour matches, the agent presents it directly without web search."""
        pipeline_result = agent_runner.run_multi_hop_pipeline(
            user_message="Tell me about Hunza Autumn Tour",
            session_id="test-session-1",
        )
        assert pipeline_result["path"] == "official_match"
        assert pipeline_result["confidence_label"] == CONFIDENCE_OFFICIAL
        assert pipeline_result["itinerary"] is not None

        steps = pipeline_result["reasoning_steps"]
        assert len(steps) == 1
        assert steps[0]["step_name"] == "check_itinerary"
        assert steps[0]["output"]["matches_found"] > 0

    def test_path2_covered_region_triggers_web_search_and_drafting(self):
        """When region is served but no direct package match, multi-hop executes all 4 steps."""
        pipeline_result = agent_runner.run_multi_hop_pipeline(
            user_message="I want to visit Chitral and Kalash Valley for 5 days with 2 people",
            session_id="test-session-2",
        )
        assert pipeline_result["path"] == "web_search_draft"
        assert pipeline_result["confidence_label"] == CONFIDENCE_UNVERIFIED
        draft = pipeline_result["itinerary"]
        assert draft is not None
        assert "Chitral" in draft["title"]
        assert draft["confidence_label"] == CONFIDENCE_UNVERIFIED
        assert draft["is_approved_by_user"] is False
        assert draft["status"] == "draft"

        # Verify exact multi-hop reasoning chain
        steps = pipeline_result["reasoning_steps"]
        assert len(steps) == 4
        step_names = [s["step_name"] for s in steps]
        assert step_names == ["check_itinerary", "check_region", "search_web", "draft_itinerary"]

        # Step 1 output: no direct pre-packaged tour
        assert steps[0]["output"]["matches_found"] == 0
        # Step 2 output: region confirmed served
        assert steps[1]["output"]["is_serviced"] is True
        # Step 3 output: web search conducted
        assert steps[2]["output"]["results_count"] > 0
        # Step 4 output: draft generated
        assert steps[3]["output"]["confidence_label"] == CONFIDENCE_UNVERIFIED

    def test_path3_out_of_coverage_stops_after_step2(self):
        """When destination is out of coverage, reasoning halts after check_region and returns polite boundary."""
        pipeline_result = agent_runner.run_multi_hop_pipeline(
            user_message="Do you offer city tours in Paris?",
            session_id="test-session-3",
        )
        assert pipeline_result["path"] == "out_of_coverage"
        assert pipeline_result["itinerary"] is None

        steps = pipeline_result["reasoning_steps"]
        assert len(steps) == 2
        assert steps[0]["step_name"] == "check_itinerary"
        assert steps[1]["step_name"] == "check_region"
        assert steps[1]["output"]["is_serviced"] is False

    def test_api_send_endpoint_returns_reasoning_steps_and_draft(self, api_client, member_user, chat_session):
        """API endpoint /api/chat/sessions/<id>/send/ returns reasoning trace and unverified draft."""
        api_client.force_authenticate(user=member_user)

        res = api_client.post(
            f"/api/chat/sessions/{chat_session.id}/send/",
            {"message": "Can you design a 6 day expedition to Swat and Kalam Valley for 2 people?"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert "reasoning_steps" in data
        assert len(data["reasoning_steps"]) >= 2
        assert data["confidence_label"] == CONFIDENCE_UNVERIFIED
        assert data["itinerary"] is not None
        assert data["itinerary"]["confidence_label"] == CONFIDENCE_UNVERIFIED

        # Check persistence in database
        assistant_msg = ChatMessage.objects.filter(session=chat_session, sender="assistant").last()
        assert assistant_msg is not None
        assert "reasoning_steps" in assistant_msg.metadata
        assert assistant_msg.metadata["confidence_label"] == CONFIDENCE_UNVERIFIED
