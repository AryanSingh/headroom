---
id: CH-18
kind: chapter
title: API and SDK Compatibility Engineering Audit
purpose: Build and assess versioned interfaces that preserve supported consumer behavior, enforce authority boundaries, and provide measurable deprecation and recovery evidence.
audience: [API engineers, SDK maintainers, platform engineers, security engineers, QA engineers, release managers]
scope: HTTP and event contracts, generated SDKs, semantic versioning, compatibility matrices, deprecation, schema evolution, error contracts, tenancy, consumer testing, and release evidence.
applicability: Public APIs, internal service contracts, client libraries, CLIs, webhooks, events, generated clients, plugins, and integration surfaces.
owners: [API owner, SDK owner, consumer owner, security owner, release owner]
inputs: [contract specification, supported-version policy, consumer inventory, compatibility matrix, schema diff, generated-client results, deprecation plan, security review]
outputs: [compatibility decision, consumer evidence, deprecation record, release gate, remediation plan]
dependencies: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
---

# API and SDK Compatibility Engineering Audit

## Purpose, audience, scope, and applicability

An API or SDK change is a distributed release. Audit whether every supported consumer can interpret the transition, preserve its authority boundary, report actionable failures, and reach a documented deprecation path. Apply this chapter to synchronous, asynchronous, generated, and human-operated interfaces.

## Concepts and engineering principles

Treat a contract as request semantics, response semantics, errors, authorization, ordering, limits, and documented defaults. Prefer additive changes and explicit versioning. A client that compiles is not necessarily compatible: validate runtime decoding, behavior, tenant scoping, retries, and rollback assumptions.

## Roles and accountability

The API owner defines contract and lifecycle rules. The SDK owner maintains generated and hand-written client behavior. Consumer owners prove supported use cases. Security reviews authority, tenant, and input boundaries. The release owner accepts evidence or blocks the promotion.

## Prerequisites and required inputs

Collect the version policy, contract specification, schema and behavior diff, supported-client inventory, generated-client versions, compatibility matrix, error catalog, deprecation notices, migration guide, rollout plan, and escalation owner.

## Standard operating procedure

1. Classify each change as additive, behavior-affecting, deprecation, or breaking across request, response, errors, authorization, limits, and events.
2. Identify every supported consumer, its version, tenancy boundary, generated-client behavior, and rollback path.
3. Run contract tests against declared old and new versions, including unknown additive fields and removed required fields.
4. Verify authorization and tenant binding remain unchanged; never make a compatibility fallback that broadens access.
5. Publish a versioned migration path, support window, telemetry signal, owner, and retirement criteria before a deprecation starts.
6. Gate rollout on consumer evidence, error-rate and semantic-outcome thresholds, support readiness, and an accountable release decision.
7. Remove compatibility code only after the support window, observed adoption, consumer confirmation, and recovery evidence meet the documented exit rule.

## Worked example

[Product Atlas offline SDK compatibility fixture](../examples/sdk-compatibility/README.md) accepts an additive v1 response field, rejects a cross-tenant request, and blocks a response that removes a required v1 field.

## Automation examples

```shell
python3 compatibility_fixture.py
# SDK_COMPATIBILITY_FIXTURE_PASS additive-safe tenant-bound breaking-change-blocked
```

```yaml
compatibility_gate:
  supported_client: atlas-sdk-python-v1
  required_response_fields: [account_id, plan, usage]
  additive_fields: tolerated
  removed_required_field: block
```

## Audit prompts

Use [Opus](../prompts/opus/ch18-compatibility-risk-synthesis.md) for change-chain synthesis, [Sonnet](../prompts/sonnet/ch18-consumer-evidence-review.md) for one consumer’s evidence, and [Haiku](../prompts/haiku/ch18-contract-inventory.md) for interface inventory normalization.

## Workflow checklist

Run [CL-SDK-COMPATIBILITY-01](../checklists/api-sdk-compatibility.md) before exposing, modifying, deprecating, or retiring a contract or supported client.

## Evidence requirements and retention guidance

Retain the specification revision, compatibility classification, supported-client matrix, request/response/error fixtures, generated-client results, consumer-contract runs, migration notice, adoption telemetry, exception approvals, and release decision. Keep traces and payloads sanitized; never retain credentials or customer data merely to prove compatibility.

## Example findings with severity and remediation

**High — SDK-ATLAS-18.** A v1 response removed `plan` after a server rollout while a supported generated client still required it. Restore or version the response, block retirement, notify consumer owners, add a regression fixture, and release only after the compatibility matrix and rollout evidence are current.

## KPIs and domain scorecard

The [API and SDK compatibility KPI catalog](../scorecards/api-sdk-compatibility-kpis.md) measures evidence coverage and deprecation completion. Do not use endpoint count as a proxy for safe adoption.

## Common failure patterns and diagnostic guidance

- An additive server change changes the meaning, default, pagination, ordering, or authorization of an existing field.
- A generated SDK is upgraded without running the previous supported client against the new service contract.
- A deprecation notice lacks a measurable adoption signal, an owner, or a rollback path.
- An error envelope changes from a stable machine-readable code to unparseable prose.
- A fallback accepts a caller, tenant, or scope that the prior contract rejected.

## Exit criteria

Exit when supported consumers have compatible request, response, error, and authority evidence; the lifecycle and deprecation decision are recorded; incompatible changes have an explicit version or migration; telemetry proves the transition state; and accountable owners accept the release.

## Related runbooks, controls, examples, and templates

Use the release-decision, verification-plan, finding, evidence-register, and migration-plan templates. Use the release engineering chapter for deployment gates and the incident response runbook when a contract regression affects confidentiality, integrity, availability, or customer outcomes.
