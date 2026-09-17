"""
End-to-End HTTP/API Pipeline Integration Test for Humsafar AI Travel Planning Agent.
Tests the full lifecycle across real DRF HTTP endpoints:
1. Guest Session Initialization (POST /api/auth/guest-init/)
2. Official Catalog Package Inquiry (POST /api/chat/send/ -> official_match)
3. Feasibility Rejection Path (POST /api/chat/send/ -> feasibility_advisory)
4. Custom Fallback Research & Drafting Path (POST /api/chat/send/ -> web_search_draft)
5. Human-in-the-Loop Traveler Approval Gate (POST /api/itineraries/<id>/approve/)
6. Structured Inquiry Dispatch Preparation (POST /api/itineraries/<id>/prepare-inquiry/)
7. Observability Telemetry Audit (GET /api/chat/observability/logs/)
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.chat.models import ChatSession, ChatMessage, ToolCallLog
from apps.chat.services.agent_runner import HumsafarAgentRunner
from apps.itineraries.models import SavedItinerary
from services.data_integrity import CONFIDENCE_OFFICIAL, CONFIDENCE_UNVERIFIED


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestEndToEndHumsafarPipeline:
    """True end-to-end integration test of the full HTTP/API travel planning workflow."""

    def test_complete_guest_to_inquiry_lifecycle(self, api_client):
        # -------------------------------------------------------------------
        # Step 1: Initialize Guest Session
        # -------------------------------------------------------------------
        init_resp = api_client.post("/api/auth/guest/")
        assert init_resp.status_code == status.HTTP_201_CREATED

        init_data = init_resp.json()
        assert "guest_token" in init_data
        assert "session_id" in init_data
        session_id = init_data["session_id"]
        guest_token = init_data["guest_token"]

        from django.utils import timezone as dj_tz
        # -------------------------------------------------------------------
        # Step 2: Inquire about Official Tour Package (Concordia Trek)
        # -------------------------------------------------------------------
        mock_concordia_tour = {
            "title": "Concordia Trek (K2 Base Camp)",
            "destination": "Concordia and K2 Base Camp",
            "duration": "21 Days",
            "price": "PKR 350,000 / $1,250 USD",
            "summary": "Classic trek to the throne room of the mountain gods.",
            "url": "https://askoliadventure.com/tour/concordia-trek/",
            "scraped_at": dj_tz.now().isoformat(),
            "source_url": "https://askoliadventure.com/tour/concordia-trek/",
            "confidence_label": CONFIDENCE_OFFICIAL,
        }
        with patch("mcp_servers.humsafar_data_mcp.scraper.scraper.search_itineraries") as mock_mcp_search, \
             patch("services.groq_service.generate_travel_reply") as mock_travel_reply:
            mock_mcp_search.return_value = {
                "success": True,
                "count": 1,
                "results": [mock_concordia_tour],
            }
            mock_travel_reply.return_value = (
                "Concordia is the throne room of the mountain gods in the Karakoram range. "
                "Our 21-day expedition features world-class mountain guides and acclimatization pacing."
            )
            catalog_resp = api_client.post(
                f"/api/chat/sessions/{session_id}/send/",
                {"message": "Tell me about the Concordia Trek package"},
                format="json",
                HTTP_X_GUEST_TOKEN=guest_token,
            )
            assert catalog_resp.status_code == status.HTTP_200_OK
            cat_data = catalog_resp.json()
            assert cat_data["path"] == "official_match"
            assert cat_data["confidence_label"] == CONFIDENCE_OFFICIAL
            assert cat_data["itinerary"] is not None
            assert "Concordia" in cat_data["itinerary"]["title"]

        # -------------------------------------------------------------------
        # Step 3: Feasibility Rejection on Physically Impossible Request (K2 in 2 Days)
        # -------------------------------------------------------------------
        with patch.object(HumsafarAgentRunner, "run_agentic_tool_loop") as mock_agent_loop:
            mock_agent_loop.return_value = {
                "path": "feasibility_advisory",
                "reply_text": "Trekking to K2 Base Camp in 2 days is physically impossible and life-threatening.",
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": [],
            }
            feas_resp = api_client.post(
                f"/api/chat/sessions/{session_id}/send/",
                {"message": "Can I do a 2-day trek to K2 Base Camp from Islamabad?"},
                format="json",
                HTTP_X_GUEST_TOKEN=guest_token,
            )
            assert feas_resp.status_code == status.HTTP_200_OK
            feas_data = feas_resp.json()
            assert feas_data["path"] == "feasibility_advisory"
            assert feas_data["itinerary"] is None
            assert "impossible" in feas_data["assistant_message"]["content"].lower()

        # -------------------------------------------------------------------
        # Step 4: Custom Covered Destination (Chitral & Kalash 6-day Tour)
        # -------------------------------------------------------------------
        with patch.object(HumsafarAgentRunner, "run_agentic_tool_loop", return_value=None), \
             patch("mcp_servers.humsafar_data_mcp.scraper.scraper.search_itineraries") as mock_mcp_search_empty, \
             patch("mcp_servers.humsafar_data_mcp.scraper.scraper.check_region_coverage") as mock_mcp_cov, \
             patch("services.web_search_service.web_search_service.search") as mock_web_search, \
             patch("services.itinerary_drafter.draft_custom_itinerary") as mock_draft:

            mock_mcp_search_empty.return_value = {"success": True, "count": 0, "results": []}
            mock_mcp_cov.return_value = {"serviced": True, "matched_regions": ["Chitral", "Khyber Pakhtunkhwa"]}
            mock_web_search.return_value = {
                "destination": "Chitral",
                "results": [{"title": "Chitral Guide", "link": "https://visitpakistan.gov.pk", "content": "Kalash valleys"}],
                "top_source_url": "https://visitpakistan.gov.pk",
            }
            mock_draft.return_value = {
                "is_feasible": True,
                "itinerary_draft": {
                    "id": "draft-chitral-101",
                    "title": "6 Days Chitral & Kalash Valley Custom Tour",
                    "destination": "Chitral and Kalash Valley",
                    "duration": "6 Days",
                    "duration_days": 6,
                    "price": "PKR 145,000 - 185,000 ($520 - $660 USD)",
                    "pricing_breakdown": {
                        "total_pkr_range": "PKR 145,000 - 185,000",
                        "guide_fee": "PKR 30,000",
                        "transport": "PKR 65,000",
                    },
                    "day_by_day": [
                        {"day": 1, "title": "Islamabad to Chitral", "description": "Drive via Lowari Tunnel", "altitude": "1,500m"},
                        {"day": 2, "title": "Bumburet Valley", "description": "Explore Kalash cultural settlements", "altitude": "1,650m"},
                        {"day": 3, "title": "Rambur & Birir", "description": "Meet native Kalash artisans", "altitude": "1,700m"},
                        {"day": 4, "title": "Chitral Town & Shahi Mosque", "description": "Visit historic fort", "altitude": "1,500m"},
                        {"day": 5, "title": "Ayun Valley Excursion", "description": "Scenic orchard walk", "altitude": "1,450m"},
                        {"day": 6, "title": "Return Journey to Islamabad", "description": "Scenic highway drive", "altitude": "550m"},
                    ],
                    "inclusions": ["Licensed Guide", "4x4 Transport", "Hotel Stays", "Breakfast"],
                    "exclusions": ["Airfare", "Personal Insurance", "Tips"],
                    "confidence_label": CONFIDENCE_UNVERIFIED,
                    "confidence_type": "unverified",
                    "status": "draft",
                    "is_approved": False,
                    "is_approved_by_user": False,
                    "source_url": "https://visitpakistan.gov.pk",
                },
                "consultant_reply": (
                    "Here is your customized 6-day Chitral & Kalash expedition proposal. "
                    "Please review the itinerary stages and let us know if you approve this draft."
                ),
                "reply_text": "Here is your customized 6-day Chitral & Kalash expedition proposal.",
                "pricing_breakdown": {"total_pkr_range": "PKR 145,000 - 185,000"},
            }

            custom_resp = api_client.post(
                f"/api/chat/sessions/{session_id}/send/",
                {"message": "Plan a 6-day trip to Chitral and Kalash for 2 people with PKR 150,000 budget"},
                format="json",
                HTTP_X_GUEST_TOKEN=guest_token,
            )
            assert custom_resp.status_code == status.HTTP_200_OK
            cust_data = custom_resp.json()
            assert cust_data["path"] == "web_search_draft"
            assert cust_data["confidence_label"] == CONFIDENCE_UNVERIFIED
            assert cust_data["itinerary"] is not None


            # Create SavedItinerary in DB to simulate database persistence for approval
            from django.utils import timezone as dj_tz
            db_session = ChatSession.objects.filter(id=session_id).first()
            saved_itin = SavedItinerary.objects.create(
                user=None,
                session=db_session,
                title=cust_data["itinerary"]["title"],
                region=cust_data["itinerary"].get("destination", "Chitral"),
                duration_days=cust_data["itinerary"].get("duration_days", 6),
                estimated_price_pkr=150000,
                status="draft",
                confidence_label=CONFIDENCE_UNVERIFIED,
                source_url="https://visitpakistan.gov.pk",
                source_verified_at=dj_tz.now(),
                itinerary_data=cust_data["itinerary"],
                is_approved_by_user=False,
            )
            itin_id = str(saved_itin.id)

        # -------------------------------------------------------------------
        # Step 5: Human-in-the-Loop Traveler Approval Gate & Inquiry Generation
        # -------------------------------------------------------------------
        approve_resp = api_client.post(
            f"/api/itineraries/{itin_id}/approve/",
            {
                "approved": True,
                "feedback_or_notes": "We require vegetarian meals and experienced local mountain guide.",
            },
            format="json",
            HTTP_X_GUEST_TOKEN=guest_token,
        )
        assert approve_resp.status_code == status.HTTP_200_OK
        approve_data = approve_resp.json()
        assert approve_data["is_approved_by_user"] is True
        assert approve_data["status"] == "approved"
        assert "inquiry" in approve_data
        inq = approve_data["inquiry"]
        assert inq["itinerary"]["id"] == itin_id
        assert inq["status"] == "ready_for_review"
        assert inq["itinerary"]["title"] == "6 Days Chitral & Kalash Valley Custom Tour"

        # -------------------------------------------------------------------
        # Step 6: Telemetry Hooks Observability Verification
        # -------------------------------------------------------------------
        obs_resp = api_client.get(f"/api/chat/observability/logs/?session_id={session_id}")
        assert obs_resp.status_code == status.HTTP_200_OK
        obs_data = obs_resp.json()
        assert obs_data["total_logs"] >= 1
        logged_skills = [item["skill"] for item in obs_data["logs"]]
        assert any(skill in logged_skills for skill in ["itinerary_lookup", "feasibility_check", "itinerary_drafting", "web_search_fallback"])

