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


from rest_framework.views import APIView


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
