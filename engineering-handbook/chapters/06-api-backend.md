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

The audit answers one question per contract: can an authorized caller produce an expected outcome, can every other caller be denied, and can an operator reconstruct what happened after a failure? Trigger it before any route, schema, identity-claim, mutation, or dependency change, and re-run it on a declared cadence for externally visible APIs. The release gate is a set of evidence records, not a code-review sign-off: every conclusion must name the fixture, trace, or schema that supports it.

## Concepts and engineering principles

Validate at the boundary, authorize the requested resource, and make every state mutation idempotent or safely detectable. Version contracts deliberately, return stable problem shapes, and never use a client-supplied tenant identifier as the authorization decision. Logs must help reconstruct an outcome without recording credentials, secrets, or regulated payloads.

Three principles govern the decisions in this chapter. First, the caller-visible contract and the internal implementation are separate: internals can change without breaking callers only when the schema, error shape, pagination, and idempotency semantics are versioned and tested. Second, authorization is evaluated against the resolved resource and the authenticated principal, never against UI state, a header, or any value a caller controls. Third, a mutation is not complete until its effect, retry, and compensation paths are all specified; a passing happy path is not an idempotency contract.

The table below is the core decision model for boundary checks. It applies to every endpoint, event consumer, and worker:

| Question asked of a request | Where the answer must come from | If the check is missing |
| --- | --- | --- |
| Who is the caller? | Verified principal claims from the session or service identity | Any caller reaches protected logic |
| Which tenant or scope is requested? | Resolved resource ownership and tenancy, not a caller-supplied header | Cross-tenant read or write |
| Is the caller allowed this action? | Policy evaluated on the resolved resource and action | Privilege escalation or data exposure |
| Is the request shape valid? | Schema validation before any side effect | Injection, type confusion, field abuse |
| Is this a retry? | Idempotency key store shared with the mutation path | Duplicate business effects |
| Is the caller within its limits? | Rate and quota state tied to principal, not IP alone | Abuse, cost spikes, availability risk |

## Roles and accountability

The API owner owns contract compatibility and deprecation. The service owner owns implementation, capacity, and recovery. The security owner approves authorization and sensitive-data controls. The data owner classifies fields; the release owner accepts evidence and blocks unsafe changes.

| Role | Owns | Accountable artifacts | Escalates when |
| --- | --- | --- | --- |
| API owner | Contract, versioning, deprecation | Schema, changelog, compatibility evidence | A change breaks a consumer contract |
| Service owner | Implementation, capacity, recovery | Load results, runbooks, idempotency tests | A mutation can duplicate or lose effects |
| Security owner | Authorization, sensitive-data controls | Authorization matrix, redaction policy | A cross-tenant or exposure finding opens |
| Data owner | Field classification, retention | Data-classification map | Regulated data enters an unapproved path |
| Release owner | Gate and evidence acceptance | Release decision, exception records | Evidence is missing for a blocking finding |

## Prerequisites and required inputs

Collect the route/event inventory, OpenAPI or equivalent schemas, consumers, identity claims, tenant model, classifications, rate limits, error catalog, dependency map, dashboards, alerts, and deterministic fixtures. Identify every mutation and its retry, deduplication, and compensating-action policy.

| Input | What it must contain | Refreshed |
| --- | --- | --- |
| Route/event inventory | Every endpoint, worker, and webhook with owner and deprecation state | At every contract change |
| Schemas | Request/response shapes, required fields, enums, limits | Before each audit |
| Identity and tenant model | Claims, roles, tenancy rules, service identities | When identity changes |
| Error catalog | Status codes, problem shapes, retry semantics per error | When failure behavior changes |
| Rate and quota policy | Limits per principal, burst tolerance, over-limit behavior | When limits change |
| Dependency map | Timeouts, retries, circuit breakers per dependency | When topology changes |
| Fixtures | Non-production identities and tenants with deterministic data | Versioned per audit |

Fixtures must be production-safe: they should be unable to contact production systems or issue real financial, notification, or destructive actions. Redact tokens and regulated fields from every captured artifact before it enters the evidence package.

## Standard operating procedure

1. Map methods, schemas, consumers, data classes, owners, and deprecation dates.
2. Exercise valid, malformed, unauthorized, cross-tenant, duplicate, delayed, and dependency-failure requests using non-production identities.
3. Verify authorization against the resolved resource and tenant, not UI state or an untrusted request header.
4. Parse success and problem responses against schemas; test pagination, limits, filtering, and field-level exposure.
5. Replay mutations with the same idempotency key and prove one business effect.
6. Review rate limits, timeouts, retries, circuit behavior, audit events, and redaction under load appropriate to the service tier.
7. Record evidence, severity, owner, remediation, and re-test result.

Steps 8 through 10 extend the procedure for release-grade evidence:

8. Diff the changed contract against the previous published version and list every breaking change, its consumers, and its deprecation plan (owner: API owner; threshold: no undocumented breaking change).
9. Verify the error contract: every expected failure returns a documented, schema-valid problem shape (owner: service owner; threshold: 100 percent of exercised failure fixtures).
10. Confirm the evidence package names a source revision, fixture version, trace IDs, and re-test results, and that every blocking finding is resolved or time-bounded (owner: release owner; threshold: gate closes only when complete).

