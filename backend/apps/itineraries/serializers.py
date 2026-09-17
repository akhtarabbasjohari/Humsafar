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

    def to_internal_value(self, data):
        import re
        from decimal import Decimal, InvalidOperation

        data_copy = data.copy() if hasattr(data, "copy") else dict(data)
        if "estimated_price_pkr" in data_copy and data_copy["estimated_price_pkr"] is not None:
            raw_val = str(data_copy["estimated_price_pkr"]).strip()
            match = re.search(
                r"(?:PKR\s*|Rs\.?\s*)?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)",
                raw_val,
                re.IGNORECASE,
            )
            if match:
                clean_num = match.group(1).replace(",", "")
                try:
                    dec = Decimal(clean_num)
                    if dec > Decimal("9999999999.99"):
                        dec = Decimal("9999999999.99")
                    data_copy["estimated_price_pkr"] = str(dec.quantize(Decimal("0.01")))
                except (InvalidOperation, ValueError):
                    data_copy["estimated_price_pkr"] = "150000.00"
            else:
                data_copy["estimated_price_pkr"] = "150000.00"
        return super().to_internal_value(data_copy)

class ItineraryApprovalSerializer(serializers.Serializer):
    """Serializer to handle explicit traveler approval of a drafted itinerary (HITL)."""
    approved = serializers.BooleanField(required=True)
    feedback_or_notes = serializers.CharField(required=False, allow_blank=True, default="")
