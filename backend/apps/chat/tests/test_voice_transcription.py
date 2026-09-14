import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_transcribe_missing_audio_file(api_client):
    url = reverse("chat-transcribe")
    res = api_client.post(url, {}, format="multipart")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.data["error_code"] == "MISSING_AUDIO_FILE"


@pytest.mark.django_db
def test_transcribe_empty_audio_file(api_client):
    url = reverse("chat-transcribe")
    empty_file = SimpleUploadedFile("recording.webm", b"", content_type="audio/webm")
    res = api_client.post(url, {"audio": empty_file}, format="multipart")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.data["error_code"] == "EMPTY_AUDIO_FILE"


@pytest.mark.django_db
def test_transcribe_success(api_client):
    url = reverse("chat-transcribe")
    audio_content = b"\x1a\x45\xdf\xa3" + b"A" * 200  # Mock WebM header and payload
    audio_file = SimpleUploadedFile("recording.webm", audio_content, content_type="audio/webm")

    with patch("services.transcription_service.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "I want to plan a 10 day trek to K2 Base Camp"}
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        res = api_client.post(url, {"audio": audio_file}, format="multipart")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["transcript"] == "I want to plan a 10 day trek to K2 Base Camp"
        assert res.data["text"] == "I want to plan a 10 day trek to K2 Base Camp"


@pytest.mark.django_db
def test_transcribe_no_speech_detected(api_client):
    url = reverse("chat-transcribe")
    audio_content = b"\x1a\x45\xdf\xa3" + b"B" * 200
    audio_file = SimpleUploadedFile("silent.webm", audio_content, content_type="audio/webm")

    with patch("services.transcription_service.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"text": "   "}  # Whitespace only
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        res = api_client.post(url, {"audio": audio_file}, format="multipart")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["error_code"] == "NO_SPEECH_DETECTED"
        assert "No speech was detected" in res.data["detail"]


@pytest.mark.django_db
def test_transcribe_api_failure_handled(api_client):
    url = reverse("chat-transcribe")
    audio_content = b"\x1a\x45\xdf\xa3" + b"C" * 200
    audio_file = SimpleUploadedFile("broken.webm", audio_content, content_type="audio/webm")

    with patch("services.transcription_service.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Groq Error"
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        res = api_client.post(url, {"audio": audio_file}, format="multipart")
        assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert res.data["error_code"] == "TRANSCRIPTION_FAILED"
