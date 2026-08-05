---
id: CL-OBS-01
kind: checklist
title: Production observability release checklist
chapter: CH-19
controls:
  - id: ENG-OBS-001
    requirement: Each critical outcome must emit a versioned, privacy-safe telemetry contract that correlates client, dependency, queue, and business evidence.
    applicability: required for customer-facing services, asynchronous workflows, durable operations, and critical control-plane actions
    procedure: Define required semantic fields, correlation and tenant-safe identifiers, redaction rules, cardinality limits, retention, and evidence queries; exercise normal, degraded, and recovery fixtures.
    expected_result: A scoped operator can reconstruct the outcome without raw credentials, customer payloads, or uncorrelated signals.
    evidence: telemetry contract, fixture report, redacted trace, metric query, log sample, access review, and retention decision
    automation: telemetry-contract and redaction fixture suite
    owner: SRE owner
    frequency: release and any telemetry, schema, retention, or access change
    failure_action: block release, remove unsafe fields, restore required correlation, and retest fixture evidence
    standards: [OTEL-SEMCONV-1.43.0, OWASP-ASVS-5.0.0]
  - id: ENG-OBS-002
    requirement: Alerts for critical outcomes must be owned, thresholded, routed, actionable, and periodically exercised against a representative failure.
    applicability: required for all critical objectives and customer-impacting dependencies
    procedure: Test detection time, signal quality, route, deduplication, suppression, dashboard query, and first safe runbook action using an isolated degraded fixture.
    expected_result: The correct owner receives an actionable alert with a scoped diagnostic link and can begin containment without guessing.
    evidence: alert definition, route test, fixture timestamps, alert payload, runbook link, acknowledgement, and follow-up finding
    automation: alert route and evidence-quality fixture
    owner: Service owner
    frequency: quarterly, release for critical-path changes, and after alert noise or miss
    failure_action: disable noisy unsafe alert, repair route or runbook, and retest before relying on the signal
    standards: [NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
---

# Production observability release checklist

- [ ] Map each critical outcome to client success, correctness, latency, dependency, and recovery evidence.
- [ ] Enforce semantic fields, stable correlation, redaction, bounded cardinality, retention, and least-privilege access.
- [ ] Exercise normal, degraded, and recovery fixtures and preserve representative redacted evidence.
- [ ] Test each critical alert for threshold, route, ownership, diagnostic query, and safe first action.
- [ ] Reconstruct a simulated incident from retained evidence within the operating window.
- [ ] Version the telemetry contract and record exceptions with owner and expiry.
