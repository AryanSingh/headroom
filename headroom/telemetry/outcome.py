"""Outcome signal module.

Captures terminal events from scanners or proxy responses to determine
success or failure of the operations. This feeds the ValueModel (B2) and
provides labels for the data flywheel (A3).
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any

class OutcomeSignal(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"

@dataclass
class OutcomeEvent:
    """Records an outcome event."""
    session_id: str
    tenant_id: str
    signal: OutcomeSignal
    timestamp_ts: float
    context: dict[str, Any]

class OutcomeEmitter:
    """Emits outcome signals."""
    
    _handlers = []
    
    @classmethod
    def register_handler(cls, handler):
        cls._handlers.append(handler)
        
    @classmethod
    def emit(cls, event: OutcomeEvent):
        for handler in cls._handlers:
            try:
                handler(event)
            except Exception as e:
                # Log but don't disrupt
                import logging
                logging.getLogger(__name__).warning(f"Error handling outcome: {e}")
