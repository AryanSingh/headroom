---
id: EX-CH19-OBSERVABILITY-README
kind: worked-example
chapter: CH-19
standards: [OTEL-SEMCONV-1.43.0, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
preconditions: [isolated Product Atlas telemetry fixture, approved redaction rules, incident runbook identifier]
placement: engineering-handbook/examples/observability
dependencies: [Python 3 standard library]
invocation: Run python3 observability_fixture.py from this directory or the handbook example runner from the handbook root.
expected_output: A delayed invoice has a stable trace identifier, tenant-safe reference, redacted evidence, and an alert with a safe first action.
failure_output: Missing correlation, token-like data, customer content, absent runbook, or absent action fails the fixture.
interpretation: Telemetry is adequate only when an authorized operator can connect outcome and diagnosis without sensitive data.
remediation: Propagate the correlation ID, replace unsafe fields with tenant-safe references, repair the alert route, and re-run the evidence fixture.
cleanup: The fixture is in-memory and creates no external resources, network traffic, credentials, or customer data.
---

# Product Atlas incident reconstruction

Atlas simulates a delayed invoice. A client-visible `queued` outcome is linked to queue age through `tr-atlas-019`; the alert directs the responder to `RB-INC-01` without exposing invoice content or credentials.

Run `python3 observability_fixture.py`. The deterministic result is:

```text
OBSERVABILITY_FIXTURE_PASS trace-correlated redaction-enforced alert-actionable
```

For a production incident, retain the alert timestamp, scoped diagnostic query, redacted trace sample, queue metric, business-ledger reconciliation, and first containment action.
