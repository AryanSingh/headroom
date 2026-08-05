---
id: CH-10
kind: chapter
title: Reliability, Performance, and Scale Engineering Audit
purpose: Build and assess services that meet explicit reliability and latency objectives under normal, degraded, and recovery conditions.
audience: [SREs, platform engineers, backend engineers, security engineers, QA, engineering leaders]
scope: Service objectives, capacity, load, latency, resiliency, observability, recovery, and scalability evidence.
applicability: APIs, asynchronous workers, data stores, gateways, dashboards, and AI-assisted production workloads.
owners: [Service owner, SRE owner, data owner]
inputs: [service objectives, traffic model, dependency map, load fixtures, recovery plan, telemetry contract]
outputs: [reliability evidence register, capacity decision, recovery findings, release gate]
dependencies: [NIST-SSDF-1.1, OTEL-SEMCONV-1.43.0, OWASP-ASVS-5.0.0]
standards: [NIST-SSDF-1.1, OTEL-SEMCONV-1.43.0, OWASP-ASVS-5.0.0]
---

# Reliability, Performance, and Scale Engineering Audit

## Purpose, audience, scope, and applicability

Reliability is a demonstrated ability to deliver the intended outcome within a declared envelope, not an average from a quiet period. Audit whether a service has measurable objectives, realistic load evidence, safe degradation, and a recovery path that preserves correctness as well as availability.

## Concepts and engineering principles

Define service-level indicators before selecting objectives. Separate client-visible availability, successful business outcome, latency, freshness, and recovery time; a `200` response for a stale or duplicate payment is not a successful outcome. Capacity claims must name workload shape, dependencies, data size, region, and failure assumptions. Emit consistent traces, metrics, and logs with correlation identifiers, while keeping sensitive content out of telemetry.

## Roles and accountability

The service owner owns correctness and performance behavior. The SRE owner owns objective design, alerting, scaling, and incident drills. The data owner owns recovery-point and integrity requirements. Security reviews denial-of-service controls and observability redaction. The release owner accepts residual risk only with evidence and an accountable expiry.

## Prerequisites and required inputs

Collect a dependency map, traffic and data-growth model, current objectives and error budgets, load profile, production-like fixture data, autoscaling policy, queue and cache limits, timeout and retry budgets, backup/restore design, telemetry schema, runbook, and incident contacts. Ensure the test environment cannot contact production or issue real financial, notification, or destructive actions.

## Standard operating procedure

1. Define each critical user and business outcome with an indicator, objective, window, owner, and source of truth.
2. Model expected, peak, burst, recovery, and abusive traffic; include payload size, tenant distribution, cache state, and dependency latency.
3. Run a baseline load test, then progressively test saturation, a slow dependency, cache loss, worker loss, queue backlog, and regional or datastore degradation.
4. Verify timeouts, retries, circuit breakers, backpressure, idempotency, and shedding preserve the declared correctness boundary.
5. Measure end-to-end latency and success from the client boundary; correlate every sampled failure to traces, logs, and metrics.
6. Restore a representative backup or replay a bounded event fixture, validate data integrity, and record recovery time and point.
7. Compare results to objectives, approve only remediated gaps or time-bounded exceptions, and rehearse rollback or traffic reduction.

## Worked example

[Product Atlas load and recovery evidence](../examples/reliability-performance/README.md) tests a tenant-scoped invoice API during a burst and a simulated primary-store outage. It demonstrates bounded queueing, an idempotent retry, and a verified restore rather than treating raw request throughput as proof of resilience.

## Automation examples

```typescript
const result = await atlas.invoices.create({
  tenant: 'atlas-a',
  idempotencyKey: 'load-fixture-0042',
  simulate: { storeLatencyMs: 1500 },
});
expect(result).toMatchObject({ status: 'queued', reason: 'dependency-latency-budget-exceeded' });
expect(await atlas.metrics.read('invoice.create.duplicate_writes')).toBe(0);
```

```sql
SELECT recovery_point_at, restored_at, integrity_verified
FROM recovery_evidence
WHERE exercise_id = 'atlas-dr-2026-08'
  AND integrity_verified = true;
```

## Audit prompts

Use [Opus](../prompts/opus/ch10-resilience-risk-assessment.md), [Sonnet](../prompts/sonnet/ch10-slo-evidence-review.md), and [Haiku](../prompts/haiku/ch10-service-inventory.md) for cross-system resilience assessment, one objective's evidence review, and compact service inventory normalization.

## Workflow checklist

Run [CL-REL-01](../checklists/reliability-performance.md) before raising an objective, changing a dependency, capacity policy, retry/timeout setting, persistence topology, or recovery procedure.

## Evidence requirements and retention guidance

Retain objective revisions, traffic model assumptions, fixture versions, load configuration, environment identity, sampled result distributions, dependency-injection records, trace and metric queries, queue depth, error-budget decision, restore evidence, integrity checks, and release decision. Keep request payloads, credentials, and personal data out of the evidence package.

## Example findings with severity and remediation

**High — REL-ATLAS-01.** Invoice creation maintained a 99.9% HTTP success rate during primary-store latency, but accepted the same idempotency key twice after retry workers restarted. Remediation: persist the idempotency state before acknowledgement, replay the restart fixture, and make duplicate business outcomes a release-blocking indicator.

## KPIs and domain scorecard

The [reliability KPI catalog](../scorecards/reliability-kpis.md) tracks objective attainment and verified recovery coverage. Interpret latency and availability by workload class and correctness outcome; a fleet average cannot excuse a failed critical tenant path.

## Common failure patterns and diagnostic guidance

- A load test uses a warm cache and uniform payloads while production has bursty tenants and cold reads.
- A retry budget exceeds the caller deadline and creates a self-amplifying dependency failure.
- Health checks show a worker process is alive while its queue is stuck or its credentials are revoked.
- A restore exercise verifies row count but not referential integrity, freshness, access policy, or downstream replay safety.
- Telemetry captures request bodies or tokens, making the diagnostic system itself a sensitive-data exposure.

## Exit criteria

Exit when critical outcomes have owned objectives, production-representative load and degradation evidence, bounded failure behavior, telemetry that supports reconstruction without sensitive disclosure, a tested restore path with integrity proof, and an approved rollback or traffic-reduction action.

## Related runbooks, controls, examples, and templates

Use the reliability checklist, verification-plan, release-decision, incident-review, and migration-plan templates. Coordinate objective breaches and failed recovery exercises with the incident response and release runbooks.
