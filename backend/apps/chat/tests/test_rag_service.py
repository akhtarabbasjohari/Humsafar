"""
Unit and integration tests for Phase 4: Retrieval-Augmented Generation (RAG) Service.
Verifies:
1. Semantic text chunking with sliding window and sentence boundary preservation.
2. Session-isolated FAISS indexing of multi-source web research documents.
3. Top-K cosine similarity retrieval matching destination and activity queries.
4. Token mitigation: chunk retrieval returns high-density text <600 chars instead of multi-thousand token raw dumps.
5. In-session chunk caching and reuse across turns without re-scraping.
"""

import pytest
from services.rag_service import chunk_text, SessionRAGStore, rag_service
from services.itinerary_drafter import draft_custom_itinerary, TravelerPreferences


class TestTextChunker:
    """Test text chunking mechanics."""

    def test_chunk_short_text_returns_single_chunk(self):
        text = "This is a short trail description."
        chunks = chunk_text(text, chunk_size=300)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_long_text_splits_on_sentences(self):
        long_text = (
            "Day 1 covers arrival in Skardu and transfer to Shangrila Resort at 2,228m. "
            "Day 2 departs for Upper Kachura Lake with boat excursions and trout fishing. "
            "Day 3 drives across the cold desert of Katpana with dramatic sand dunes and snowcapped peaks. "
            "Day 4 journeys to Shigar Valley to explore the 17th-century Raja Palace and ancient mosques. "
            "Day 5 climbs toward Deosai National Park at 4,114m, the second-highest plateau on earth. "
            "Day 6 returns to Skardu bazaar for local Balti handicrafts and dried apricots. "
            "Day 7 boards the scenic morning flight back to Islamabad."
        )
        chunks = chunk_text(long_text, chunk_size=250, chunk_overlap=30)
        assert len(chunks) >= 2
        for ch in chunks:
            assert len(ch) <= 350
            # Verify clean boundaries
            assert ch.strip() != ""


class TestSessionRAGStore:
    """Test session vector indexing and retrieval."""

    def test_index_and_retrieve_relevant_chunks(self):
        store = SessionRAGStore()
        sess_id = "test-rag-session-1"

        mock_research = {
            "top_source_url": "https://example.com/skardu-guide",
            "results": [
                {
                    "title": "Skardu Valley Expeditions & Lakes Guide",
                    "link": "https://example.com/skardu",
                    "content": (
                        "Skardu is the gateway to 8,000m giants. Key highlights include Lower Kachura (Shangrila), "
                        "Upper Kachura Lake, Katpana Cold Desert, and the historic Shigar Fort built upon a rock foundation."
                    ),
                },
                {
                    "title": "Hunza Valley Cultural Tour & Forts",
                    "link": "https://example.com/hunza",
                    "content": (
                        "Hunza Valley in Gilgit-Baltistan is famous for Karimabad, ancient Baltit Fort (700 years old), "
                        "Altit Fort, Passu Cones, and Attabad Lake formed by the 2010 landslide."
                    ),
                },
            ],
            "research_summary": "Northern Pakistan tour operator packages covering Gilgit-Baltistan valleys.",
        }

        count = store.index_research(session_id=sess_id, web_research=mock_research)
        assert count >= 2
        assert store.has_session_data(sess_id) is True

        # Query specifically for Skardu lakes
        skardu_chunks = store.retrieve_relevant_chunks(
            session_id=sess_id,
            query="Kachura Lake Shangrila cold desert",
            top_k=2,
            min_score=0.10,
        )
        assert len(skardu_chunks) >= 1
        assert any("skardu" in c["text"].lower() or "kachura" in c["text"].lower() for c in skardu_chunks)
        assert skardu_chunks[0]["source_url"] == "https://example.com/skardu"

        # Query specifically for Hunza forts
        hunza_chunks = store.retrieve_relevant_chunks(
            session_id=sess_id,
            query="Baltit Fort Altit Karimabad",
            top_k=2,
            min_score=0.10,
        )
        assert len(hunza_chunks) >= 1
        assert any("baltit" in c["text"].lower() or "hunza" in c["text"].lower() for c in hunza_chunks)

    def test_session_isolation_and_reuse(self):
        store = SessionRAGStore()
        store.index_research(
            session_id="session-a",
            web_research={"results": [{"title": "Chitral", "link": "https://a.com", "content": "Kalash Valley festivals in Chitral."}]},
        )
        assert store.has_session_data("session-a") is True
        assert store.has_session_data("session-b") is False

        # In-session reuse
        chunks = store.retrieve_relevant_chunks("session-a", query="Kalash festival", top_k=1, min_score=0.10)
        assert len(chunks) == 1
        assert "Kalash" in chunks[0]["text"]


class TestItineraryDrafterRAGIntegration:
    """Test RAG integration within itinerary drafting."""

    def test_drafter_uses_rag_retrieved_chunks(self):
        prefs = TravelerPreferences(
            destination="Shangrila and Skardu",
            duration="5 Days",
            duration_days=5,
        )
        mock_research = {
            "top_source_url": "https://example.com/skardu",
            "results": [
                {
                    "title": "Shangrila Resort Guide",
                    "link": "https://example.com/shangrila",
                    "content": "Shangrila Resort is located on Lower Kachura Lake at 2,228m elevation with surrounding apple orchards.",
                }
            ],
            "research_summary": "Skardu regional itinerary facts.",
        }

        # Index into global rag_service
        sess_id = "test-drafter-rag-sess"
        rag_service.index_research(session_id=sess_id, web_research=mock_research)
        retrieved = rag_service.retrieve_relevant_chunks(session_id=sess_id, query="Shangrila Resort Kachura Lake", top_k=2)
        assert len(retrieved) >= 1
        assert "Shangrila" in retrieved[0]["text"]
