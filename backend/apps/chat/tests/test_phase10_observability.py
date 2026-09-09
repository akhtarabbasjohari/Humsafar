"""
Phase 10: Observability Across Every Tool Call Tests.
Verifies:
1. Every tool call, itinerary check, region check, web search, and draft generation is logged with timestamp, skill, and status.
2. ToolCallLog records are queryable via simple table and internal endpoint /api/chat/observability/logs/.
3. Full tool call chain inspection for a session.
4. Ollama wired as secondary LLM for cleaning/summarizing scraped content with LLM attribution logged.
5. Ollama fallback on connection failure with failed status logged.
6. Minimal internal HTML dashboard view at /api/chat/observability/view/.
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.chat.models import ChatSession, ToolCallLog
from services.observability_service import log_tool_call, get_session_logs
from services.ollama_service import OllamaService, ollama_service
from apps.chat.services.agent_runner import HumsafarAgentRunner


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="observability_tester",
        email="obs@example.com",
        password="Password123!",
    )


@pytest.mark.django_db
class TestToolCallObservability:
    """Test suite for logging and queryability of tool execution logs."""

    def test_log_tool_call_creates_db_record(self):
        """Direct log_tool_call persists to ToolCallLog table with correct fields."""
        entry = log_tool_call(
            session_id="test_session_101",
            skill="itinerary_lookup",
            tool_name="search_itineraries",
            status="success",
            llm_provider="",
            input_data={"query": "K2 Base Camp"},
            output_data={"count": 1, "matched_titles": ["K2 Classic Trek"]},
            duration_ms=45.5,
        )

        assert entry is not None
        assert entry.session_id == "test_session_101"
        assert entry.skill == "itinerary_lookup"
        assert entry.tool_name == "search_itineraries"
        assert entry.status == "success"
        assert entry.input_data["query"] == "K2 Base Camp"
        assert entry.output_data["count"] == 1
        assert entry.duration_ms == 45.5
        assert entry.created_at is not None

        # Verify queryable from DB
        db_record = ToolCallLog.objects.get(id=entry.id)
        assert db_record.session_id == "test_session_101"

    def test_itinerary_check_logs_observability(self):
        """Runner search_itineraries records itinerary_lookup in ToolCallLog."""
        runner = HumsafarAgentRunner()
        mock_result = {
            "success": True,
            "results": [
                {
                    "title": "K2 Concordia Trek",
                    "duration": "14 Days",
                    "price": "PKR 350,000",
                    "source_url": "https://askoliadventure.com/tours/k2",
                    "scraped_at": "2026-09-09T10:00:00Z",
                    "summary": "14-day trekking journey across Baltoro Glacier to Concordia.",
                }
            ],
            "count": 1,
            "cached": False,
        }

        with patch("apps.chat.services.agent_runner.search_itineraries", return_value=mock_result):
            res = runner.search_itineraries(query="K2 Concordia", session_id="sess_itin_test")
            assert res["success"] is True

        logs = ToolCallLog.objects.filter(session_id="sess_itin_test", skill="itinerary_lookup")
        assert logs.exists()
        log_entry = logs.first()
        assert log_entry.tool_name == "search_itineraries"
        assert log_entry.status == "success"
        assert log_entry.input_data["query"] == "K2 Concordia"
        assert log_entry.output_data["count"] == 1

    def test_region_check_logs_observability(self):
        """Runner check_region_coverage records region_coverage_check in ToolCallLog."""
        runner = HumsafarAgentRunner()
        mock_res = {
            "success": True,
            "destination": "Hunza",
            "serviced": True,
            "matched_regions": ["Gilgit-Baltistan"],
            "cached": False,
        }

        with patch("apps.chat.services.agent_runner.check_region_coverage", return_value=mock_res):
            res = runner.check_region_coverage(destination="Hunza", session_id="sess_reg_test")
            assert res["serviced"] is True

        logs = ToolCallLog.objects.filter(session_id="sess_reg_test", skill="region_coverage_check")
        assert logs.exists()
        log_entry = logs.first()
        assert log_entry.tool_name == "check_region_coverage"
        assert log_entry.status == "success"
        assert log_entry.input_data["destination"] == "Hunza"
        assert log_entry.output_data["serviced"] is True

    def test_failed_tool_call_logged(self):
        """Tool failure records status='failed' with error_message in ToolCallLog."""
        runner = HumsafarAgentRunner()

        with patch("apps.chat.services.agent_runner.search_itineraries", side_effect=RuntimeError("Scraper connection timeout")):
            res = runner.search_itineraries(query="BrokenQuery", session_id="sess_fail_test")
            assert res["success"] is False

        logs = ToolCallLog.objects.filter(session_id="sess_fail_test")
        assert logs.exists()
        failed_log = logs.first()
        assert failed_log.status == "failed"
        assert "Scraper connection timeout" in failed_log.error_message


@pytest.mark.django_db
class TestObservabilityEndpoints:
    """Test suite for queryable endpoints and inspection view."""

    def test_observability_logs_endpoint(self, api_client):
        """GET /api/chat/observability/logs/?session_id=... returns full chronological tool chain."""
        session_id = "test_chain_sess_1"
        log_tool_call(
            session_id=session_id,
            skill="itinerary_lookup",
            tool_name="search_itineraries",
            status="success",
            input_data={"query": "Rakaposhi"},
            output_data={"count": 0},
        )
        log_tool_call(
            session_id=session_id,
            skill="region_coverage_check",
            tool_name="check_region_coverage",
            status="success",
            input_data={"destination": "Rakaposhi"},
            output_data={"serviced": True},
        )
        log_tool_call(
            session_id=session_id,
            skill="web_search_fallback",
            tool_name="search_web",
            status="success",
            input_data={"destination": "Rakaposhi"},
            output_data={"provider": "serpapi", "results_count": 5},
        )
        log_tool_call(
            session_id=session_id,
            skill="itinerary_drafting",
            tool_name="draft_itinerary",
            status="success",
            llm_provider="groq:openai/gpt-oss-120b",
            input_data={"destination": "Rakaposhi"},
            output_data={"draft_title": "7 Days Rakaposhi Base Camp Expedition"},
        )

        res = api_client.get(f"/api/chat/observability/logs/?session_id={session_id}")
        assert res.status_code == status.HTTP_200_OK
        data = res.data
        assert data["session_id"] == session_id
        assert data["total_logs"] == 4
        chain = data["chain"]
        assert len(chain) == 4
        assert chain[0]["skill"] == "itinerary_lookup"
        assert chain[1]["skill"] == "region_coverage_check"
        assert chain[2]["skill"] == "web_search_fallback"
        assert chain[3]["skill"] == "itinerary_drafting"
        assert chain[3]["llm_provider"] == "groq:openai/gpt-oss-120b"

    def test_session_scoped_observability_endpoint(self, api_client):
        """GET /api/chat/sessions/<id>/observability/ returns session's tool call chain."""
        sess = ChatSession.objects.create(title="Obs Session", is_guest=True)
        log_tool_call(
            session_id=str(sess.id),
            skill="itinerary_lookup",
            tool_name="search_itineraries",
            status="success",
        )

        res = api_client.get(f"/api/chat/sessions/{sess.id}/observability/")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["session_id"] == str(sess.id)
        assert res.data["total_logs"] == 1

    def test_observability_dashboard_html_view(self, api_client):
        """GET /api/chat/observability/view/ returns clean HTML inspection view."""
        log_tool_call(
            session_id="html_test_sess",
            skill="content_cleaning",
            tool_name="clean_scraped_content",
            status="success",
            llm_provider="ollama:llama3.2:3b",
        )

        res = api_client.get("/api/chat/observability/view/?session_id=html_test_sess")
        assert res.status_code == status.HTTP_200_OK
        assert "text/html" in res.headers["Content-Type"]
        content = res.content.decode("utf-8")
        assert "Humsafar Observability Dashboard" in content
        assert "content_cleaning" in content
        assert "ollama:llama3.2:3b" in content
        assert "SUCCESS" in content


