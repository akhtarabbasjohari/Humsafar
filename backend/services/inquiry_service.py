import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def build_inquiry_object(
    itinerary,  # SavedItinerary instance
    user=None,  # User instance or None
    session=None,  # ChatSession instance or None
    additional_notes: str = "",
) -> Dict[str, Any]:
    """
    Build a structured inquiry object ready for company-side human review.
    
    This object bundles visitor details (auto-filled from user profile if
    authenticated), the approved itinerary, and session context into a
    single payload. It is NOT automatically submitted — it is prepared
    and returned for a human on the company side to review and send.
    """
    visitor = {
        "name": user.username if user else "Guest Traveler",
        "email": user.email if user else None,
        "phone": getattr(user, "phone_number", None) if user else None,
        "is_registered": user is not None,
        "user_id": str(user.id) if user else None,
    }

    itinerary_payload = {
        "id": str(itinerary.id),
        "title": itinerary.title,
        "region": itinerary.region,
        "duration_days": itinerary.duration_days,
        "status": itinerary.status,
        "approval_timestamp": (
            itinerary.approval_timestamp.isoformat()
            if itinerary.approval_timestamp
            else None
        ),
        "confidence_label": itinerary.confidence_label,
        "source_url": itinerary.source_url,
        "itinerary_data": itinerary.itinerary_data,
        "estimated_price_pkr": (
            str(itinerary.estimated_price_pkr)
            if itinerary.estimated_price_pkr
            else None
        ),
    }

    session_context = None
    if session:
        session_context = {
            "session_id": str(session.id),
            "session_title": session.title,
            "message_count": session.messages.count(),
        }

    return {
        "inquiry_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_review",
        "visitor": visitor,
        "itinerary": itinerary_payload,
        "session_context": session_context,
        "notes": additional_notes or itinerary.notes,
    }
