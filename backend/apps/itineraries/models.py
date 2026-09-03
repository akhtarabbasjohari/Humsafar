import uuid
from django.conf import settings
from django.db import models
from apps.chat.models import ChatSession

class SavedItinerary(models.Model):
    """Stores travel itineraries synthesized by Humsafar or curated from itp.7scribes.com."""
    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_INQUIRY_SENT = "inquiry_sent"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft (Pending Traveler Approval)"),
        (STATUS_APPROVED, "Approved by Traveler"),
        (STATUS_INQUIRY_SENT, "Inquiry Sent to Operator"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="saved_itineraries",
        help_text="User who owns this saved itinerary. Null for guest session itineraries.",
    )
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itineraries",
        help_text="The chat session where this itinerary was synthesized.",
    )
    title = models.CharField(max_length=255)
    region = models.CharField(max_length=150, help_text="Target region or valley (e.g. Hunza, Skardu, Fairy Meadows).")
    duration_days = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        help_text="Human-in-the-Loop state: must be explicitly approved by the traveler before finalization.",
    )
    is_approved_by_user = models.BooleanField(
        default=False,
        help_text="Explicit approval flag set only upon direct visitor confirmation.",
    )
    approval_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Exact timestamp when the traveler confirmed this itinerary.",
    )
    itinerary_data = models.JSONField(
        default=dict,
        help_text="Structured day-by-day plan, inclusions, exclusions, and trek grading.",
    )
    source_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data freshness timestamp recording when live data was scraped from itp.7scribes.com.",
    )
    estimated_price_pkr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated or quoted price in PKR.",
    )
    confidence_label = models.CharField(
        max_length=150,
        default="from our official listing",
        help_text="Confidence label: 'from our official listing' or 'researched just now, unverified, please confirm with our team'.",
    )
    source_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Live URL from where this itinerary was verified.",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        from services.data_integrity import is_timestamp_fresh
        if self.is_approved_by_user or self.status == self.STATUS_APPROVED:
            if not self.source_url:
                from django.core.exceptions import ValidationError
                raise ValidationError({"source_url": "Approved itineraries must have an explicit source URL."})
            if not self.source_verified_at or not is_timestamp_fresh(self.source_verified_at):
                from django.core.exceptions import ValidationError
                raise ValidationError({"source_verified_at": "Approved itineraries must have a fresh verification timestamp."})

    class Meta:
        verbose_name = "Saved Itinerary"
        verbose_name_plural = "Saved Itineraries"
        ordering = ["-updated_at"]

    def __str__(self):
        owner = self.user.username if self.user else "Guest"
        return f"{self.title} ({self.region}, {self.duration_days}d) - [{self.status}] by {owner}"
