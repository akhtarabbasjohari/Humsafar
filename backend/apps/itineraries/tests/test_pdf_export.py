import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.itineraries.models import SavedItinerary
from services.pdf_service import generate_itinerary_pdf

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user():
    return User.objects.create_user(
        username="pdf_traveler",
        email="pdf_traveler@askoliadventure.com",
        password="ValidPassword123!",
    )


@pytest.fixture
def sample_itinerary_payload():
    return {
        "title": "K2 Base Camp & Concordia Trek",
        "region": "Gilgit-Baltistan",
        "duration_days": 14,
        "estimated_price_pkr": "385,000",
        "confidence_label": "from our official listing",
        "day_by_day": [
            {"day": 1, "title": "Arrival in Islamabad", "description": "Expedition briefing and orientation.", "altitude": "540m"},
            {"day": 2, "title": "Fly Islamabad to Skardu", "description": "Spectacular flight over Nanga Parbat.", "altitude": "2,230m"},
            {"day": 3, "title": "Skardu to Askole", "description": "4x4 Jeep transfer to roadhead.", "altitude": "3,000m"},
        ],
        "inclusions": [
            "Licensed high-altitude mountain guide",
            "Balti porters and camp cook",
            "All camp meals and 2-person tents",
        ],
        "exclusions": [
            "International flights and visa fees",
            "Personal mountain equipment",
        ],
        "equipment": [
            "Sturdy high-altitude trekking boots",
            "4-season sleeping bag (-15°C)",
        ],
    }


def test_pdf_generation_binary_output(sample_itinerary_payload):
    pdf_bytes = generate_itinerary_pdf(sample_itinerary_payload)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    # Must start with standard PDF header
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.django_db
def test_export_pdf_endpoint_success(api_client, sample_itinerary_payload):
    url = reverse("itinerary-export-pdf")
    res = api_client.post(url, sample_itinerary_payload, format="json")
    assert res.status_code == status.HTTP_200_OK
    assert res["Content-Type"] == "application/pdf"
    assert "attachment; filename=" in res["Content-Disposition"]
    assert len(res.content) > 500
    assert res.content.startswith(b"%PDF-")


@pytest.mark.django_db
def test_export_pdf_missing_payload(api_client):
    url = reverse("itinerary-export-pdf")
    res = api_client.post(url, {}, format="json")
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.data["error_code"] == "MISSING_PAYLOAD"


@pytest.mark.django_db
def test_download_saved_itinerary_pdf_by_id(api_client, test_user, sample_itinerary_payload):
    api_client.force_authenticate(user=test_user)
    saved = SavedItinerary.objects.create(
        user=test_user,
        title="Spantik Peak Expedition",
        region="Karakoram",
        duration_days=21,
        itinerary_data=sample_itinerary_payload,
        confidence_label="from our official listing",
        source_url="https://askoliadventure.com/expeditions/spantik/",
    )

    url = reverse("itinerary-detail-pdf", kwargs={"id": saved.id})
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK
    assert res["Content-Type"] == "application/pdf"
    assert "attachment; filename=" in res["Content-Disposition"]
    assert res.content.startswith(b"%PDF-")


@pytest.mark.django_db
def test_download_saved_itinerary_cross_user_forbidden(api_client, test_user, sample_itinerary_payload):
    other_user = User.objects.create_user(
        username="other_traveler",
        email="other@askoliadventure.com",
        password="ValidPassword123!",
    )
    saved = SavedItinerary.objects.create(
        user=other_user,
        title="Secret Route",
        region="Chitral",
        duration_days=5,
        itinerary_data=sample_itinerary_payload,
        source_url="https://askoliadventure.com",
    )

    api_client.force_authenticate(user=test_user)
    url = reverse("itinerary-detail-pdf", kwargs={"id": saved.id})
    res = api_client.get(url)
    assert res.status_code == status.HTTP_403_FORBIDDEN
