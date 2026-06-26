"""
Cutctx - The Context Optimization Layer for LLM Applications.

Cut your LLM costs by 50-90% without losing accuracy.

Cutctx wraps LLM clients to provide:
- Smart compression of tool outputs (keeps errors, anomalies, relevant items)
- Cache-aligned prefix optimization for better provider cache hits
- Rolling window token management for long conversations
- Full streaming support with zero accuracy loss

Quick Start:

    from cutctx import CutctxClient, OpenAIProvider
    from openai import OpenAI

    # Wrap your existing client
    client = CutctxClient(
        original_client=OpenAI(),
        provider=OpenAIProvider(),
        default_mode="optimize",
    )

    # Use exactly like the original client
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": "Hello!"},
        ],
    )

    # Check savings
    stats = client.get_stats()
    print(f"Tokens saved: {stats['session']['tokens_saved_total']}")

Verify It's Working:

    # Validate configuration
    result = client.validate_setup()
    if not result["valid"]:
        print("Issues:", result)

    # Enable logging to see what's happening
    import logging
    logging.basicConfig(level=logging.INFO)
    # INFO:cutctx.transforms.pipeline:Pipeline complete: 45000 -> 4500 tokens

Simulate Before Sending:

    plan = client.chat.completions.simulate(
        model="gpt-4o",
        messages=large_messages,
    )
    print(f"Would save {plan.tokens_saved} tokens")
    print(f"Transforms: {plan.transforms}")

Error Handling:

    from cutctx import CutctxError, ConfigurationError, ProviderError

    try:
        response = client.chat.completions.create(...)
    except ConfigurationError as e:
        print(f"Config issue: {e.details}")
    except CutctxError as e:
        print(f"Cutctx error: {e}")

For more examples, see https://github.com/cutctx-sdk/cutctx/tree/main/examples
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from ._version import __version__  # noqa: F401

# Keep a real callable bound for the one-function compression API so
# `from cutctx import compress` is never shadowed by the submodule object.

__all__ = [
    # Main client
    "CutctxClient",
    "CutctxClient",
    "CutctxClient",
    # Providers
    "Provider",
    "TokenCounter",
    "OpenAIProvider",
    "AnthropicProvider",
    # Exceptions
    "CutctxError",
    "CutctxError",
    "CutctxError",
    "ConfigurationError",
    "ProviderError",
    "StorageError",
    "CompressionError",
    "TokenizationError",
    "CacheError",
    "ValidationError",
    "TransformError",
    # Config
    "CutctxConfig",
    "CutctxMode",
    "CutctxConfig",
    "CutctxMode",
    # Backward-compat: rebrand from CutctxConfig/CutctxMode (pre-db7f7a4).
    # External callers may still reference the old names. Aliases will be
    # removed in the next minor release.
    "CutctxConfig",
    "CutctxMode",
    "SmartCrusherConfig",
    "CacheAlignerConfig",
    "CacheOptimizerConfig",
    "RelevanceScorerConfig",
    # Data models
    "Block",
    "CachePrefixMetrics",
    "DiffArtifact",
    "RequestMetrics",
    "SimulationResult",
    "TransformDiff",
    "TransformResult",
    "WasteSignals",
    # Transforms
    "SmartCrusher",
    "CacheAligner",
    "TransformPipeline",
    # Cache optimizers
    "BaseCacheOptimizer",
    "CacheConfig",
    "CacheMetrics",
    "CacheResult",
    "CacheStrategy",
    "OptimizationContext",
    "CacheOptimizerRegistry",
    "AnthropicCacheOptimizer",
    "OpenAICacheOptimizer",
    "GoogleCacheOptimizer",
    "SemanticCache",
    "SemanticCacheLayer",
    # Relevance scoring - BM25 always available, embeddings require sentence-transformers
    "RelevanceScore",
    "RelevanceScorer",
    "BM25Scorer",
    "EmbeddingScorer",
    "HybridScorer",
    "create_scorer",
    "embedding_available",
    # Utilities
    "Tokenizer",
    "count_tokens_text",
    "count_tokens_messages",
    "generate_report",
    # Observability
    "CutctxOtelMetrics",
    "CutctxTracer",
    "CutctxOtelMetrics",
    "CutctxTracer",
    "CutctxOtelMetrics",
    "CutctxTracer",
    "LangfuseTracingConfig",
    "OTelMetricsConfig",
    "configure_otel_metrics",
    "configure_langfuse_tracing",
    "get_cutctx_tracer",
    "get_langfuse_tracing_status",
    "get_otel_metrics",
    "get_otel_metrics_status",
    "reset_cutctx_tracing",
    "reset_otel_metrics",
    # Memory - optional hierarchical memory system
    "with_memory",  # Main user-facing API
    "Memory",
    "ScopeLevel",
    "HierarchicalMemory",
    "MemoryConfig",
    "EmbedderBackend",
    # One-function compression API
    "compress",
    "CompressConfig",
    "CompressResult",
    # Hooks
    "CompressionHooks",
    "CompressContext",
    "CompressEvent",
    # Canonical pipeline
    "PipelineStage",
    "PipelineEvent",
    "PipelineExtensionManager",
    "CANONICAL_PIPELINE_STAGES",
    # Shared context for multi-agent workflows
    "SharedContext",
]

# Keep package-level imports lightweight so `import cutctx` does not eagerly
# load provider SDKs, ML stacks, or optional proxy/runtime integrations.
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Main client
    "CutctxClient": ("cutctx.client", "CutctxClient"),
    "CutctxClient": ("cutctx.client", "CutctxClient"),
    # Providers
    "Provider": ("cutctx.providers", "Provider"),
    "TokenCounter": ("cutctx.providers", "TokenCounter"),
    "OpenAIProvider": ("cutctx.providers", "OpenAIProvider"),
    "AnthropicProvider": ("cutctx.providers", "AnthropicProvider"),
    # Exceptions
    "CutctxError": ("cutctx.exceptions", "CutctxError"),
    "CutctxError": ("cutctx.exceptions", "CutctxError"),
    "CutctxError": ("cutctx.exceptions", "CutctxError"),
    "ConfigurationError": ("cutctx.exceptions", "ConfigurationError"),
    "ProviderError": ("cutctx.exceptions", "ProviderError"),
    "StorageError": ("cutctx.exceptions", "StorageError"),
    "CompressionError": ("cutctx.exceptions", "CompressionError"),
    "TokenizationError": ("cutctx.exceptions", "TokenizationError"),
    "CacheError": ("cutctx.exceptions", "CacheError"),
    "ValidationError": ("cutctx.exceptions", "ValidationError"),
    "TransformError": ("cutctx.exceptions", "TransformError"),
    # Config
    "CutctxConfig": ("cutctx.config", "CutctxConfig"),
    "CutctxMode": ("cutctx.config", "CutctxMode"),
    "CutctxConfig": ("cutctx.config", "CutctxConfig"),
    "CutctxMode": ("cutctx.config", "CutctxMode"),
    "SmartCrusherConfig": ("cutctx.config", "SmartCrusherConfig"),
    "CacheAlignerConfig": ("cutctx.config", "CacheAlignerConfig"),
    "CacheOptimizerConfig": ("cutctx.config", "CacheOptimizerConfig"),
    "RelevanceScorerConfig": ("cutctx.config", "RelevanceScorerConfig"),
    # Data models
    "Block": ("cutctx.config", "Block"),
    "CachePrefixMetrics": ("cutctx.config", "CachePrefixMetrics"),
    "DiffArtifact": ("cutctx.config", "DiffArtifact"),
    "RequestMetrics": ("cutctx.config", "RequestMetrics"),
    "SimulationResult": ("cutctx.config", "SimulationResult"),
    "TransformDiff": ("cutctx.config", "TransformDiff"),
    "TransformResult": ("cutctx.config", "TransformResult"),
    "WasteSignals": ("cutctx.config", "WasteSignals"),
    # Transforms
    "SmartCrusher": ("cutctx.transforms", "SmartCrusher"),
    "CacheAligner": ("cutctx.transforms", "CacheAligner"),
    "TransformPipeline": ("cutctx.transforms", "TransformPipeline"),
    # Cache optimizers
    "BaseCacheOptimizer": ("cutctx.cache", "BaseCacheOptimizer"),
    "CacheConfig": ("cutctx.cache", "CacheConfig"),
    "CacheMetrics": ("cutctx.cache", "CacheMetrics"),
    "CacheResult": ("cutctx.cache", "CacheResult"),
    "CacheStrategy": ("cutctx.cache", "CacheStrategy"),
    "OptimizationContext": ("cutctx.cache", "OptimizationContext"),
    "CacheOptimizerRegistry": ("cutctx.cache", "CacheOptimizerRegistry"),
    "AnthropicCacheOptimizer": ("cutctx.cache", "AnthropicCacheOptimizer"),
    "OpenAICacheOptimizer": ("cutctx.cache", "OpenAICacheOptimizer"),
    "GoogleCacheOptimizer": ("cutctx.cache", "GoogleCacheOptimizer"),
    "SemanticCache": ("cutctx.cache", "SemanticCache"),
    "SemanticCacheLayer": ("cutctx.cache", "SemanticCacheLayer"),
    # Relevance scoring
    "RelevanceScore": ("cutctx.relevance", "RelevanceScore"),
    "RelevanceScorer": ("cutctx.relevance", "RelevanceScorer"),
    "BM25Scorer": ("cutctx.relevance", "BM25Scorer"),
    "EmbeddingScorer": ("cutctx.relevance", "EmbeddingScorer"),
    "HybridScorer": ("cutctx.relevance", "HybridScorer"),
    "create_scorer": ("cutctx.relevance", "create_scorer"),
    "embedding_available": ("cutctx.relevance", "embedding_available"),
    # Utilities
    "Tokenizer": ("cutctx.tokenizer", "Tokenizer"),
    "count_tokens_text": ("cutctx.tokenizer", "count_tokens_text"),
    "count_tokens_messages": ("cutctx.tokenizer", "count_tokens_messages"),
    "generate_report": ("cutctx.reporting", "generate_report"),
    # Observability
    "CutctxOtelMetrics": ("cutctx.observability", "CutctxOtelMetrics"),
    "CutctxTracer": ("cutctx.observability", "CutctxTracer"),
    "CutctxOtelMetrics": ("cutctx.observability", "CutctxOtelMetrics"),
    "CutctxTracer": ("cutctx.observability", "CutctxTracer"),
    "CutctxOtelMetrics": ("cutctx.observability", "CutctxOtelMetrics"),
    "CutctxTracer": ("cutctx.observability", "CutctxTracer"),
    "LangfuseTracingConfig": ("cutctx.observability", "LangfuseTracingConfig"),
    "OTelMetricsConfig": ("cutctx.observability", "OTelMetricsConfig"),
    "configure_otel_metrics": ("cutctx.observability", "configure_otel_metrics"),
    "configure_langfuse_tracing": ("cutctx.observability", "configure_langfuse_tracing"),
    "get_cutctx_tracer": ("cutctx.observability", "get_cutctx_tracer"),
    "get_langfuse_tracing_status": ("cutctx.observability", "get_langfuse_tracing_status"),
    "get_otel_metrics": ("cutctx.observability", "get_otel_metrics"),
    "get_otel_metrics_status": ("cutctx.observability", "get_otel_metrics_status"),
    "reset_cutctx_tracing": ("cutctx.observability", "reset_cutctx_tracing"),
    "reset_otel_metrics": ("cutctx.observability", "reset_otel_metrics"),
    # One-function API
    "compress": ("cutctx.compress", "compress"),
    "CompressConfig": ("cutctx.compress", "CompressConfig"),
    "CompressResult": ("cutctx.compress", "CompressResult"),
    # Hooks
    "CompressionHooks": ("cutctx.hooks", "CompressionHooks"),
    "CompressContext": ("cutctx.hooks", "CompressContext"),
    "CompressEvent": ("cutctx.hooks", "CompressEvent"),
    # Canonical pipeline
    "PipelineStage": ("cutctx.pipeline", "PipelineStage"),
    "PipelineEvent": ("cutctx.pipeline", "PipelineEvent"),
    "PipelineExtensionManager": ("cutctx.pipeline", "PipelineExtensionManager"),
    "CANONICAL_PIPELINE_STAGES": ("cutctx.pipeline", "CANONICAL_PIPELINE_STAGES"),
    # Shared context
    "SharedContext": ("cutctx.shared_context", "SharedContext"),
}

# Memory remains optional and preserves the long-standing behavior of exposing
# `None` when the extra dependencies are not installed.
_OPTIONAL_EXPORTS = {
    "with_memory": ("cutctx.memory", "with_memory"),
    "Memory": ("cutctx.memory", "Memory"),
    "ScopeLevel": ("cutctx.memory", "ScopeLevel"),
    "HierarchicalMemory": ("cutctx.memory", "HierarchicalMemory"),
    "MemoryConfig": ("cutctx.memory", "MemoryConfig"),
    "EmbedderBackend": ("cutctx.memory", "EmbedderBackend"),
}


def __getattr__(name: str) -> Any:
    """Resolve package exports lazily while preserving legacy import paths."""
    module_attr = _LAZY_EXPORTS.get(name)
    if module_attr is not None:
        module_name, attr_name = module_attr
        value = getattr(import_module(module_name), attr_name)
        globals()[name] = value
        return value

    optional_module_attr = _OPTIONAL_EXPORTS.get(name)
    if optional_module_attr is not None:
        module_name, attr_name = optional_module_attr
        try:
            value = getattr(import_module(module_name), attr_name)
        except ImportError:
            value = None
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
