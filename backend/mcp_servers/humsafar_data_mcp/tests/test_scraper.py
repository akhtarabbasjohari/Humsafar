"""
Unit tests for SourceSiteScraper with mocked HTML responses.
Ensures tests do not depend on the live site being reachable.
"""

import os
import pytest
import httpx
from mcp_servers.humsafar_data_mcp.scraper import (
    SourceSiteScraper,
    extract_duration,
    extract_price,
    get_source_site_url,
)
from mcp_servers.humsafar_data_mcp.cache import SessionScopedCache

MOCK_SEARCH_HTML = """
<!DOCTYPE html>
<html>
<head><title>Search Results - Indus Trekking and Tours</title></head>
<body>
    <main>
        <article class="tour-item">
            <h2 class="entry-title">
                <a href="/tours/k2-concordia-trek/">14-Day K2 & Concordia Classic Trek</a>
            </h2>
            <div class="tour-meta">
                <span class="duration">Duration: 14 Days / 13 Nights</span>
                <span class="price">Price: PKR 380,000 per person</span>
            </div>
            <div class="entry-content">
                <p>An unforgettable expedition through the heart of the Karakoram range to Concordia and K2 Base Camp.</p>
            </div>
        </article>

        <article class="tour-item">
            <h2 class="entry-title">
                <a href="/tours/hunza-autumn-tour/">7-Day Hunza Autumn Foliage Trail</a>
            </h2>
            <div class="tour-meta">
                <span class="duration">Duration: 7 Days</span>
                <span class="price">Price: PKR 195,000 per couple</span>
            </div>
            <div class="entry-content">
                <p>Witness the apricot blossoms and golden poplar trees in Karimabad, Altit and Baltit Forts.</p>
            </div>
        </article>
    </main>
</body>
</html>
"""

MOCK_DESTINATIONS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Destinations - Indus Trekking and Tours</title></head>
<body>
    <h1>Our Expedition Regions</h1>
    <div class="regions-list">
        <h2>Gilgit-Baltistan</h2>
        <p>Covering Hunza Valley, Skardu, Baltistan, Nagar, and the mighty Karakoram range.</p>
        <h2>Khyber Pakhtunkhwa</h2>
        <p>Offering treks in Swat Valley, Kalam, and Chitral Kalash valleys.</p>
        <h2>Fairy Meadows & Nanga Parbat</h2>
        <p>Expeditions across the Himalayan front of Diamer and Raikot Glacier.</p>
    </div>
</body>
</html>
"""


def test_regex_extractors():
    assert extract_duration("14 Days in Baltistan") == "14 Days"
    assert extract_duration("Duration: 7 Days / 6 Nights") == "7 Days / 6 Nights"
    assert extract_price("Estimated: PKR 380,000 per person") == "PKR 380,000 per person"
    assert extract_price("Price: USD 1,850") == "USD 1,850"


def test_dynamic_source_site_url_resolution(monkeypatch):
    monkeypatch.setenv("SOURCE_SITE_URL", "https://tours.example.com")
    assert get_source_site_url() == "https://tours.example.com"

    monkeypatch.setenv("SOURCE_SITE_URL", "example-travel.pk")
    assert get_source_site_url() == "https://example-travel.pk"


def test_search_itineraries_mocked(monkeypatch):
    monkeypatch.setenv("SOURCE_SITE_URL", "https://mock-itp.test")

    def mock_handler(request: httpx.Request):
        assert "mock-itp.test" in request.url.host
        assert "s=Hunza" in request.url.query.decode()
        return httpx.Response(200, text=MOCK_SEARCH_HTML)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    cache = SessionScopedCache(default_ttl_seconds=60)
    scraper = SourceSiteScraper(cache=cache)

    result = scraper.search_itineraries(query="Hunza", session_id="test-session", client=client)

    assert result["success"] is True
    assert result["count"] == 2
    assert result["cached"] is False
    assert "scraped_at" in result

    first_tour = result["results"][0]
    assert "14-Day K2 & Concordia Classic Trek" in first_tour["title"]
    assert "14 Days" in first_tour["duration"]
    assert "PKR 380,000" in first_tour["price"]
    assert first_tour["url"] == "https://mock-itp.test/tours/k2-concordia-trek/"

    # Test Session Caching: subsequent call does NOT hit mock_handler again
    cached_result = scraper.search_itineraries(query="Hunza", session_id="test-session", client=None)
    assert cached_result["cached"] is True
    assert cached_result["count"] == 2


def test_check_region_coverage_mocked(monkeypatch):
    monkeypatch.setenv("SOURCE_SITE_URL", "https://mock-itp.test")

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=MOCK_DESTINATIONS_HTML)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    cache = SessionScopedCache(default_ttl_seconds=60)
    scraper = SourceSiteScraper(cache=cache)

    # Test covered region: Hunza
    hunza_cov = scraper.check_region_coverage(destination="Hunza", session_id="test-sess", client=client)
    assert hunza_cov["success"] is True
    assert hunza_cov["serviced"] is True
    assert "Hunza" in hunza_cov["matched_regions"]

    # Test covered region: Swat
    swat_cov = scraper.check_region_coverage(destination="Swat", session_id="test-sess", client=client)
    assert swat_cov["serviced"] is True
    assert "Swat" in swat_cov["matched_regions"]

    # Test unserviced region: Antarctica
    antarctica_cov = scraper.check_region_coverage(destination="Antarctica", session_id="test-sess", client=client)
    assert antarctica_cov["serviced"] is False


def test_graceful_error_handling(monkeypatch):
    monkeypatch.setenv("SOURCE_SITE_URL", "https://mock-error.test")

    def mock_500_handler(request: httpx.Request):
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(mock_500_handler))
    cache = SessionScopedCache(default_ttl_seconds=60)
    scraper = SourceSiteScraper(cache=cache)

    result = scraper.search_itineraries(query="Skardu", session_id="err-sess", client=client)
    assert result["success"] is False
    assert "results" in result
    assert len(result["results"]) == 0
    assert "Source site returned HTTP 500" in result["error"]
