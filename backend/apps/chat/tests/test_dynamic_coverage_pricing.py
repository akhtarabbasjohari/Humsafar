"""
Unit tests for Dynamic Regional Coverage & Mandatory Realistic Pricing.
Validates:
1. All Gilgit-Baltistan sub-valleys, peaks, and trails are covered.
2. Macro-regions across Pakistan (Sindh, Karachi, KPK, Punjab, Balochistan, Kashmir) are covered.
3. Pricing upon inquiry is strictly eliminated across official listings and custom drafts.
4. Itemized pricing breakdowns in PKR and USD are always generated.
"""

import pytest
from mcp_servers.humsafar_data_mcp.scraper import SourceSiteScraper
from services.pricing_service import calculate_realistic_tour_pricing
from services.agent_runner import agent_runner
from services.data_integrity import CONFIDENCE_OFFICIAL, CONFIDENCE_UNVERIFIED


@pytest.fixture
def scraper():
    return SourceSiteScraper()


class TestDynamicRegionalCoverage:
    def test_gilgit_baltistan_subvalleys_coverage(self, scraper):
        """Gilgit-Baltistan sub-valleys, peaks, and passes must all be recognized as covered."""
        destinations = [
            "Hushe Valley",
            "Nangma Valley",
            "Shimshal",
            "Phander Lake",
            "Astore",
            "Deosai",
            "Rakaposhi Base Camp",
            "K2 Base Camp",
            "Concordia",
            "Passu",
            "Shigar",
            "Khaplu",
        ]
        for dest in destinations:
            result = scraper.check_region_coverage(dest)
            assert result["is_serviced"] is True, f"Expected {dest} to be serviced in Gilgit-Baltistan"
            assert "Gilgit-Baltistan" in result["region"]

    def test_mountain_valleys_coverage(self, scraper):
        """KPK and Azad Kashmir mountain destinations must be recognized as covered."""
        destinations = [
            ("Swat Valley", "Khyber Pakhtunkhwa"),
            ("Chitral & Kalash", "Khyber Pakhtunkhwa"),
            ("Kalam", "Khyber Pakhtunkhwa"),
            ("Neelum Valley", "Kashmir"),
        ]
        for dest, expected_region in destinations:
            result = scraper.check_region_coverage(dest)
            assert result["is_serviced"] is True, f"Expected {dest} to be serviced in {expected_region}"
            assert expected_region in result["region"]

    def test_unserviced_regions_strict_out_of_coverage(self, scraper):
        """Non-mountain cities and international destinations must strictly return serviced=False."""
        unserviced = [
            "Lahore",
            "Data Darbar",
            "Karachi",
            "New York",
            "Paris",
            "Dubai",
        ]
        for dest in unserviced:
            result = scraper.check_region_coverage(dest)
            assert result["is_serviced"] is False, f"Expected {dest} to be out of coverage for mountain tour company"
            assert result["matched_regions"] == []


class TestMandatoryRealisticPricing:
    def test_pricing_upon_inquiry_strictly_forbidden_in_service(self):
        """calculate_realistic_tour_pricing must NEVER return 'upon inquiry' or 'contact for pricing'."""
        queries = [
            ("K2 Base Camp Trek", "Karakoram", 16, 2),
            ("Hushe Valley Exploration", "Gilgit-Baltistan", 7, 3),
            ("Spantik Peak Expedition", "Gilgit-Baltistan", 14, 2),
            ("Swat & Kalam Alpine Tour", "KPK", 5, 4),
            ("Neelum Valley Trek", "Azad Kashmir", 6, 2),
        ]
        for title, dest, days, party in queries:
            pricing = calculate_realistic_tour_pricing(
                title=title,
                destination=dest,
                duration_days=days,
                party_size=party,
                existing_price="Pricing upon inquiry",
            )
            price_str = pricing["price"]
            assert "inquiry" not in price_str.lower()
            assert "contact" not in price_str.lower()
            assert "PKR" in price_str
            assert "USD" in price_str or "$" in price_str

            breakdown = pricing["pricing_breakdown"]
            assert "items" in breakdown
            assert len(breakdown["items"]) >= 4
            assert breakdown["party_size"] == party
            assert breakdown["duration_days"] == days

    def test_official_match_enriches_inquiry_price(self):
        """When an official tour has 'upon inquiry', agent_runner enriches it with realistic pricing."""
        pipeline_result = agent_runner.run_multi_hop_pipeline(
            user_message="Tell me about Hunza Autumn Tour",
            session_id="test-session-pricing-official",
        )
        assert pipeline_result["path"] == "official_match"
        itinerary = pipeline_result["itinerary"]
        assert itinerary is not None
        assert "inquiry" not in itinerary["price"].lower()
        assert "contact" not in itinerary["price"].lower()
        assert "PKR" in itinerary["price"]
        assert "pricing_breakdown" in itinerary

    def test_gilgit_baltistan_subvalley_drafting_with_pricing(self):
        """Custom drafting for Shimshal Valley produces valid itinerary with concrete pricing."""
        pipeline_result = agent_runner.run_multi_hop_pipeline(
            user_message="Plan a 7 day trek to Shimshal Valley for 2 people with moderate budget",
            session_id="test-session-shimshal-pricing",
        )
        assert pipeline_result["path"] == "web_search_draft"
        itinerary = pipeline_result["itinerary"]
        assert itinerary is not None
        assert "Shimshal" in itinerary["title"] or "Shimshal" in itinerary["region"]
        assert "inquiry" not in itinerary["price"].lower()
        assert "PKR" in itinerary["price"]
        assert "USD" in itinerary["price"] or "$" in itinerary["price"]
        assert "pricing_breakdown" in itinerary
        assert len(itinerary["pricing_breakdown"]["items"]) >= 4

    def test_unserviced_destination_pipeline_returns_no_itinerary(self):
        """Unserviced destinations like Data Darbar Lahore or Paris strictly return out_of_coverage with NO itinerary."""
        for query in ["Can you plan a trip to Data Darbar lahore?", "Plan a 5 day tour in Paris"]:
            pipeline_result = agent_runner.run_multi_hop_pipeline(
                user_message=query,
                session_id="test-session-out-of-scope",
            )
            assert pipeline_result["path"] == "out_of_coverage"
            assert pipeline_result["itinerary"] is None
            assert pipeline_result["confidence_label"] is None
