---
id: CH-08
kind: chapter
title: Routing and Orchestration Engineering Audit
purpose: Build and assess routing systems that make bounded, explainable, and reversible provider, model, and workflow decisions.
audience: [Platform engineers, AI engineers, SREs, security engineers, QA]
scope: Classification, policy evaluation, provider selection, budgets, fallback, queues, retries, and decision telemetry.
applicability: Model gateways, job orchestrators, workflow engines, feature routing, and multi-provider services.
owners: [Routing owner, SRE owner, security owner]
inputs: [route policy, workload inventory, provider capabilities, budget policy, failure fixtures]
outputs: [decision matrix, route evidence, release findings, rollback gate]
dependencies: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
---

# Routing and Orchestration Engineering Audit

## Purpose, audience, scope, and applicability

Routing is a production decision system, not a convenience `if` statement. Audit the route selected for each workload, the authority that permitted it, and the evidence needed to reconstruct a fallback or budget decision.

## Concepts and engineering principles

Separate classification, policy, selection, execution, and observation. Keep policy deterministic for the same declared inputs; attach a policy version and correlation ID to every decision. A fallback must preserve tenant, safety tier, data-residency constraint, and user intent rather than merely find any available provider.

## Roles and accountability

The routing owner owns policy semantics and test fixtures. The SRE owner owns capacity, timeout, and rollback behavior. Security approves provider/data boundaries. Product approves quality-cost tradeoffs and the release owner accepts evidence.

## Prerequisites and required inputs

Gather workload classes, allowed providers/models, data classifications, regional constraints, spend and latency budgets, feature flags, fallback graph, timeout policy, evaluation set, telemetry schema, and a kill switch.

## Standard operating procedure

1. Enumerate workload classes and the providers, models, tools, regions, and budgets each may use.
2. Exercise allowed, denied, degraded, budget-exhausted, timeout, and provider-outage fixtures.
3. Verify the selected route is explainable from versioned policy inputs, without secret or prompt leakage in telemetry.
4. Prove a fallback stays inside the original workload's safety, tenant, residency, and approval boundary.
5. Test queue ordering, retry limits, cancellation, and dead-letter handling for duplicate or stranded work.
6. Compare candidate routes against a fixed evaluation set before raising a quality or cost threshold.
7. Retain decision records, rollback evidence, and owner sign-off.

## Worked example

[Product Atlas routing evidence](../examples/routing-orchestration/README.md) routes invoice extraction to an approved low-latency model, rejects a cross-region fallback, and records a deterministic reason when the budget forces a safe queue rather than silent model substitution.

## Automation examples

```typescript
const result = route({ tenant: 'atlas-eu', class: 'invoice-extraction', region: 'eu', budget: 'standard', policy: '2026.08.1' });
expect(result).toMatchObject({ action: 'queue', reason: 'eu-approved-capacity-unavailable' });
expect(result.fallback).toBeUndefined();
```

## Audit prompts

Use [Opus](../prompts/opus/ch08-routing-risk-map.md), [Sonnet](../prompts/sonnet/ch08-fallback-evidence-review.md), and [Haiku](../prompts/haiku/ch08-route-inventory.md) for policy-risk synthesis, a single fallback-path review, and inventory normalization.

## Workflow checklist

Run [CL-ROUTE-01](../checklists/routing-orchestration.md) whenever policy, provider capability, evaluation threshold, fallback graph, or budget behavior changes.

## Evidence requirements and retention guidance

Retain the versioned policy, fixture inputs, selected route, denied candidates, reason code, latency/cost envelope, correlation ID, evaluation revision, and rollback decision. Redact prompts, credentials, and regulated content.

## Example findings with severity and remediation

**High — ROUTE-ATLAS-01.** An EU invoice request fell back to a US-only provider when the preferred provider timed out. Remediation: make residency a non-negotiable predicate, queue when no approved route exists, and add outage regression fixtures.

## KPIs and domain scorecard

The [routing KPI catalog](../scorecards/routing-kpis.md) measures policy-explainability coverage and boundary-preserving fallback coverage. A low-cost route is not successful if it crosses an approved boundary.

## Common failure patterns and diagnostic guidance

- A hidden provider default bypasses the policy evaluator.
- A timeout fallback drops tenant or residency constraints.
- A retry duplicates an orchestrated action after a worker acknowledgement is lost.
- A dashboard aggregates a route reason but cannot identify the governing policy revision.

## Exit criteria

Exit when every workload class has an owner, allowed routes, deterministic reason codes, failure behavior, evaluation evidence, and a tested rollback or disable path.

## Related runbooks, controls, examples, and templates

Use the routing checklist, release-decision, verification-plan, threat-model, and incident-review templates. Coordinate provider outages with the incident response runbook.
