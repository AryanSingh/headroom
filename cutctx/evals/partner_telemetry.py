"""Validation contract for anonymized design-partner telemetry evidence."""

from __future__ import annotations

from typing import Any

REQUIRED_TOP_LEVEL = {
    "schema_version",
    "period_days",
    "summary",
    "telemetry",
    "savings_by_source_tokens",
}
FORBIDDEN_KEYS = {"messages", "prompt", "completion", "content", "api_key", "authorization"}


def validate_partner_snapshot(payload: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL.difference(payload)
    if missing:
        raise ValueError(f"missing required fields: {sorted(missing)}")
    if payload["period_days"] < 7:
        raise ValueError("partner snapshot must cover at least seven days")
    telemetry = payload["telemetry"]
    for field in ("requests_observed", "fallback", "decline_reasons", "latency_ms", "routing"):
        if field not in telemetry:
            raise ValueError(f"telemetry missing {field}")
    if not payload["savings_by_source_tokens"]:
        raise ValueError("snapshot must include source-level savings")

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            forbidden = FORBIDDEN_KEYS.intersection(value)
            if forbidden:
                raise ValueError(f"snapshot includes disallowed content keys: {sorted(forbidden)}")
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(payload)
