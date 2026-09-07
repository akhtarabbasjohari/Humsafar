import pytest
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatSession, ChatMessage
from apps.itineraries.models import SavedItinerary
from services.conversation_memory import conversation_memory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_user():
    return User.objects.create_user(
        username="hiker_ali",
        email="ali@example.com",
        password="ValidPassword123!",
        phone_number="+923001234567",
    )


@pytest.mark.django_db
class TestConversationMemory:
    """Test in-context conversation memory extraction and persistence across turns."""

    def test_guest_memory_across_multiple_turns(self):
        messages = [
            {"role": "user", "content": "I am looking to travel with 3 friends for about 10 days."},
            {"role": "assistant", "content": "Welcome! Where in Northern Pakistan would you like to explore?"},
            {"role": "user", "content": "We are interested in Skardu and Deosai, with a budget of PKR 250,000."},
        ]

        prefs = conversation_memory.extract_conversation_preferences(messages)

        assert prefs["duration"] == "10 Days"
        assert prefs["duration_days"] == 10
        assert prefs["party_size"] == "3 Persons"
        assert prefs["budget"] == "PKR 250,000"
        assert prefs["destination"] in ["Skardu", "Deosai"]

    def test_preference_update_overrides_specific_field_while_retaining_others(self):
        messages = [
            {"role": "user", "content": "I want a 7 days trek in Hunza for 2 people with a luxury budget."},
            {"role": "assistant", "content": "Certainly, Hunza has wonderful boutique lodges."},
            {"role": "user", "content": "Actually, let's make it 5 days instead, but keep everything else the same."},
        ]

        prefs = conversation_memory.extract_conversation_preferences(messages)

        # Duration updated to 5 days
        assert prefs["duration"] == "5 Days"
        assert prefs["duration_days"] == 5
        # Party size, destination, and budget retained without repeating
        assert prefs["party_size"] == "2 Persons"
        assert prefs["destination"] == "Hunza"
        assert prefs["budget"] == "Premium / Boutique"

    def test_memory_context_prompt_formatting(self):
        prefs = {
            "destination": "Spantik",
            "duration": "14 Days",
            "party_size": "4 Persons",
            "budget": "PKR 450,000",
            "fitness_level": "Strenuous / High Endurance",
            "special_requests": ["Prioritizes gradual acclimatization", "Wants dedicated rest/acclimatization days"],
        }
        prompt = conversation_memory.build_memory_context_prompt(prefs)

        assert "IN-CONTEXT MEMORY" in prompt
        assert "Spantik" in prompt
        assert "14 Days" in prompt
        assert "4 Persons" in prompt
        assert "PKR 450,000" in prompt
        assert "acclimatization" in prompt


@pytest.mark.django_db
class TestHumanInTheLoopRedraftAndApproval:
    """Test the HITL redraft endpoint and approval gate."""

    def test_redraft_endpoint_folds_feedback_and_resets_approval(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)

        session = ChatSession.objects.create(
            user=auth_user,
            title="Spantik Custom Expedition",
        )

        # Initial assistant draft
        ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.SENDER_USER,
            content="Plan a 7-day trek to Spantik for 2 people.",
        )
        initial_itinerary = {
            "title": "7 Days Spantik Custom Expedition",
            "region": "Spantik, Pakistan",
            "duration": "7 Days",
            "duration_days": 7,
            "price": "PKR 150,000",
            "is_draft": True,
            "is_approved_by_user": False,
            "status": "draft",
        }
        draft_db = SavedItinerary.objects.create(
            user=auth_user,
            session=session,
            title="7 Days Spantik Custom Expedition",
            region="Spantik",
            duration_days=7,
            itinerary_data=initial_itinerary,
            source_url="https://itp.7scribes.com/destinations/spantik",
            confidence_label="researched just now, unverified, please confirm with our team",
            status=SavedItinerary.STATUS_DRAFT,
            is_approved_by_user=False,
        )

        # Traveler requests changes via redraft endpoint
        redraft_payload = {
            "feedback": "Please reduce duration to 5 days and add an extra rest day for acclimatization.",
            "itinerary_id": str(draft_db.id),
        }
        response = api_client.post(
            f"/api/chat/sessions/{session.id}/redraft/",
            data=redraft_payload,
            format="json",
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "assistant_message" in data
        assert "itinerary" in data
        assert data["approval_status"] == "draft"
        assert data["is_approved"] is False

        # Verify feedback is captured in user message
        assert "reduce duration to 5 days" in data["user_message"]["content"]

        # Verify database itinerary updated with draft status
        draft_db.refresh_from_db()
        assert draft_db.duration_days == 5
        assert draft_db.status == SavedItinerary.STATUS_DRAFT
        assert draft_db.is_approved_by_user is False
        assert "reduce duration to 5 days" in draft_db.notes

    def test_redraft_requires_non_empty_feedback(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        session = ChatSession.objects.create(user=auth_user, title="Test Session")

        response = api_client.post(
            f"/api/chat/sessions/{session.id}/redraft/",
            data={"feedback": "   "},
            format="json",
        )
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_guest_can_redraft_with_valid_guest_token(self, api_client):
        session = ChatSession.objects.create(
            is_guest=True,
            guest_token="guest-secret-token-123",
            title="Guest Expedition",
        )

        # Without guest token -> 403 Forbidden
        bad_res = api_client.post(
            f"/api/chat/sessions/{session.id}/redraft/",
            data={"feedback": "Make it cheaper"},
            format="json",
        )
        assert bad_res.status_code == 403

        # With guest token header -> 200 OK
        ok_res = api_client.post(
            f"/api/chat/sessions/{session.id}/redraft/",
            data={"feedback": "Make it cheaper"},
            format="json",
            HTTP_X_GUEST_TOKEN="guest-secret-token-123",
        )
        assert ok_res.status_code == 200
        assert ok_res.json()["is_approved"] is False
