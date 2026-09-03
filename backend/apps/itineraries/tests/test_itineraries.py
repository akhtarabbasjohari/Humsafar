import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatSession
from apps.itineraries.models import SavedItinerary

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="trekker_sara",
        email="sara@example.com",
        password="Password123!",
    )

@pytest.mark.django_db
class TestSavedItinerary:
    def test_create_itinerary_defaults_to_draft(self, api_client, test_user):
        """HITL Rule: Generated itineraries must default to draft state."""
        api_client.force_authenticate(user=test_user)
        session = ChatSession.objects.create(user=test_user, title="Swat Valley Tour")

        payload = {
            "session": str(session.id),
            "title": "5-Day Swat Valley Discovery",
            "region": "Swat Valley",
            "duration_days": 5,
            "itinerary_data": {
                "day1": "Arrival in Mingora, visit White Palace",
                "day2": "Malam Jabba ski resort visit",
            },
            "estimated_price_pkr": "85000.00",
        }
        response = api_client.post("/api/itineraries/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == SavedItinerary.STATUS_DRAFT
        assert response.data["is_approved_by_user"] is False
        assert response.data["approval_timestamp"] is None

    def test_traveler_explicit_approval_hitl(self, api_client, test_user):
        """HITL Rule: Explicit traveler approval transitions draft to approved."""
        api_client.force_authenticate(user=test_user)
        itinerary = SavedItinerary.objects.create(
            user=test_user,
            title="7-Day Hunza Autumn Blossom",
            region="Hunza",
            duration_days=7,
            status=SavedItinerary.STATUS_DRAFT,
            is_approved_by_user=False,
        )

        approval_payload = {
            "approved": True,
            "feedback_or_notes": "Looks great, please confirm hotels with mountain views.",
        }
        response = api_client.post(
            f"/api/itineraries/{itinerary.id}/approve/",
            approval_payload,
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == SavedItinerary.STATUS_APPROVED
        assert response.data["is_approved_by_user"] is True
        assert response.data["approval_timestamp"] is not None
        assert "mountain views" in response.data["notes"]
