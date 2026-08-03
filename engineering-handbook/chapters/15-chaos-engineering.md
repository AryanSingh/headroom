---
id: CH-15
kind: chapter
title: Chaos Engineering Audit
purpose: Demonstrate that critical outcomes remain safe, observable, and recoverable when realistic failures are deliberately introduced.
audience: [SREs, platform engineers, service owners, security engineers, release managers]
scope: Hypothesis-driven experiments, blast-radius controls, steady-state measures, abort criteria, recovery evidence, and corrective actions.
applicability: Customer-facing services, queues, data stores, identity dependencies, control planes, and AI-assisted workflows.
owners: [Service owner, SRE owner, incident commander]
inputs: [service map, risk register, steady-state indicators, experiment plan, rollback runbook, isolated fixtures]
outputs: [experiment record, findings, remediation backlog, release decision]
dependencies: [NIST-SSDF-1.1, NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
---

# Chaos Engineering Audit

## Purpose, audience, scope, and applicability

Chaos engineering is controlled learning from failure, not unbounded disruption. Audit whether critical outcomes have a measurable steady state, a reversible fault plan, a named stop authority, and evidence that recovery preserves correctness.

## Concepts and engineering principles

Start with a falsifiable hypothesis: under a specified fault, a specified outcome remains within its declared boundary. Bound blast radius by tenant, time, rate, environment, and irreversible actions. A recovered process is not proof if accepted work was duplicated, silently lost, or attributed to the wrong tenant.

## Roles and accountability

The service owner owns the business boundary. The SRE owner designs injection and observability. The incident commander may abort immediately. Security approves experiments that affect authorization, secrets, or tenant isolation. The release owner accepts only remediated or time-bounded residual risk.

## Prerequisites and required inputs

Obtain a dependency map, production-like but isolated fixtures, approved hypothesis, steady-state query, rollback action, abort thresholds, communications channel, and evidence location. Confirm that fault injection cannot contact production or issue irreversible external actions.

## Standard operating procedure

1. Choose one critical outcome and state its success, correctness, latency, and recovery boundary.
2. Define the fault, blast radius, steady-state observation window, stop thresholds, owner, and rollback.
3. Record a baseline; inject one reversible fault at a time.
4. Observe client outcome, queue state, traces, logs, and business ledger together.
5. Abort on a threshold breach; contain, recover, and preserve evidence before retrying.
6. Compare observed behavior with the hypothesis and create a finding for every unsupported claim.
7. Re-run the fixture after remediation and attach the decision to the release evidence.

## Worked example

[Product Atlas queue-partition experiment](../examples/chaos/README.md) injects a bounded worker outage. It proves that an accepted invoice is queued once, exposed as delayed, and recovered without a duplicate charge.

## Automation examples

```bash
python3 chaos_fixture.py
# CHAOS_FIXTURE_PASS queued-once recovered-once abort-threshold-armed
```

```sql
SELECT idempotency_key, COUNT(*)
FROM invoice_outcomes
WHERE experiment_id = 'atlas-queue-partition-01'
GROUP BY idempotency_key HAVING COUNT(*) > 1;
```

## Audit prompts

Use [Opus](../prompts/opus/ch15-chaos-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch15-experiment-evidence-review.md), and [Haiku](../prompts/haiku/ch15-experiment-inventory.md) for risk synthesis, experiment evidence review, and compact experiment inventory.

## Workflow checklist

Use [CL-CHAOS-01](../checklists/chaos-engineering.md) before any fault injection, recovery exercise, or chaos-derived release claim.

## Evidence requirements and retention guidance

Retain the approved hypothesis, scope, fixture version, baseline, injection record, abort decision, trace and metric queries, business-ledger reconciliation, recovery record, finding, and owner decision. Exclude payloads, credentials, and customer content.

## Example findings with severity and remediation

**High — CHAOS-ATLAS-01.** A worker restart replayed an acknowledged invoice without an idempotency record. Remediate by writing durable deduplication state before acknowledgement and repeating the restart fixture as a release gate.

## KPIs and domain scorecard

The [chaos KPI catalog](../scorecards/chaos-kpis.md) measures hypothesis coverage and verified recovery. Do not count a planned experiment as coverage until its business result and abort behavior are evidenced.

## Common failure patterns and diagnostic guidance

- An experiment measures process uptime instead of customer outcome and duplicate work.
- A broad fault lacks a kill switch or named abort authority.
- A synthetic fixture hides tenant skew, cold-cache behavior, or queue age.
- Recovery evidence is collected after logs have expired or sampling discarded the failing trace.

## Exit criteria

Exit when the fault hypothesis has baseline and observed evidence, blast radius remained bounded, abort and recovery paths were demonstrably usable, accepted work reconciles correctly, and findings have an owner and due date.

## Related runbooks, controls, examples, and templates

Use the incident-review, verification-plan, and release-decision templates with the chaos checklist and production incident runbook.
