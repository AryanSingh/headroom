---
id: RB-OPS-001
kind: runbook
title: External Provider Outage
triggers: [Provider availability or latency threshold breach, authentication failure surge, degraded provider status, exhausted fallback capacity]
severity: [High, Critical when a core customer journey has no safe alternative]
roles: [Incident Commander, Integration Owner, On-call SRE, Product Owner, Vendor Liaison, Communications Lead]
prerequisites: [Provider dependency map, health telemetry, fallback policy, rate limits, support contract, status contacts]
decisions: [Fail over, degrade feature, queue work, rate limit, disable integration, restore primary]
communication: [Incident channel, provider liaison, support/status owners, affected internal teams]
containment_or_rollback: [Circuit break failing requests, select approved fallback, queue idempotent work, disable optional integration, cap retries]
evidence: [Provider request metrics, status references, correlation IDs, fallback decisions, queue state, customer impact, vendor ticket]
recovery: [Validate provider health, drain work safely, remove temporary controls, monitor recurrence]
exit_criteria: [Primary or approved fallback is stable, queued work is reconciled, customers receive current status]
follow_up: [Review dependency assumptions, fallback coverage, retry policy, vendor escalation, and capacity]
standards: [NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0, NIST-SSDF-1.1]
---

# External Provider Outage

## Purpose

Manage loss or degradation of a dependency without turning it into an internal retry storm, duplicate work, or unbounded cost event. A provider status page is supporting evidence, not a replacement for measurements of the product's own customer impact.

## Product Atlas example

Atlas's tax-calculation provider begins returning timeouts. The integration owner opens the circuit after the five-minute error threshold, shows customers a delayed-estimate message, and queues idempotent recalculation requests. A configured regional fallback is used only for supported jurisdictions. When the primary recovers, the team drains queued work using idempotency keys and reconciles totals before removing the banner.

## Procedure

1. Confirm the symptom using provider-specific error rate, latency, authentication outcome, and correlation IDs. Rule out local DNS, deployment, credential, and quota changes.
2. Declare incident severity from the affected customer journey, not from the provider's reported category. Assign vendor liaison and internal technical owner.
3. Enable the documented containment: circuit breaker, bounded retry, rate limit, queue, feature degradation, or approved fallback. Never fail over to a provider that lacks the required data, residency, safety, or contractual approval.
4. Publish customer behavior: unavailable, delayed, cached, estimated, or queued. Avoid claiming a provider root cause until evidence supports it.
5. Track backlog age, retry volume, duplicate-prevention results, fallback error rate, and customer completion. Escalate if queue age or cost crosses declared limits.
6. When health improves, test a small controlled slice, then drain queued work with idempotency and ordering controls. Reconcile side effects before declaring recovery.
7. Remove temporary controls only after primary and downstream health are stable through the observation window.

## Decision points

| Situation | Action |
| --- | --- |
| Optional feature is affected | Degrade explicitly and preserve the primary journey |
| Idempotent work can wait | Queue with age limit and customer-visible status |
| Approved compatible fallback exists | Fail over in bounded cohort and monitor its own thresholds |
| Non-idempotent financial or stateful action is uncertain | Stop automatic retry; require reconciliation and owner decision |

## Exit and follow-up

Exit when the dependency path is stable, queued work is reconciled, and customer communications reflect reality. Capture provider ticket, timeline, fallback performance, and any retry/queue defect. Update dependency maps and rehearse the changed fallback before relying on it again.
