"""
Live Multi-Model Comparison Service for Humsafar (Phase 12).
Routes the exact same query concurrently to both Groq and Ollama,
measures latency for each, enforces schema validation with a single-retry policy,
and packages side-by-side results for evaluation.
"""

import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, Tuple, List
import httpx
from django.utils import timezone

from services.groq_service import (
    post_groq_with_retry,
    strip_think_tags,
    DEFAULT_MODEL as DEFAULT_GROQ_MODEL,
    GROQ_API_URL,
)
from services.ollama_service import (
    ollama_service,
    DEFAULT_OLLAMA_MODEL,
)
from services.schema_guard import (
    schema_guard,
    ValidationResult,
)
from services.observability_service import log_tool_call

logger = logging.getLogger(__name__)


class ModelComparisonService:
    """
    Coordinates simultaneous execution of user queries against both
    Groq (primary cloud LLM) and Ollama (local secondary LLM), enforcing
    output schema validation and single-retry recovery on both paths.
    """

    def __init__(self):
        self.groq_model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.ollama_service = ollama_service

    def _build_task_prompts(
        self,
        query: str,
        task_type: str = "itinerary_draft",
    ) -> Tuple[str, str]:
        """
        Build system prompt and user prompt appropriate for the evaluated task type.
        """
        if task_type == "itinerary_draft":
            system_prompt = (
                "You are Humsafar, the mountain expedition planning AI for Askoli Adventure (askoliadventure.com).\n"
                "When asked to draft an itinerary, you MUST respond strictly with a valid JSON object adhering to this schema:\n"
                "{\n"
                '  "title": "string (e.g. 5-Day Hunza Expedition)",\n'
                '  "destination": "string (e.g. Hunza Valley)",\n'
                '  "duration": "string (e.g. 5 Days)",\n'
                '  "duration_days": integer (e.g. 5),\n'
                '  "price": "string (e.g. PKR 120,000 - 160,000 ($450 - $600 USD))",\n'
                '  "day_by_day": [\n'
                '    {"day": 1, "title": "Day Title", "description": "Day Description", "altitude": "Elevation"}\n'
                "  ],\n"
                '  "inclusions": ["Guide", "Transport", "Meals", "Hotels"],\n'
                '  "exclusions": ["Flights", "Personal Insurance", "Tips"]\n'
                "}\n"
                "Return ONLY the raw JSON object. Do not enclose in backticks if possible, and do not add conversational prose."
            )
            user_prompt = (
                f"Draft a complete itinerary for the following request:\n{query}\n\n"
                "Remember: output strictly valid JSON matching the required schema."
            )
        else:
            system_prompt = (
                "You are Humsafar, the official AI travel planning companion for Askoli Adventure (askoliadventure.com).\n"
                "Tagline: 'Plan better. Travel farther.'\n"
                "Provide a warm, hospitable, concise, and helpful response for the traveler's question.\n"
                "Do NOT output internal reasoning tags like <think> or </think>."
            )
            user_prompt = query

        return system_prompt, user_prompt

    def _execute_groq_path(
        self,
        query: str,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "itinerary_draft",
    ) -> Dict[str, Any]:
        """
        Execute query against Groq API with latency measurement, schema validation,
        and single-retry recovery if validation fails.
        """
        start_time = time.perf_counter()
        key = self.groq_api_key or os.getenv("GROQ_API_KEY", "").strip()
        model_name = self.groq_model

        if not key:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "provider": "groq",
                "model": model_name,
                "latency_ms": round(elapsed_ms, 2),
                "status": "error",
                "error_code": "API_KEY_MISSING",
                "error_message": "GROQ_API_KEY is not configured.",
                "validation": {
                    "is_valid": False,
                    "retried": False,
                    "retry_count": 0,
                    "errors": ["API key missing"],
                },
                "raw_output": None,
                "structured_output": None,
            }

        def _call_groq(prompt_text: str, max_tokens: int = 800) -> Tuple[str, Optional[str]]:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text},
            ]
            with httpx.Client(timeout=30.0) as client:
                resp = post_groq_with_retry(
                    client,
                    payload={
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": max_tokens,
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                )
                data = resp.json()
                raw_reply = data["choices"][0]["message"]["content"]
                return strip_think_tags(raw_reply), None

        retried = False
        retry_count = 0
        raw_output = ""

        try:
            # 1. Initial generation
            raw_output, err = _call_groq(user_prompt)
            if err:
                raise RuntimeError(err)

            # 2. Schema guard validation
            schema_type = "itinerary_draft" if task_type == "itinerary_draft" else "conversational"
            val_result = schema_guard.validate(raw_output, schema_type=schema_type)

            # 3. Single retry if invalid
            if not val_result.is_valid:
                logger.info("Groq output failed schema guard (%s). Triggering 1 retry...", val_result.error_message)
                retried = True
                retry_count = 1
                retry_prompt = schema_guard.generate_retry_prompt(
                    original_query=query,
                    validation_errors=val_result.errors,
                    schema_type=schema_type,
                )
                retry_output, retry_err = _call_groq(retry_prompt, max_tokens=900)
                if not retry_err and retry_output:
                    raw_output = retry_output
                    val_result = schema_guard.validate(raw_output, schema_type=schema_type)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if val_result.is_valid:
                return {
                    "provider": "groq",
                    "model": model_name,
                    "latency_ms": round(elapsed_ms, 2),
                    "status": "success",
                    "validation": {
                        "is_valid": True,
                        "retried": retried,
                        "retry_count": retry_count,
                        "errors": [],
                    },
                    "raw_output": raw_output,
                    "structured_output": val_result.data,
                }
            else:
                return {
                    "provider": "groq",
                    "model": model_name,
                    "latency_ms": round(elapsed_ms, 2),
                    "status": "error",
                    "error_code": "SCHEMA_VALIDATION_FAILED",
                    "error_message": f"Output rejected: failed schema validation after {retry_count} retry. Errors: {val_result.error_message}",
                    "validation": {
                        "is_valid": False,
                        "retried": retried,
                        "retry_count": retry_count,
                        "errors": val_result.errors,
                    },
                    "raw_output": raw_output,
                    "structured_output": None,
                }

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("Groq path execution error: %s", exc)
            return {
                "provider": "groq",
                "model": model_name,
                "latency_ms": round(elapsed_ms, 2),
                "status": "error",
                "error_code": "PROVIDER_CALL_FAILED",
                "error_message": str(exc),
                "validation": {
                    "is_valid": False,
                    "retried": retried,
                    "retry_count": retry_count,
                    "errors": [str(exc)],
                },
                "raw_output": raw_output or None,
                "structured_output": None,
            }

    def _execute_ollama_path(
        self,
        query: str,
        system_prompt: str,
        user_prompt: str,
        task_type: str = "itinerary_draft",
    ) -> Dict[str, Any]:
        """
        Execute query against local Ollama instance with latency measurement,
        schema validation, and single-retry recovery if validation fails.
        """
        start_time = time.perf_counter()
        active_model = self.ollama_service.resolve_model()

        if not self.ollama_service.is_available():
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return {
                "provider": "ollama",
                "model": active_model,
                "latency_ms": round(elapsed_ms, 2),
                "status": "error",
                "error_code": "DAEMON_UNAVAILABLE",
                "error_message": f"Local Ollama daemon is offline or unreachable at {self.ollama_service.base_url}.",
                "validation": {
                    "is_valid": False,
                    "retried": False,
                    "retry_count": 0,
                    "errors": ["Ollama daemon offline"],
                },
                "raw_output": None,
                "structured_output": None,
            }

        def _call_ollama(prompt_text: str, max_tokens: int = 500) -> Tuple[str, Optional[str]]:
            output = self.ollama_service.generate_completion(
                prompt=prompt_text,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.2,
                session_id="comparison_ollama",
            )
            if not output:
                return "", "Ollama returned empty response or timed out."
            return strip_think_tags(output), None

        retried = False
        retry_count = 0
        raw_output = ""

        try:
            # 1. Initial generation
            raw_output, err = _call_ollama(user_prompt)
            if err:
                raise RuntimeError(err)

            # 2. Schema guard validation
            schema_type = "itinerary_draft" if task_type == "itinerary_draft" else "conversational"
            val_result = schema_guard.validate(raw_output, schema_type=schema_type)

            # 3. Single retry if invalid
            if not val_result.is_valid:
                logger.info("Ollama output failed schema guard (%s). Triggering 1 retry...", val_result.error_message)
                retried = True
                retry_count = 1
                retry_prompt = schema_guard.generate_retry_prompt(
                    original_query=query,
                    validation_errors=val_result.errors,
                    schema_type=schema_type,
                )
                retry_output, retry_err = _call_ollama(retry_prompt, max_tokens=600)
                if not retry_err and retry_output:
                    raw_output = retry_output
                    val_result = schema_guard.validate(raw_output, schema_type=schema_type)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if val_result.is_valid:
                return {
                    "provider": "ollama",
                    "model": active_model,
                    "latency_ms": round(elapsed_ms, 2),
                    "status": "success",
                    "validation": {
                        "is_valid": True,
                        "retried": retried,
                        "retry_count": retry_count,
                        "errors": [],
                    },
                    "raw_output": raw_output,
                    "structured_output": val_result.data,
                }
            else:
                return {
                    "provider": "ollama",
                    "model": active_model,
                    "latency_ms": round(elapsed_ms, 2),
                    "status": "error",
                    "error_code": "SCHEMA_VALIDATION_FAILED",
                    "error_message": f"Output rejected: failed schema validation after {retry_count} retry. Errors: {val_result.error_message}",
                    "validation": {
                        "is_valid": False,
                        "retried": retried,
                        "retry_count": retry_count,
                        "errors": val_result.errors,
                    },
                    "raw_output": raw_output,
                    "structured_output": None,
                }

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("Ollama path execution error: %s", exc)
            return {
                "provider": "ollama",
                "model": active_model,
                "latency_ms": round(elapsed_ms, 2),
                "status": "error",
                "error_code": "PROVIDER_CALL_FAILED",
                "error_message": str(exc),
                "validation": {
                    "is_valid": False,
                    "retried": retried,
                    "retry_count": retry_count,
                    "errors": [str(exc)],
                },
                "raw_output": raw_output or None,
                "structured_output": None,
            }

    def compare_live(
        self,
        query: str,
        task_type: str = "itinerary_draft",
        session_id: str = "internal-comparison",
    ) -> Dict[str, Any]:
        """
        Simultaneously dispatch the same query to Groq and Ollama,
        collect side-by-side results with latency and schema guard validation,
        and log the comparison run to the observability chain.
        """
        system_prompt, user_prompt = self._build_task_prompts(query, task_type=task_type)

        overall_start = time.perf_counter()
        results: Dict[str, Any] = {}

        # Run both paths concurrently in parallel threads
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="model_comp") as executor:
            future_groq = executor.submit(
                self._execute_groq_path,
                query=query,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type=task_type,
            )
            future_ollama = executor.submit(
                self._execute_ollama_path,
                query=query,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                task_type=task_type,
            )

            results["groq"] = future_groq.result()
            results["ollama"] = future_ollama.result()

        total_elapsed_ms = (time.perf_counter() - overall_start) * 1000

        groq_lat = results["groq"].get("latency_ms", 0.0)
        ollama_lat = results["ollama"].get("latency_ms", 0.0)

        # Comparative analytics
        if results["groq"].get("status") == "success" and results["ollama"].get("status") == "success":
            if groq_lat < ollama_lat:
                faster = "groq"
                delta_ms = round(ollama_lat - groq_lat, 2)
                ratio = round(ollama_lat / max(groq_lat, 1.0), 2)
            elif ollama_lat < groq_lat:
                faster = "ollama"
                delta_ms = round(groq_lat - ollama_lat, 2)
                ratio = round(groq_lat / max(ollama_lat, 1.0), 2)
            else:
                faster = "tie"
                delta_ms = 0.0
                ratio = 1.0
        elif results["groq"].get("status") == "success":
            faster = "groq"
            delta_ms = round(ollama_lat - groq_lat, 2)
            ratio = None
        elif results["ollama"].get("status") == "success":
            faster = "ollama"
            delta_ms = round(groq_lat - ollama_lat, 2)
            ratio = None
        else:
            faster = "none"
            delta_ms = 0.0
            ratio = None

        comparison_payload = {
            "query": query,
            "task_type": task_type,
            "timestamp": timezone.now().isoformat(),
            "total_wall_clock_ms": round(total_elapsed_ms, 2),
            "providers": results,
            "comparison": {
                "faster_provider": faster,
                "latency_delta_ms": delta_ms,
                "speed_ratio": f"{ratio}x faster" if ratio else "N/A",
                "both_valid": (
                    results["groq"].get("validation", {}).get("is_valid", False)
                    and results["ollama"].get("validation", {}).get("is_valid", False)
                ),
            },
        }

        # Log comparison event into ToolCallLog for full observability
        try:
            log_tool_call(
                session_id=session_id,
                skill="live_model_comparison",
                tool_name="compare_groq_vs_ollama",
                status="success" if (results["groq"]["status"] == "success" or results["ollama"]["status"] == "success") else "failed",
                llm_provider=f"groq:{self.groq_model}+ollama:{results['ollama'].get('model', 'llama3.2')}",
                input_data={"query": query, "task_type": task_type},
                output_data={
                    "groq_latency_ms": groq_lat,
                    "ollama_latency_ms": ollama_lat,
                    "faster": faster,
                    "both_valid": comparison_payload["comparison"]["both_valid"],
                },
                duration_ms=total_elapsed_ms,
            )
        except Exception as log_exc:
            logger.warning("Observability logging for model comparison skipped: %s", log_exc)

        return comparison_payload


# Singleton instance
model_comparison_service = ModelComparisonService()
