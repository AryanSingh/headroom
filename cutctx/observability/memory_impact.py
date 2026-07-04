"""Telemetry surface to capture and expose memory impact metrics."""

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MemoryImpactEvent:
    org_id: str
    workspace_id: str
    tokens_saved: int
    success_lift: float
    timestamp: datetime


class MemoryImpactTelemetry:
    """Records memory impact telemetry for B3."""

    _events: list[MemoryImpactEvent] = []

    @classmethod
    def record_impact(cls, org_id: str, workspace_id: str, tokens_saved: int, success_lift: float):
        event = MemoryImpactEvent(
            org_id=org_id,
            workspace_id=workspace_id,
            tokens_saved=tokens_saved,
            success_lift=success_lift,
            timestamp=datetime.utcnow(),
        )
        cls._events.append(event)
        logger.info(
            f"MemoryImpact [org={org_id}]: saved {tokens_saved} tokens, lift={success_lift}"
        )

    @classmethod
    def get_metrics_for_org(cls, org_id: str) -> dict:
        org_events = [e for e in cls._events if e.org_id == org_id]
        return {
            "total_tokens_saved": sum(e.tokens_saved for e in org_events),
            "average_success_lift": sum(e.success_lift for e in org_events)
            / max(1, len(org_events)),
            "events_count": len(org_events),
        }
