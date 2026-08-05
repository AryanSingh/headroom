---
id: EX-CH10-RELIABILITY
kind: worked-example
chapter: CH-10
standards: [NIST-SSDF-1.1, OTEL-SEMCONV-1.43.0, OWASP-ASVS-5.0.0]
preconditions: [isolated Atlas staging tenant fixtures, versioned traffic profile, simulated datastore failover, validated backup snapshot]
placement: engineering-handbook/examples/reliability-performance
dependencies: [local load generator, Atlas invoice API fixture, telemetry collector, recovery-evidence store]
invocation: Run the baseline, burst, slow-datastore, worker-restart, and restore fixtures against the isolated Atlas invoice service.
expected_output: The API queues safely after its dependency latency budget, produces no duplicate invoice, emits correlated telemetry, and restores the fixture with integrity verification.
failure_output: The service accepts duplicate work, drops tenant scope, silently loses queued invoices, exposes request content in telemetry, or restores data without integrity evidence.
interpretation: Availability evidence is acceptable only when the business outcome, error behavior, and recovery evidence meet their declared envelope.
remediation: Persist idempotency state before acknowledgement, cap retry work by caller deadline, add queue backpressure, redact telemetry, and rehearse restore until integrity checks pass.
cleanup: Delete generated staging invoices, reset queues and fault injection, and remove sanitized fixture telemetry according to the test retention rule.
---

# Product Atlas load and recovery evidence

Atlas invoices arrive in bursts at month end. The service accepts a tenant-scoped request only once for an idempotency key, queues work if the primary store exceeds the dependency-latency budget, and makes the result traceable without recording invoice content in telemetry.

| Fixture | Conditions | Expected business result | Required evidence |
| --- | --- | --- | --- |
| Baseline | 80 requests/second, warm cache | Invoice accepted once | p95 latency, trace ID, outcome counter |
| Burst | 600 requests/second for 120 seconds | Bounded queue, no dropped accepted request | queue depth, shedding reason, tenant distribution |
| Slow primary | 1,500 ms datastore latency | Request queues before caller deadline; no duplicate retry | timeout trace, idempotency record, reason code |
| Worker restart | Restart after acknowledgement loss | Exactly one invoice exists | replay record and duplicate-outcome query |
| Restore | Restore a bounded backup fixture | Tenant data and invoice relationships validate | recovery time, recovery point, integrity report |

The release owner compares the observed p95/p99 distributions and accepted-outcome count with the documented service objective. If a slow primary causes a caller-visible error, the evidence must show that no later retry created a second invoice. If the restore succeeds by row count but fails referential-integrity or tenant-access verification, it is a failed recovery exercise.

**Product Atlas result.** During the slow-primary fixture, `load-fixture-0042` received `queued` with reason `dependency-latency-budget-exceeded`. After restart, one invoice and one idempotency record existed. The restore completed in 18 minutes from a snapshot 11 minutes old; integrity and tenant-scope checks passed. The remaining capacity action is to reduce the 600-request burst queue from 9,000 to 6,000 jobs before the next month-end release.
