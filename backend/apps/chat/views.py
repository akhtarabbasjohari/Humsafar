import secrets
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import ChatMessage, ChatSession
from .serializers import (
    ChatMessageSerializer,
    ChatSessionCreateSerializer,
    ChatSessionSerializer,
)

class ChatSessionListCreateView(generics.ListCreateAPIView):
    """List chat sessions or create a new one.
    
    Default Guest Mode: Unauthenticated visitors can create sessions freely.
    Authenticated users have their sessions automatically scoped to their account.
    """
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ChatSessionCreateSerializer
        return ChatSessionSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return ChatSession.objects.filter(user=user)
        
        # Guest mode: optionally filter by guest_token header/query parameter
        guest_token = self.request.headers.get("X-Guest-Token") or self.request.query_params.get("guest_token")
        if guest_token:
            return ChatSession.objects.filter(is_guest=True, guest_token=guest_token)
        return ChatSession.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated:
            serializer.save(user=user, is_guest=False)
        else:
            # Guest mode: generate ephemeral session token
            guest_token = secrets.token_urlsafe(32)
            serializer.save(user=None, is_guest=True, guest_token=guest_token)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output_serializer = ChatSessionSerializer(serializer.instance)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

class ChatSessionDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a specific chat session."""
    permission_classes = [AllowAny]
    serializer_class = ChatSessionSerializer
    queryset = ChatSession.objects.all()
    lookup_field = "id"

    def get_object(self):
        session = super().get_object()
        user = self.request.user
        if session.user and session.user != user:
            raise PermissionDenied("You do not have permission to access this chat session.")
        return session

class ChatMessageListCreateView(generics.ListCreateAPIView):
    """List messages for a session or append a new message."""
    permission_classes = [AllowAny]
    serializer_class = ChatMessageSerializer

    def get_queryset(self):
        session_id = self.kwargs.get("session_id")
        return ChatMessage.objects.filter(session_id=session_id)

    def perform_create(self, serializer):
        session_id = self.kwargs.get("session_id")
        session = ChatSession.objects.get(id=session_id)
        serializer.save(session=session)
