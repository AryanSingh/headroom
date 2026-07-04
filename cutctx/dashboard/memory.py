"""Dashboard view for Team Memory impact.

Exposes telemetry and impact metrics tracked by the memory impact runner
and the proxy observability layer.
"""

from fastapi import APIRouter

from cutctx.observability.memory_impact import MemoryImpactTelemetry

router = APIRouter(prefix="/v1/dashboard/memory", tags=["Team Memory Dashboard"])


@router.get("/{org_id}")
async def get_team_memory_dashboard(org_id: str) -> dict:
    """Return aggregated memory metrics for the dashboard view."""
    # A real dashboard would render HTML or provide a richer JSON payload
    metrics = MemoryImpactTelemetry.get_metrics_for_org(org_id)

    return {
        "org_id": org_id,
        "title": "Team Memory Impact Dashboard",
        "metrics": {
            "total_tokens_saved": metrics["total_tokens_saved"],
            "dollars_saved": metrics["total_tokens_saved"] * 0.000001,
            "success_lift": metrics["average_success_lift"],
            "events_count": metrics["events_count"],
        },
    }
