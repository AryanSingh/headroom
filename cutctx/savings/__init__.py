"""Savings orchestration: shared types, provider parsers, policy, and aggregation.

The savings package normalizes every token saved by Cutctx into one of
five canonical sources so that downstream consumers (stats, history, CLI,
dashboard) can attribute savings correctly and never double-count.
"""

from cutctx.savings.integrations import (
    parse_gptcache_hit,
    parse_litellm_cache,
    parse_model_routing_metadata,
    parse_vllm_apc,
)
from cutctx.savings.orchestrator import AggregateSavings, SavingsOrchestrator
from cutctx.savings.parsers import (
    parse_anthropic_savings,
    parse_azure_openai_savings,
    parse_bedrock_savings,
    parse_gemini_savings,
    parse_openai_savings,
    parse_provider_savings,
)
from cutctx.savings.policy import (
    PolicyDecision,
    StrategyResolver,
    WorkloadClass,
)
from cutctx.savings.types import (
    RequestSavingsBreakdown,
    SavingsBySource,
    SavingsSource,
)

__all__ = [
    "AggregateSavings",
    "PolicyDecision",
    "RequestSavingsBreakdown",
    "SavingsBySource",
    "SavingsOrchestrator",
    "SavingsSource",
    "StrategyResolver",
    "WorkloadClass",
    "parse_anthropic_savings",
    "parse_azure_openai_savings",
    "parse_bedrock_savings",
    "parse_gemini_savings",
    "parse_gptcache_hit",
    "parse_litellm_cache",
    "parse_model_routing_metadata",
    "parse_openai_savings",
    "parse_provider_savings",
    "parse_vllm_apc",
]
