"""
Unit tests for Authentication & Authorization Gating in Chat Sessions.
Enforces:
- Guest single-session limit
- Authenticated user multiple sessions
- Session isolation & ownership authorization (403 on cross-user access)
- Session deletion by owner
- Claiming guest session upon login
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatMessage, ChatSession


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_a(db):
    return User.objects.create_user(
        username="traveler_ali",
        email="ali@example.com",
        password="Password123!",
    )


@pytest.fixture
def user_b(db):
    return User.objects.create_user(
        username="traveler_zara",
        email="zara@example.com",
        password="Password123!",
    )


@pytest.mark.django_db
class TestChatAuthGating:
    def test_guest_limited_to_single_session(self, api_client):
        """Unauthenticated guest is limited to a single active session."""
        guest_headers = {"HTTP_X_GUEST_TOKEN": "guest_token_abc123"}
        
        # First session creation succeeds
        res1 = api_client.post(
            "/api/chat/sessions/",
            {"title": "Guest Autumn Plan"},
            format="json",
            **guest_headers,
        )
        assert res1.status_code == status.HTTP_201_CREATED
        session_id = res1.data["id"]

        # Second session creation returns existing session
        res2 = api_client.post(
            "/api/chat/sessions/",
            {"title": "Second Chat Attempt"},
            format="json",
            **guest_headers,
        )
        assert res2.status_code == status.HTTP_200_OK
        assert res2.data["id"] == session_id

        # Forcing a new chat as guest is rejected with 403
        res3 = api_client.post(
            "/api/chat/sessions/",
            {"title": "Force New Chat", "force_new": True},
            format="json",
            **guest_headers,
        )
        assert res3.status_code == status.HTTP_403_FORBIDDEN
        assert res3.data["error_code"] == "MULTIPLE_CHATS_REQUIRE_AUTH"

    def test_authenticated_user_creates_multiple_sessions(self, api_client, user_a):
        """Logged-in member can create multiple distinct chat sessions and list all."""
        api_client.force_authenticate(user=user_a)

        res1 = api_client.post("/api/chat/sessions/", {"title": "Hunza Autumn Trek"}, format="json")
        assert res1.status_code == status.HTTP_201_CREATED

        res2 = api_client.post("/api/chat/sessions/", {"title": "K2 Base Camp Expedition"}, format="json")
        assert res2.status_code == status.HTTP_201_CREATED

        res3 = api_client.post("/api/chat/sessions/", {"title": "Swat Valley Cultural Tour"}, format="json")
        assert res3.status_code == status.HTTP_201_CREATED

        list_res = api_client.get("/api/chat/sessions/")
        assert list_res.status_code == status.HTTP_200_OK
        assert len(list_res.data) == 3
        titles = [s["title"] for s in list_res.data]
        assert "Hunza Autumn Trek" in titles
        assert "K2 Base Camp Expedition" in titles
        assert "Swat Valley Cultural Tour" in titles

    def test_session_ownership_cross_access_forbidden(self, api_client, user_a, user_b):
        """Strict authorization: User B cannot access, read, send messages to, or delete User A's session."""
        session_a = ChatSession.objects.create(user=user_a, title="Ali's Private Trip", is_guest=False)
        ChatMessage.objects.create(session=session_a, sender="user", content="Secret travel plan")

        api_client.force_authenticate(user=user_b)

        # 1. Detail view access forbidden
        get_res = api_client.get(f"/api/chat/sessions/{session_a.id}/")
        assert get_res.status_code == status.HTTP_403_FORBIDDEN

        # 2. Messages list forbidden
        msgs_res = api_client.get(f"/api/chat/sessions/{session_a.id}/messages/")
        assert msgs_res.status_code == status.HTTP_403_FORBIDDEN

        # 3. Send message forbidden
        send_res = api_client.post(
            f"/api/chat/sessions/{session_a.id}/send/",
            {"message": "Intruding into session"},
            format="json",
        )
        assert send_res.status_code == status.HTTP_403_FORBIDDEN

        # 4. Deletion forbidden
        del_res = api_client.delete(f"/api/chat/sessions/{session_a.id}/")
        assert del_res.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_delete_session(self, api_client, user_a):
        """Session owner can delete their chat session."""
        api_client.force_authenticate(user=user_a)
        session = ChatSession.objects.create(user=user_a, title="To Be Deleted")

        del_res = api_client.delete(f"/api/chat/sessions/{session.id}/")
        assert del_res.status_code == status.HTTP_204_NO_CONTENT
        assert not ChatSession.objects.filter(id=session.id).exists()

    def test_claim_guest_session_upon_login(self, api_client, user_a):
        """Logged-in member can claim a guest session and migrate history."""
        guest_session = ChatSession.objects.create(
            title="Guest Initial Route",
            is_guest=True,
            guest_token="guest_token_123",
        )
        ChatMessage.objects.create(session=guest_session, sender="user", content="Guest route query")

        api_client.force_authenticate(user=user_a)
        claim_res = api_client.post(
            "/api/chat/sessions/claim/",
            {"session_id": str(guest_session.id), "guest_token": "guest_token_123"},
            format="json",
        )
        assert claim_res.status_code == status.HTTP_200_OK
        assert claim_res.data["is_guest"] is False
        assert str(claim_res.data["user"]) == str(user_a.id)

        # Refresh from database
        guest_session.refresh_from_db()
        assert guest_session.user == user_a
        assert guest_session.is_guest is False
