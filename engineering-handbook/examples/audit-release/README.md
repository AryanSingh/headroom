---
id: EX-CH01-API-RELEASE
kind: worked-example
chapter: CH-01
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
preconditions: [Atlas Billing API fixture, seeded tenants alpha and beta, clean checkout]
placement: engineering-handbook/examples/audit-release
dependencies: [Python 3.12, pytest, local fixture database]
invocation: rtk pytest tests/contracts/test_invoice_scope.py -q
expected_output: 1 passed; the beta tenant receives a 404 or 403 for alpha invoice inv_0142.
failure_output: AssertionError; response status 200 with invoice inv_0142 for beta tenant.
interpretation: A 200 response is cross-tenant data exposure and blocks release approval.
remediation: Add tenant_id to the repository predicate, add the negative contract test, and retest on the release revision.
cleanup: Drop the local fixture database and remove generated reports.
---

# API release audit example: Atlas Billing 2026.4.0

## Scenario

Atlas Billing introduces an invoice-detail endpoint. The audit asks whether the
endpoint enforces tenant isolation for authenticated sessions. The fixture has
two tenants: `alpha` owns invoice `inv_0142`; `beta` must not read it.

## Procedure

1. Seed alpha, beta, and `inv_0142` in the local fixture database.
2. Obtain a fixture session for beta only; no production credentials are used.
3. Request `GET /v1/invoices/inv_0142` with beta’s session.
4. Save request headers with the token redacted, response status, test output,
   source revision, and database fixture checksum in the evidence register.
5. If the response is `200`, open Important finding `AUTHZ-ATLAS-02`, stop the
   release decision, and route remediation to the API owner.
6. Apply the repository predicate and add a regression test. Re-run both the
   negative case and a positive alpha-owner case.

## Expected evidence packet

The clean packet contains the audit brief, command, test output, fixture
checksum, source revision, review timestamp, finding disposition, and retest
output. The remediation is accepted only if beta no longer receives invoice
data while alpha’s legitimate request still succeeds.
