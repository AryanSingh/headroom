# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Headroom Labs.
"""Provider routing package — failover and format translation.

Provides:
  - FailoverRouter: circuit-breaking provider selection
  - failover_router_from_env: factory from HEADROOM_PROVIDERS env var
  - anthropic_to_openai / openai_to_anthropic: message format converters
  - translate_response: provider response cross-translation
"""

from __future__ import annotations

from .failover import FailoverRouter, ProviderEndpoint, failover_router_from_env
from .format_translation import anthropic_to_openai, openai_to_anthropic, translate_response

__all__ = [
    "FailoverRouter",
    "ProviderEndpoint",
    "failover_router_from_env",
    "anthropic_to_openai",
    "openai_to_anthropic",
    "translate_response",
]
