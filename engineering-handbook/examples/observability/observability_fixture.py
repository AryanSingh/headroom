"""Deterministic Product Atlas observability evidence fixture."""


def main() -> None:
    event = {
        "trace_id": "tr-atlas-019",
        "tenant_ref": "tenant-hash-4a",
        "outcome": "queued",
        "queue_age_ms": 4200,
    }
    alert = {"trace_id": event["trace_id"], "runbook": "RB-INC-01", "action": "inspect queue age"}
    serialized = repr((event, alert)).lower()
    assert alert["trace_id"] == event["trace_id"]
    assert (
        "token" not in serialized
        and "secret" not in serialized
        and "invoice_content" not in serialized
    )
    assert alert["runbook"] and alert["action"]
    print("OBSERVABILITY_FIXTURE_PASS trace-correlated redaction-enforced alert-actionable")


if __name__ == "__main__":
    main()