| SOP step | Owner | Pass threshold | Timeline |
| --- | --- | --- | --- |
| 1 Inventory | API owner | No route without owner, schema, deprecation state | At audit start |
| 2 Negative and boundary cases | Service owner | All fixtures executed and recorded | 2 working days |
| 3 Resource authorization | Security owner | Cross-tenant and role-denied fixtures pass | 2 working days |
| 4 Schema and problem parsing | Service owner | Success and failure responses match schemas | 2 working days |
| 5 Idempotent replay | Service owner | One business effect per key | 2 working days |
| 6 Limits and observability | SRE owner | Limits hold and telemetry redacts | Before gate |
| 7 Evidence recording | Service owner | Trace IDs and retest results linked | Before gate |
| 8 Contract diff | API owner | Breaking changes documented and approved | Before gate |
| 9 Error contract | Service owner | All failure fixtures pass | Before gate |
| 10 Gate closure | Release owner | Evidence complete or exceptions time-bounded | Gate day |

## Worked example

[Product Atlas API contract evidence](../examples/api-contracts/README.md) models `POST /v1/transfers`. It rejects an account from another tenant even if the caller changes `X-Tenant`, and it returns the same transfer for a repeated idempotency key instead of charging twice.

Walk the example as a reviewer rather than as a test author:

| Step | Action | Expected evidence | Observed evidence and pass check |
| --- | --- | --- | --- |
| 1 | Submit a valid tenant-a transfer with key `pay-104` | `201` with transfer `tr-104`, one ledger entry | Response schema parses; ledger count is exactly one |
| 2 | Read `acct-b` with the tenant-a token | `404` or documented `403`, no account fields | No `acct-b` field appears in the response body |
| 3 | Replay `pay-104` with the same body | Original `tr-104`, no second ledger entry | Transfer ID matches the first response; ledger count unchanged |
| 4 | Replay `pay-104` with changed cents | Documented conflict, no mutation | A stable problem shape names the conflict reason |
| 5 | Retry after an induced timeout | Status query returns `tr-104`; no duplicate | The recovery path returns the accepted result, not a retry error |
| 6 | Inspect captured evidence | Sanitized requests, trace IDs, schema version | No authorization header or account number in evidence |

Each row passes only when the observed evidence matches the expected column. A failing row becomes a finding with the fixture identity and trace ID attached.

## Automation examples

```typescript
const first = await request.post('/v1/transfers', { headers: { Authorization: 'Bearer atlas-a', 'Idempotency-Key': 'pay-104' }, data: { account_id: 'acct-a', cents: 5000 } });
const replay = await request.post('/v1/transfers', { headers: { Authorization: 'Bearer atlas-a', 'Idempotency-Key': 'pay-104' }, data: { account_id: 'acct-a', cents: 5000 } });
expect(replay.json().transfer_id).toBe(first.json().transfer_id);
```

Automation should also assert the negative cases the replay test does not cover. A companion check parses every failure response against the documented problem schema:

```python
for fixture in failure_fixtures:
    response = client.post("/v1/transfers", **fixture.request)
    assert response.status_code == fixture.expected_status
    assert problem_schema.validate(response.json()) is None
```

Failure interpretation: a fixture that returns `500` where the contract declares a client error, or a success body missing a required field, is a contract failure and blocks release regardless of the happy-path result. Keep the fixture set deterministic, offline, and tied to the source revision.

> Application note (Cutctx): the token-compression proxy exposes API surface for its own audit in the same shape — routing endpoints, authentication, and retry semantics are contracts like any other. Apply this chapter's boundary and replay checks to its control-plane API; product-specific results stay in repository evidence rather than in this manual.

## Audit prompts

Use [Opus](../prompts/opus/ch06-api-contract-analysis.md), [Sonnet](../prompts/sonnet/ch06-api-authorz-review.md), and [Haiku](../prompts/haiku/ch06-api-inventory.md) for contract analysis, authorization evidence review, and route normalization.

The three prompts divide the work by scope, not importance. The Haiku prompt normalizes the route and mutation inventory into a reviewable matrix. The Sonnet prompt reviews one authorization decision against its evidence, including cross-tenant and role-denied fixtures. The Opus prompt synthesizes the contract matrix, authorization results, and operational signals into a prioritized cross-system risk assessment. Treat their outputs as working material only; every claim must trace to a source link or fixture before it can be entered as evidence.

## Workflow checklist

Run [CL-API-01](../checklists/api-backend.md) before changing a route, schema, identity claim, mutation, or service dependency.

Select controls by what the change touches:

| Change | Primary controls | Also review |
| --- | --- | --- |
| New or changed route | `ENG-API-001`, `ENG-API-003` | `ENG-API-005` |
| Mutation or retry change | `ENG-API-002` | `ENG-API-004` |
| Rate limit or quota change | `ENG-API-004` | `ENG-API-005` |
| Error or problem-shape change | `ENG-API-005` | `ENG-API-003` |
| Any release | All five controls | Evidence requirements below |

