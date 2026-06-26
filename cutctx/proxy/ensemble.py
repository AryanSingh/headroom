"""Multi-Model Ensemble (Mixture of Agents).

Queries multiple LLM models concurrently and uses a fast evaluator
to select the best response. Provides accuracy guarantees for high-stakes
queries by leveraging model diversity.

Usage:
    coordinator = EnsembleCoordinator(config)
    result = await coordinator.execute(
        messages=messages,
        models=["claude-3-5-sonnet-20241022", "gpt-4o", "gemini-1.5-pro"],
        evaluator_model="claude-3-haiku-20240307",
    )
    print(result["winning_model"], result["content"])
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cutctx.proxy.ensemble")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class EnsembleConfig:
    """Configuration for multi-model ensemble execution."""
    enabled: bool = False
    default_models: list[str] = field(default_factory=lambda: [
        "claude-3-5-sonnet-20241022",
        "gpt-4o",
    ])
    evaluator_model: str = "claude-3-haiku-20240307"
    evaluator_max_tokens: int = 256
    timeout_seconds: float = 120.0
    max_concurrent: int = 5
    require_all_models: bool = False  # if True, fail if any model fails

    @classmethod
    def from_env(cls) -> EnsembleConfig:
        return cls(
            enabled=os.environ.get("CUTCTX_ENSEMBLE_ENABLED", "").strip() == "1",
            evaluator_model=os.environ.get(
                "CUTCTX_ENSEMBLE_EVALUATOR_MODEL", "claude-3-haiku-20240307"
            ),
            timeout_seconds=float(os.environ.get("CUTCTX_ENSEMBLE_TIMEOUT", "120")),
            require_all_models=os.environ.get("CUTCTX_ENSEMBLE_REQUIRE_ALL", "").strip() == "1",
        )


# ---------------------------------------------------------------------------
# Model result
# ---------------------------------------------------------------------------

@dataclass
class ModelResult:
    """Result from a single model in the ensemble."""
    model: str
    content: str
    latency_ms: float
    tokens_used: int = 0
    error: str | None = None
    success: bool = True


# ---------------------------------------------------------------------------
# Ensemble result
# ---------------------------------------------------------------------------

@dataclass
class EnsembleResult:
    """Final result from ensemble execution."""
    content: str
    winning_model: str
    all_results: list[ModelResult]
    evaluator_latency_ms: float
    total_latency_ms: float
    evaluation_reasoning: str = ""


# ---------------------------------------------------------------------------
# Evaluator prompt
# ---------------------------------------------------------------------------

EVALUATOR_SYSTEM_PROMPT = """You are a quality evaluator for AI-generated responses. You will receive:
1. The original user message
2. Multiple model responses labeled by model name

Your task: Evaluate each response for:
- Accuracy (is the answer correct?)
- Completeness (does it fully address the question?)
- Clarity (is it well-written and easy to understand?)
- Safety (no harmful or misleading content)

