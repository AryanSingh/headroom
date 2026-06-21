"""Handler mixins for CutctxProxy.

Each mixin class contains methods extracted from CutctxProxy that handle
requests for a specific provider or concern. The mixins rely on CutctxProxy's
__init__ for all self.* attributes (duck typing).
"""

from headroom.proxy.handlers.anthropic import AnthropicHandlerMixin
from headroom.proxy.handlers.batch import BatchHandlerMixin
from headroom.proxy.handlers.gemini import GeminiHandlerMixin
from headroom.proxy.handlers.openai import OpenAIHandlerMixin
from headroom.proxy.handlers.streaming import StreamingMixin

__all__ = [
    "AnthropicHandlerMixin",
    "BatchHandlerMixin",
    "GeminiHandlerMixin",
    "OpenAIHandlerMixin",
    "StreamingMixin",
]