## Evidence requirements and retention guidance

Retain schema versions, sanitized request/response pairs, principal and tenant fixture identities, trace IDs, service revision, test results, alert links, and retest evidence. Store hashes or approved redacted captures for sensitive data.

| Evidence item | Purpose | Retention | Redaction |
| --- | --- | --- | --- |
| Schema version and diff | Reconstruct the contract at test time | Life of the API version | None |
| Sanitized request/response pairs | Reproduce the outcome | 13 months or legal minimum | Tokens, account numbers, regulated fields |
| Fixture principal/tenant identities | Prove who and what was tested | As long as the finding is open | No real credentials |
| Trace IDs and alert links | Connect evidence to operations | 13 months | None |
| Test results and re-test | Prove remediation | Life of the finding | Payload content |
| Release decision and exceptions | Explain gate closure | Permanent | None |

Retain hashes instead of raw sensitive payloads wherever a hash is sufficient to prove a control.

## Example findings with severity and remediation

**Critical — API-ATLAS-01.** `GET /v1/accounts/{id}` checked a valid session but not ownership of `{id}`. Remediation: enforce tenant-scoped resource lookup, add cross-tenant fixtures, rotate exposed audit exports, and verify no cached response bypasses the corrected policy.

**High — API-ATLAS-02.** `POST /v1/transfers` returned `200` with a business-failure body that no schema documented, so callers could not distinguish a rejected transfer from a completed one. Remediation: define the problem shape, return the documented status, and add a fixture asserting every failure type.

**Medium — API-ATLAS-03.** Rate limits were enforced per instance, so a distributed burst bypassed the quota for a finance tenant. Remediation: centralize or coordinate limit state, document the tolerated skew, and add a multi-instance quota fixture.

## KPIs and domain scorecard

The [API KPI catalog](../scorecards/api-kpis.md) measures contract coverage, cross-tenant denial coverage, mutation replay safety, and operational error budget. A high aggregate does not offset an exploitable authorization gap.

| KPI | Measures | Release rule |
| --- | --- | --- |
| `KPI-API-001` | Protected-route authorization coverage | Any untested protected route blocks release |
| `KPI-API-002` | Mutation replay safety | A duplicate charge or provisioning event blocks release |
| `KPI-API-003` | Contract and error-shape coverage | An undocumented or schema-invalid response blocks release |

Read the scorecard as a veto set, not a weighted average: the authorization and replay indicators are binary release gates, and the operational error budget adds context on live behavior.

## Common failure patterns and diagnostic guidance

- A gateway authenticates but a downstream service trusts a forged tenant header.
- A retry policy repeats a payment because the idempotency store is not shared.
- A `200` response carries a business failure that callers cannot distinguish.
- Logs contain authorization tokens while troubleshooting a dependency timeout.

| Symptom | Likely cause | Check | Fix |
| --- | --- | --- | --- |
| Caller reads another tenant's object | Resource lookup not tenant-scoped | Cross-tenant fixture with a valid session | Scope lookup to the resolved principal tenant; add regression fixture |
| Duplicate charge after retry | Idempotency store not shared, or key persisted after the side effect | Replay after an induced timeout on each replica | Persist key and result atomically before the side effect |
| `200` with a business failure | Error contract undocumented | Parse failures against the problem schema | Define problem shapes; return documented statuses |
| Gateway passes forged `X-Tenant` downstream | Downstream trusts a caller-controlled header | Inspect header origin at each hop | Strip or overwrite untrusted headers at the boundary |
| Quota bypass under burst | Per-instance limit state | Multi-instance burst fixture | Coordinate limit state or document tolerated skew |
| Logs contain tokens | Naive request logging | Scan evidence and log samples | Redact at capture, not at export |

## Exit criteria

Exit when every exposed contract has schema and owner evidence, resource-level authorization and cross-tenant denials are tested, mutations are recoverable, and blocking security or reliability findings are resolved or time-bounded.

| Criterion | Evidence required | Owner | Status |
| --- | --- | --- | --- |
| Every contract has schema and owner | Inventory rows with links | API owner | Open/Pass |
| Resource authorization tested | Cross-tenant and role-denied fixtures | Security owner | Open/Pass |
| Mutations recoverable | Idempotency replay evidence | Service owner | Open/Pass |
| Error contract documented | Problem schema and failure fixtures | Service owner | Open/Pass |
| Blocking findings resolved | Re-test results or time-bounded exception | Release owner | Open/Pass |

## Related runbooks, controls, examples, and templates

Use the API checklist, finding, threat-model, verification-plan, and release-decision templates. Pair this chapter with the database migration and incident runbooks for data-changing service releases.

Choose the asset by situation: the API checklist gates any contract or mutation change; the threat-model template drives a first review of a new surface; the verification-plan template turns findings into testable tasks; the migration runbook applies when a schema change accompanies the release; and the incident runbook applies when a live exposure or outage is suspected.
