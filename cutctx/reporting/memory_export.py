"""Reporting export for memory metrics.

Provides downloadable formats (CSV, PDF placeholders) for team memory metrics.
"""

from fastapi import APIRouter, Response

from cutctx.observability.memory_impact import MemoryImpactTelemetry

router = APIRouter(prefix="/v1/reports/memory", tags=["Team Memory Reporting"])


@router.get("/{org_id}/csv")
async def export_memory_metrics_csv(org_id: str) -> Response:
    """Export memory metrics as CSV."""
    metrics = MemoryImpactTelemetry.get_metrics_for_org(org_id)

    # Generate simple CSV
    csv_content = "Metric,Value\n"
    csv_content += f"Total Tokens Saved,{metrics['total_tokens_saved']}\n"
    csv_content += f"Average Success Lift,{metrics['average_success_lift']:.2f}\n"
    csv_content += f"Dollars Saved,${metrics['total_tokens_saved'] * 0.000001:.2f}\n"
    csv_content += f"Total Impact Events,{metrics['events_count']}\n"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="memory_impact_{org_id}.csv"'},
    )
