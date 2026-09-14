import io
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from apps.chat.models import ChatSession
from services.document_service import (
    CONFIDENCE_LABEL_DOCUMENT,
    detect_file_type_from_bytes,
    DocumentValidationError,
    get_session_documents,
    _EPHEMERAL_DOCUMENTS,
)

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user():
    return User.objects.create_user(
        username="traveler_phase13",
        email="traveler13@askoliadventure.com",
        password="ValidPassword123!",
    )


@pytest.fixture
def guest_session():
    return ChatSession.objects.create(
        is_guest=True,
        guest_token="guest_token_12345",
        title="Guest Planning",
    )


@pytest.fixture
def user_session(test_user):
    return ChatSession.objects.create(
        user=test_user,
        is_guest=False,
        title="Member Mountain Expedition",
    )


@pytest.mark.django_db
def test_magic_byte_detection():
    # Valid PDF
    assert detect_file_type_from_bytes(b"%PDF-1.4 header text") == "application/pdf"

    # Valid PNG
    assert detect_file_type_from_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") == "image/png"

    # Valid JPEG
    assert detect_file_type_from_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"

    # Valid WEBP
    assert detect_file_type_from_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"

    # Valid Plain text
    assert detect_file_type_from_bytes(b"Flight PK605 Islamabad to Skardu on July 15") == "text/plain"

    # Invalid / Unsupported binary
    with pytest.raises(DocumentValidationError):
        detect_file_type_from_bytes(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00")

    # Empty file
    with pytest.raises(DocumentValidationError):
        detect_file_type_from_bytes(b"")


@pytest.mark.django_db
def test_upload_missing_session_or_file(api_client):
    url = reverse("chat-document-upload")
    res = api_client.post(url, {}, format="multipart")
    assert res.status_code == status.HTTP_400_BAD_REQUEST

    file = SimpleUploadedFile("notes.txt", b"Flight details", content_type="text/plain")
    res = api_client.post(url, {"file": file}, format="multipart")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.data["error_code"] == "MISSING_SESSION_ID"


@pytest.mark.django_db
def test_upload_plain_text_document_guest_ephemeral(api_client, guest_session):
    url = reverse("chat-document-upload")
    content = b"PIA Flight PK-451: Islamabad to Skardu. Departure: July 12, 2026. Passenger: Akhtar Abbas."
    file = SimpleUploadedFile("flight_ticket.txt", content, content_type="text/plain")

    res = api_client.post(
        url,
        {"file": file, "session_id": str(guest_session.id), "guest_token": guest_session.guest_token},
        format="multipart",
    )

    assert res.status_code == status.HTTP_200_OK
    assert res.data["success"] is True
    assert res.data["confidence_label"] == CONFIDENCE_LABEL_DOCUMENT
    doc = res.data["document"]
    assert doc["filename"] == "flight_ticket.txt"
    assert doc["mime_type"] == "text/plain"
    assert "Islamabad to Skardu" in doc["distilled_content"] or "PK-451" in doc["distilled_content"]

    # Verify stored in ephemeral cache
    docs = get_session_documents(str(guest_session.id))
    assert len(docs) >= 1
    assert docs[0]["filename"] == "flight_ticket.txt"


@pytest.mark.django_db
def test_upload_persisted_for_authenticated_user(api_client, test_user, user_session):
    api_client.force_authenticate(user=test_user)
    url = reverse("chat-document-upload")
    content = b"Hotel Shangrila Resort Skardu Booking Confirmation. Dates: July 15 to July 20. 2 Guests."
    file = SimpleUploadedFile("hotel_voucher.txt", content, content_type="text/plain")

    res = api_client.post(
        url,
        {"file": file, "session_id": str(user_session.id)},
        format="multipart",
    )

    assert res.status_code == status.HTTP_200_OK
    user_session.refresh_from_db()
    assert "uploaded_documents" in user_session.metadata
    stored_docs = user_session.metadata["uploaded_documents"]
    assert len(stored_docs) == 1
    assert stored_docs[0]["filename"] == "hotel_voucher.txt"
    assert stored_docs[0]["confidence_label"] == CONFIDENCE_LABEL_DOCUMENT


@pytest.mark.django_db
def test_upload_exceeding_10mb_rejected(api_client, guest_session):
    url = reverse("chat-document-upload")
    # Simulate oversized file header > 10MB
    with patch("services.document_service.MAX_UPLOAD_SIZE_BYTES", 500):
        oversized_content = b"A" * 600
        file = SimpleUploadedFile("huge_file.txt", oversized_content, content_type="text/plain")
        res = api_client.post(
            url,
            {
                "file": file,
                "session_id": str(guest_session.id),
                "guest_token": guest_session.guest_token,
            },
            format="multipart",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["error_code"] == "VALIDATION_FAILED"


@pytest.mark.django_db
def test_chat_message_send_uses_uploaded_document_label(api_client, test_user, user_session):
    api_client.force_authenticate(user=test_user)

    # 1. Upload document
    upload_url = reverse("chat-document-upload")
    content = b"K2 Trekking Itinerary from previous guide: Day 1 Islamabad, Day 2 Skardu, Day 3 Askole."
    file = SimpleUploadedFile("previous_plan.txt", content, content_type="text/plain")
    api_client.post(upload_url, {"file": file, "session_id": str(user_session.id)}, format="multipart")

    # 2. Send chat message referencing the document
    send_url = reverse("chat-message-send", kwargs={"session_id": user_session.id})

    with patch("apps.chat.services.agent_runner.HumsafarAgentRunner.run_multi_hop_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {
            "path": "custom_draft",
            "reply_text": "I reviewed your uploaded itinerary from previous guide.",
            "itinerary": {
                "title": "Adapted Karakoram Trek",
                "days": "7 Days",
                "confidence_label": CONFIDENCE_LABEL_DOCUMENT,
            },
            "confidence_label": CONFIDENCE_LABEL_DOCUMENT,
            "source_url": "from your uploaded document",
            "reasoning_steps": [],
        }

        res = api_client.post(send_url, {"content": "Can you review my uploaded document and plan around it?"})
        assert res.status_code == status.HTTP_200_OK
        assert res.data["confidence_label"] == CONFIDENCE_LABEL_DOCUMENT
        assert res.data["itinerary"]["confidence_label"] == CONFIDENCE_LABEL_DOCUMENT
