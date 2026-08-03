---
id: CH-06
kind: chapter
title: API and Backend Engineering Audit
purpose: Build and assess backend services whose contracts, authorization, mutations, and operational failures are safe and observable.
audience: [Backend engineers, API owners, security engineers, SREs, QA engineers]
scope: HTTP and event contracts, identity, tenancy, validation, idempotency, data handling, observability, and recovery.
applicability: Public APIs, internal service APIs, webhooks, and asynchronous workers.
owners: [API owner, security owner, service owner]
inputs: [API inventory, schemas, authorization model, data classification, production-safe fixtures]
outputs: [contract matrix, authorization evidence, findings, service release gate]
dependencies: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023, NIST-SSDF-1.1]
standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023, NIST-SSDF-1.1]
---

# API and Backend Engineering Audit

## Purpose, audience, scope, and applicability

Treat each endpoint, event, and worker as a durable contract: callers need documented inputs, authorization, outcomes, failure semantics, and recovery. Apply this chapter to service-to-service interfaces as well as customer APIs; an internal endpoint is not exempt from tenant, authorization, or audit duties.

## Concepts and engineering principles

Validate at the boundary, authorize the requested resource, and make every state mutation idempotent or safely detectable. Version contracts deliberately, return stable problem shapes, and never use a client-supplied tenant identifier as the authorization decision. Logs must help reconstruct an outcome without recording credentials, secrets, or regulated payloads.

## Roles and accountability

The API owner owns contract compatibility and deprecation. The service owner owns implementation, capacity, and recovery. The security owner approves authorization and sensitive-data controls. The data owner classifies fields; the release owner accepts evidence and blocks unsafe changes.

## Prerequisites and required inputs

Collect the route/event inventory, OpenAPI or equivalent schemas, consumers, identity claims, tenant model, classifications, rate limits, error catalog, dependency map, dashboards, alerts, and deterministic fixtures. Identify every mutation and its retry, deduplication, and compensating-action policy.

## Standard operating procedure

1. Map methods, schemas, consumers, data classes, owners, and deprecation dates.
2. Exercise valid, malformed, unauthorized, cross-tenant, duplicate, delayed, and dependency-failure requests using non-production identities.
3. Verify authorization against the resolved resource and tenant, not UI state or an untrusted request header.
4. Parse success and problem responses against schemas; test pagination, limits, filtering, and field-level exposure.
5. Replay mutations with the same idempotency key and prove one business effect.
6. Review rate limits, timeouts, retries, circuit behavior, audit events, and redaction under load appropriate to the service tier.
7. Record evidence, severity, owner, remediation, and re-test result.

## Worked example

[Product Atlas API contract evidence](../examples/api-contracts/README.md) models `POST /v1/transfers`. It rejects an account from another tenant even if the caller changes `X-Tenant`, and it returns the same transfer for a repeated idempotency key instead of charging twice.

## Automation examples

```typescript
const first = await request.post('/v1/transfers', { headers: { Authorization: 'Bearer atlas-a', 'Idempotency-Key': 'pay-104' }, data: { account_id: 'acct-a', cents: 5000 } });
const replay = await request.post('/v1/transfers', { headers: { Authorization: 'Bearer atlas-a', 'Idempotency-Key': 'pay-104' }, data: { account_id: 'acct-a', cents: 5000 } });
expect(replay.json().transfer_id).toBe(first.json().transfer_id);
```

## Audit prompts

Use [Opus](../prompts/opus/ch06-api-contract-analysis.md), [Sonnet](../prompts/sonnet/ch06-api-authorz-review.md), and [Haiku](../prompts/haiku/ch06-api-inventory.md) for contract analysis, authorization evidence review, and route normalization.

## Workflow checklist

Run [CL-API-01](../checklists/api-backend.md) before changing a route, schema, identity claim, mutation, or service dependency.

## Evidence requirements and retention guidance

Retain schema versions, sanitized request/response pairs, principal and tenant fixture identities, trace IDs, service revision, test results, alert links, and retest evidence. Store hashes or approved redacted captures for sensitive data.

## Example findings with severity and remediation

**Critical — API-ATLAS-01.** `GET /v1/accounts/{id}` checked a valid session but not ownership of `{id}`. Remediation: enforce tenant-scoped resource lookup, add cross-tenant fixtures, rotate exposed audit exports, and verify no cached response bypasses the corrected policy.

## KPIs and domain scorecard

The [API KPI catalog](../scorecards/api-kpis.md) measures contract coverage, cross-tenant denial coverage, mutation replay safety, and operational error budget. A high aggregate does not offset an exploitable authorization gap.

## Common failure patterns and diagnostic guidance

- A gateway authenticates but a downstream service trusts a forged tenant header.
- A retry policy repeats a payment because the idempotency store is not shared.
- A `200` response carries a business failure that callers cannot distinguish.
- Logs contain authorization tokens while troubleshooting a dependency timeout.

## Exit criteria

Exit when every exposed contract has schema and owner evidence, resource-level authorization and cross-tenant denials are tested, mutations are recoverable, and blocking security or reliability findings are resolved or time-bounded.

## Related runbooks, controls, examples, and templates

Use the API checklist, finding, threat-model, verification-plan, and release-decision templates. Pair this chapter with the database migration and incident runbooks for data-changing service releases.
