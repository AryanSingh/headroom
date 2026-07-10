from __future__ import annotations

from scripts.validate_partner_telemetry_snapshot import validate_partner_snapshot


def _snapshot() -> dict:
    return {
        "schema_version": "agent_context_report_v1",
        "period_days": 7,
        "summary": {"requests": 20, "tokens_saved": 100},
        "savings_by_source_tokens": {"cutctx_compression": 100},
        "telemetry": {
            "requests_observed": 20,
            "fallback": {"count": 0},
            "decline_reasons": {},
            "latency_ms": {"p50": 1.0, "p95": 2.0},
            "routing": {"routed_requests": 0},
        },
    }


def test_partner_snapshot_requires_release_evidence_fields() -> None:
    validate_partner_snapshot(_snapshot())


def test_partner_snapshot_rejects_prompt_content() -> None:
    payload = _snapshot()
    payload["telemetry"]["content"] = "customer prompt"
    try:
        validate_partner_snapshot(payload)
    except ValueError as exc:
        assert "disallowed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected redaction validation failure")
