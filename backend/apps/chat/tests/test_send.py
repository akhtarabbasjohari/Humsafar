"""
Unit tests for ChatMessageSendView (Phase 5 core chat flow).
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APIClient

from apps.chat.models import ChatMessage, ChatSession


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestChatMessageSendView:
    def test_send_message_simple_itinerary_match(self, api_client):
        """Test sending a message that matches an official tour itinerary."""
        from apps.authentication.models import User
        user = User.objects.create_user(username="send_test_user", password="password123")
        session = ChatSession.objects.create(title="Trip Planning Session", user=user, is_guest=False)
        api_client.force_authenticate(user=user)

        mock_tour = {
            "title": "14-Day K2 & Concordia Classic Trek",
            "duration": "14 Days",
            "price": "PKR 380,000",
            "source_url": "https://askoliadventure.com/tour/k2-concordia-trek/",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "confidence_label": "from our official listing",
            "summary": "Expedition to Concordia and K2 base camp.",
        }

        mock_search_res = {
            "success": True,
            "results": [mock_tour],
            "count": 1,
            "cached": False,
        }

        mock_llm_reply = (
            "Salam! The 14-Day K2 & Concordia Classic Trek is our premier Karakoram expedition, "
            "priced at PKR 380,000 as listed on our official catalog."
        )

        with patch("services.agent_runner.HumsafarAgentRunner.search_itineraries", return_value=mock_search_res), \
             patch("services.groq_service.generate_travel_reply", return_value=mock_llm_reply):

            payload = {"message": "Tell me about the K2 trek"}
            response = api_client.post(
                f"/api/chat/sessions/{session.id}/send/",
                payload,
                format="json",
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.data
            assert "user_message" in data
            assert "assistant_message" in data
            assert data["user_message"]["content"] == "Tell me about the K2 trek"
            assert "14-Day K2 & Concordia Classic Trek" in data["assistant_message"]["content"]
            assert data["confidence_label"] == "from our official listing"
            assert data["itinerary"]["title"] == "14-Day K2 & Concordia Classic Trek"

            # Check database persistence
            messages = ChatMessage.objects.filter(session=session).order_by("created_at")
            assert messages.count() == 2
            assert messages[0].sender == "user"
            assert messages[1].sender == "assistant"
            assert messages[1].metadata["confidence_label"] == "from our official listing"

    def test_send_message_empty_content_rejected(self, api_client):
        session = ChatSession.objects.create(title="Trip", is_guest=True)
        response = api_client.post(
            f"/api/chat/sessions/{session.id}/send/",
            {"message": "   "},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_send_message_invalid_session_not_found(self, api_client):
        import uuid
        random_id = uuid.uuid4()
        response = api_client.post(
            f"/api/chat/sessions/{random_id}/send/",
            {"message": "Hello"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
