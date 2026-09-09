"""
Phase 9: Persistence & Auth Isolation Tests.
Verifies:
- Guest messages are NOT persisted to ChatMessage table
- Guest itineraries are NOT persisted to SavedItinerary table  
- Authenticated user messages ARE persisted
- Cross-user itinerary isolation
- Inquiry object returned on approval
- Guest cannot list itineraries
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatMessage, ChatSession
from apps.itineraries.models import SavedItinerary
from django.utils import timezone


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_a(db):
    return User.objects.create_user(
        username="hiker_ahmed",
        email="ahmed@example.com",
        password="SecurePass123!",
        phone_number="+923001234567",
    )


@pytest.fixture
def user_b(db):
    return User.objects.create_user(
        username="hiker_fatima",
        email="fatima@example.com",
        password="SecurePass123!",
    )


def _mock_pipeline_result():
    """Standard mock pipeline result for testing persistence gating."""
    return {
        "reply_text": "Here is a beautiful trek through the Karakoram.",
        "itinerary": {
            "title": "K2 Base Camp Trek",
            "region": "Baltistan",
            "duration_days": 14,
            "is_draft": True,
            "source_url": "https://askoliadventure.com/expeditions/k2-base-camp",
        },
        "confidence_label": "from our official listing",
        "source_url": "https://askoliadventure.com/expeditions/k2-base-camp",
        "reasoning_steps": [],
        "path": "web_search_draft",
    }


@pytest.mark.django_db
class TestGuestPersistenceIsolation:
    """Confirm nothing guest-related is ever written to persistent tables."""

    @patch("apps.chat.views.HumsafarAgentRunner")
    def test_guest_messages_not_persisted(self, MockRunner, api_client):
        """Guest send → valid response returned but zero ChatMessage rows created."""
        mock_instance = MockRunner.return_value
        mock_instance.run_multi_hop_pipeline.return_value = _mock_pipeline_result()

        guest_session = ChatSession.objects.create(
            is_guest=True, guest_token="guest_tok_phase9", title="Guest Test"
        )
        res = api_client.post(
            f"/api/chat/sessions/{guest_session.id}/send/",
            {"message": "Tell me about K2 base camp"},
            format="json",
            HTTP_X_GUEST_TOKEN="guest_tok_phase9",
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["assistant_message"]["content"]
        assert res.data["user_message"]["content"] == "Tell me about K2 base camp"
        # Critical: Zero messages persisted
        assert ChatMessage.objects.filter(session=guest_session).count() == 0

    @patch("apps.chat.views.HumsafarAgentRunner")
    def test_guest_itineraries_not_persisted(self, MockRunner, api_client):
        """Guest send with itinerary draft → zero SavedItinerary rows created."""
        mock_instance = MockRunner.return_value
        mock_instance.run_multi_hop_pipeline.return_value = _mock_pipeline_result()

        guest_session = ChatSession.objects.create(
            is_guest=True, guest_token="guest_tok_itin", title="Guest Itin Test"
        )
        res = api_client.post(
            f"/api/chat/sessions/{guest_session.id}/send/",
            {"message": "Plan a K2 trip"},
            format="json",
            HTTP_X_GUEST_TOKEN="guest_tok_itin",
        )
        assert res.status_code == status.HTTP_200_OK
        assert SavedItinerary.objects.filter(session=guest_session).count() == 0


@pytest.mark.django_db
class TestAuthenticatedPersistence:
    """Confirm authenticated user data IS persisted."""

    @patch("apps.chat.views.HumsafarAgentRunner")
    def test_authenticated_messages_persisted(self, MockRunner, api_client, user_a):
        """Logged-in user send → ChatMessage rows created."""
        mock_instance = MockRunner.return_value
        mock_instance.run_multi_hop_pipeline.return_value = _mock_pipeline_result()

        api_client.force_authenticate(user=user_a)
        session = ChatSession.objects.create(user=user_a, title="Auth Test")
        res = api_client.post(
            f"/api/chat/sessions/{session.id}/send/",
            {"message": "Tell me about K2"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        # User message + assistant message = 2 rows
        assert ChatMessage.objects.filter(session=session).count() == 2

    @patch("apps.chat.views.HumsafarAgentRunner")
    def test_authenticated_itineraries_persisted(self, MockRunner, api_client, user_a):
        """Logged-in user send with draft → SavedItinerary row created."""
        mock_instance = MockRunner.return_value
        mock_instance.run_multi_hop_pipeline.return_value = _mock_pipeline_result()

        api_client.force_authenticate(user=user_a)
        session = ChatSession.objects.create(user=user_a, title="Auth Itin Test")
        api_client.post(
            f"/api/chat/sessions/{session.id}/send/",
            {"message": "Plan K2 trek"},
            format="json",
        )
        assert SavedItinerary.objects.filter(session=session, user=user_a).count() == 1


@pytest.mark.django_db
class TestItineraryOwnershipIsolation:
    """Users can only read their own itineraries."""

    def test_cross_user_itinerary_list_isolated(self, api_client, user_a, user_b):
        """User B cannot see User A's itineraries."""
        session_a = ChatSession.objects.create(user=user_a, title="A's session")
        SavedItinerary.objects.create(
            user=user_a,
            session=session_a,
            title="A's Private Trek",
            region="Baltistan",
            source_url="https://askoliadventure.com/test",
            source_verified_at=timezone.now(),
        )
        api_client.force_authenticate(user=user_b)
        res = api_client.get("/api/itineraries/")
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 0

    def test_cross_user_itinerary_detail_forbidden(self, api_client, user_a, user_b):
        """User B cannot access User A's itinerary detail."""
        session_a = ChatSession.objects.create(user=user_a, title="A's session")
        itin = SavedItinerary.objects.create(
            user=user_a,
            session=session_a,
            title="A's Private Trek",
            region="Baltistan",
            source_url="https://askoliadventure.com/test",
            source_verified_at=timezone.now(),
        )
        api_client.force_authenticate(user=user_b)
        res = api_client.get(f"/api/itineraries/{itin.id}/")
        assert res.status_code == status.HTTP_403_FORBIDDEN

    def test_guest_cannot_list_itineraries(self, api_client):
        """Unauthenticated guest gets 401 on itinerary listing."""
        res = api_client.get("/api/itineraries/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestInquiryObjectOnApproval:
    """Verify structured inquiry object returned on HITL approval."""

    def test_inquiry_object_returned_on_approval(self, api_client, user_a):
        """Approving an itinerary returns structured inquiry with visitor details."""
        session = ChatSession.objects.create(user=user_a, title="Inquiry Test")
        itin = SavedItinerary.objects.create(
            user=user_a,
            session=session,
            title="Concordia Trek",
            region="Baltistan",
            status="draft",
            source_url="https://askoliadventure.com/expeditions/concordia",
            source_verified_at=timezone.now(),
        )
        api_client.force_authenticate(user=user_a)
        res = api_client.post(
            f"/api/itineraries/{itin.id}/approve/",
            {"approved": True, "feedback_or_notes": "Looks great!"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        assert "inquiry" in res.data
        inquiry = res.data["inquiry"]
        assert inquiry["status"] == "ready_for_review"
        assert inquiry["visitor"]["name"] == "hiker_ahmed"
        assert inquiry["visitor"]["email"] == "ahmed@example.com"
        assert inquiry["visitor"]["phone"] == "+923001234567"
        assert inquiry["visitor"]["is_registered"] is True
        assert inquiry["itinerary"]["title"] == "Concordia Trek"
        assert inquiry["session_context"]["session_id"] == str(session.id)
