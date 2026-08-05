---
id: EX-CH06-API-CONTRACTS
kind: worked-example
chapter: CH-06
standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023, NIST-SSDF-1.1]
preconditions: [Atlas transfer fixture service, tenant-a and tenant-b test principals, empty idempotency store]
placement: engineering-handbook/examples/api-contracts
dependencies: [local API fixture, contract test runner]
invocation: Submit valid, cross-tenant, duplicate-key, malformed, and dependency-timeout transfer requests.
expected_output: A valid tenant-a transfer is created once; cross-tenant access is denied; malformed input is rejected with a stable problem record.
failure_output: A client-controlled tenant header selects another account or a duplicate key creates another transfer.
interpretation: Cross-tenant access is critical; duplicate mutation is a release blocker.
remediation: Scope resource lookup to authenticated tenant, share idempotency state, and add regression fixtures.
cleanup: Delete fixture records and sanitized request captures after the test run.
---

# Product Atlas API contract evidence

Atlas exposes `POST /v1/transfers` for an authenticated finance operator. The
service derives the tenant from the signed principal, not `X-Tenant`, and stores
the idempotency key with tenant, principal, request hash, and transfer result.

| Case | Fixture request | Expected result |
| --- | --- | --- |
| Valid transfer | tenant-a token, `acct-a`, key `pay-104` | `201`, transfer `tr-104`, one ledger entry |
| Cross-tenant read | tenant-a token, `acct-b` | `404` or documented `403`, no account fields |
| Duplicate replay | same body and `pay-104` | original `tr-104`, no second ledger entry |
| Same key, changed body | key `pay-104`, different cents | documented conflict, no mutation |
| Timeout after accept | retry `pay-104` | status query returns `tr-104`; no duplicate |

The evidence record stores status, schema version, trace ID, redacted principal,
and ledger count. It deliberately excludes authorization headers and account
numbers. A successful happy path alone is insufficient evidence.

## Executable fixture

Run the deterministic contract fixture with the handbook example runner
(`python3 automation/check_examples.py engineering-handbook`) or directly from
this directory:

```shell
python3 api_contracts_fixture.py
```

Expected output on stdout, exactly:

```text
API_CONTRACTS_FIXTURE_PASS tenant-scoped idempotent-conflict malformed-rejected
```

The fixture uses only the Python standard library with in-memory state and
makes no network calls. Failure interpretation: a non-zero exit or assertion
failure means a contract case regressed — cross-tenant access, a duplicate
mutation, an accepted malformed request, or a silently changed idempotency
conflict. Cleanup: the fixture creates no files, credentials, or external
resources, so no cleanup step is required.
