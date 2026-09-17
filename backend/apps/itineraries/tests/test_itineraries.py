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
        """HITL Rule: Explicit traveler approval transitions draft to approved when fresh source exists."""
        from django.utils import timezone
        api_client.force_authenticate(user=test_user)
        itinerary = SavedItinerary.objects.create(
            user=test_user,
            title="7-Day Hunza Autumn Blossom",
            region="Hunza",
            duration_days=7,
            status=SavedItinerary.STATUS_DRAFT,
            is_approved_by_user=False,
            source_url="https://askoliadventure.com/tour/hunza/",
            source_verified_at=timezone.now(),
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

    def test_approval_rejected_if_missing_source_url(self, api_client, test_user):
        """Data Integrity Rule: Reject approval if itinerary lacks an explicit source URL."""
        from django.utils import timezone
        api_client.force_authenticate(user=test_user)
        itinerary = SavedItinerary.objects.create(
            user=test_user,
            title="Ungrounded Fairy Meadows Trek",
            region="Fairy Meadows",
            duration_days=4,
            status=SavedItinerary.STATUS_DRAFT,
            source_url="",  # missing source
            source_verified_at=timezone.now(),
        )

        response = api_client.post(
            f"/api/itineraries/{itinerary.id}/approve/",
            {"approved": True},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "MISSING_SOURCE_URL"

    def test_approval_rejected_if_source_data_is_stale(self, api_client, test_user):
        """Data Integrity Rule: Reject approval if source verification timestamp is stale."""
        from datetime import timedelta
        from django.utils import timezone
        api_client.force_authenticate(user=test_user)
        stale_time = timezone.now() - timedelta(hours=3)

        itinerary = SavedItinerary.objects.create(
            user=test_user,
            title="Stale K2 Circuit",
            region="Baltistan",
            duration_days=14,
            status=SavedItinerary.STATUS_DRAFT,
            source_url="https://askoliadventure.com/tour/k2/",
            source_verified_at=stale_time,
        )

        response = api_client.post(
            f"/api/itineraries/{itinerary.id}/approve/",
            {"approved": True},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error_code"] == "STALE_OR_MISSING_SOURCE_DATA"

    def test_create_itinerary_with_price_range_string(self, api_client, test_user):
        """Ensure price ranges like 'PKR 220,000 - 260,000' or long numbers do not cause 12-digit error."""
        api_client.force_authenticate(user=test_user)
        session = ChatSession.objects.create(user=test_user, title="Price Range Test")

        payload = {
            "session": str(session.id),
            "title": "Nanga Parbat BC Trek",
            "region": "Northern Pakistan",
            "duration_days": 10,
            "itinerary_data": {"test": "data"},
            "estimated_price_pkr": "PKR 220,000 – 260,000 ($790 – $930 USD)",
        }
        response = api_client.post("/api/itineraries/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert float(response.data["estimated_price_pkr"]) == 220000.00

