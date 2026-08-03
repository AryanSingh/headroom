---
id: CH-20
kind: chapter
title: Continuous Verification and Release Automation
purpose: Establish candidate-bound, evidence-led continuous verification and release automation that can safely promote, stop, contain, and learn from change.
audience: [Release engineers, platform engineers, service owners, SREs, security engineers, engineering leaders]
scope: Qualification policies, CI evidence, provenance, promotion gates, exceptions, staged rollout, post-release verification, rollback, and continuous improvement.
applicability: Services, clients, infrastructure, configuration, data changes, feature flags, dependencies, and all production promotions.
owners: [Release engineering owner, service owner, security owner, SRE owner]
inputs: [candidate manifest, release policy, check catalog, provenance, test evidence, exception register, rollout plan, telemetry]
outputs: [release decision, qualification record, rollout evidence, rollback record, improvement findings]
dependencies: [NIST-SSDF-1.1, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
---

# Continuous Verification and Release Automation

## Purpose, audience, scope, and applicability

Continuous verification turns engineering assertions into repeatable evidence tied to a specific candidate. Audit whether production automation blocks unsafe promotion, records authorized exceptions, observes outcome quality, and provides a timely stop or recovery path.

## Concepts and engineering principles

A build is not a release decision. Bind source, dependencies, artifact, configuration, target environment, policy version, check outputs, and approval to the same candidate. Prefer a small explicit policy over an opaque green pipeline. A release gate needs a named owner, threshold, evidence, failure action, and exception path.

## Roles and accountability

Release engineering owns the qualification policy and evidence assembly. The service owner owns product and operational thresholds. Security owns security-gate interpretation and exception review. SRE owns staged-rollout observation and containment readiness. The release owner accepts or rejects the candidate; automation must not silently substitute for that accountable decision.

## Prerequisites and required inputs

Collect the immutable candidate identifier, source/dependency provenance, required-check catalog, environment configuration, test and security evidence, migration and compatibility status, exception register, rollout plan, objectives, stop thresholds, rollback plan, and named on-call ownership.

## Standard operating procedure

1. Version the release policy and bind each required check to candidate, environment, owner, threshold, evidence reference, and failure action.
2. Build once, record provenance, and promote the same immutable artifact through qualification rather than rebuilding per environment.
3. Evaluate required checks; fail closed when a check is failed, skipped, stale, unavailable, or not candidate-bound.
4. Allow an exception only when scope, owner, compensating controls, expiry, risk acceptance, and follow-up work are recorded.
5. Select the rollout cohort, observation window, health and business outcome thresholds, stop authority, and rollback or forward-repair decision before deployment.
6. Promote in stages, evaluate telemetry and customer outcomes against declared thresholds, and halt or contain on breach.
7. Retain the decision and post-release verification, then turn failures, near misses, and manual intervention into a policy or automation improvement.

## Worked example

[Product Atlas continuous-verification release gate](../examples/continuous-verification/README.md) blocks a failed reconciliation check, requires evidence linkage, and permits promotion only after the same candidate’s declared check passes.

## Automation examples

```bash
python3 verification_fixture.py
# CONTINUOUS_VERIFICATION_FIXTURE_PASS failed-check-blocked evidence-linked promotion-approved
```

```yaml
candidate: atlas-api@sha256:8cf1
required_checks: [unit, security, migration-reconciliation]
stop_when: "customer-success < 99.9% or integrity-alert == true"
```

## Audit prompts

Use [Opus](../prompts/opus/ch20-release-assurance-synthesis.md), [Sonnet](../prompts/sonnet/ch20-gate-evidence-review.md), and [Haiku](../prompts/haiku/ch20-verification-inventory.md) for cross-system assurance synthesis, candidate evidence review, and mechanical inventory normalization.

## Workflow checklist

Run [CL-CONTINUOUS-VERIFICATION-01](../checklists/continuous-verification-release-automation.md) for every production promotion and any policy, pipeline, environment, dependency, or rollout change.

## Evidence requirements and retention guidance

Retain candidate identity, source and artifact provenance, policy version, check configuration and output references, approvals, exceptions, rollout configuration, threshold evaluations, deployment log, rollback or containment record, and post-release verification. Keep only safe references for secrets, customer data, and privileged production output.

## Example findings with severity and remediation

**High — CV-ATLAS-01.** The production gate accepted a passing integration result from a different artifact digest than the deployed candidate. Block promotion, invalidate the decision, repair the candidate binding, rerun qualification from immutable provenance, and review all releases evaluated by the same policy.

## KPIs and domain scorecard

The [continuous-verification KPI catalog](../scorecards/continuous-verification-kpis.md) measures candidate-bound evidence completeness and safe release-automation coverage. Deployment frequency is not evidence of controlled promotion.

## Common failure patterns and diagnostic guidance

- A green aggregate hides a skipped required check or a result from another candidate.
- A waiver has no expiry, compensating control, or accountable risk owner.
- Canary telemetry measures host health but not customer outcome or integrity.
- Rollback is documented but not executable for data, configuration, or dependency changes.

## Exit criteria

Exit when the candidate has complete required-check evidence or an authorized time-bounded exception, promotion and rollout thresholds are explicit, containment or recovery is rehearsed, post-release outcomes are verified, and the accountable owner records the decision.

## Related runbooks, controls, examples, and templates

Use the release-decision, verification-plan, incident-review, finding, and evidence-register templates. Use release engineering for deployment mechanics, database migrations for data-change evidence, and the incident response runbook when release impact crosses declared safety or integrity thresholds.
