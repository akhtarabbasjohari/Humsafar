"""
Test suite for Phase 12: Live Multi-Model Comparison & Output Validation Guard.
Verifies:
1. SchemaGuard validation of itinerary drafts and conversational text.
2. Extraction of JSON from markdown blocks, raw objects, and malformed strings.
3. Single-retry recovery mechanism on schema validation failures.
4. Fallback to structured error state when retry fails.
5. Simultaneous dispatch to Groq and Ollama with latency benchmarking.
6. Internal API endpoint POST /api/chat/comparison/ and HTML dashboard view.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework.test import APIClient

from services.schema_guard import schema_guard, SchemaGuard, ValidationResult
from services.model_comparison_service import ModelComparisonService, model_comparison_service
from apps.chat.models import ToolCallLog


class TestSchemaGuard:
    """Tests for output validation and schema enforcement."""

    def test_valid_itinerary_draft_dict(self):
        valid_payload = {
            "title": "5-Day Hunza Valley Cultural Trek",
            "destination": "Hunza Valley",
            "duration": "5 Days",
            "duration_days": 5,
            "price": "PKR 140,000 - 180,000 ($500 - $650 USD)",
            "day_by_day": [
                {"day": 1, "title": "Islamabad to Gilgit", "description": "Flight to Gilgit and drive to Karimabad", "altitude": "2,400m"},
                {"day": 2, "title": "Karimabad & Baltit Fort", "description": "Explore ancient forts and valley orchards", "altitude": "2,450m"},
            ],
            "inclusions": ["Licensed Guide", "4x4 Transport", "Hotel Stays", "Breakfast"],
            "exclusions": ["Airfare", "Personal Insurance", "Tips"],
        }
        res = schema_guard.validate(valid_payload, schema_type="itinerary_draft")
        assert res.is_valid is True
        assert res.data is not None
        assert res.data["title"] == "5-Day Hunza Valley Cultural Trek"
        assert len(res.errors) == 0

    def test_valid_itinerary_draft_json_string_with_markdown_fences(self):
        json_str = """```json
{
  "title": "7-Day Skardu & Deosai Plains Safari",
  "destination": "Skardu",
  "duration_days": 7,
  "price": "PKR 190,000 ($680 USD)",
  "day_by_day": [
    {"day": 1, "title": "Arrival in Skardu", "description": "Acclimatize by Shangrila Resort"}
  ],
  "inclusions": ["4x4 Jeeps", "Guide"]
}
```"""
        res = schema_guard.validate(json_str, schema_type="itinerary_draft")
        assert res.is_valid is True
        assert res.data["title"] == "7-Day Skardu & Deosai Plains Safari"
        assert res.data["duration_days"] == 7

    def test_invalid_itinerary_draft_missing_required_fields(self):
        # Missing title, price, and empty day_by_day
        broken_payload = {
            "destination": "Hunza",
            "duration_days": 5,
            "day_by_day": [],
        }
        res = schema_guard.validate(broken_payload, schema_type="itinerary_draft")
        assert res.is_valid is False
        assert res.data is None
        assert any("title" in err.lower() for err in res.errors)
        assert any("price" in err.lower() for err in res.errors)
        assert any("day_by_day" in err.lower() for err in res.errors)

    def test_invalid_itinerary_draft_malformed_json(self):
        broken_json = "{title: 'Bad JSON', missing_quotes: true"
        res = schema_guard.validate(broken_json, schema_type="itinerary_draft")
        assert res.is_valid is False
        assert "not valid json" in res.error_message.lower()

    def test_conversational_validation_strips_think_tags(self):
        valid_prose = "Salam and welcome to Askoli Adventure! The trekking season for K2 Base Camp runs from June to August."
        res = schema_guard.validate(valid_prose, schema_type="conversational")
        assert res.is_valid is True

        think_leak = "<think>Internal reasoning step</think>The season is July."
        res_fail = schema_guard.validate(think_leak, schema_type="conversational")
        assert res_fail.is_valid is False
        assert any("think" in err for err in res_fail.errors)

    def test_corrective_retry_prompt_generation(self):
        errors = ["Field 'price' is missing", "Field 'day_by_day' must be a non-empty list"]
        retry_prompt = schema_guard.generate_retry_prompt(
            original_query="5 days Hunza trip",
            validation_errors=errors,
            schema_type="itinerary_draft",
        )
        assert "CORRECTIVE RETRY REQUIRED" in retry_prompt
        assert "Field 'price' is missing" in retry_prompt
        assert "```json" in retry_prompt
        assert "5 days Hunza trip" in retry_prompt


class TestModelComparisonService:
    """Tests for multi-model live routing, concurrent execution, and retry handling."""

    @pytest.fixture
    def comparison_svc(self):
        svc = ModelComparisonService()
        svc.groq_api_key = "gsk_test_mock_key"
        return svc

    @pytest.fixture
    def valid_itinerary_json(self):
        return json.dumps({
            "title": "5-Day Hunza Adventure",
            "destination": "Hunza Valley",
            "duration": "5 Days",
            "duration_days": 5,
            "price": "PKR 150,000 ($540 USD)",
            "day_by_day": [
                {"day": 1, "title": "Islamabad to Gilgit", "description": "Mountain flight and drive"}
            ],
            "inclusions": ["Guide", "Jeep"],
            "exclusions": ["Insurance"],
        })

    def test_concurrent_both_success_without_retry(self, comparison_svc, valid_itinerary_json):
        """When both models return valid schema on first try, both succeed with retry_count=0."""
        with patch.object(comparison_svc, "_call_groq_mock", create=True) as mock_groq, \
             patch.object(comparison_svc.ollama_service, "is_available", return_value=True), \
             patch.object(comparison_svc.ollama_service, "generate_completion", return_value=valid_itinerary_json):

            # Mock Groq call directly
            with patch("services.model_comparison_service.post_groq_with_retry") as mock_post:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": valid_itinerary_json}}]
                }
                mock_post.return_value = mock_resp

                res = comparison_svc.compare_live(
                    query="Draft 5 days Hunza tour",
                    task_type="itinerary_draft",
                )

                assert "groq" in res["providers"]
                assert "ollama" in res["providers"]
                assert res["providers"]["groq"]["status"] == "success"
                assert res["providers"]["ollama"]["status"] == "success"
                assert res["providers"]["groq"]["validation"]["is_valid"] is True
                assert res["providers"]["groq"]["validation"]["retry_count"] == 0
                assert res["providers"]["ollama"]["validation"]["is_valid"] is True
                assert res["providers"]["ollama"]["validation"]["retry_count"] == 0
                assert res["comparison"]["both_valid"] is True
                assert res["providers"]["groq"]["latency_ms"] >= 0.0
                assert res["providers"]["ollama"]["latency_ms"] >= 0.0

    def test_groq_retry_recovers_from_malformed_first_response(self, comparison_svc, valid_itinerary_json):
        """Groq fails schema validation on attempt 1, retries once, succeeds on attempt 2."""
        broken_first = "Here is an itinerary: Day 1 Skardu, price upon inquiry."  # not JSON
        call_count = [0]

        def mock_post_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock()
            if call_count[0] == 1:
                mock_resp.json.return_value = {"choices": [{"message": {"content": broken_first}}]}
            else:
                mock_resp.json.return_value = {"choices": [{"message": {"content": valid_itinerary_json}}]}
            return mock_resp

        with patch.object(comparison_svc.ollama_service, "is_available", return_value=False), \
             patch("services.model_comparison_service.post_groq_with_retry", side_effect=mock_post_side_effect):

            groq_res = comparison_svc._execute_groq_path(
                query="Plan Hunza tour",
                system_prompt="system",
                user_prompt="prompt",
                task_type="itinerary_draft",
            )

            assert call_count[0] == 2  # 1 initial + 1 retry
            assert groq_res["status"] == "success"
            assert groq_res["validation"]["is_valid"] is True
            assert groq_res["validation"]["retried"] is True
            assert groq_res["validation"]["retry_count"] == 1
            assert groq_res["structured_output"]["title"] == "5-Day Hunza Adventure"

    def test_ollama_fallback_to_error_state_when_retry_fails(self, comparison_svc):
        """Ollama returns invalid schema on both attempt 1 and retry attempt 2; falls back to error state."""
        broken_output = "I cannot generate valid JSON for this."

        with patch.object(comparison_svc.ollama_service, "is_available", return_value=True), \
             patch.object(comparison_svc.ollama_service, "generate_completion", return_value=broken_output) as mock_gen:

            ollama_res = comparison_svc._execute_ollama_path(
                query="Plan Skardu tour",
                system_prompt="system",
                user_prompt="prompt",
                task_type="itinerary_draft",
            )

            assert mock_gen.call_count == 2  # 1 initial + 1 retry
            assert ollama_res["status"] == "error"
            assert ollama_res["error_code"] == "SCHEMA_VALIDATION_FAILED"
            assert ollama_res["validation"]["is_valid"] is False
            assert ollama_res["validation"]["retried"] is True
            assert ollama_res["validation"]["retry_count"] == 1
            assert ollama_res["structured_output"] is None
            assert "rejected: failed schema validation after 1 retry" in ollama_res["error_message"]

    def test_ollama_offline_returns_clear_error_state(self, comparison_svc):
        """When local Ollama is offline, returns clear daemon unavailable error without crashing."""
        with patch.object(comparison_svc.ollama_service, "is_available", return_value=False):
            ollama_res = comparison_svc._execute_ollama_path(
                query="Plan tour",
                system_prompt="sys",
                user_prompt="usr",
                task_type="itinerary_draft",
            )
            assert ollama_res["status"] == "error"
            assert ollama_res["error_code"] == "DAEMON_UNAVAILABLE"
            assert "offline or unreachable" in ollama_res["error_message"]


@pytest.mark.django_db
class TestModelComparisonEndpoints:
    """Tests for the internal API endpoint and HTML dashboard view."""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def mock_comparison_result(self):
        return {
            "query": "5-Day Hunza Trek",
            "task_type": "itinerary_draft",
            "timestamp": "2026-09-11T18:00:00Z",
            "total_wall_clock_ms": 1250.5,
            "providers": {
                "groq": {
                    "provider": "groq",
                    "model": "openai/gpt-oss-120b",
                    "latency_ms": 420.2,
                    "status": "success",
                    "validation": {"is_valid": True, "retried": False, "retry_count": 0, "errors": []},
                    "raw_output": '{"title": "Hunza Trek"}',
                    "structured_output": {
                        "title": "5-Day Hunza Trek",
                        "destination": "Hunza",
                        "duration": "5 Days",
                        "price": "PKR 140,000",
                        "day_by_day": [{"day": 1, "title": "Gilgit to Karimabad", "description": "Scenic drive"}],
                        "inclusions": ["Guide", "Jeep"],
                    },
                },
                "ollama": {
                    "provider": "ollama",
                    "model": "llama3.2",
                    "latency_ms": 1180.4,
                    "status": "success",
                    "validation": {"is_valid": True, "retried": False, "retry_count": 0, "errors": []},
                    "raw_output": '{"title": "Hunza Trek"}',
                    "structured_output": {
                        "title": "5-Day Hunza Trek",
                        "destination": "Hunza",
                        "duration": "5 Days",
                        "price": "PKR 140,000",
                        "day_by_day": [{"day": 1, "title": "Gilgit to Karimabad", "description": "Scenic drive"}],
                        "inclusions": ["Guide", "Jeep"],
                    },
                },
            },
            "comparison": {
                "faster_provider": "groq",
                "latency_delta_ms": 760.2,
                "speed_ratio": "2.81x faster",
                "both_valid": True,
            },
        }

    def test_api_post_comparison_success(self, client, mock_comparison_result):
        url = reverse("model-comparison-api")
        with patch.object(model_comparison_service, "compare_live", return_value=mock_comparison_result):
            resp = client.post(url, data={"query": "5-Day Hunza Trek", "task_type": "itinerary_draft"}, format="json")
            assert resp.status_code == 200
            data = resp.json()
            assert data["query"] == "5-Day Hunza Trek"
            assert "groq" in data["providers"]
            assert "ollama" in data["providers"]
            assert data["comparison"]["faster_provider"] == "groq"
            assert data["comparison"]["both_valid"] is True

    def test_api_post_comparison_missing_query_returns_400(self, client):
        url = reverse("model-comparison-api")
        resp = client.post(url, data={"task_type": "itinerary_draft"}, format="json")
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_QUERY"

    def test_api_get_comparison_info(self, client):
        url = reverse("model-comparison-api")
        resp = client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert "configured_models" in data
        assert "supported_task_types" in data

    def test_html_dashboard_view_renders(self, client):
        url = reverse("model-comparison-dashboard")
        resp = client.get(url)
        assert resp.status_code == 200
        assert "text/html" in resp["Content-Type"]
        content = resp.content.decode("utf-8")
        assert "Live Multi-Model Comparison & Schema Guard" in content
        assert "Test Query / Visitor Message" in content
        assert "Run Live Comparison" in content

    def test_html_dashboard_view_with_query_executes(self, client, mock_comparison_result):
        url = reverse("model-comparison-dashboard")
        with patch.object(model_comparison_service, "compare_live", return_value=mock_comparison_result):
            resp = client.get(url, {"query": "5-Day Hunza Trek", "task_type": "itinerary_draft"})
            assert resp.status_code == 200
            content = resp.content.decode("utf-8")
            assert "Groq (Primary Cloud)" in content
            assert "Ollama (Secondary Local)" in content
            assert "VALID SCHEMA" in content
            assert "420.2 ms" in content
            assert "1180.4 ms" in content

    def test_comparison_logs_to_tool_call_log(self, client, mock_comparison_result):
        url = reverse("model-comparison-api")
        with patch.object(model_comparison_service, "compare_live", return_value=mock_comparison_result):
            resp = client.post(url, data={"query": "5-Day Hunza Trek"}, format="json")
            assert resp.status_code == 200
