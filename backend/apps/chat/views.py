import secrets
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ChatMessage, ChatSession
from .serializers import (
    ChatMessageSerializer,
    ChatSessionCreateSerializer,
    ChatSessionSerializer,
)


class ChatSessionListCreateView(generics.ListCreateAPIView):
    """List chat sessions or create a new one.
    
    Authorization & Gating:
    - Authenticated users: Can create unlimited sessions and list all their past chats.
    - Unauthenticated guests: Restricted to a single active session associated with their guest_token.
      Attempting to create multiple sessions is gated (returns existing session or 403 on force_new).
    """
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ChatSessionCreateSerializer
        return ChatSessionSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return ChatSession.objects.filter(user=user).order_by("-updated_at")
        
        # Guest mode: optionally filter by guest_token header/query parameter
        guest_token = self.request.headers.get("X-Guest-Token") or self.request.query_params.get("guest_token")
        if guest_token:
            return ChatSession.objects.filter(is_guest=True, guest_token=guest_token).order_by("-updated_at")
        return ChatSession.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        guest_token = request.headers.get("X-Guest-Token") or request.query_params.get("guest_token")

        if not user.is_authenticated:
            # Rule: Unauthenticated visitors are limited to 1 active session
            if guest_token:
                existing_session = ChatSession.objects.filter(is_guest=True, guest_token=guest_token).first()
                if existing_session:
                    if request.data.get("force_new"):
                        return Response(
                            {
                                "detail": "Guest visitors are limited to a single active chat session. Please log in or register to unlock multiple chats.",
                                "error_code": "MULTIPLE_CHATS_REQUIRE_AUTH",
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    return Response(ChatSessionSerializer(existing_session).data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output_serializer = ChatSessionSerializer(serializer.instance)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated:
            serializer.save(user=user, is_guest=False)
        else:
            guest_token = self.request.headers.get("X-Guest-Token") or secrets.token_urlsafe(32)
            serializer.save(user=None, is_guest=True, guest_token=guest_token)


class ChatSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update (title/metadata), or delete a specific chat session."""
    permission_classes = [AllowAny]
    serializer_class = ChatSessionSerializer
    queryset = ChatSession.objects.all()
    lookup_field = "id"

    def get_object(self):
        session = super().get_object()
        user = self.request.user
        guest_token = self.request.headers.get("X-Guest-Token") or self.request.query_params.get("guest_token")

        if session.user:
            if session.user != user:
                raise PermissionDenied("You do not have permission to access this chat session.")
        elif session.is_guest and guest_token:
            if session.guest_token != guest_token:
                raise PermissionDenied("You do not have permission to access this chat session.")
        return session


class ChatSessionClaimView(APIView):
    """
    Claim an active guest session and link it to the newly authenticated user account.
    Migrates the conversation history and any draft itineraries seamlessly.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required to claim a guest session."}, status=status.HTTP_401_UNAUTHORIZED)

        session_id = request.data.get("session_id")
        guest_token = request.data.get("guest_token") or request.headers.get("X-Guest-Token")

        if not session_id:
            return Response({"detail": "session_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(ChatSession, id=session_id)
        if not session.is_guest:
            return Response({"detail": "Session is already an account-linked session."}, status=status.HTTP_400_BAD_REQUEST)

        if guest_token and session.guest_token and session.guest_token != guest_token:
            raise PermissionDenied("Invalid guest token for this session.")

        # Migrate session to authenticated user
        session.user = request.user
        session.is_guest = False
        session.save(update_fields=["user", "is_guest"])

        # Also migrate any saved itineraries created during this session
        from apps.itineraries.models import SavedItinerary
        SavedItinerary.objects.filter(session=session, user=None).update(user=request.user)

        return Response(ChatSessionSerializer(session).data, status=status.HTTP_200_OK)


class ChatMessageListCreateView(generics.ListCreateAPIView):
    """List messages for a session or append a new message with authorization check."""
    permission_classes = [AllowAny]
    serializer_class = ChatMessageSerializer

    def get_session(self):
        session_id = self.kwargs.get("session_id")
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            raise NotFound("Chat session not found.")

        user = self.request.user
        guest_token = self.request.headers.get("X-Guest-Token") or self.request.query_params.get("guest_token")

        if session.user:
            if session.user != user:
                raise PermissionDenied("You do not have permission to access messages in this chat session.")
        elif session.is_guest and guest_token:
            if session.guest_token != guest_token:
                raise PermissionDenied("You do not have permission to access messages in this chat session.")

        return session

    def get_queryset(self):
        session = self.get_session()
        return ChatMessage.objects.filter(session=session).order_by("created_at")

    def perform_create(self, serializer):
        session = self.get_session()
        serializer.save(session=session)


class ChatMessageSendView(APIView):
    """
    Conversational turn endpoint:
    Receives visitor message, searches live itineraries via humsafar-data-mcp,
    synthesizes a grounded response via Groq LLM, enforces Phase 4 data integrity,
    and returns both the user message and verified assistant reply with confidence metadata.
    """
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"detail": "Chat session not found."}, status=status.HTTP_404_NOT_FOUND)

        # Authorization check
        user = request.user
        guest_token = request.headers.get("X-Guest-Token") or request.query_params.get("guest_token")
        if session.user and session.user != user:
            return Response({"detail": "You do not have permission to access this chat session."}, status=status.HTTP_403_FORBIDDEN)
        if session.is_guest and guest_token and session.guest_token != guest_token:
            return Response({"detail": "You do not have permission to access this chat session."}, status=status.HTTP_403_FORBIDDEN)

        content = request.data.get("message") or request.data.get("content")
        if not content or not str(content).strip():
            return Response({"detail": "Message content cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        content = str(content).strip()

        # 1. Save user message
        user_msg = ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.SENDER_USER,
            content=content,
        )

        # 2. Query humsafar-data-mcp for matching itineraries
        from services.agent_runner import agent_runner
        from services.groq_service import generate_travel_reply

        search_result = agent_runner.search_itineraries(query=content, session_id=str(session.id))
        matched_tours = search_result.get("results", [])

        # 3. Retrieve recent conversation history for LLM context
        recent_messages = [
            {"role": m.sender, "content": m.content}
            for m in ChatMessage.objects.filter(session=session).exclude(id=user_msg.id).order_by("created_at")[:6]
        ]

        # 4. Generate grounded reply via Groq LLM
        raw_reply = generate_travel_reply(
            user_message=content,
            conversation_history=recent_messages,
            matched_itineraries=matched_tours,
        )

        # 5. Enforce Phase 4 data integrity & confidence labeling
        primary_tour = matched_tours[0] if matched_tours else None
        grounding_payload = primary_tour if primary_tour else None

        presented = agent_runner.present_to_visitor(
            text=raw_reply,
            grounding_data=grounding_payload,
        )

        # 6. Save assistant message with grounding metadata
        meta = {
            "confidence_label": presented.get("confidence_label"),
            "source_url": presented.get("source_url"),
            "timestamp": presented.get("timestamp"),
            "is_grounded": presented.get("is_grounded", False),
            "itinerary": primary_tour,
        }
        assistant_msg = ChatMessage.objects.create(
            session=session,
            sender=ChatMessage.SENDER_ASSISTANT,
            content=presented["text"],
            metadata=meta,
        )

        # Update session title if generic
        if session.title in ["New Chat", "New Trip Plan", "Trip Planning Session", "Custom Expedition Plan"] and primary_tour:
            session.title = primary_tour.get("title", session.title)[:100]
            session.save(update_fields=["title"])

        return Response(
            {
                "user_message": ChatMessageSerializer(user_msg).data,
                "assistant_message": ChatMessageSerializer(assistant_msg).data,
                "itinerary": primary_tour,
                "confidence_label": presented.get("confidence_label"),
            },
            status=status.HTTP_200_OK,
        )
