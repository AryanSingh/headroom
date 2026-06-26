"""Provider-aware policy engine for savings orchestration.

Decides how Cutctx should optimize a request, taking into account the
provider, the model, the workload class, and the request structure.

Key principle: when a provider has a native prompt cache, we do not
compress cache-friendly prefixes. Cutting the prefix would invalidate
the provider cache and lose the larger savings it provides.

The resolver is deterministic, can be disabled cleanly, and never
mutates inputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class WorkloadClass(str, Enum):
    """Coarse workload classification for policy defaults."""

    CODING_AGENT = "coding_agent"
    SUPPORT_SEARCH = "support_search"
    LONG_DOC_QA = "long_doc_qa"
    REPETITIVE_WORKFLOW = "repetitive_workflow"
    UNKNOWN = "unknown"

    @classmethod
    def from_str(cls, value: str) -> WorkloadClass:
        try:
            return cls(value)
        except ValueError:
            return WorkloadClass.UNKNOWN


@dataclass
class PolicyDecision:
    """Output of the strategy resolver. All fields are advisory."""

    preserve_prefix_for_provider_cache: bool = True
    compress_tool_outputs_only: bool = False
    compress_history_after_turn_n: int = 0
    semantic_cache_enabled: bool = False
    semantic_cache_threshold: float = 0.92
    strategy_label: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DEFAULTS_BY_WORKLOAD: dict[WorkloadClass, dict[str, Any]] = {
    WorkloadClass.CODING_AGENT: {
        "preserve_prefix_for_provider_cache": True,
        "compress_tool_outputs_only": True,
        "compress_history_after_turn_n": 0,
        "semantic_cache_enabled": True,
        "semantic_cache_threshold": 0.88,
        "strategy_label": "coding_agent",
    },
    WorkloadClass.SUPPORT_SEARCH: {
        "preserve_prefix_for_provider_cache": True,
        "compress_tool_outputs_only": False,
        "compress_history_after_turn_n": 5,
        "semantic_cache_enabled": True,
        "semantic_cache_threshold": 0.90,
        "strategy_label": "support_search",
    },
    WorkloadClass.LONG_DOC_QA: {
        "preserve_prefix_for_provider_cache": False,
        "compress_tool_outputs_only": False,
        "compress_history_after_turn_n": 2,
        "semantic_cache_enabled": True,
        "semantic_cache_threshold": 0.95,
        "strategy_label": "long_doc_qa",
    },
    WorkloadClass.REPETITIVE_WORKFLOW: {
        "preserve_prefix_for_provider_cache": True,
        "compress_tool_outputs_only": True,
        "compress_history_after_turn_n": 0,
        "semantic_cache_enabled": True,
        "semantic_cache_threshold": 0.80,
        "strategy_label": "repetitive_workflow",
    },
    WorkloadClass.UNKNOWN: {
        "preserve_prefix_for_provider_cache": True,
        "compress_tool_outputs_only": False,
        "compress_history_after_turn_n": 0,
        "semantic_cache_enabled": False,
        "semantic_cache_threshold": 0.92,
        "strategy_label": "default",
    },
}


# Providers known to have a native prompt cache. When we see these,
# we bias toward preserving the cache-friendly prefix.
_PROVIDERS_WITH_NATIVE_CACHE = frozenset(
    {"anthropic", "openai", "gemini", "google", "bedrock", "aws", "azure", "azure_openai"}
)


class StrategyResolver:
    """Deterministic, side-effect-free strategy resolver."""

    def __init__(self, user_overrides: dict[str, Any] | None = None) -> None:
        self._user_overrides = dict(user_overrides or {})

    def resolve(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        workload: str | WorkloadClass | None = None,
        request_shape: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        workload_cls = self._coerce_workload(workload)
        defaults = dict(_DEFAULTS_BY_WORKLOAD[workload_cls])

        provider_lc = (provider or "").lower().strip()
        if provider_lc in _PROVIDERS_WITH_NATIVE_CACHE:
            defaults["preserve_prefix_for_provider_cache"] = True
        else:
            defaults["preserve_prefix_for_provider_cache"] = False

        request_shape = request_shape or {}
        n_tool_results = int(request_shape.get("tool_result_count") or 0)
        n_user_turns = int(request_shape.get("user_turn_count") or 0)
        if n_tool_results > 0:
            defaults["compress_tool_outputs_only"] = True
        if n_user_turns >= 8:
            defaults["compress_history_after_turn_n"] = min(
                defaults.get("compress_history_after_turn_n") or 0, 2
            )

        defaults.update(self._user_overrides)
        return PolicyDecision(**defaults)

    @staticmethod
    def _coerce_workload(value: str | WorkloadClass | None) -> WorkloadClass:
        if value is None:
            return WorkloadClass.UNKNOWN
        if isinstance(value, WorkloadClass):
            return value
        return WorkloadClass.from_str(str(value).strip().lower())


__all__ = [
    "PolicyDecision",
    "StrategyResolver",
    "WorkloadClass",
]
