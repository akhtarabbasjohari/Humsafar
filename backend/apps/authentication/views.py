import uuid
import secrets
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.chat.models import ChatSession
from .models import User
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

class RegisterView(generics.CreateAPIView):
    """Register a new user and return JWT authentication tokens."""
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens for immediate login
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                "message": "User registered successfully.",
            },
            status=status.HTTP_201_CREATED,
        )

class CustomLoginView(TokenObtainPairView):
    """Log in with username/password and receive JWT tokens with user payload."""
    serializer_class = CustomTokenObtainPairSerializer

class CurrentUserView(APIView):
    """Retrieve currently authenticated user profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GuestSessionInitView(APIView):
    """Initialize an ephemeral guest session for an unauthenticated visitor.
    
    Default mode: An unauthenticated visitor receives an ephemeral guest token
    and a pre-provisioned ChatSession with no persistent account requirement.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        guest_token = secrets.token_urlsafe(32)
        initial_title = request.data.get("title", "New Trip Plan (Guest)")
        metadata = request.data.get("metadata", {})

        session = ChatSession.objects.create(
            user=None,
            is_guest=True,
            guest_token=guest_token,
            title=initial_title,
            metadata=metadata,
        )

        return Response(
            {
                "session_id": str(session.id),
                "guest_token": guest_token,
                "is_guest": True,
                "title": session.title,
                "created_at": session.created_at,
                "message": "Guest session initialized successfully. Session will not persist past the browser session.",
            },
            status=status.HTTP_201_CREATED,
        )