@pytest.mark.django_db
class TestOllamaSecondaryLLM:
    """Test suite for Ollama secondary LLM content cleaning and preprocessing."""

    def test_ollama_cleaning_success(self):
        """Ollama cleans raw scraped content, returns cleaned text, and logs LLM attribution."""
        raw_html_text = (
            "Home > Tours > K2\n"
            "Main Menu Cart (0) Login\n"
            "K2 Base Camp & Concordia Trek is 14 days. Altitude 5100m. Includes all porters, guide, and camps.\n"
            "Copyright 2026 Askoli Adventure. Privacy Policy Terms."
        )

        mock_ollama_response = MagicMock()
        mock_ollama_response.status_code = 200
        mock_ollama_response.json.return_value = {
            "response": "14 Days K2 & Concordia Trek at 5,100m. Inclusions: native mountain guides, Balti porters, all camp meals."
        }

        service = OllamaService(base_url="http://localhost:11434", model="llama3.2:3b")

        with patch("httpx.Client.post", return_value=mock_ollama_response):
            result = service.clean_and_summarize_scraped_content(
                raw_content=raw_html_text,
                title="K2 Base Camp",
                source_url="https://askoliadventure.com/tour/k2",
                session_id="ollama_sess_success",
            )

            assert result["success"] is True
            assert "14 Days K2 & Concordia Trek" in result["cleaned_content"]
            assert result["llm_provider"] == "ollama:llama3.2:3b"
            assert result["fallback_used"] is False

        # Verify logged in ToolCallLog table
        logs = ToolCallLog.objects.filter(session_id="ollama_sess_success")
        assert logs.exists()
        log = logs.first()
        assert log.skill == "content_cleaning"
        assert log.tool_name == "clean_scraped_content"
        assert log.status == "success"
        assert log.llm_provider == "ollama:llama3.2:3b"
        assert log.input_data["title"] == "K2 Base Camp"

    def test_ollama_fallback_on_connection_failure(self):
        """When Ollama daemon is unreachable, cleans via heuristic fallback and logs failed status."""
        raw_text = (
            "Navigation Menu Home Search Contact\n"
            "Explore Shangrila Resort in Skardu, known for Lower Kachura Lake and alpine cottages.\n"
            "Footer copyright 2026."
        )

        service = OllamaService(base_url="http://localhost:11434", model="llama3.2:3b")

        with patch("httpx.Client.post", side_effect=Exception("Connection refused to http://localhost:11434")):
            result = service.clean_and_summarize_scraped_content(
                raw_content=raw_text,
                title="Shangrila",
                source_url="https://askoliadventure.com/tour/shangrila",
                session_id="ollama_sess_fail",
            )

            assert result["success"] is False
            assert result["fallback_used"] is True
            assert "Shangrila Resort in Skardu" in result["cleaned_content"]

        logs = ToolCallLog.objects.filter(session_id="ollama_sess_fail")
        assert logs.exists()
        log = logs.first()
        assert log.skill == "content_cleaning"
        assert log.status == "failed"
        assert log.llm_provider == "ollama:llama3.2:3b"
        assert "Connection refused" in log.error_message
