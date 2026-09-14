"""
Ollama Secondary LLM Service for Humsafar.
Provides lightweight local processing (cleaning or summarizing raw scraped page content
before it reaches Groq), conserving Groq tokens and latency.
Logs tool calls to the observability service tracking Ollama as the responsible LLM.
"""

import os
import re
import time
import logging
from typing import Dict, Any, Optional
import httpx

from services.observability_service import log_tool_call

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"


class OllamaService:
    """
    Client for local Ollama instance serving as Humsafar's secondary LLM.
    Handles concrete light tasks such as cleaning and summarizing raw scraped
    webpage text before passing the grounded facts to Groq.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.timeout = timeout or float(os.getenv("OLLAMA_TIMEOUT", "45.0"))
        self._avail_cache: Optional[bool] = None
        self._avail_timestamp: float = 0.0

    @property
    def provider_label(self) -> str:
        return f"ollama:{self.model}"

    def get_available_models(self) -> list:
        """Retrieve list of locally pulled models from Ollama."""
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    return [m.get("name", "") for m in res.json().get("models", [])]
        except Exception:
            pass
        return []

    def resolve_model(self) -> str:
        """
        Dynamically resolve the model tag (e.g. mapping llama3.2:3b to llama3.2:latest)
        so local model naming differences never cause 404s.
        """
        available = self.get_available_models()
        if not available:
            return self.model

        # Exact match
        if self.model in available:
            return self.model

        # Prefix or base name match (e.g. llama3.2 matching llama3.2:latest)
        base = self.model.split(":")[0]
        for m in available:
            if m == base or m == f"{base}:latest" or m.startswith(f"{base}:"):
                return m

        # Fallback to first available model if any
        return available[0]

    def is_available(self) -> bool:
        """Check if local Ollama daemon is active and responding (cached for 15s)."""
        now = time.time()
        if self._avail_cache is not None and (now - self._avail_timestamp) < 15.0:
            return self._avail_cache

        try:
            with httpx.Client(timeout=0.75) as client:
                res = client.get(f"{self.base_url}/api/tags")
                self._avail_cache = bool(res.status_code == 200)
        except Exception:
            self._avail_cache = False

        self._avail_timestamp = now
        return self._avail_cache

    def generate_completion(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1000,
        temperature: float = 0.2,
        session_id: str = "default",
    ) -> Optional[str]:
        """
        Generate a completion using local Ollama as secondary LLM failover
        when primary Groq service hits rate limits or is offline.
        """
        if not self.is_available():
            return None

        start_time = time.time()
        active_model = self.resolve_model()
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        payload = {
            "model": active_model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data.get("response", "").strip()
                if not text:
                    return None

                duration_ms = (time.time() - start_time) * 1000
                log_tool_call(
                    session_id=session_id,
                    skill="secondary_llm_fallback",
                    tool_name="ollama_generate_completion",
                    status="success",
                    llm_provider=f"ollama:{active_model}",
                    input_data={"prompt_snippet": prompt[:200]},
                    output_data={"response_snippet": text[:200]},
                    duration_ms=duration_ms,
                )
                return text
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            logger.warning("Ollama generate_completion failed: %s", exc)
            log_tool_call(
                session_id=session_id,
                skill="secondary_llm_fallback",
                tool_name="ollama_generate_completion",
                status="failed",
                llm_provider=f"ollama:{active_model}",
                input_data={"prompt_snippet": prompt[:200]},
                error_message=str(exc),
                duration_ms=duration_ms,
            )
            return None

    def clean_and_summarize_scraped_content(
        self,
        raw_content: str,
        title: str = "",
        source_url: str = "",
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Concrete light task: Clean and summarize raw scraped page content
        before it reaches Groq. Removes HTML remnants, navigation boilerplate,
        and irrelevant text while preserving itinerary milestones, altitude,
        and logistical details.
        """
        if not raw_content or not raw_content.strip():
            return {
                "success": True,
                "cleaned_content": "",
                "llm_provider": self.provider_label,
                "fallback_used": False,
            }

        # Fast path: if Ollama is not active, clean with regex instantaneously without network delay
        if not self.is_available():
            clean_fast = re.sub(r"\s+", " ", raw_content).strip()[:450]
            return {
                "success": True,
                "cleaned_content": clean_fast,
                "llm_provider": self.provider_label,
                "fallback_used": True,
            }

        start_time = time.time()
        # Truncate overly long content before sending to local model
        truncated_raw = raw_content.strip()[:2000]

        prompt = (
            "You are a travel content cleaning engine. Clean the following raw scraped website text. "
            "Remove website navigation, menus, copyright notices, and boilerplate. "
            "Summarize the key itinerary facts (destinations, route milestones, altitude, inclusions, highlights) "
            "into concise, high-density factual text for a trip planner.\n\n"
            f"TITLE: {title}\n"
            f"RAW CONTENT:\n{truncated_raw}\n\n"
            "CLEANED SUMMARY:"
        )

        active_model = self.resolve_model()
        payload = {
            "model": active_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 100,
            },
        }

        try:
            # Short timeout for scraping cleaning so user chat is never blocked
            with httpx.Client(timeout=min(self.timeout, 4.0)) as client:
                resp = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                cleaned_text = data.get("response", "").strip()

                if not cleaned_text:
                    raise ValueError("Ollama returned empty response.")

                duration_ms = (time.time() - start_time) * 1000

                # Log successful execution in observability table
                log_tool_call(
                    session_id=session_id,
                    skill="content_cleaning",
                    tool_name="clean_scraped_content",
                    status="success",
                    llm_provider=self.provider_label,
                    input_data={
                        "title": title,
                        "source_url": source_url,
                        "raw_length": len(raw_content),
                    },
                    output_data={
                        "cleaned_length": len(cleaned_text),
                        "summary_snippet": cleaned_text[:250],
                    },
                    duration_ms=duration_ms,
                )

                return {
                    "success": True,
                    "cleaned_content": cleaned_text,
                    "llm_provider": self.provider_label,
                    "fallback_used": False,
                    "duration_ms": duration_ms,
                }

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            error_str = str(exc)
            logger.info("Ollama cleaning unavailable (%s); falling back to heuristic cleaner.", error_str)

            # Deterministic heuristic fallback cleaner
            fallback_text = self._heuristic_clean(truncated_raw)

            # Log failed execution with fallback in observability table
            log_tool_call(
                session_id=session_id,
                skill="content_cleaning",
                tool_name="clean_scraped_content",
                status="failed",
                llm_provider=self.provider_label,
                input_data={
                    "title": title,
                    "source_url": source_url,
                    "raw_length": len(raw_content),
                },
                output_data={
                    "cleaned_length": len(fallback_text),
                    "summary_snippet": fallback_text[:250],
                    "fallback_used": True,
                },
                error_message=f"Ollama call failed: {error_str}",
                duration_ms=duration_ms,
            )

            return {
                "success": False,
                "cleaned_content": fallback_text,
                "llm_provider": self.provider_label,
                "fallback_used": True,
                "error": error_str,
                "duration_ms": duration_ms,
            }

    def _heuristic_clean(self, text: str) -> str:
        """Deterministic cleanup of raw scraped text when Ollama is offline."""
        # Remove multiple newlines and spaces
        cleaned = re.sub(r"<[^>]+>", " ", text)
        cleaned = re.sub(r"[\r\t]+", " ", cleaned)
        cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
        cleaned = re.sub(r"[ ]{2,}", " ", cleaned)
        # Strip common web nav patterns
        cleaned = re.sub(r"(?i)\b(?:home|about us|contact us|tours|expeditions|destinations|search|menu|cart)\b", "", cleaned)
        lines = [line.strip() for line in cleaned.split("\n") if len(line.strip()) > 20]
        result = "\n".join(lines[:8])
        return result.strip() if result else text[:500].strip()

    def distill_uploaded_document_content(
        self,
        raw_text: str,
        filename: str = "",
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Distill raw extracted text from a traveler-uploaded document (ticket, itinerary,
        hotel booking, screenshot) into only the relevant travel fields before it reaches Groq.
        """
        if not raw_text or not raw_text.strip():
            return {
                "success": True,
                "distilled_content": "",
                "llm_provider": self.provider_label,
                "fallback_used": False,
            }

        start_time = time.time()
        truncated_raw = raw_text.strip()[:3500]

        if not self.is_available():
            fallback_text = self._heuristic_distill_document(truncated_raw)
            return {
                "success": True,
                "distilled_content": fallback_text,
                "llm_provider": self.provider_label,
                "fallback_used": True,
            }

        prompt = (
            "You are a travel document distillation engine for Humsafar. "
            "The traveler uploaded a document (travel ticket, itinerary, hotel voucher, or booking screenshot). "
            "Extract and distill ONLY the relevant travel facts into a concise summary:\n"
            "- Destination & Regions\n"
            "- Travel Dates, Duration, & Schedule\n"
            "- Flights, Transport, & Vehicle bookings\n"
            "- Lodging & Accommodation details\n"
            "- Itinerary stops or planned activities\n"
            "- Budget, Payments, & Costs mentioned\n"
            "- Special traveler preferences or notes\n\n"
            "Exclude all fine print, terms and conditions, barcode numbers, legal disclaimers, and irrelevant marketing text.\n\n"
            f"FILENAME: {filename}\n"
            f"DOCUMENT TEXT:\n{truncated_raw}\n\n"
            "DISTILLED TRAVEL FACTS:"
        )

        active_model = self.resolve_model()
        payload = {
            "model": active_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 250,
            },
        }

        try:
            with httpx.Client(timeout=min(self.timeout, 8.0)) as client:
                resp = client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                distilled = resp.json().get("response", "").strip()

                if not distilled:
                    raise ValueError("Ollama returned empty distillation.")

                duration_ms = (time.time() - start_time) * 1000
                log_tool_call(
                    session_id=session_id,
                    skill="document_distillation",
                    tool_name="distill_uploaded_document",
                    status="success",
                    llm_provider=self.provider_label,
                    input_data={"filename": filename, "raw_length": len(raw_text)},
                    output_data={"distilled_length": len(distilled), "summary_snippet": distilled[:200]},
                    duration_ms=duration_ms,
                )

                return {
                    "success": True,
                    "distilled_content": distilled,
                    "llm_provider": self.provider_label,
                    "fallback_used": False,
                    "duration_ms": duration_ms,
                }

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            error_str = str(exc)
            logger.info("Ollama document distillation unavailable (%s); using heuristic distillation.", error_str)
            fallback_text = self._heuristic_distill_document(truncated_raw)

            log_tool_call(
                session_id=session_id,
                skill="document_distillation",
                tool_name="distill_uploaded_document",
                status="failed",
                llm_provider=self.provider_label,
                input_data={"filename": filename, "raw_length": len(raw_text)},
                output_data={"distilled_length": len(fallback_text), "summary_snippet": fallback_text[:200], "fallback_used": True},
                error_message=f"Ollama distillation failed: {error_str}",
                duration_ms=duration_ms,
            )

            return {
                "success": False,
                "distilled_content": fallback_text,
                "llm_provider": self.provider_label,
                "fallback_used": True,
                "error": error_str,
                "duration_ms": duration_ms,
            }

    def _heuristic_distill_document(self, text: str) -> str:
        """Deterministic travel field distillation when Ollama is offline."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        relevant_keywords = {
            "flight", "hotel", "stay", "check-in", "check-out", "day", "destination",
            "skardu", "hunza", "gilgit", "islamabad", "k2", "trek", "tour", "pkr", "usd",
            "rs", "price", "cost", "date", "departure", "arrival", "ticket", "passenger",
            "booking", "pnr", "seat", "route", "itinerary"
        }
        extracted = []
        for line in lines:
            lower = line.lower()
            if any(k in lower for k in relevant_keywords) or re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", line) or re.search(r"\b\d+\s*(?:days?|nights?)\b", lower):
                if len(line) < 160:
                    extracted.append(line)

        if extracted:
            return "\n".join(extracted[:12])
        # Fallback to compact slice
        clean_fast = re.sub(r"\s+", " ", text).strip()
        return clean_fast[:500]


# Singleton instance
ollama_service = OllamaService()

