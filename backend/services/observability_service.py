"""
Observability service for tool calls and multi-hop reasoning steps in Humsafar.
Provides structured recording and querying of tool executions:
- itinerary check (itinerary_lookup)
- region check (region_coverage_check)
- web search (web_search_fallback)
- itinerary drafting (itinerary_drafting)
- scraped content cleaning/summarizing (content_cleaning)
Tracks timestamps, triggering skills, success/failure status, input/output data,
execution durations, and the LLM provider (Ollama vs Groq) responsible for each step.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def log_tool_call(
    session_id: str,
    skill: str,
    tool_name: str,
    status: str = "success",
    llm_provider: str = "",
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    error_message: str = "",
    duration_ms: Optional[float] = None,
) -> Optional[Any]:
    """
    Persist an execution log to the ToolCallLog queryable table.
    Fails safely without breaking conversational execution flow.
    """
    try:
        from apps.chat.models import ToolCallLog

        clean_session_id = str(session_id) if session_id else "default"
        clean_input = input_data or {}
        clean_output = output_data or {}

        # Truncate any massive strings in input/output to keep table queries snappy
        def _sanitize(obj: Any) -> Any:
            if isinstance(obj, str):
                return obj[:2000] + ("..." if len(obj) > 2000 else "")
            elif isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_sanitize(item) for item in obj[:15]]
            return obj

        entry = ToolCallLog.objects.create(
            session_id=clean_session_id,
            skill=skill,
            tool_name=tool_name,
            status="failed" if status in ["failed", "error", False] else "success",
            llm_provider=llm_provider,
            input_data=_sanitize(clean_input),
            output_data=_sanitize(clean_output),
            error_message=str(error_message) if error_message else "",
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            created_at=datetime.now(timezone.utc),
        )
        return entry
    except Exception as exc:
        logger.warning("Failed to record ToolCallLog entry: %s", exc)
        return None


def get_session_logs(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve all chronological tool call logs for a session."""
    try:
        from apps.chat.models import ToolCallLog
        qs = ToolCallLog.objects.filter(session_id=str(session_id)).order_by("created_at")
        return [
            {
                "id": str(log.id),
                "session_id": log.session_id,
                "skill": log.skill,
                "tool_name": log.tool_name,
                "status": log.status,
                "llm_provider": log.llm_provider,
                "input_data": log.input_data,
                "output_data": log.output_data,
                "error_message": log.error_message,
                "duration_ms": log.duration_ms,
                "created_at": log.created_at.isoformat(),
            }
            for log in qs
        ]
    except Exception as exc:
        logger.error("Error retrieving session tool logs for %s: %s", session_id, exc)
        return []
