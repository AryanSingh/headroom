---
id: EX-CH15-CHAOS-README
kind: worked-example
chapter: CH-15
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
preconditions: [isolated Product Atlas fixture, approved queue-partition hypothesis, abort threshold of 30 seconds]
placement: engineering-handbook/examples/chaos
dependencies: [Python 3 standard library]
invocation: Run python3 chaos_fixture.py from this directory or the handbook example runner from the handbook root.
expected_output: The accepted Atlas invoice queues once, recovers once for its original tenant, and remains below the abort threshold.
failure_output: A duplicate outcome, missing accepted invoice, wrong tenant, or queue age at or above the abort threshold fails the fixture.
interpretation: A worker outage is acceptable only when durable acknowledgement, tenant scope, and recovery correctness remain evidenced.
remediation: Persist idempotency before acknowledgement, cap queue age, supply a visible delay state, and rerun the isolated experiment.
cleanup: The fixture is in-memory and creates no external resources, network traffic, credentials, or customer data.
---

# Product Atlas bounded queue-partition experiment

Atlas injects a worker partition after one tenant-scoped invoice has been durably accepted. The hypothesis is that the invoice is queued once, the abort threshold remains armed, and recovery produces exactly one outcome for `atlas-a`.

Run `python3 chaos_fixture.py`. The fixture uses only the Python standard library and returns deterministic evidence:

```text
CHAOS_FIXTURE_PASS queued-once recovered-once abort-threshold-armed
```

In a deployed experiment, attach the scoped queue-age metric, idempotency-ledger query, trace ID, abort decision, and recovery timestamp to the evidence register.
