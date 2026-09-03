from rest_framework import serializers
from .models import ChatMessage, ChatSession

class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for individual chat messages."""
    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "session",
            "sender",
            "content",
            "tool_calls",
            "tool_results",
            "metadata",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for chat sessions including recent messages."""
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.IntegerField(source="messages.count", read_only=True)

    class Meta:
        model = ChatSession
        fields = (
            "id",
            "user",
            "title",
            "is_guest",
            "guest_token",
            "metadata",
            "created_at",
            "updated_at",
            "messages",
            "message_count",
        )
        read_only_fields = ("id", "user", "is_guest", "created_at", "updated_at")

class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new chat session."""
    class Meta:
        model = ChatSession
        fields = ("id", "title", "metadata")
