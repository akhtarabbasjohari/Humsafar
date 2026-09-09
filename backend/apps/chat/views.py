import re
import secrets
from typing import Optional, Dict, Any
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
from .services.agent_runner import HumsafarAgentRunner


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

        if session.is_guest:
            if user and user.is_authenticated:
                session.user = user
                session.is_guest = False
                session.save(update_fields=["user", "is_guest"])
            elif session.guest_token:
                if not guest_token or session.guest_token != guest_token:
                    raise PermissionDenied("You do not have permission to access this chat session.")
        elif session.user:
            if session.user != user:
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

        if session.is_guest:
            if user and user.is_authenticated:
                session.user = user
                session.is_guest = False
                session.save(update_fields=["user", "is_guest"])
            elif session.guest_token:
                if not guest_token or session.guest_token != guest_token:
                    raise PermissionDenied("You do not have permission to access messages in this chat session.")
        elif session.user:
            if session.user != user:
                raise PermissionDenied("You do not have permission to access messages in this chat session.")

        return session

    def get_queryset(self):
        session = self.get_session()
        return ChatMessage.objects.filter(session=session).order_by("created_at")

    def perform_create(self, serializer):
        session = self.get_session()
        serializer.save(session=session)


def derive_semantic_session_title(user_query: str, itinerary_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Analyze the user's first query and any generated itinerary to assign an intelligent,
    human-readable, and concise title to the chat session.
    """
    if itinerary_data and itinerary_data.get("title"):
        clean_title = re.sub(r"\s+", " ", itinerary_data["title"]).strip()
        if len(clean_title) >= 4:
            return clean_title[:60]

    q_lower = user_query.lower().strip()

    # Destination and region keyword heuristics
    dest_map = {
        "k2": "K2 Base Camp Trek",
        "concordia": "Concordia & Baltoro Expedition",
        "gondogoro": "Gondogoro La Circuit",
        "snow lake": "Snow Lake & Hispar La",
        "broad peak": "Broad Peak Expedition",
        "hunza": "Hunza Valley Journey",
        "skardu": "Skardu & Baltistan Discovery",
        "deosai": "Deosai Plateau Safari",
        "fairy meadows": "Fairy Meadows & Nanga Parbat",
        "nanga parbat": "Nanga Parbat Expedition",
        "swat": "Swat Valley & Kalam Trip",
        "chitral": "Chitral & Kalash Valleys",
        "kalash": "Kalash Cultural Tour",
        "rakaposhi": "Rakaposhi Base Camp",
        "passu": "Passu Cones & Upper Hunza",
        "shimshal": "Shimshal Valley Trek",
    }

    for key, title in dest_map.items():
        if key in q_lower:
            return title

    # Conversational / greeting check
    greetings = ["hello", "hi", "hey", "salaam", "aoa", "good morning", "good afternoon"]
    if any(q_lower.startswith(g) or q_lower == g for g in greetings) and len(q_lower.split()) <= 4:
        return "Travel Inquiry & Planning"

    # General query: extract first 4-5 meaningful words and title case
    stopwords = {"what", "is", "the", "can", "you", "i", "we", "want", "to", "for", "a", "an", "and", "in", "of", "how", "much", "tell", "me", "about", "please"}
    words = [w for w in re.findall(r"[a-zA-Z0-9]+", user_query) if w.lower() not in stopwords]
    if words:
        candidate = " ".join(words[:5]).title()
        if len(candidate) > 40:
            candidate = candidate[:40].rsplit(" ", 1)[0]
        return candidate if len(candidate) >= 3 else "Expedition Planning"

    return "Custom Expedition Plan"


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
        if session.is_guest:
            if user and user.is_authenticated:
                session.user = user
                session.is_guest = False
                session.save(update_fields=["user", "is_guest"])
            elif session.guest_token:
                if not guest_token or session.guest_token != guest_token:
                    return Response({"detail": "You do not have permission to access this chat session."}, status=status.HTTP_403_FORBIDDEN)
        elif session.user and session.user != user:
            return Response({"detail": "You do not have permission to access this chat session."}, status=status.HTTP_403_FORBIDDEN)

        content = request.data.get("message") or request.data.get("content")
        if not content or not str(content).strip():
            return Response({"detail": "Message content cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        content = str(content).strip()

        # 1. Save user message
        user_msg = None
        if session.user:
            user_msg = ChatMessage.objects.create(
                session=session,
                sender=ChatMessage.SENDER_USER,
                content=content,
            )
        else:
            import uuid as uuid_module
            now_str = timezone.now().isoformat()
            user_msg_data = {
                "id": str(uuid_module.uuid4()),
                "session": str(session.id),
                "sender": "user",
                "content": content,
                "tool_calls": [],
                "tool_results": [],
                "metadata": {},
                "created_at": now_str,
            }

        # 2. Retrieve all conversation history for in-context memory
        if user_msg:
            all_messages = [
                {"role": m.sender, "content": m.content}
                for m in ChatMessage.objects.filter(session=session).exclude(id=user_msg.id).order_by("created_at")
            ]
        else:
            all_messages = [
                {"role": m.sender, "content": m.content}
                for m in ChatMessage.objects.filter(session=session).order_by("created_at")
            ]

        # 3. Run multi-hop pipeline through HumsafarAgentRunner
        runner = HumsafarAgentRunner()
        pipeline_result = runner.run_multi_hop_pipeline(
            user_message=content,
            session_id=str(session.id),
            conversation_history=all_messages,
        )

        presented_text = pipeline_result.get("reply_text", "")
        itinerary_data = pipeline_result.get("itinerary")
        confidence_label = pipeline_result.get("confidence_label")
        reasoning_steps = pipeline_result.get("reasoning_steps", [])

        # 3. If itinerary was drafted, create or update draft SavedItinerary record
        itinerary_id = None
        if itinerary_data and (itinerary_data.get("is_draft") or pipeline_result.get("path") == "web_search_draft"):
            if session.user:
                from apps.itineraries.models import SavedItinerary
                itinerary_obj, _ = SavedItinerary.objects.update_or_create(
                    session=session,
                    status=SavedItinerary.STATUS_DRAFT,
                    defaults={
                        "user": session.user if session.user else None,
                        "title": itinerary_data.get("title", session.title or "Custom Expedition Draft"),
                        "region": itinerary_data.get("region", "Northern Pakistan"),
                        "duration_days": itinerary_data.get("duration_days", 7),
                        "itinerary_data": itinerary_data,
                        "source_url": pipeline_result.get("source_url") or itinerary_data.get("source_url", "https://visitpakistan.gov.pk"),
                        "source_verified_at": timezone.now(),
                        "confidence_label": confidence_label or "researched just now, unverified, please confirm with our team",
                        "status": SavedItinerary.STATUS_DRAFT,
                        "is_approved_by_user": False,
                    }
                )
                itinerary_id = str(itinerary_obj.id)
                itinerary_data["id"] = itinerary_id
            else:
                import uuid as uuid_module
                itinerary_id = str(uuid_module.uuid4())
                itinerary_data["id"] = itinerary_id

        # 4. Save assistant message with metadata
        meta = {
            "path": pipeline_result.get("path"),
            "confidence_label": confidence_label,
            "source_url": pipeline_result.get("source_url"),
            "reasoning_steps": reasoning_steps,
            "itinerary": itinerary_data,
            "itinerary_id": itinerary_id,
        }
        
        if session.user:
            assistant_msg = ChatMessage.objects.create(
                session=session,
                sender=ChatMessage.SENDER_ASSISTANT,
                content=presented_text,
                metadata=meta,
            )
            assistant_msg_data = ChatMessageSerializer(assistant_msg).data
            user_msg_dict = ChatMessageSerializer(user_msg).data
        else:
            import uuid as uuid_module
            assistant_msg_data = {
                "id": str(uuid_module.uuid4()),
                "session": str(session.id),
                "sender": "assistant",
                "content": presented_text,
                "tool_calls": [],
                "tool_results": [],
                "metadata": meta,
                "created_at": now_str,
            }
            user_msg_dict = user_msg_data

        # 5. Update session title if generic or first message
        if session.user:
            generic_titles = ["New Chat", "New Trip Plan", "Trip Planning Session", "Custom Expedition Plan", "New Expedition Plan"]
            if session.title in generic_titles or session.messages.count() <= 2:
                new_title = derive_semantic_session_title(content, itinerary_data)
                if new_title and new_title != session.title:
                    session.title = new_title[:100]
                    session.save(update_fields=["title"])

        return Response(
            {
                "user_message": user_msg_dict,
                "assistant_message": assistant_msg_data,
                "itinerary": itinerary_data,
                "itinerary_id": itinerary_id,
                "confidence_label": confidence_label,
                "reasoning_steps": reasoning_steps,
                "session_title": session.title,
                "session_id": str(session.id),
                "approval_status": "draft" if itinerary_id else None,
                "is_approved": False,
            },
            status=status.HTTP_200_OK,
        )


class ChatItineraryRedraftView(APIView):
    """
    Human-in-the-Loop Redraft Endpoint:
    When a visitor asks for changes, redrafts using the same drafting skill with feedback folded in,
    resets approval status in database to draft, and asks for approval again.
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
        if session.is_guest:
            if user and user.is_authenticated:
                session.user = user
                session.is_guest = False
                session.save(update_fields=["user", "is_guest"])
            elif session.guest_token:
                if not guest_token or session.guest_token != guest_token:
                    return Response({"detail": "You do not have permission to access this chat session."}, status=status.HTTP_403_FORBIDDEN)
        elif session.user and session.user != user:
            return Response({"detail": "You do not have permission to access this chat session."}, status=status.HTTP_403_FORBIDDEN)

        feedback = request.data.get("feedback") or request.data.get("message") or request.data.get("content")
        if not feedback or not str(feedback).strip():
            return Response({"detail": "Feedback for redrafting cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        feedback = str(feedback).strip()
        itinerary_id = request.data.get("itinerary_id")
        current_itinerary = request.data.get("current_itinerary")

        # 1. Save user change request message
        user_msg = None
        if session.user:
            user_msg = ChatMessage.objects.create(
                session=session,
                sender=ChatMessage.SENDER_USER,
                content=f"Request changes: {feedback}",
            )
        else:
            import uuid as uuid_module
            now_str = timezone.now().isoformat()
            user_msg_data = {
                "id": str(uuid_module.uuid4()),
                "session": str(session.id),
                "sender": "user",
                "content": f"Request changes: {feedback}",
                "tool_calls": [],
                "tool_results": [],
                "metadata": {},
                "created_at": now_str,
            }

        # 2. Retrieve all prior messages in session for in-context conversation memory
        if user_msg:
            all_messages = [
                {"role": m.sender, "content": m.content}
                for m in ChatMessage.objects.filter(session=session).exclude(id=user_msg.id).order_by("created_at")
            ]
        else:
            all_messages = [
                {"role": m.sender, "content": m.content}
                for m in ChatMessage.objects.filter(session=session).order_by("created_at")
            ]

        # 3. Invoke redrafting skill on HumsafarAgentRunner
        runner = HumsafarAgentRunner()
        redraft_result = runner.redraft_itinerary(
            session_id=str(session.id),
            feedback=feedback,
            conversation_history=all_messages,
            current_itinerary=current_itinerary,
        )

        presented_text = redraft_result.get("reply_text", "")
        itinerary_data = redraft_result.get("itinerary")
        confidence_label = redraft_result.get("confidence_label")
        reasoning_steps = redraft_result.get("reasoning_steps", [])

        # 4. Save or update SavedItinerary record in draft state
        if session.user:
            from apps.itineraries.models import SavedItinerary

            target_itinerary = None
            if itinerary_id:
                try:
                    target_itinerary = SavedItinerary.objects.get(id=itinerary_id)
                except SavedItinerary.DoesNotExist:
                    pass

            if not target_itinerary:
                target_itinerary = SavedItinerary.objects.filter(session=session).order_by("-updated_at").first()

            if target_itinerary:
                target_itinerary.title = itinerary_data.get("title", target_itinerary.title)
                target_itinerary.region = itinerary_data.get("region", target_itinerary.region)
                target_itinerary.duration_days = itinerary_data.get("duration_days", target_itinerary.duration_days)
                target_itinerary.itinerary_data = itinerary_data
                target_itinerary.status = SavedItinerary.STATUS_DRAFT
                target_itinerary.is_approved_by_user = False
                target_itinerary.approval_timestamp = None
                target_itinerary.notes = f"{target_itinerary.notes}\n[Traveler Feedback]: {feedback}".strip()
                target_itinerary.source_verified_at = timezone.now()
                target_itinerary.save()
                itinerary_id = str(target_itinerary.id)
                itinerary_data["id"] = itinerary_id
            else:
                new_draft = SavedItinerary.objects.create(
                    user=session.user if session.user else None,
                    session=session,
                    title=itinerary_data.get("title", session.title or "Custom Expedition Draft"),
                    region=itinerary_data.get("region", "Northern Pakistan"),
                    duration_days=itinerary_data.get("duration_days", 7),
                    itinerary_data=itinerary_data,
                    source_url=redraft_result.get("source_url") or "https://visitpakistan.gov.pk",
                    source_verified_at=timezone.now(),
                    confidence_label=confidence_label or "researched just now, unverified, please confirm with our team",
                    status=SavedItinerary.STATUS_DRAFT,
                    is_approved_by_user=False,
                    notes=f"[Traveler Feedback]: {feedback}",
                )
                itinerary_id = str(new_draft.id)
                itinerary_data["id"] = itinerary_id
        else:
            import uuid as uuid_module
            itinerary_id = str(uuid_module.uuid4())
            if itinerary_data:
                itinerary_data["id"] = itinerary_id

        # 5. Save assistant message with metadata
        meta = {
            "path": "web_search_draft",
            "confidence_label": confidence_label,
            "source_url": redraft_result.get("source_url"),
            "reasoning_steps": reasoning_steps,
            "itinerary": itinerary_data,
            "itinerary_id": itinerary_id,
            "is_redraft": True,
            "is_approved_by_user": False,
        }
        if session.user:
            assistant_msg = ChatMessage.objects.create(
                session=session,
                sender=ChatMessage.SENDER_ASSISTANT,
                content=presented_text,
                metadata=meta,
            )
            assistant_msg_data = ChatMessageSerializer(assistant_msg).data
            user_msg_dict = ChatMessageSerializer(user_msg).data
        else:
            import uuid as uuid_module
            assistant_msg_data = {
                "id": str(uuid_module.uuid4()),
                "session": str(session.id),
                "sender": "assistant",
                "content": presented_text,
                "tool_calls": [],
                "tool_results": [],
                "metadata": meta,
                "created_at": now_str,
            }
            user_msg_dict = user_msg_data

        return Response(
            {
                "user_message": user_msg_dict,
                "assistant_message": assistant_msg_data,
                "itinerary": itinerary_data,
                "itinerary_id": itinerary_id,
                "confidence_label": confidence_label,
                "reasoning_steps": reasoning_steps,
                "session_title": session.title,
                "session_id": str(session.id),
                "approval_status": "draft",
                "is_approved": False,
            },
            status=status.HTTP_200_OK,
        )


class ObservabilityLogsAPIView(APIView):
    """
    Queryable endpoint exposing an execution session's full tool call chain.
    Accepts:
    - session_id in URL (/api/chat/sessions/<session_id>/observability/)
    - or session_id query parameter (/api/chat/observability/logs/?session_id=<session_id>)
    - optional filters: skill, status, limit
    """
    permission_classes = [AllowAny]

    def get(self, request, session_id=None):
        target_session = str(session_id) if session_id else request.query_params.get("session_id", "").strip()
        skill_filter = request.query_params.get("skill", "").strip()
        status_filter = request.query_params.get("status", "").strip()
        try:
            limit = int(request.query_params.get("limit", 100))
        except (TypeError, ValueError):
            limit = 100

        from .models import ToolCallLog

        qs = ToolCallLog.objects.all().order_by("created_at")
        if target_session:
            qs = qs.filter(session_id=target_session)
        if skill_filter:
            qs = qs.filter(skill=skill_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)

        logs = list(qs[:limit])

        chain = [
            {
                "id": str(log.id),
                "session_id": log.session_id,
                "timestamp": log.created_at.isoformat(),
                "skill": log.skill,
                "tool_name": log.tool_name,
                "status": log.status,
                "llm_provider": log.llm_provider or None,
                "duration_ms": log.duration_ms,
                "input": log.input_data,
                "output": log.output_data,
                "error_message": log.error_message,
            }
            for log in logs
        ]

        return Response(
            {
                "session_id": target_session or "all",
                "total_logs": len(chain),
                "chain": chain,
            },
            status=status.HTTP_200_OK,
        )


class ObservabilityDashboardView(APIView):
    """
    Minimal internal HTML dashboard view so engineers and operators can visually
    inspect a session's full tool call chain during development and testing.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        target_session = request.query_params.get("session_id", "").strip()
        from .models import ToolCallLog
        from django.http import HttpResponse
        import json

        qs = ToolCallLog.objects.all().order_by("-created_at")
        if target_session:
            qs = qs.filter(session_id=target_session)
        logs = list(qs[:100])

        rows_html = ""
        for log in logs:
            status_badge = (
                '<span style="background: #10B981; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">SUCCESS</span>'
                if log.status == "success"
                else '<span style="background: #EF4444; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">FAILED</span>'
            )
            llm_badge = (
                f'<span style="background: #E0E7FF; color: #3730A3; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 500;">{log.llm_provider}</span>'
                if log.llm_provider
                else '<span style="color: #9CA3AF; font-size: 11px;">—</span>'
            )
            duration_text = f"{log.duration_ms:.1f} ms" if log.duration_ms is not None else "—"

            in_json = json.dumps(log.input_data, indent=2)
            out_json = json.dumps(log.output_data, indent=2)
            err_html = f'<div style="color: #DC2626; font-size: 11px; margin-top: 4px;">{log.error_message}</div>' if log.error_message else ""

            rows_html += f"""
            <tr style="border-bottom: 1px solid #E5E7EB; font-size: 13px;">
                <td style="padding: 10px 12px; white-space: nowrap; color: #6B7280;">{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td>
                <td style="padding: 10px 12px; font-family: monospace; font-size: 11px;">{log.session_id[:8]}...</td>
                <td style="padding: 10px 12px; font-weight: 600; color: #0F2C3E;">{log.skill}</td>
                <td style="padding: 10px 12px; color: #0D9488; font-family: monospace;">{log.tool_name}</td>
                <td style="padding: 10px 12px;">{llm_badge}</td>
                <td style="padding: 10px 12px; text-align: center;">{status_badge}</td>
                <td style="padding: 10px 12px; text-align: right; color: #4B5563;">{duration_text}</td>
                <td style="padding: 10px 12px;">
                    <details>
                        <summary style="cursor: pointer; color: #0D9488; font-size: 12px;">View Payload</summary>
                        <div style="background: #F9FAFB; padding: 8px; border-radius: 4px; margin-top: 4px; font-size: 11px; max-height: 200px; overflow-y: auto;">
                            <strong>Input:</strong><pre style="margin: 2px 0;">{in_json}</pre>
                            <strong>Output:</strong><pre style="margin: 2px 0;">{out_json}</pre>
                            {err_html}
                        </div>
                    </details>
                </td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Humsafar — Tool Call Observability Chain</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #F8FAFC; color: #1E293B; margin: 0; padding: 24px;">
    <div style="max-width: 1200px; margin: 0 auto;">
        <div style="background: #0F2C3E; color: white; padding: 20px 24px; border-radius: 8px 8px 0 0; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="margin: 0; font-size: 20px; font-weight: 700; color: #FFFFFF;">Humsafar Observability Dashboard</h1>
                <p style="margin: 4px 0 0 0; font-size: 12px; color: #94A3B8;">Real-time Tool Call Chain & LLM Attribution Inspector (Phase 10)</p>
            </div>
            <div style="font-size: 12px; color: #0D9488; background: #08212D; padding: 6px 12px; border-radius: 6px;">
                Total Traced: <strong>{len(logs)}</strong>
            </div>
        </div>
        <div style="background: white; padding: 16px 24px; border: 1px solid #E2E8F0; border-top: none; display: flex; gap: 12px; align-items: center;">
            <form method="get" action="" style="display: flex; gap: 8px; width: 100%;">
                <input type="text" name="session_id" value="{target_session}" placeholder="Filter by session ID (e.g. 81a6c4b2-...)" style="flex: 1; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 6px; font-size: 13px;" />
                <button type="submit" style="background: #0D9488; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer;">Inspect Session</button>
                {f'<a href="?" style="display: inline-flex; align-items: center; padding: 8px 12px; color: #64748B; text-decoration: none; font-size: 13px;">Clear Filter</a>' if target_session else ''}
            </form>
        </div>
        <div style="background: white; border: 1px solid #E2E8F0; border-top: none; border-radius: 0 0 8px 8px; overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="background: #F1F5F9; border-bottom: 2px solid #E2E8F0; font-size: 12px; color: #475569; text-transform: uppercase;">
                        <th style="padding: 10px 12px;">Timestamp (UTC)</th>
                        <th style="padding: 10px 12px;">Session</th>
                        <th style="padding: 10px 12px;">Skill</th>
                        <th style="padding: 10px 12px;">Tool / Step</th>
                        <th style="padding: 10px 12px;">LLM Provider</th>
                        <th style="padding: 10px 12px; text-align: center;">Status</th>
                        <th style="padding: 10px 12px; text-align: right;">Latency</th>
                        <th style="padding: 10px 12px;">Payload</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="8" style="padding: 32px; text-align: center; color: #94A3B8;">No tool execution logs found.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""
        return HttpResponse(html, content_type="text/html")

