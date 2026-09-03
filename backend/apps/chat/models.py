import uuid
from django.conf import settings
from django.db import models

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
