---
id: CH-19
kind: chapter
title: Production Observability Engineering Audit
purpose: Establish evidence-quality telemetry that detects, explains, and safely supports recovery from production degradation.
audience: [SREs, platform engineers, service owners, security engineers, incident commanders]
scope: Service indicators, telemetry contracts, alert quality, traceability, dashboards, retention, redaction, and operational evidence.
applicability: APIs, workers, data pipelines, control planes, dashboards, integrations, and AI-assisted services.
owners: [SRE owner, service owner, security owner]
inputs: [service inventory, objectives, telemetry schema, alert policy, dashboard queries, incident records]
outputs: [observability assessment, alert findings, telemetry contract, evidence register]
dependencies: [OTEL-SEMCONV-1.43.0, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
standards: [OTEL-SEMCONV-1.43.0, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
---

# Production Observability Engineering Audit

## Purpose, audience, scope, and applicability

Observability is the ability to answer an operational question from safe, correlated evidence. Audit whether telemetry explains customer outcomes and supports containment without making logs or dashboards a new sensitive-data system.

## Concepts and engineering principles

Instrument the client boundary, business outcome, dependencies, queue, and recovery path. Use stable correlation identifiers and semantic conventions. Separate symptom, cause, and actionability; an alert is useful only if it identifies an owner, threshold, impact, and first safe action.

## Roles and accountability

The SRE owner owns telemetry contracts, alert quality, and operational dashboards. The service owner owns business indicators and remediation. Security owns redaction and access review. The incident commander uses evidence to coordinate severity, containment, and communications.

## Prerequisites and required inputs

Collect service inventory, critical outcome map, objectives, dashboards and alert rules, telemetry schema, sample traces, retention policy, access roles, and recent incident records. Use sanitized fixtures for tests and prohibit credentials, tokens, and customer payloads in evidence.

## Standard operating procedure

1. Map every critical outcome to success, latency, correctness, and dependency indicators.
2. Define required trace, metric, log, and business-ledger fields, including correlation and tenant-safe identifiers.
3. Exercise normal, degraded, and recovery fixtures and verify cross-signal correlation.
4. Test each alert for detection time, signal quality, routing, actionable runbook link, and suppression behavior.
5. Review sampling, retention, access, and redaction against diagnostic and privacy needs.
6. Reconstruct a recent or simulated incident from retained evidence; record gaps and false positives.
7. Version the telemetry contract and reject releases that remove required evidence without an approved replacement.

## Worked example

[Product Atlas incident reconstruction](../examples/observability/README.md) correlates a delayed invoice from a client outcome through queue age, dependency latency, trace ID, and a redacted alert without storing invoice content.

## Automation examples

```bash
python3 observability_fixture.py
# OBSERVABILITY_FIXTURE_PASS trace-correlated redaction-enforced alert-actionable
```

```json
{"trace_id":"tr-atlas-019","tenant_ref":"tenant-hash-4a","outcome":"queued","queue_age_ms":4200}
```

## Audit prompts

Use [Opus](../prompts/opus/ch19-observability-gap-analysis.md), [Sonnet](../prompts/sonnet/ch19-alert-evidence-review.md), and [Haiku](../prompts/haiku/ch19-telemetry-inventory.md) for cross-signal gap analysis, alert evidence review, and telemetry inventory normalization.

## Workflow checklist

Run [CL-OBS-01](../checklists/production-observability.md) for new critical outcomes, alerts, dashboards, telemetry fields, retention changes, and release reviews.

## Evidence requirements and retention guidance

Retain telemetry contract versions, dashboard and alert definitions, synthetic exercise results, sample redacted traces, alert route tests, access review, retention decision, incident timeline, and query references. Do not retain raw authentication material, prompt content, or customer payloads merely for troubleshooting.

## Example findings with severity and remediation

**High — OBS-ATLAS-01.** The latency alert fired but no trace identifier connected the alert to a queue or business ledger. Remediate by propagating a stable correlation ID at ingestion and making the alert link to a scoped diagnostic query.

## KPIs and domain scorecard

The [observability KPI catalog](../scorecards/observability-kpis.md) measures reconstruction coverage and actionable alert quality. Low alert volume is not success if incidents are discovered by customers.

## Common failure patterns and diagnostic guidance

- Dashboard averages hide tail latency or a tenant-specific failure.
- Logs contain raw tokens or payloads because redaction was not tested.
- Alerts route to an unowned channel or link to a stale runbook.
- Sampling removes the only traces for errors or recovery actions.

## Exit criteria

Exit when critical outcomes are correlated across telemetry and business evidence, alerts are actionable and owned, retention and access protect sensitive data, and a simulated incident can be reconstructed within the declared operational window.

## Related runbooks, controls, examples, and templates

Use the incident-review, verification-plan, and release-decision templates with the production incident response and observability checklist.
