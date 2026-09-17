"""
Tests for Retrieval-Augmented Matching with FAISS Vector Store in humsafar-data-mcp.
Verifies that search_itineraries resolves loosely worded queries, destination nicknames,
and partial names even when exact keyword matching on titles would have missed them.
Verifies strict adherence to Phase 4 data freshness rules (retrieval accuracy does not exempt).
"""

from datetime import datetime, timezone, timedelta
import pytest
import httpx

from mcp_servers.humsafar_data_mcp.vector_store import (
    ItineraryVectorStore,
    ItineraryEmbeddingEngine,
    global_vector_store,
)
from mcp_servers.humsafar_data_mcp.scraper import SourceSiteScraper
from mcp_servers.humsafar_data_mcp.cache import SessionScopedCache
from apps.chat.services.agent_runner import HumsafarAgentRunner
from services.data_integrity import (
    DataIntegrityGuard,
    CONFIDENCE_OFFICIAL,
    CONFIDENCE_UNVERIFIED,
)


@pytest.fixture
def clean_vector_store():
    """Provides an isolated clean vector store for tests."""
    store = ItineraryVectorStore()
    store.clear()
    return store


@pytest.fixture
def custom_scraper(clean_vector_store, monkeypatch):
    """Provides a scraper with an isolated cache and vector store, mocking network calls."""
    cache = SessionScopedCache(default_ttl_seconds=300)
    scr = SourceSiteScraper(cache=cache, vector_store=clean_vector_store)
    monkeypatch.setattr(scr, "_fetch_html", lambda url, client=None: (False, None, "Mocked offline"))
    return scr


def test_loosely_worded_k2_base_camp_finds_concordia_trek(custom_scraper):
    """
    Test Case 1: Loose wording / different title.
    A visitor asks for 'K2 base camp' when the official page is titled 'Concordia Trek'.
    Plain keyword search on title has 0 title words matching 'K2', 'base', or 'camp'.
    Retrieval augmented matching must find 'Concordia Trek' based on embedded page content.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    # Itinerary page titled "Concordia Trek" (no "K2" or "base" or "camp" in title)
    concordia_page = {
        "title": "Concordia Trek",
        "url": "https://askoliadventure.com/tour/concordia-trek/",
        "source_url": "https://askoliadventure.com/tour/concordia-trek/",
        "duration": "20 Days",
        "price": "PKR 450,000 / USD 2,850",
        "region": "Baltoro Glacier, Karakoram, Gilgit-Baltistan",
        "summary": "The world's greatest mountain wilderness trek into the Baltoro Glacier and the foot of K2.",
        "itinerary_schedule": [
            {"day": 10, "title": "Trek to Concordia", "description": "Reach the Throne Room of Mountain Gods.", "altitude": "4,691m"},
            {"day": 11, "title": "Excursion to K2 Base Camp", "description": "Hike to Gilkey Memorial and the base camp of K2.", "altitude": "5,150m"},
        ],
        "highlights": ["Concordia", "K2 base camp excursion", "Gilkey Memorial", "Baltoro Glacier"],
        "scraped_at": now_iso,
    }

    hunza_page = {
        "title": "Hunza Valley Tour",
        "url": "https://askoliadventure.com/tour/hunza-tour/",
        "source_url": "https://askoliadventure.com/tour/hunza-tour/",
        "duration": "7 Days",
        "price": "PKR 145,000",
        "region": "Hunza, Gilgit-Baltistan",
        "summary": "Cultural and scenic exploration of Central Hunza, Baltit Fort, and Altit Fort.",
        "scraped_at": now_iso,
    }

    # Index both items in scraper's vector store
    custom_scraper.vector_store.add_or_update(concordia_page)
    custom_scraper.vector_store.add_or_update(hunza_page)

    # Visitor asks for "K2 base camp"
    result = custom_scraper.search_itineraries(query="K2 base camp", session_id="test-k2-session")

    assert result["success"] is True
    assert len(result["results"]) > 0

    top_match = result["results"][0]
    # Successfully retrieved the Concordia Trek!
    assert top_match["title"] == "Concordia Trek"
    assert top_match["_retrieval_method"] in ["vector_store", "hybrid"]
    assert top_match["_retrieval_score"] > 0.40


def test_nickname_golden_peak_finds_spantik_expedition(custom_scraper):
    """
    Test Case 2: Destination nickname.
    Visitor asks for 'Golden Peak' when the package is titled 'Spantik Peak Expedition'.
    Page content notes 'Expedition to summit Golden Peak (7,027m) via Southeast Ridge'.
    Semantic vector retrieval must retrieve 'Spantik Peak Expedition'.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    spantik_page = {
        "title": "Spantik Peak Expedition",
        "url": "https://askoliadventure.com/tour/spantik-expedition/",
        "source_url": "https://askoliadventure.com/tour/spantik-expedition/",
        "duration": "24 Days",
        "price": "PKR 650,000 / USD 3,900",
        "region": "Chogo Lungma, Gilgit-Baltistan",
        "summary": "Mountaineering expedition to summit Golden Peak (7,027m) via the Southeast Ridge.",
        "highlights": ["Golden Peak summit attempt", "Chogo Lungma glacier", "Arandu base camp"],
        "scraped_at": now_iso,
    }

    skardu_page = {
        "title": "Skardu Lakes Tour",
        "url": "https://askoliadventure.com/tour/skardu-lakes/",
        "source_url": "https://askoliadventure.com/tour/skardu-lakes/",
        "duration": "5 Days",
        "price": "PKR 95,000",
        "region": "Skardu, Gilgit-Baltistan",
        "summary": "Relaxing visit to Upper and Lower Kachura lakes and Katpana cold desert.",
        "scraped_at": now_iso,
    }

    custom_scraper.vector_store.add_or_update(spantik_page)
    custom_scraper.vector_store.add_or_update(skardu_page)

    result = custom_scraper.search_itineraries(query="Golden Peak", session_id="test-golden-peak")

    assert result["success"] is True
    assert len(result["results"]) > 0
    top_match = result["results"][0]
    assert top_match["title"] == "Spantik Peak Expedition"
    assert top_match["_retrieval_score"] > 0.35


