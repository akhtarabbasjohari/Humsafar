import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatSession

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="trekker_ali",
        email="ali@example.com",
        password="SecurePassword123!",
    )

@pytest.mark.django_db
class TestAuthentication:
    def test_user_registration_success(self, api_client):
        """Test successful registration returns user and JWT tokens."""
        payload = {
            "username": "fatima_explorer",
            "email": "fatima@example.com",
            "password": "StrongPassword789!",
            "password2": "StrongPassword789!",
        }
        response = api_client.post("/api/auth/register/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "user" in response.data
        assert response.data["user"]["username"] == "fatima_explorer"
        assert response.data["user"]["email"] == "fatima@example.com"
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert User.objects.filter(username="fatima_explorer").exists()

    def test_user_registration_password_mismatch(self, api_client):
        """Test registration fails when passwords do not match."""
        payload = {
            "username": "mismatch_user",
            "email": "mismatch@example.com",
            "password": "Password123!",
            "password2": "DifferentPassword456!",
        }
        response = api_client.post("/api/auth/register/", payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data

    def test_user_registration_with_password_confirm(self, api_client):
        """Test registration succeeds with password_confirm or single password."""
        payload = {
            "username": "karakoram_guide",
            "email": "guide@example.com",
            "password": "StrongPassword999!",
            "password_confirm": "StrongPassword999!",
        }
        response = api_client.post("/api/auth/register/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["username"] == "karakoram_guide"
        assert User.objects.filter(username="karakoram_guide").exists()

    def test_user_login_success(self, api_client, test_user):
        """Test login with valid credentials returns JWT tokens and user payload."""
        payload = {
            "username": "trekker_ali",
            "password": "SecurePassword123!",
        }
        response = api_client.post("/api/auth/login/", payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data
        assert response.data["user"]["id"] == str(test_user.id)
        assert response.data["user"]["username"] == "trekker_ali"

    def test_user_login_invalid_credentials(self, api_client, test_user):
        """Test login fails with incorrect password."""
        payload = {
            "username": "trekker_ali",
            "password": "WrongPassword!",
        }
        response = api_client.post("/api/auth/login/", payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, test_user):
        """Test refreshing an access token using a valid refresh token."""
        login_response = api_client.post(
            "/api/auth/login/",
            {"username": "trekker_ali", "password": "SecurePassword123!"},
            format="json",
        )
        refresh_token = login_response.data["refresh"]

        refresh_response = api_client.post(
            "/api/auth/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        assert refresh_response.status_code == status.HTTP_200_OK
        assert "access" in refresh_response.data

    def test_current_user_me_authenticated(self, api_client, test_user):
        """Test /api/auth/me/ endpoint with Bearer token."""
        api_client.force_authenticate(user=test_user)
        response = api_client.get("/api/auth/me/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == "trekker_ali"
        assert response.data["email"] == "ali@example.com"

    def test_current_user_me_unauthenticated(self, api_client):
        """Test /api/auth/me/ without auth returns 401."""
        response = api_client.get("/api/auth/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_guest_session_initialization(self, api_client):
        """Test guest mode initialization creates an ephemeral session without an account."""
        response = api_client.post(
            "/api/auth/guest/",
            {"title": "Explore Hunza Valley", "metadata": {"region": "Hunza"}},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "session_id" in response.data
        assert "guest_token" in response.data
        assert response.data["is_guest"] is True

        session = ChatSession.objects.get(id=response.data["session_id"])
        assert session.user is None
        assert session.is_guest is True
        assert session.guest_token == response.data["guest_token"]
        assert session.metadata.get("region") == "Hunza"
