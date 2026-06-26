"""Re-exports from ``cutctx.transforms.content_router`` for backward compatibility.

Usage::

    from cutctx.proxy.router import ContentRouter, ContentRouterConfig, RouterCompressionResult

These names are aliases for the canonical definitions in
``cutctx.transforms.content_router``.
"""

from __future__ import annotations

from cutctx.transforms.content_router import (
    CompressionStrategy,
    ContentRouter,
    ContentRouterConfig,
    ContentSection,
    RouterCompressionResult,
    RoutingDecision,
)

__all__ = [
    "CompressionStrategy",
    "ContentRouter",
    "ContentRouterConfig",
    "ContentSection",
    "RouterCompressionResult",
    "RoutingDecision",
]
