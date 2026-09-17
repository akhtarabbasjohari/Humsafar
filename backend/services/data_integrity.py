"""
Humsafar Data Integrity & Freshness Layer.
Sits between MCP tools (live scrape, web search fallback) and the agent presentation layer.
Enforces that every price, date, or itinerary detail is verifiably grounded in fresh data,
assigns mandatory confidence labels, and rejects stale, missing, or unverified claims.
"""

import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Mandatory Confidence Labels
CONFIDENCE_OFFICIAL = "from our official listing"
CONFIDENCE_UNVERIFIED = "researched just now, unverified, please confirm with our team"

# Maximum Freshness Window: 1 hour (3600 seconds) by default
MAX_FRESHNESS_AGE_SECONDS = int(os.getenv("DATA_INTEGRITY_MAX_STALENESS_SECONDS", "3600"))

# Regex patterns for detecting prices and schedules in text
PRICE_PATTERN = re.compile(
    r"\b(?:PKR|Rs\.?|USD|\$|EUR|€|GBP|£)\s*[\d,]+(?:\.\d{2})?",
    re.IGNORECASE,
)
SCHEDULE_PATTERN = re.compile(
    r"\b(?:Day\s*\d+|Stage\s*\d+|Itinerary\s*[:\-])\b",
    re.IGNORECASE,
)


class DataIntegrityError(Exception):
    """Raised when data fails freshness or grounding verification."""
    pass


