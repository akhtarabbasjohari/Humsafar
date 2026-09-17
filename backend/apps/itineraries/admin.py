from django.contrib import admin
from .models import SavedItinerary

@admin.register(SavedItinerary)
class SavedItineraryAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "region",
        "duration_days",
        "status",
        "is_approved_by_user",
        "user",
        "source_verified_at",
        "created_at",
    )
    list_filter = ("status", "is_approved_by_user", "region", "created_at")
    search_fields = ("title", "region", "user__username", "notes")
    readonly_fields = ("id", "created_at", "updated_at", "approval_timestamp")
