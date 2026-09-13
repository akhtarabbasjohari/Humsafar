"""
Targeted test suite verifying that Humsafar does NOT force itinerary generation
when the user asks general knowledge questions, travel advice, or pricing for their own plans.
"""

import pytest
import re
from apps.chat.services.agent_runner import HumsafarAgentRunner, classify_user_intent

agent_runner = HumsafarAgentRunner()


@pytest.mark.django_db
class TestIntentRoutingAndNoForcedItinerary:
    def test_classify_intent_pricing(self):
        """Pricing questions should be classified as 'pricing'."""
        assert classify_user_intent("How much will a 5-day trip to Skardu cost?") == "pricing"
        assert classify_user_intent("What is the budget for Hunza for 2 people?") == "pricing"
        assert classify_user_intent("Skardu jane me kitna kharcha aayega?") == "pricing"
        assert classify_user_intent("I have a plan: Day 1 Skardu, Day 2 Shigar. What will be the price?") == "pricing"
        assert classify_user_intent("My plan is 4 days in Swat, how much will you charge?") == "pricing"

    def test_classify_intent_general_knowledge(self):
        """General curiosity, culture, weather, road questions should be 'general_knowledge'."""
        assert classify_user_intent("Tell me about Hunza valley culture and traditions") == "general_knowledge"
        assert classify_user_intent("What are the best places to visit in Swat?") == "general_knowledge"
        assert classify_user_intent("Is the road to Babusar Top open in May?") == "general_knowledge"
        assert classify_user_intent("Is Skardu safe for family with kids?") == "general_knowledge"
        assert classify_user_intent("Swat me ghoomne ki achi jaghein konsi hain?") == "general_knowledge"

    def test_classify_intent_itinerary_planning(self):
        """Explicit planning requests should be classified as 'itinerary_planning'."""
        assert classify_user_intent("Plan a 5-day trip to Hunza for me") == "itinerary_planning"
        assert classify_user_intent("Make an itinerary for Skardu") == "itinerary_planning"
        assert classify_user_intent("7-day tour plan for Chitral and Kalash") == "itinerary_planning"
        assert classify_user_intent("Mujhe Skardu ka 5 din ka plan bana ke do") == "itinerary_planning"

    def test_pricing_query_returns_no_forced_itinerary(self):
        """When asking for price/cost, agent provides pricing breakdown and does NOT attach an itinerary card."""
        result = agent_runner.run_multi_hop_pipeline(
            user_message="How much does a 5-day trip to Skardu cost for 2 people?",
            session_id="test-intent-pricing-1",
        )
        assert result["path"] == "pricing_inquiry"
        assert result["itinerary"] is None
        reply = result["reply_text"]
        assert len(reply) > 0
        assert "PKR" in reply or "$" in reply or "USD" in reply
        # Should not force day-by-day table in prose
        assert not re.search(r"\|\s*Day\s*\|\s*Route", reply, re.IGNORECASE)

    def test_user_own_plan_pricing_returns_no_forced_itinerary(self):
        """When user shares their own plan and asks for pricing, agent evaluates cost without forcing a new itinerary."""
        result = agent_runner.run_multi_hop_pipeline(
            user_message="I have a plan: Day 1 Skardu, Day 2 Shangrila, Day 3 Deosai. What will this cost?",
            session_id="test-intent-pricing-user-plan",
        )
        assert result["path"] == "pricing_inquiry"
        assert result["itinerary"] is None
        reply = result["reply_text"]
        assert len(reply) > 0
        assert "PKR" in reply or "$" in reply or "USD" in reply

    def test_general_knowledge_query_returns_no_forced_itinerary(self):
        """When asking about attractions/culture, agent provides informative advice without attaching an itinerary card."""
        result = agent_runner.run_multi_hop_pipeline(
            user_message="Tell me about Hunza valley culture and historical forts",
            session_id="test-intent-gk-1",
        )
        assert result["path"] in ["general_knowledge", "factual"]
        assert result["itinerary"] is None
        reply = result["reply_text"]
        assert len(reply) > 0
        assert not re.search(r"\|\s*Day\s*\|\s*Route", reply, re.IGNORECASE)

    def test_explicit_planning_still_generates_itinerary(self):
        """When traveler explicitly asks to plan a trip, the agent produces full structured itinerary."""
        result = agent_runner.run_multi_hop_pipeline(
            user_message="Plan a 5 day tour to Hunza for me with 2 people",
            session_id="test-intent-planning-1",
        )
        assert result["path"] in ["official_match", "web_search_draft"]
        assert result["itinerary"] is not None
        assert "day_by_day" in result["itinerary"]
        assert len(result["itinerary"]["day_by_day"]) >= 3