def parse_timestamp(timestamp_val: Union[str, datetime, None]) -> Optional[datetime]:
    """Parse various timestamp formats into UTC datetime."""
    if timestamp_val is None:
        return None
    if isinstance(timestamp_val, datetime):
        return timestamp_val if timestamp_val.tzinfo else timestamp_val.replace(tzinfo=timezone.utc)
    if isinstance(timestamp_val, str):
        try:
            dt = datetime.fromisoformat(timestamp_val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def is_timestamp_fresh(
    timestamp_val: Union[str, datetime, None],
    max_age_seconds: int = MAX_FRESHNESS_AGE_SECONDS,
    now: Optional[datetime] = None,
) -> bool:
    """
    Verify whether a retrieval timestamp is strictly within the allowed freshness window.
    Rejects missing, future (by >60s clock skew), or stale timestamps.
    """
    dt = parse_timestamp(timestamp_val)
    if dt is None:
        return False

    current_time = now or datetime.now(timezone.utc)
    age = (current_time - dt).total_seconds()

    # Reject if in future beyond 60s
    if age < -60:
        return False

    # Reject if older than freshness threshold
    return age <= max_age_seconds


def get_official_host() -> str:
    """Get the normalized configured source site host."""
    url = os.getenv("SOURCE_SITE_URL", os.getenv("COMPANY_SITE_URL", "https://askoliadventure.com"))
    clean = url.replace("https://", "").replace("http://", "").rstrip("/")
    return clean.lower()


class DataIntegrityGuard:
    """
    Enforces grounding, data freshness, and confidence labeling on any content
    destined for the traveler or saved as an itinerary.
    """

    def __init__(self, max_age_seconds: int = MAX_FRESHNESS_AGE_SECONDS):
        self.max_age_seconds = max_age_seconds

    def determine_confidence_label(self, source_url: str, source_type: str = "live_scrape") -> str:
        """
        Assign the mandatory confidence label:
        - 'from our official listing' for direct matches from SOURCE_SITE_URL.
        - 'researched just now, unverified, please confirm with our team' for web search fallback.
        """
        official_host = get_official_host()
        url_lower = (source_url or "").lower()

        if source_type == "web_search" or (official_host and official_host not in url_lower):
            return CONFIDENCE_UNVERIFIED
        return CONFIDENCE_OFFICIAL

    def validate_itinerary_provenance(
        self,
        itinerary: Dict[str, Any],
        max_age_seconds: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Code-enforced validation that an itinerary has an explicit source and fresh timestamp.
        Returns: (is_valid: bool, error_reason: Optional[str])
        """
        max_age = max_age_seconds or self.max_age_seconds

        # 1. Source URL must be present and non-empty
        source_url = itinerary.get("source_url") or itinerary.get("url")
        if not source_url or not str(source_url).strip():
            return False, "Missing required source URL. Content cannot be traced to a verifiable origin."

        # 2. Timestamp must be present and fresh
        timestamp = (
            itinerary.get("scraped_at")
            or itinerary.get("source_verified_at")
            or itinerary.get("timestamp")
        )
        if not timestamp:
            return False, "Missing required retrieval timestamp. Content freshness cannot be confirmed."

        if not is_timestamp_fresh(timestamp, max_age_seconds=max_age):
            dt = parse_timestamp(timestamp)
            age_desc = f"{int((datetime.now(timezone.utc) - dt).total_seconds())}s old" if dt else "invalid"
            return False, f"Stale data rejected. Timestamp is {age_desc} (maximum allowed: {max_age}s)."

        return True, None

    def process_itinerary_detail(
        self,
        itinerary: Dict[str, Any],
        source_type: str = "live_scrape",
        max_age_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Process an itinerary record through the integrity layer:
        - Validates freshness and source.
        - Attaches mandatory confidence label.
        - Attaches standardized ISO timestamp.
        - Flags/rejects unverified data.
        """
        max_age = max_age_seconds or self.max_age_seconds
        is_valid, error_reason = self.validate_itinerary_provenance(itinerary, max_age_seconds=max_age)

        source_url = str(itinerary.get("source_url") or itinerary.get("url") or "")
        confidence = self.determine_confidence_label(source_url, source_type=source_type)

        processed = dict(itinerary)
        processed["confidence_label"] = confidence
        processed["source_url"] = source_url

        if not is_valid:
            processed["is_verified"] = False
            processed["rejection_reason"] = error_reason
            processed["status"] = "rejected_unverified"
            # Never present price as confirmed when unverified
            if "price" in processed:
                processed["price_unconfirmed"] = processed["price"]
                processed["price"] = "Unconfirmed (requires live verification with tour team)"
            logger.warning("Itinerary rejected by data integrity layer: %s", error_reason)
        else:
            processed["is_verified"] = True
            if itinerary.get("is_draft") or itinerary.get("status") == "draft" or source_type == "web_search":
                processed["status"] = "draft"
            else:
                processed["status"] = "verified"

        return processed

    def enforce_presentation_integrity(
        self,
        text: str,
        grounding_data: Optional[Dict[str, Any]] = None,
        max_age_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Inspect text destined for a visitor.
        If it contains price quotes or itinerary steps, enforce that valid fresh
        grounding data is attached.
        If ungrounded or stale, refuse to present it as confirmed and attach an operator disclaimer.
        """
        max_age = max_age_seconds or self.max_age_seconds
        has_prices = bool(PRICE_PATTERN.search(text))
        has_schedules = bool(SCHEDULE_PATTERN.search(text))

        requires_grounding = has_prices or has_schedules

        if not requires_grounding:
            # General greeting or generic conversational text
            return {
                "text": text,
                "is_grounded": True,
                "confidence_label": None,
                "source_url": None,
                "timestamp": None,
            }

        # Content contains specific prices or schedules: verify grounding
        if not grounding_data:
            warning = (
                "\n\n*(Notice: The prices or schedules mentioned above could not be verified against a fresh live source. "
                "Humsafar refuses to present unverified figures as confirmed facts. Please confirm exact rates with our team.)*"
            )
            return {
                "text": text + warning,
                "is_grounded": False,
                "rejection_reason": "No grounding data provided for specific prices or itinerary details.",
                "confidence_label": CONFIDENCE_UNVERIFIED,
                "source_url": None,
                "timestamp": None,
            }

        is_valid, error_reason = self.validate_itinerary_provenance(grounding_data, max_age_seconds=max_age)
        source_url = grounding_data.get("source_url") or grounding_data.get("url") or ""
        source_type = grounding_data.get("source_type", "live_scrape")
        confidence = self.determine_confidence_label(source_url, source_type=source_type)
        timestamp_str = str(grounding_data.get("scraped_at") or grounding_data.get("timestamp") or "")

        if not is_valid:
            warning = (
                f"\n\n*(Notice: Data integrity check flagged this information: {error_reason} "
                "All pricing and schedules must be confirmed directly with Askoli Adventure.)*"
            )
            return {
                "text": text + warning,
                "is_grounded": False,
                "rejection_reason": error_reason,
                "confidence_label": CONFIDENCE_UNVERIFIED,
                "source_url": source_url,
                "timestamp": timestamp_str,
            }

        # Valid fresh grounding
        attribution = f"\n\n[Confidence: {confidence} | Source: {source_url} | Verified: {timestamp_str}]"
        return {
            "text": text + attribution,
            "is_grounded": True,
            "confidence_label": confidence,
            "source_url": source_url,
            "timestamp": timestamp_str,
        }


# Global singleton guard instance
data_integrity_guard = DataIntegrityGuard()