def test_landmark_cathedral_spires_finds_hunza_tour(custom_scraper):
    """
    Test Case 3: Landmark / partial name.
    Visitor asks for 'Cathedral Spires' (a nickname for Passu Cones).
    The itinerary is titled 'Hunza Autumn Tour' and mentions Passu cathedral spires in schedule.
    Vector retrieval must surface 'Hunza Autumn Tour'.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    hunza_page = {
        "title": "Hunza Autumn Tour",
        "url": "https://askoliadventure.com/tour/hunza-autumn/",
        "source_url": "https://askoliadventure.com/tour/hunza-autumn/",
        "duration": "7 Days",
        "price": "PKR 145,000",
        "region": "Hunza Valley, Gilgit-Baltistan",
        "summary": "Spectacular autumn foliage tour across Hunza and Nagar valleys.",
        "highlights": ["Baltit Fort", "Passu cathedral spires", "Attabad Lake", "Duikar sunset"],
        "itinerary_schedule": [
            {"day": 5, "title": "Passu Cones & Glacier Hike", "description": "Excursion to Passu cathedral spires and suspension bridges."},
        ],
        "scraped_at": now_iso,
    }

    custom_scraper.vector_store.add_or_update(hunza_page)

    result = custom_scraper.search_itineraries(query="Cathedral Spires", session_id="test-spires")

    assert result["success"] is True
    assert len(result["results"]) > 0
    top_match = result["results"][0]
    assert top_match["title"] == "Hunza Autumn Tour"


def test_retrieval_preserves_original_scraped_at_and_source_url(clean_vector_store):
    """
    Test Case 4: Provenance preservation.
    Confirms that vector retrieval does not mutate or overwrite the original
    scrape timestamp or source URL.
    """
    specific_timestamp = "2026-09-11T12:30:00+00:00"
    specific_url = "https://askoliadventure.com/tour/k2-base-camp-trek/"

    item = {
        "title": "Concordia & Baltoro Trek",
        "url": specific_url,
        "source_url": specific_url,
        "summary": "Trek to K2 base camp and Concordia.",
        "scraped_at": specific_timestamp,
    }

    clean_vector_store.add_or_update(item)
    matches = clean_vector_store.query("K2 base camp", top_k=1)

    assert len(matches) == 1
    matched = matches[0]
    assert matched["scraped_at"] == specific_timestamp
    assert matched["source_url"] == specific_url
    assert matched["_retrieval_method"] == "vector_store"


def test_stale_retrieved_match_rejected_by_phase4_freshness_rule(clean_vector_store):
    """
    Test Case 5: Phase 4 Freshness Enforcement.
    A retrieved match has very high semantic similarity, but its original
    scrape timestamp is 5,000 seconds old (> 3,600s allowed freshness window).
    Retrieval accuracy does NOT exempt it: DataIntegrityGuard must flag and reject it.
    """
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=5000)).isoformat()
    stale_tour = {
        "title": "Concordia Trek",
        "url": "https://askoliadventure.com/tour/concordia-trek/",
        "source_url": "https://askoliadventure.com/tour/concordia-trek/",
        "price": "PKR 450,000",
        "summary": "Trek to K2 base camp and Baltoro Glacier.",
        "scraped_at": stale_time,
    }

    clean_vector_store.add_or_update(stale_tour)
    matches = clean_vector_store.query("K2 base camp", top_k=1)
    assert len(matches) == 1
    candidate = matches[0]

    # Verify candidate retains the stale timestamp
    assert candidate["scraped_at"] == stale_time

    # Run candidate through Phase 4 DataIntegrityGuard
    guard = DataIntegrityGuard(max_age_seconds=3600)
    processed = guard.process_itinerary_detail(candidate, source_type="live_scrape")

    # MUST be rejected as unverified due to stale timestamp
    assert processed["is_verified"] is False
    assert processed["status"] == "rejected_unverified"
    assert "Stale data rejected" in processed["rejection_reason"]
    assert "Unconfirmed" in processed["price"]


def test_rescraping_updates_vector_store_without_duplicate_entries(clean_vector_store):
    """
    Test Case 6: Rescraping and Updating.
    When a page is rescraped, updating the vector store should replace the document
    without bloating or duplicating the FAISS index size.
    """
    initial_item = {
        "title": "Hunza Tour",
        "url": "https://askoliadventure.com/tour/hunza/",
        "summary": "Initial summary without autumn details.",
        "scraped_at": "2026-09-11T10:00:00+00:00",
    }
    clean_vector_store.add_or_update(initial_item)
    assert clean_vector_store.size() == 1

    # Rescrape with updated details
    updated_item = {
        "title": "Hunza Tour",
        "url": "https://askoliadventure.com/tour/hunza/",
        "summary": "Updated summary with golden autumn foliage, Altit Fort, and Passu Cones.",
        "scraped_at": "2026-09-11T12:00:00+00:00",
    }
    clean_vector_store.add_or_update(updated_item)
    # Size remains 1 (no duplicate)
    assert clean_vector_store.size() == 1

    matches = clean_vector_store.query("Passu Cones", top_k=1)
    assert len(matches) == 1
    assert "Passu Cones" in matches[0]["summary"]
    assert matches[0]["scraped_at"] == "2026-09-11T12:00:00+00:00"


def test_agent_runner_search_itineraries_with_semantic_query(monkeypatch):
    """
    Test Case 7: End-to-end Agent Runner integration.
    HumsafarAgentRunner.search_itineraries uses retrieval-augmented matching
    and enriches with Phase 4 confidence label ('from our official listing').
    """
    from mcp_servers.humsafar_data_mcp.scraper import scraper
    from mcp_servers.humsafar_data_mcp.vector_store import global_vector_store
    global_vector_store.clear()
    monkeypatch.setattr(scraper, "_fetch_html", lambda url, client=None: (False, None, "Mocked offline"))
    monkeypatch.setattr("services.ollama_service.ollama_service.clean_and_summarize_scraped_content", lambda **kw: {"cleaned_content": kw.get("raw_content", "")})

    runner = HumsafarAgentRunner()
    result = runner.search_itineraries(query="K2 base camp", session_id="runner-vector-test")

    assert result["success"] is True
    assert len(result["results"]) > 0

    top = result["results"][0]
    assert "K2" in top["title"] or "Concordia" in top["title"]
    # Phase 4 label attached
    assert top["confidence_label"] == CONFIDENCE_OFFICIAL
    assert top.get("scraped_at") is not None
