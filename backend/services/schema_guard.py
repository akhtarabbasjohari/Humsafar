"""
Output Schema Guard for Humsafar.
Enforces structural integrity and validation rules across LLM generation paths.
Rejects malformed outputs (such as invalid itinerary drafts) and generates
targeted corrective prompts for single-retry recovery before falling back to a safe error state.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Represents the outcome of a schema validation check."""
    is_valid: bool
    data: Optional[Dict[str, Any]] = None
    raw_text: str = ""
    errors: List[str] = field(default_factory=list)
    schema_type: str = "itinerary_draft"

    @property
    def error_message(self) -> str:
        return "; ".join(self.errors) if self.errors else ""


class SchemaGuard:
    """
    Schema Guard ensuring model responses conform to expected structured schemas
    before being presented to visitors or downstream systems.
    """

    SUPPORTED_SCHEMAS = ["itinerary_draft", "conversational", "custom_json"]

    @staticmethod
    def extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Robustly extract and parse JSON from a model output string,
        handling markdown code fences (```json ... ```), raw objects, and leading/trailing text.
        """
        if not raw_text or not isinstance(raw_text, str):
            return None

        clean_text = raw_text.strip()

        # 1. Direct JSON parse
        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Markdown fenced block: ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", clean_text, re.DOTALL)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        # 3. Outer-most curly braces regex search
        brace_match = re.search(r"(\{[\s\S]*\})", clean_text)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def validate_itinerary_draft(self, raw_output: Any) -> ValidationResult:
        """
        Validate an itinerary draft against the mandatory structure:
        - title: non-empty string (at least 3 characters)
        - destination or region: non-empty string
        - duration_days: positive integer (or parseable duration string)
        - price: non-empty string or dict containing price range
        - day_by_day: non-empty list of stage objects, each having day (int/str) and title or description
        - inclusions: non-empty list of strings
        """
        errors: List[str] = []
        parsed_data: Optional[Dict[str, Any]] = None
        raw_text = raw_output if isinstance(raw_output, str) else json.dumps(raw_output)

        if isinstance(raw_output, dict):
            parsed_data = raw_output
        elif isinstance(raw_output, str):
            parsed_data = self.extract_json(raw_output)
            if parsed_data is None:
                errors.append("Output is not valid JSON and contains no parseable JSON object")
                return ValidationResult(
                    is_valid=False,
                    data=None,
                    raw_text=raw_text,
                    errors=errors,
                    schema_type="itinerary_draft",
                )
        else:
            errors.append(f"Unsupported payload type for itinerary draft: {type(raw_output).__name__}")
            return ValidationResult(
                is_valid=False,
                data=None,
                raw_text=str(raw_output),
                errors=errors,
                schema_type="itinerary_draft",
            )

        # 1. Validate title
        title = parsed_data.get("title")
        if not title or not isinstance(title, str) or len(title.strip()) < 3:
            errors.append("Field 'title' is missing or has fewer than 3 characters")

        # 2. Validate destination / region
        destination = parsed_data.get("destination") or parsed_data.get("region")
        if not destination or not isinstance(destination, str) or not destination.strip():
            errors.append("Field 'destination' (or 'region') is missing or empty")

        # 3. Validate duration / duration_days
        duration_days = parsed_data.get("duration_days")
        duration = parsed_data.get("duration")
        valid_duration = False
        if duration_days is not None:
            try:
                if int(duration_days) >= 1:
                    valid_duration = True
            except (ValueError, TypeError):
                pass
        if not valid_duration and duration and isinstance(duration, str) and duration.strip():
            valid_duration = True
        if not valid_duration:
            errors.append("Field 'duration_days' must be an integer >= 1 or 'duration' must be a valid string")

        # 4. Validate price
        price = parsed_data.get("price") or parsed_data.get("pricing_breakdown") or parsed_data.get("estimated_price_pkr")
        if not price:
            errors.append("Field 'price' or 'pricing_breakdown' is missing or empty")

        # 5. Validate day_by_day stages
        day_by_day = parsed_data.get("day_by_day")
        if not isinstance(day_by_day, list) or len(day_by_day) == 0:
            errors.append("Field 'day_by_day' must be a non-empty list of daily itinerary stages")
        else:
            for idx, stage in enumerate(day_by_day, start=1):
                if not isinstance(stage, dict):
                    errors.append(f"Day stage at index {idx} must be a JSON object, got {type(stage).__name__}")
                    break
                stage_day = stage.get("day")
                stage_title = stage.get("title") or stage.get("description")
                if stage_day is None:
                    errors.append(f"Day stage at index {idx} is missing required 'day' number")
                    break
                if not stage_title or not str(stage_title).strip():
                    errors.append(f"Day stage at index {idx} must have a non-empty 'title' or 'description'")
                    break

        # 6. Validate inclusions (or exclusions / highlights)
        inclusions = parsed_data.get("inclusions") or parsed_data.get("included_services")
        if inclusions is not None and not isinstance(inclusions, list):
            errors.append("Field 'inclusions' must be a list if provided")

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            data=parsed_data if is_valid else None,
            raw_text=raw_text,
            errors=errors,
            schema_type="itinerary_draft",
        )

    def validate_conversational(self, raw_output: str) -> ValidationResult:
        """
        Validate conversational prose output:
        - Must be non-empty text (at least 10 characters)
        - Must not contain unstripped <think> tags or internal scratchpad traces
        - Must not be raw JSON or code block dumps
        """
        errors = []
        if not raw_output or not isinstance(raw_output, str) or len(raw_output.strip()) < 10:
            errors.append("Conversational response is empty or under 10 characters")

        if "<think>" in raw_output or "</think>" in raw_output:
            errors.append("Response contains forbidden <think> internal reasoning tags")

        if re.search(r"^\s*```(?:json)?\s*\{", raw_output.strip()):
            errors.append("Response is raw code block instead of natural conversational prose")

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            data={"text": raw_output.strip()} if is_valid else None,
            raw_text=raw_output,
            errors=errors,
            schema_type="conversational",
        )

    def validate(
        self,
        raw_output: Any,
        schema_type: str = "itinerary_draft",
        required_fields: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Universal validation dispatcher.
        """
        if schema_type == "itinerary_draft":
            return self.validate_itinerary_draft(raw_output)
        elif schema_type == "conversational":
            return self.validate_conversational(raw_output if isinstance(raw_output, str) else str(raw_output))
        elif schema_type == "custom_json" and required_fields:
            parsed = self.extract_json(raw_output) if isinstance(raw_output, str) else (raw_output if isinstance(raw_output, dict) else None)
            errors = []
            if parsed is None:
                errors.append("Payload is not valid JSON")
            else:
                for field_name in required_fields:
                    if field_name not in parsed or parsed[field_name] in (None, "", []):
                        errors.append(f"Required field '{field_name}' is missing or empty")
            is_valid = len(errors) == 0
            return ValidationResult(
                is_valid=is_valid,
                data=parsed if is_valid else None,
                raw_text=str(raw_output),
                errors=errors,
                schema_type="custom_json",
            )
        else:
            # Default fallback validation
            return self.validate_itinerary_draft(raw_output)

    def generate_retry_prompt(
        self,
        original_query: str,
        validation_errors: List[str],
        schema_type: str = "itinerary_draft",
    ) -> str:
        """
        Generate a targeted, high-precision corrective prompt for a single retry,
        explaining exactly which schema constraints failed and requiring strict compliance.
        """
        error_list = "\n".join(f"- {err}" for err in validation_errors)

        if schema_type == "itinerary_draft":
            return (
                f"CORRECTIVE RETRY REQUIRED — SCHEMA VALIDATION FAILED\n\n"
                f"Your previous response to the query '{original_query}' was rejected because it failed "
                f"the mandatory JSON schema validation with the following errors:\n"
                f"{error_list}\n\n"
                f"You have ONE retry to provide a valid JSON response adhering strictly to the schema below. "
                f"Do not output markdown prose outside the JSON. Return a SINGLE valid JSON object:\n\n"
                f"```json\n"
                f"{{\n"
                f'  "title": "Descriptive Expedition Title (e.g. 5-Day Hunza Valley Cultural Tour)",\n'
                f'  "destination": "Target Destination / Region in Pakistan",\n'
                f'  "duration": "Duration in days (e.g. 5 Days)",\n'
                f'  "duration_days": 5,\n'
                f'  "price": "Realistic cost range in PKR and USD (e.g. PKR 120,000 - 160,000 ($450 - $600 USD))",\n'
                f'  "day_by_day": [\n'
                f'    {{"day": 1, "title": "Route title", "description": "Activities and overnight stop", "altitude": "2,400m"}},\n'
                f'    {{"day": 2, "title": "Route title", "description": "Activities and overnight stop", "altitude": "2,800m"}}\n'
                f'  ],\n'
                f'  "inclusions": ["Licensed Mountain Guide", "4x4 Jeep Transport", "Hotel Accommodations", "All Camp Meals"],\n'
                f'  "exclusions": ["International Flights", "Personal Travel Insurance", "Tips for Porters"]\n'
                f"}}\n"
                f"```"
            )
        else:
            return (
                f"CORRECTIVE RETRY REQUIRED:\n"
                f"Your previous response failed validation:\n{error_list}\n\n"
                f"Please regenerate your response addressing '{original_query}' strictly following the requirements."
            )


# Singleton instance
schema_guard = SchemaGuard()
