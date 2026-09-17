"""
Unit tests for MCP Server and Agent Runner tool integration.
"""

import pytest
from unittest.mock import MagicMock, patch
from mcp_servers.humsafar_data_mcp.server import (
    search_itineraries,
    check_region_coverage,
    mcp_server,
)
from apps.chat.services.agent_runner import HumsafarAgentRunner, AVAILABLE_TOOLS


def test_mcp_server_initialization():
    assert mcp_server.name == "humsafar-data-mcp"


def test_agent_runner_tool_dispatch():
    runner = HumsafarAgentRunner()

    mock_search_return = {
        "success": True,
        "query": "Hunza",
        "results": [{"title": "7-Day Hunza Tour", "duration": "7 Days", "price": "PKR 195,000"}],
        "cached": False,
    }

    mock_coverage_return = {
        "success": True,
        "destination": "Skardu",
        "serviced": True,
        "matched_regions": ["Baltistan"],
        "cached": False,
    }

    with patch("apps.chat.services.agent_runner.search_itineraries", return_value=mock_search_return) as mock_s:
        result = runner.execute_tool("search_itineraries", {"query": "Hunza"}, session_id="test-123")
        assert result["success"] is True
        assert len(result["results"]) == 1
        mock_s.assert_called_once_with(query="Hunza", session_id="test-123")

    with patch("apps.chat.services.agent_runner.check_region_coverage", return_value=mock_coverage_return) as mock_c:
        result = runner.execute_tool("check_region_coverage", {"destination": "Skardu"}, session_id="test-123")
        assert result["success"] is True
        assert result["serviced"] is True
        mock_c.assert_called_once_with(destination="Skardu", session_id="test-123")


def test_agent_runner_unknown_tool():
    runner = HumsafarAgentRunner()
    result = runner.execute_tool("nonexistent_tool", {})
    assert result["success"] is False
    assert "Unknown tool" in result["error"]


def test_tool_definitions():
    runner = HumsafarAgentRunner()
    tools = runner.get_tool_definitions()
    assert len(tools) == 2
    tool_names = [t["function"]["name"] for t in tools]
    assert "search_itineraries" in tool_names
    assert "check_region_coverage" in tool_names
