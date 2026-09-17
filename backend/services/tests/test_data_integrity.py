"""
Unit tests for the Data Integrity & Freshness Layer.
Verifies that stale or missing source data is rejected and cannot be presented as confirmed.
"""

from datetime import datetime, timezone, timedelta
import pytest

from services.data_integrity import (
    DataIntegrityGuard,
    is_timestamp_fresh,
    CONFIDENCE_OFFICIAL,
    CONFIDENCE_UNVERIFIED,
)
from apps.chat.services.agent_runner import HumsafarAgentRunner


def test_is_timestamp_fresh():
    now = datetime.now(timezone.utc)

    # 5 minutes ago -> Fresh
    fresh_time = (now - timedelta(minutes=5)).isoformat()
    assert is_timestamp_fresh(fresh_time, max_age_seconds=3600, now=now) is True

    # 2 hours ago -> Stale (> 3600s)
    stale_time = (now - timedelta(hours=2)).isoformat()
    assert is_timestamp_fresh(stale_time, max_age_seconds=3600, now=now) is False

    # Missing or None -> Stale
    assert is_timestamp_fresh(None, max_age_seconds=3600, now=now) is False
    assert is_timestamp_fresh("", max_age_seconds=3600, now=now) is False
    assert is_timestamp_fresh("invalid-date-string", max_age_seconds=3600, now=now) is False

    # Distant future (> 60s) -> Rejected
    future_time = (now + timedelta(minutes=10)).isoformat()
    assert is_timestamp_fresh(future_time, max_age_seconds=3600, now=now) is False


def test_confidence_label_assignment():
    guard = DataIntegrityGuard()

    # Official company site
    label_official = guard.determine_confidence_label("https://askoliadventure.com/tour/k2/", source_type="live_scrape")
    assert label_official == CONFIDENCE_OFFICIAL

    # Web search fallback
    label_web = guard.determine_confidence_label("https://en.wikipedia.org/wiki/Hunza_Valley", source_type="web_search")
    assert label_web == CONFIDENCE_UNVERIFIED

    # Third party blog even if labeled live_scrape
    label_other = guard.determine_confidence_label("https://random-travel-blog.com/swat", source_type="live_scrape")
    assert label_other == CONFIDENCE_UNVERIFIED


def test_process_itinerary_with_missing_source():
    guard = DataIntegrityGuard(max_age_seconds=3600)
    now = datetime.now(timezone.utc)

    itinerary_missing_source = {
        "title": "Unverified K2 Expedition",
        "price": "PKR 450,000",
        "scraped_at": now.isoformat(),
        # missing source_url
    }

    result = guard.process_itinerary_detail(itinerary_missing_source)
    assert result["is_verified"] is False
    assert result["status"] == "rejected_unverified"
    assert "Missing required source URL" in result["rejection_reason"]
    assert "requires live verification" in result["price"]


def test_process_itinerary_with_stale_data():
    guard = DataIntegrityGuard(max_age_seconds=1800)  # 30 min max
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    itinerary_stale = {
        "title": "Stale Skardu Circuit",
        "price": "PKR 210,000",
        "source_url": "https://askoliadventure.com/tour/skardu/",
        "scraped_at": two_hours_ago,
    }

    result = guard.process_itinerary_detail(itinerary_stale)
    assert result["is_verified"] is False
    assert result["status"] == "rejected_unverified"
    assert "Stale data rejected" in result["rejection_reason"]
    assert "requires live verification" in result["price"]


def test_process_itinerary_valid_fresh():
    guard = DataIntegrityGuard(max_age_seconds=3600)
    recent = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()

    itinerary_fresh = {
        "title": "14-Day K2 & Concordia Classic Trek",
        "price": "PKR 380,000",
        "source_url": "https://askoliadventure.com/tour/k2/",
        "scraped_at": recent,
    }

    result = guard.process_itinerary_detail(itinerary_fresh)
    assert result["is_verified"] is True
    assert result["status"] == "verified"
    assert result["confidence_label"] == CONFIDENCE_OFFICIAL
    assert result["price"] == "PKR 380,000"


def test_presentation_refuses_unverified_prices():
    runner = HumsafarAgentRunner()

    # Agent claims a price without any fresh grounding metadata
    claimed_text = "The 7-Day Hunza Autumn tour is priced at PKR 195,000 per couple."
    presented = runner.present_to_visitor(claimed_text, grounding_data=None)

    assert presented["is_grounded"] is False
    assert "Humsafar refuses to present unverified figures as confirmed facts" in presented["text"]
    assert presented["confidence_label"] == CONFIDENCE_UNVERIFIED


def test_presentation_refuses_stale_source_prices():
    runner = HumsafarAgentRunner()
    stale_timestamp = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()

    claimed_text = "The K2 trek is available for PKR 380,000."
    stale_grounding = {
        "source_url": "https://askoliadventure.com/tour/k2/",
        "scraped_at": stale_timestamp,
    }

    presented = runner.present_to_visitor(claimed_text, grounding_data=stale_grounding)
    assert presented["is_grounded"] is False
    assert "Data integrity check flagged this information: Stale data rejected" in presented["text"]


def test_presentation_attaches_official_confidence_when_verified():
    runner = HumsafarAgentRunner()
    fresh_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    claimed_text = "We have confirmed the 7-Day Hunza Autumn trail for PKR 195,000."
    fresh_grounding = {
        "source_url": "https://askoliadventure.com/tour/hunza/",
        "scraped_at": fresh_timestamp,
        "source_type": "live_scrape",
    }

    presented = runner.present_to_visitor(claimed_text, grounding_data=fresh_grounding)
    assert presented["is_grounded"] is True
    assert "[Confidence: from our official listing" in presented["text"]
    assert "Source: https://askoliadventure.com/tour/hunza/" in presented["text"]


def test_presentation_attaches_unverified_confidence_for_web_fallback():
    runner = HumsafarAgentRunner()
    fresh_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    claimed_text = "Based on regional research, the Shimshal Pass trek is estimated at PKR 280,000."
    web_grounding = {
        "source_url": "https://travel-guide-pakistan.org/shimshal",
        "scraped_at": fresh_timestamp,
        "source_type": "web_search",
    }

    presented = runner.present_to_visitor(claimed_text, grounding_data=web_grounding)
    assert presented["is_grounded"] is True
    assert "[Confidence: researched just now, unverified, please confirm with our team" in presented["text"]
