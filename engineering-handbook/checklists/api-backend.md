---
id: CL-API-01
kind: checklist
title: API and backend release checklist
chapter: CH-06
controls:
  - id: ENG-API-001
    requirement: Every protected API resource is authorized against the resolved resource and tenant.
    applicability: required for every authenticated route and worker-triggered mutation
    procedure: Run same-tenant, cross-tenant, absent-identity, and insufficient-role fixture cases.
    expected_result: Only explicitly authorized principals can read or mutate the requested resource.
    evidence: Sanitized test report, principal fixture, trace ID, and source revision.
    automation: authorization contract suite
    owner: API owner
    frequency: every route or policy change
    failure_action: block release and investigate affected access records
    standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023]
  - id: ENG-API-002
    requirement: Retried state mutations have a tested idempotency and recovery contract.
    applicability: required for payment, provisioning, deletion, and other externally visible mutations
    procedure: Submit the same accepted request and idempotency key concurrently and after an induced timeout.
    expected_result: One business effect occurs and the caller can retrieve its resulting state.
    evidence: Replay test output, mutation audit record, and recovery procedure.
    automation: idempotency replay suite
    owner: Service owner
    frequency: every mutation change
    failure_action: block deployment until duplicate effects are impossible or compensated
    standards: [NIST-SSDF-1.1]
---

# API and backend release checklist

- [ ] Inventory routes, consumers, owners, data classes, and deprecation commitments.
- [ ] Validate schemas and stable problem responses for valid and invalid requests.
- [ ] Prove resource-level authorization and cross-tenant denial with fixture identities.
- [ ] Replay mutations and document timeout, retry, and recovery behavior.
- [ ] Confirm rate limits, timeouts, audit events, logs, and traces redact sensitive fields.
