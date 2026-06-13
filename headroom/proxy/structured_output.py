"""Enforced Structured Outputs with auto-retries.

Guarantees JSON schema compliance by validating LLM responses and
automatically retrying with error feedback when validation fails.

Usage:
    validator = StructuredOutputValidator()
    result = await validator.execute_with_retries(
        client=llm_client,
        messages=messages,
        schema=my_json_schema,
        model="claude-3-haiku-20240307",
        max_retries=3,
    )
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("headroom.proxy.structured_output")


# ---------------------------------------------------------------------------
# Try to import jsonschema (optional dependency)
# ---------------------------------------------------------------------------

try:
    import jsonschema

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class StructuredOutputConfig:
    """Configuration for structured output enforcement."""
    enabled: bool = True
    max_retries: int = 3
    validate_response_format: bool = True  # auto-detect json_schema in requests
    strip_markdown_fences: bool = True  # strip ```json...``` wrappers
    strict_mode: bool = False  # if True, fail even on warnings

    @classmethod
    def from_env(cls) -> StructuredOutputConfig:
        import os
        return cls(
            enabled=os.environ.get("HEADROOM_STRUCTURED_OUTPUT_ENABLED", "1").strip() != "0",
            max_retries=int(os.environ.get("HEADROOM_STRUCTURED_OUTPUT_MAX_RETRIES", "3")),
            strict_mode=os.environ.get("HEADROOM_STRUCTURED_OUTPUT_STRICT", "").strip() == "1",
        )


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    parsed_json: Any = None
    raw_text: str = ""
    validation_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

class StructuredOutputValidator:
    """Validates LLM responses against a JSON schema and auto-retries on failure."""

    def __init__(self, config: StructuredOutputConfig | None = None) -> None:
        self.config = config or StructuredOutputConfig.from_env()
        if not JSONSCHEMA_AVAILABLE and self.config.enabled:
            logger.warning(
                "jsonschema not installed — structured output validation disabled. "
                "Install with: pip install jsonschema"
            )
            self.config.enabled = False

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def detect_schema(self, request_body: dict[str, Any]) -> dict[str, Any] | None:
        """Detect JSON schema from a request body.

        Supports:
        - OpenAI: response_format.json_schema.schema
        - Anthropic: response_format.json_schema (less common)
        """
        if not self.config.validate_response_format:
            return None

        # OpenAI format: {"response_format": {"type": "json_schema", "json_schema": {"schema": {...}}}}
        response_format = request_body.get("response_format")
        if isinstance(response_format, dict):
            if response_format.get("type") == "json_schema":
                json_schema = response_format.get("json_schema", {})
                if isinstance(json_schema, dict):
                    schema = json_schema.get("schema")
                    if isinstance(schema, dict):
                        return schema

        return None

    def validate(self, text: str, schema: dict[str, Any]) -> ValidationResult:
        """Validate JSON text against a schema.

        Returns ValidationResult with parsed JSON if valid, or errors if not.
        """
        t0 = time.monotonic()

        # Step 1: Extract JSON from text (strip markdown fences, etc.)
        json_text = self._extract_json(text)

        # Step 2: Parse JSON
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as e:
            elapsed = (time.monotonic() - t0) * 1000
            return ValidationResult(
                valid=False,
                errors=[f"Invalid JSON: {e.msg} at position {e.pos}"],
                raw_text=text,
                validation_time_ms=elapsed,
            )

        # Step 3: Validate against schema
        if not JSONSCHEMA_AVAILABLE:
            # Without jsonschema, we can only check if it parses
            elapsed = (time.monotonic() - t0) * 1000
            return ValidationResult(
                valid=True,
                parsed_json=parsed,
                raw_text=text,
                validation_time_ms=elapsed,
            )

        try:
            jsonschema.validate(instance=parsed, schema=schema)
            elapsed = (time.monotonic() - t0) * 1000
            return ValidationResult(
                valid=True,
                parsed_json=parsed,
                raw_text=text,
                validation_time_ms=elapsed,
            )
        except jsonschema.ValidationError as e:
            error_msg = f"{e.message} (path: {'.'.join(str(p) for p in e.absolute_path)})" if e.absolute_path else e.message
            elapsed = (time.monotonic() - t0) * 1000
            return ValidationResult(
                valid=False,
                errors=[error_msg],
                parsed_json=parsed,  # return what we could parse for debugging
                raw_text=text,
                validation_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - t0) * 1000
            return ValidationResult(
                valid=False,
                errors=[f"Schema validation error: {e}"],
                raw_text=text,
                validation_time_ms=elapsed,
            )

    async def execute_with_retries(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        model: str,
        max_retries: int | None = None,
        api_provider: str = "anthropic",
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute an LLM call with schema validation and auto-retries.

        On validation failure, appends an error message and retries up to
        max_retries times.

        Args:
            client: httpx.AsyncClient for making LLM calls
            messages: The chat messages
            schema: JSON schema to validate against
            model: Model identifier
            max_retries: Override default max_retries
            api_provider: "anthropic" or "openai"
            temperature: Temperature (lower = more deterministic)
            **kwargs: Additional params for the API call

        Returns:
            The validated response content (parsed JSON).

        Raises:
            StructuredOutputError: If all retries fail.
        """
        if not self.config.enabled:
            raise StructuredOutputError("Structured output validation is disabled")

        retries = max_retries if max_retries is not None else self.config.max_retries
        retry_messages = list(messages)  # copy
        last_error = None

        for attempt in range(retries + 1):
            # Make the LLM call
            t0 = time.monotonic()
            raw_text = await self._call_llm(
                client=client,
                messages=retry_messages,
                model=model,
                api_provider=api_provider,
                temperature=temperature,
                **kwargs,
            )
            call_ms = (time.monotonic() - t0) * 1000

            # Validate
            result = self.validate(raw_text, schema)

            if result.valid:
                logger.info(
                    "Structured output validated on attempt %d/%d (%.1fms call, %.1fms validate)",
                    attempt + 1, retries + 1, call_ms, result.validation_time_ms,
                )
                return {
                    "content": result.parsed_json,
                    "attempts": attempt + 1,
                    "validation_ms": result.validation_time_ms,
                    "call_ms": call_ms,
                    "raw_text": raw_text,
                }

            last_error = result.errors
            logger.warning(
                "Structured output validation failed on attempt %d/%d: %s",
                attempt + 1, retries + 1, "; ".join(result.errors),
            )

            if attempt < retries:
                # Append error feedback for retry
                error_feedback = (
                    f"Your previous response failed JSON schema validation. "
                    f"Error(s): {'; '.join(result.errors)}. "
                    f"Please correct your response to match the schema exactly. "
                    f"Return ONLY valid JSON, no markdown fences or explanations."
                )
                retry_messages.append({
                    "role": "user",
                    "content": error_feedback,
                })

        raise StructuredOutputError(
            f"Failed to produce valid JSON after {retries + 1} attempts. "
            f"Last error(s): {'; '.join(last_error or ['unknown'])}",
            attempts=retries + 1,
            last_errors=last_error or [],
        )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, stripping markdown fences if present."""
        stripped = text.strip()

        # Strip markdown code fences
        if self.config.strip_markdown_fences:
            if stripped.startswith("```"):
                # Find opening and closing fences
                lines = stripped.split("\n")
                # Remove first line (```json or ```)
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                # Remove last line (```)
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                stripped = "\n".join(lines).strip()

        # Try to find JSON object or array in the text
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start = stripped.find(start_char)
            end = stripped.rfind(end_char)
            if start != -1 and end > start:
                candidate = stripped[start:end + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue

        return stripped

    async def _call_llm(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        model: str,
        api_provider: str = "anthropic",
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> str:
        """Make an LLM call and return the text response."""
        if api_provider == "anthropic":
            return await self._call_anthropic(
                client=client, messages=messages, model=model,
                temperature=temperature, **kwargs,
            )
        elif api_provider == "openai":
            return await self._call_openai(
                client=client, messages=messages, model=model,
                temperature=temperature, **kwargs,
            )
        else:
            raise ValueError(f"Unsupported API provider: {api_provider}")

    async def _call_anthropic(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """Call Anthropic Messages API."""
        api_key = kwargs.pop("api_key", None)
        base_url = kwargs.pop("base_url", "https://api.anthropic.com")

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if api_key:
            headers["x-api-key"] = api_key

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": kwargs.pop("max_tokens", 4096),
            "temperature": temperature,
        }
        body.update(kwargs)

        resp = await client.post(
            f"{base_url}/v1/messages",
            headers=headers,
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract text from content blocks
        content_blocks = data.get("content", [])
        text_parts = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)

    async def _call_openai(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """Call OpenAI Chat Completions API."""
        api_key = kwargs.pop("api_key", None)
        base_url = kwargs.pop("base_url", "https://api.openai.com")

        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        body.update(kwargs)

        resp = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class StructuredOutputError(Exception):
    """Raised when structured output validation fails after all retries."""

    def __init__(
        self,
        message: str,
        attempts: int = 0,
        last_errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_errors = last_errors or []
