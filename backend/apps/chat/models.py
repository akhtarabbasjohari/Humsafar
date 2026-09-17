import uuid
from django.conf import settings
from django.db import models

from django.utils import timezone

class ChatSession(models.Model):
    """Represents a conversation session between a traveler (guest or registered) and Humsafar."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_sessions",
        help_text="Null for guest sessions; linked for registered users.",
    )
    title = models.CharField(max_length=255, default="New Trip Plan")
    is_guest = models.BooleanField(
        default=False,
        help_text="True if this session was initiated by an unauthenticated guest visitor.",
    )
    guest_token = models.CharField(
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text="Ephemeral client-side token scoped to the browser session for guest access verification.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Stores session preferences such as destination region, duration, budget, fitness level.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Chat Session"
        verbose_name_plural = "Chat Sessions"
        ordering = ["-updated_at"]

    def __str__(self):
        owner = self.user.username if self.user else f"Guest ({str(self.id)[:8]})"
        return f"{self.title} - {owner}"

class ChatMessage(models.Model):
    """Individual message in a chat session."""
    SENDER_USER = "user"
    SENDER_ASSISTANT = "assistant"
    SENDER_SYSTEM = "system"
    SENDER_TOOL = "tool"

    SENDER_CHOICES = [
        (SENDER_USER, "User"),
        (SENDER_ASSISTANT, "Assistant"),
        (SENDER_SYSTEM, "System"),
        (SENDER_TOOL, "Tool"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
    content = models.TextField()
    tool_calls = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured tool calls initiated by the model.",
    )
    tool_results = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured tool outputs returned from MCP servers.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Timestamp of live scrape, grounding citations, confidence metrics.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.session_id}] {self.sender}: {self.content[:30]}..."


class ToolCallLog(models.Model):
    """
    Observability log table tracking every tool invocation, itinerary check,
    region check, web search, Ollama preprocessing, and draft generation.
    Enables developers and operators to inspect a session's full tool call chain.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Associated chat session ID (or 'default').",
    )
    skill = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Skill that triggered this call (e.g. itinerary_lookup, region_coverage_check, web_search_fallback, itinerary_drafting, content_cleaning).",
    )
    tool_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Name of the tool or execution step.",
    )
    status = models.CharField(
        max_length=20,
        db_index=True,
        default="success",
        help_text="Outcome status: 'success' or 'failed'.",
    )
    llm_provider = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="LLM provider and model handling this step (e.g. 'ollama:llama3.2:3b', 'groq:openai/gpt-oss-120b', or empty).",
    )
    input_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arguments or input payload for this tool call.",
    )
    output_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Summary or structured result returned by the tool.",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Captured error or exception message if the tool failed.",
    )
    duration_ms = models.FloatField(
        null=True,
        blank=True,
        help_text="Execution duration in milliseconds.",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Timestamp when the tool call was executed.",
    )

    class Meta:
        verbose_name = "Tool Call Log"
        verbose_name_plural = "Tool Call Logs"
        ordering = ["created_at"]

    def __str__(self):
        llm_tag = f" [{self.llm_provider}]" if self.llm_provider else ""
        return f"[{self.created_at.strftime('%H:%M:%S')}] {self.skill}:{self.tool_name}{llm_tag} -> {self.status}"