Return ONLY a JSON object with this exact format:
{
  "winner": "<model-name>",
  "reasoning": "<brief 1-2 sentence explanation>",
  "scores": {"<model-name>": <1-10>, ...}
}"""


# ---------------------------------------------------------------------------
# EnsembleCoordinator
# ---------------------------------------------------------------------------

class EnsembleCoordinator:
    """Fans out requests to multiple models and evaluates the best response."""

    def __init__(self, config: EnsembleConfig | None = None) -> None:
        self.config = config or EnsembleConfig.from_env()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    async def execute(
        self,
        *,
        messages: list[dict[str, Any]],
        models: list[str] | None = None,
        evaluator_model: str | None = None,
        client: Any = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> EnsembleResult:
        """Execute the ensemble: fan out to all models, evaluate, return best.

        Args:
            messages: Chat messages to send to all models
            models: List of model identifiers (uses default if None)
            evaluator_model: Model to use for evaluation (uses config default if None)
            client: httpx.AsyncClient
            temperature: Temperature for generation
            max_tokens: Max tokens per model response
            **kwargs: Additional API params

        Returns:
            EnsembleResult with winning model and all results
        """
        t0 = time.monotonic()
        target_models = models or self.config.default_models
        eval_model = evaluator_model or self.config.evaluator_model

        # Phase 1: Fan out to all models concurrently
        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        async def _call_model(model: str) -> ModelResult:
            async with semaphore:
                return await self._call_single_model(
                    client=client,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

        tasks = [_call_model(m) for m in target_models]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful results
        model_results: list[ModelResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                model_results.append(ModelResult(
                    model=target_models[i],
                    content="",
                    latency_ms=0,
                    error=str(result),
                    success=False,
                ))
            elif isinstance(result, ModelResult):
                model_results.append(result)

        successful = [r for r in model_results if r.success]

        if not successful:
            total_ms = (time.monotonic() - t0) * 1000
            raise EnsembleError(
                f"All {len(target_models)} models failed. "
                f"Errors: {'; '.join(r.error or 'unknown' for r in model_results)}"
            )

        if len(successful) == 1:
            # Only one model succeeded — return it directly
            winner = successful[0]
            total_ms = (time.monotonic() - t0) * 1000
            return EnsembleResult(
                content=winner.content,
                winning_model=winner.model,
                all_results=model_results,
                evaluator_latency_ms=0,
                total_latency_ms=total_ms,
                evaluation_reasoning="Only one model succeeded",
            )

        # Phase 2: Evaluate with fast model
        eval_t0 = time.monotonic()
        evaluation = await self._evaluate_responses(
            client=client,
            messages=messages,
            model_results=successful,
            evaluator_model=eval_model,
            **kwargs,
        )
        eval_ms = (time.monotonic() - eval_t0) * 1000

        # Find winning model result
        winning_model = evaluation.get("winner", successful[0].model)
        winning_result = next(
            (r for r in successful if r.model == winning_model),
            successful[0],
        )

        total_ms = (time.monotonic() - t0) * 1000

        logger.info(
            "Ensemble: %d models queried, winner=%s (total=%.0fms, eval=%.0fms)",
            len(successful), winning_model, total_ms, eval_ms,
        )

        return EnsembleResult(
            content=winning_result.content,
            winning_model=winning_model,
            all_results=model_results,
            evaluator_latency_ms=eval_ms,
            total_latency_ms=total_ms,
            evaluation_reasoning=evaluation.get("reasoning", ""),
        )

    async def _call_single_model(
        self,
        *,
        client: Any,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> ModelResult:
        """Call a single model and return the result."""
        t0 = time.monotonic()

        try:
            # Detect provider from model name
            if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
                content, tokens = await self._call_openai(
                    client=client, model=model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens, **kwargs,
                )
            elif model.startswith("gemini"):
                content, tokens = await self._call_gemini(
                    client=client, model=model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens, **kwargs,
                )
            else:
                # Default to Anthropic
                content, tokens = await self._call_anthropic(
                    client=client, model=model, messages=messages,
                    temperature=temperature, max_tokens=max_tokens, **kwargs,
                )

            latency = (time.monotonic() - t0) * 1000
            return ModelResult(
                model=model,
                content=content,
                latency_ms=latency,
                tokens_used=tokens,
                success=True,
            )
        except Exception as e:
            latency = (time.monotonic() - t0) * 1000
            logger.warning("Ensemble model %s failed: %s", model, e)
            return ModelResult(
                model=model,
                content="",
                latency_ms=latency,
                error=str(e),
                success=False,
            )

    async def _evaluate_responses(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        model_results: list[ModelResult],
        evaluator_model: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Use a fast model to evaluate and rank responses."""
        # Build evaluation prompt
        eval_content = "## Original Message\n\n"
        # Extract user message
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    eval_content += content[:2000] + "\n\n"
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            eval_content += block.get("text", "")[:2000] + "\n\n"
                break

        eval_content += "## Model Responses\n\n"
        for i, result in enumerate(model_results):
            eval_content += f"### Response {i + 1} (Model: {result.model})\n\n"
            eval_content += result.content[:3000] + "\n\n"

        eval_messages = [
            {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
            {"role": "user", "content": eval_content},
        ]

        try:
            # Try calling the evaluator model
            if evaluator_model.startswith("gpt-"):
                content, _ = await self._call_openai(
                    client=client, model=evaluator_model, messages=eval_messages,
                    temperature=0.0, max_tokens=self.config.evaluator_max_tokens,
                )
            else:
                content, _ = await self._call_anthropic(
                    client=client, model=evaluator_model, messages=eval_messages,
                    temperature=0.0, max_tokens=self.config.evaluator_max_tokens,
                )

            # Parse evaluation JSON
            # Strip markdown fences if present
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]).strip()

            return json.loads(content)
        except Exception as e:
            logger.warning("Ensemble evaluation failed: %s — defaulting to first model", e)
            return {
                "winner": model_results[0].model,
                "reasoning": f"Evaluation failed: {e}",
                "scores": {},
            }

    async def _call_anthropic(
        self, *, client: Any, model: str, messages: list[dict],
        temperature: float, max_tokens: int, **kwargs: Any,
    ) -> tuple[str, int]:
        """Call Anthropic API, return (content, tokens_used)."""
        api_key = kwargs.pop("anthropic_api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
        base_url = kwargs.pop("anthropic_base_url", "https://api.anthropic.com")

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if api_key:
            headers["x-api-key"] = api_key

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        resp = await client.post(
            f"{base_url}/v1/messages",
            headers=headers, json=body, timeout=self.config.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()

        content_parts = []
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                content_parts.append(block.get("text", ""))

        usage = data.get("usage", {})
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        return "\n".join(content_parts), tokens

    async def _call_openai(
        self, *, client: Any, model: str, messages: list[dict],
        temperature: float, max_tokens: int, **kwargs: Any,
    ) -> tuple[str, int]:
        """Call OpenAI API, return (content, tokens_used)."""
        api_key = kwargs.pop("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))
        base_url = kwargs.pop("openai_base_url", "https://api.openai.com")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = await client.post(
            f"{base_url}/v1/chat/completions",
            headers=headers, json=body, timeout=self.config.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        return content, tokens

    async def _call_gemini(
        self, *, client: Any, model: str, messages: list[dict],
        temperature: float, max_tokens: int, **kwargs: Any,
    ) -> tuple[str, int]:
        """Call Gemini API, return (content, tokens_used)."""
        api_key = kwargs.pop("gemini_api_key", os.environ.get("GEMINI_API_KEY", ""))
        base_url = kwargs.pop("gemini_base_url", "https://generativelanguage.googleapis.com")

        if not api_key:
            raise ValueError("GEMINI_API_KEY required for Gemini models in ensemble")

        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            contents.append({"role": role, "parts": [{"text": content}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        resp = await client.post(
            f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}",
            json=body, timeout=self.config.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        content = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = " ".join(p.get("text", "") for p in parts)

        usage = data.get("usageMetadata", {})
        tokens = usage.get("totalTokenCount", 0)
        return content, tokens


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class EnsembleError(Exception):
    """Raised when ensemble execution fails."""
    pass
