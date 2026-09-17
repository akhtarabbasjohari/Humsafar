"""
Unit and integration tests for FeasibilityEngine and dynamic feasibility reasoning.
Verifies:
1. Physical impossibility detection for high-altitude treks (e.g. K2 Base Camp, Gondogoro La in <= 4 days).
2. Mountain transit overhead constraints for multi-valley trips (e.g. Hunza + Skardu in <= 3 days).
3. Plain-language explanation of physical constraints and dynamic generation of realistic alternatives.
4. Feasible requests passing cleanly without false alarms.
5. Integration with HumsafarAgentRunner and draft_custom_itinerary.
"""

import pytest
from services.feasibility_engine import feasibility_engine, FeasibilityEvaluation
from services.itinerary_drafter import draft_custom_itinerary, TravelerPreferences
from apps.chat.services.agent_runner import HumsafarAgentRunner


class TestFeasibilityEngine:
    """Test unit rules of FeasibilityEngine."""

    def test_k2_base_camp_impossible_duration(self):
        """K2 Base Camp reaches 5,150m and requires >=14 days. 3 days must be rejected."""
        eval_res = feasibility_engine.evaluate(
            destination="K2 Base Camp",
            duration_days=3,
            user_message="I want to trek to K2 base camp in 3 days",
        )
        assert eval_res.is_feasible is False
        assert "5150m" in eval_res.reason or "5,150m" in eval_res.reason or "acclimatization" in eval_res.reason.lower()
        assert eval_res.suggested_minimum_days >= 14
        assert "Option A" in eval_res.alternative_scope
        assert len(eval_res.logistics_breakdown) > 0

    def test_multi_valley_short_duration_infeasible(self):
        """Trying to do Hunza AND Skardu in 2 days must be rejected due to mountain road transit."""
        eval_res = feasibility_engine.evaluate(
            destination="Hunza and Skardu",
            duration_days=2,
            user_message="Can we visit both Hunza and Skardu over a 2 day weekend?",
        )
        assert eval_res.is_feasible is False
        assert "transit" in eval_res.reason.lower() or "road" in eval_res.reason.lower()
        assert eval_res.suggested_minimum_days >= 6

    def test_feasible_hunza_tour(self):
        """5 days in Hunza Valley is completely feasible."""
        eval_res = feasibility_engine.evaluate(
            destination="Hunza Valley",
            duration_days=5,
            user_message="Plan a 5 day leisure trip to Hunza Valley for my family",
        )
        assert eval_res.is_feasible is True
        assert eval_res.suggested_minimum_days == 5

    def test_feasible_k2_expedition(self):
        """18 days for K2 Base Camp & Concordia is realistic and feasible."""
        eval_res = feasibility_engine.evaluate(
            destination="K2 Base Camp & Concordia Trek",
            duration_days=18,
            user_message="We have 18 days for K2 Base Camp expedition",
        )
        assert eval_res.is_feasible is True

    def test_drafter_returns_feasibility_advisory(self):
        """draft_custom_itinerary should return feasibility advisory when asked for impossible trek."""
        prefs = TravelerPreferences(
            destination="K2 Base Camp",
            duration="3 Days",
            duration_days=3,
        )
        res = draft_custom_itinerary(
            user_message="Plan a 3-day trek to K2 base camp",
            conversation_history=[],
            destination="K2 Base Camp",
            web_research={"results": [], "research_summary": ""},
            preferences=prefs,
        )
        assert res["is_feasible"] is False
        assert res["itinerary_draft"] is None
        assert "Feasibility & Safety Advisory" in res["consultant_reply"]


@pytest.mark.django_db
class TestAgentRunnerFeasibilityIntegration:
    """Test integration in HumsafarAgentRunner."""

    def test_agent_runner_returns_feasibility_advisory_path(self):
        from unittest.mock import patch
        runner = HumsafarAgentRunner()
        with patch.object(runner, "run_agentic_tool_loop") as mock_loop:
            mock_loop.return_value = {
                "path": "feasibility_advisory",
                "reply_text": "Trekking to K2 Base Camp in 2 days is physically impossible and life-threatening.",
                "itinerary": None,
                "confidence_label": None,
                "source_url": None,
                "reasoning_steps": [],
            }
            res = runner.run_multi_hop_pipeline(
                user_message="Can I do a 2-day trek to K2 Base Camp from Islamabad?",
                session_id="test-feasibility-sess",
            )
            assert res["path"] == "feasibility_advisory"
            assert res["itinerary"] is None
            assert "impossible" in res["reply_text"].lower()



