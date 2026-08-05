---
id: EX-CH16-MIGRATION-README
kind: worked-example
chapter: CH-16
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, NIST-IR-800-61R3]
preconditions: [isolated Product Atlas fixture, approved migration plan, tenant-scoped backup verification]
placement: engineering-handbook/examples/migrations
dependencies: [Python 3 standard library]
invocation: Run python3 migration_fixture.py from this directory or use the handbook example runner from the handbook root.
expected_output: The Atlas A name expansion resumes after interruption exactly once, Atlas B stays unchanged, and contract validation blocks removal until the backfill is complete.
failure_output: Missing expanded data, a cross-tenant write, duplicate mutation after resume, or contract removal before validation fails the fixture.
interpretation: Recovery correctness requires a durable progress boundary and a tenant-scoped reconciliation result, not simply a successful process restart.
remediation: Restore from the approved backup when integrity fails; otherwise repair the checkpoint or transform, reconcile every affected tenant, and repeat expand, backfill, and contract validation.
cleanup: The fixture is in memory and creates no database, network traffic, credentials, or customer data.
---

# Product Atlas resumable name migration

Atlas introduces `display_name` without breaking readers of the existing name fields. The fixture expands the schema compatibly, simulates an interruption after an acknowledged boundary, resumes from a durable checkpoint, confirms Atlas B remains untouched, and verifies a repeat resume causes no further write.

Run `python3 migration_fixture.py`. Expected evidence is:

```text
MIGRATION_FIXTURE_PASS expand-compatible resumed-once tenant-isolated contract-safe
```

Production evidence adds the approved migration record, backup-restore result, checksum or row-count reconciliation, query-plan review, change window, feature-flag state, alert links, and accountable rollback decision.
