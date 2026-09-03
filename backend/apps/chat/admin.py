from django.contrib import admin
from .models import ChatMessage, ChatSession

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("sender", "content", "created_at")

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "is_guest", "created_at", "updated_at")
    list_filter = ("is_guest", "created_at")
    search_fields = ("title", "id", "user__username")
    inlines = [ChatMessageInline]

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "sender", "content_preview", "created_at")
    list_filter = ("sender", "created_at")
    search_fields = ("content", "session__id")

    def content_preview(self, obj):
        return obj.content[:50]
    content_preview.short_description = "Content"
