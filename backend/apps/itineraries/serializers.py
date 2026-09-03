from rest_framework import serializers
from .models import SavedItinerary

class SavedItinerarySerializer(serializers.ModelSerializer):
    """Serializer for saved itineraries with HITL and freshness metadata."""
    class Meta:
        model = SavedItinerary
        fields = (
            "id",
            "user",
            "session",
            "title",
            "region",
            "duration_days",
            "status",
            "is_approved_by_user",
            "approval_timestamp",
            "itinerary_data",
            "source_verified_at",
            "source_url",
            "confidence_label",
            "estimated_price_pkr",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "user",
            "is_approved_by_user",
            "approval_timestamp",
            "created_at",
            "updated_at",
        )

class ItineraryApprovalSerializer(serializers.Serializer):
    """Serializer to handle explicit traveler approval of a drafted itinerary (HITL)."""
    approved = serializers.BooleanField(required=True)
    feedback_or_notes = serializers.CharField(required=False, allow_blank=True, default="")
