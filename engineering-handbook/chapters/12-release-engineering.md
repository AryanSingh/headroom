---
id: CH-12
kind: chapter
title: Release Engineering Audit
purpose: Build and assess release systems that create attributable, reproducible, reversible, and observable changes from approved source to production.
audience: [Release engineers, platform engineers, SREs, security engineers, QA, engineering leaders]
scope: Build provenance, test gates, artifact promotion, configuration, change approval, deployment, rollback, verification, and release evidence.
applicability: Services, CLIs, desktop applications, dashboards, infrastructure, data changes, and AI model or policy releases.
owners: [Release owner, service owner, security owner, SRE owner]
inputs: [approved change, source revision, dependency lockfile, test evidence, artifact manifest, deployment plan, rollback plan]
outputs: [release decision, provenance record, deployment evidence, rollback readiness result]
dependencies: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OTEL-SEMCONV-1.43.0]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OTEL-SEMCONV-1.43.0]
---

# Release Engineering Audit

## Purpose, audience, scope, and applicability

A release is a controlled production change, not merely a successful build. Audit whether source, dependencies, configuration, artifacts, approvals, deployment observations, and rollback actions can be connected without ambiguity.

## Concepts and engineering principles

Promote immutable artifacts rather than rebuilding per environment. Separate code, configuration, policy, and data changes while linking them in one release record. A rollback must be executable under degraded conditions and must state whether it reverses binaries, configuration, schema, traffic, or customer-visible state.

## Roles and accountability

The release owner owns the gate and evidence package. The service owner owns functional and compatibility acceptance. SRE owns deployment health, traffic control, and rollback execution. Security owns supply-chain and change-control review. QA owns scenario coverage; the incident commander directs emergency changes when activated.

## Prerequisites and required inputs

Collect the approved change record, source revision, dependency lockfile, build identity, artifact digest, SBOM or equivalent dependency evidence, test results, migration assessment, feature-flag plan, deployment target, telemetry queries, communication plan, and rollback criteria.

## Standard operating procedure

1. Freeze the release candidate source revision, dependencies, build inputs, and artifact digest in a release record.
2. Run required unit, integration, security, migration, accessibility, and customer-journey gates against the candidate.
3. Verify configuration and secrets are injected by approved references; never copy production secrets into release evidence or build logs.
4. Promote the same immutable artifact through staged environments with explicit approvals, traffic limits, and observable health criteria.
5. Execute canary or bounded rollout fixtures; compare client outcomes, error rate, latency, security signals, and business correctness against baseline.
6. Stop or roll back when a declared criterion is breached; capture the reason, action, and customer impact.
7. Close only after post-deployment verification, release communication, evidence retention, and any follow-up owner assignment are complete.

## Worked example

[Product Atlas release engineering evidence](../examples/release-engineering/README.md) promotes a tenant-export service through a 5% canary, blocks a schema-incompatible worker, and rolls back the immutable artifact without reversing completed exports.

## Automation examples

```bash
atlasctl release verify --artifact sha256:atlas-export-2026-09-18 --environment staging --format json
atlasctl release promote --artifact sha256:atlas-export-2026-09-18 --environment production --traffic-percent 5
atlasctl release rollback --release rel-atlas-2026-09-18 --reason "canary-error-budget-breach"
```

## Audit prompts

Use [Opus](../prompts/opus/ch12-release-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch12-release-evidence-review.md), and [Haiku](../prompts/haiku/ch12-release-inventory.md) for release-chain risk synthesis, one candidate's evidence review, and release-record normalization.

## Workflow checklist

Run [CL-RELENG-01](../checklists/release-engineering.md) for every production promotion and for any change to deployment policy, pipeline, signing, environment configuration, migration, or rollback mechanism.

## Evidence requirements and retention guidance

Retain change approval, source revision, dependency and artifact digest, test run IDs, deployment target, configuration revision, traffic decision, telemetry query/result, rollback result, and owner attestations. Retain references and hashes rather than secrets, customer content, or full production logs.

## Example findings with severity and remediation

**Critical — REL-ATLAS-01.** Production rebuilt from the same tag with a changed dependency resolution, so the tested artifact digest could not be deployed. Remediation: fail rebuild-on-promotion, persist the tested immutable digest, and require a new candidate when build inputs change.

## KPIs and domain scorecard

The [release KPI catalog](../scorecards/release-kpis.md) measures verified promotion coverage and rollback readiness. Deployment frequency is not a health metric when evidence or reversibility is absent.

## Common failure patterns and diagnostic guidance

- A pipeline reports green while its test result belongs to another source revision.
- A feature flag lacks an owner, expiry, or safe default when the control plane fails.
- A rollback restores code but leaves an incompatible asynchronous consumer or policy revision active.
- Emergency changes bypass evidence collection permanently instead of creating a retrospective record.

## Exit criteria

Exit when the release record ties one approved change to immutable artifacts, passing gates, environment configuration, observable deployment results, usable rollback, post-deployment verification, and retained evidence.

## Related runbooks, controls, examples, and templates

Use the release checklist, release-decision, verification-plan, migration-plan, incident-review, and executive-summary templates. Use the incident response runbook for an active customer-impacting deployment failure.
