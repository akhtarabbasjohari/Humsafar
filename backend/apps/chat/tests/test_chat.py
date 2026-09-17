import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatMessage, ChatSession

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def registered_user(db):
    return User.objects.create_user(
        username="hiker_zain",
        email="zain@example.com",
        password="Password123!",
    )

@pytest.mark.django_db
class TestChatSession:
    def test_unauthenticated_visitor_creates_guest_session_by_default(self, api_client):
        """Unauthenticated visitor creates a session; defaults to guest mode."""
        payload = {
            "title": "Skardu Expedition Planning",
            "metadata": {"budget": "moderate", "days": 7},
        }
        response = api_client.post("/api/chat/sessions/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_guest"] is True
        assert response.data["user"] is None
        assert response.data["guest_token"] != ""
        assert response.data["title"] == "Skardu Expedition Planning"

    def test_authenticated_user_creates_user_scoped_session(self, api_client, registered_user):
        """Authenticated user creates session scoped to their account."""
        api_client.force_authenticate(user=registered_user)
        payload = {"title": "K2 Base Camp Trek"}
        response = api_client.post("/api/chat/sessions/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_guest"] is False
        assert str(response.data["user"]) == str(registered_user.id)

    def test_user_session_isolation(self, api_client, registered_user):
        """A user only sees their own chat sessions."""
        other_user = User.objects.create_user(
            username="other_traveler",
            email="other@example.com",
            password="Password123!",
        )
        ChatSession.objects.create(user=registered_user, title="Zain's Trip")
        ChatSession.objects.create(user=other_user, title="Other's Trip")

        api_client.force_authenticate(user=registered_user)
        response = api_client.get("/api/chat/sessions/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["title"] == "Zain's Trip"

    def test_chat_messages_flow(self, api_client):
        """Test adding messages to a session."""
        session = ChatSession.objects.create(title="Fairy Meadows Trek", is_guest=True)

        # Post user message
        msg_payload = {
            "session": str(session.id),
            "sender": "user",
            "content": "Can I visit Fairy Meadows in late October?",
        }
        response = api_client.post(
            f"/api/chat/sessions/{session.id}/messages/",
            msg_payload,
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["content"] == "Can I visit Fairy Meadows in late October?"

        # Post assistant reply
        reply_payload = {
            "session": str(session.id),
            "sender": "assistant",
            "content": "Late October brings cold weather and potential early snow at Fairy Meadows.",
            "metadata": {"verified_at": "2026-09-03T10:00:00Z"},
        }
        reply_res = api_client.post(
            f"/api/chat/sessions/{session.id}/messages/",
            reply_payload,
            format="json",
        )
        assert reply_res.status_code == status.HTTP_201_CREATED

        # Fetch messages
        list_res = api_client.get(f"/api/chat/sessions/{session.id}/messages/")
        assert list_res.status_code == status.HTTP_200_OK
        assert len(list_res.data) == 2
