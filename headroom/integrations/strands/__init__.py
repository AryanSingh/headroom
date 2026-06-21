"""Strands Agents integration for Cutctx SDK.

This module provides seamless integration with Strands Agents,
enabling automatic context optimization for Strands agents.

Components:
1. CutctxStrandsModel - Wraps any Strands model to apply Cutctx transforms
2. CutctxHookProvider - Hook provider for Strands agents
3. get_headroom_provider - Detects appropriate provider for a Strands model
4. get_model_name_from_strands - Extracts model name from a Strands model

Example:
    from strands import Agent
    from strands.models import BedrockModel
    from headroom.integrations.strands import CutctxStrandsModel

    # Wrap any Strands model
    model = BedrockModel(model_id="anthropic.claude-3-5-sonnet-20241022-v2:0")
    optimized_model = CutctxStrandsModel(model)

    # Use with agent
    agent = Agent(model=optimized_model)
    response = agent("Hello!")
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .bundle import CutctxBundle
    from .hooks import CutctxHookProvider
    from .model import CutctxStrandsModel, OptimizationMetrics, optimize_messages
    from .providers import get_headroom_provider, get_model_name_from_strands


def strands_available() -> bool:
    """Check if strands-agents is installed and available.

    Returns:
        True if strands-agents package is available, False otherwise.
    """
    return importlib.util.find_spec("strands") is not None


# Lazy imports to avoid import errors when strands is not installed
def __getattr__(name: str) -> Any:
    """Lazy import of integration components."""
    if name == "HeadroomHookProvider":
        from .hooks import CutctxHookProvider

        return CutctxHookProvider
    elif name in ("HeadroomStrandsModel", "CutctxStrandsModel"):
        from .model import CutctxStrandsModel

        return CutctxStrandsModel
    elif name == "OptimizationMetrics":
        from .model import OptimizationMetrics

        return OptimizationMetrics
    elif name == "optimize_messages":
        from .model import optimize_messages

        return optimize_messages
    elif name == "get_headroom_provider":
        from .providers import get_headroom_provider

        return get_headroom_provider
    elif name == "get_model_name_from_strands":
        from .providers import get_model_name_from_strands

        return get_model_name_from_strands
    elif name == "HeadroomBundle":
        from .bundle import CutctxBundle

        return CutctxBundle
    # Backward-compat aliases (pre-db7f7a4 rebrand).
    elif name in ("HeadroomHookProvider", "HeadroomStrandsModel"):
        from . import hooks as _hooks_mod
        from . import model as _model_mod

        if name == "HeadroomHookProvider":
            return _hooks_mod.CutctxHookProvider
        return _model_mod.CutctxStrandsModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Availability check
    "strands_available",
    # Hook provider
    "HeadroomHookProvider",
    # Model wrapper
    "HeadroomStrandsModel",
    "OptimizationMetrics",
    "optimize_messages",
    # Provider detection
    "get_headroom_provider",
    "get_model_name_from_strands",
    # One-helper MCP + hook wiring (Cutctx + Serena + RTK-equivalent)
    "HeadroomBundle",
]
