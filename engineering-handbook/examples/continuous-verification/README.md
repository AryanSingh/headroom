---
id: EX-CH20-CONTINUOUS-VERIFICATION-README
kind: worked-example
chapter: CH-20
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
preconditions: [isolated Product Atlas fixture, approved verification policy, named release owner]
placement: engineering-handbook/examples/continuous-verification
dependencies: [Python 3 standard library]
invocation: Run python3 verification_fixture.py from this directory or use the handbook example runner from the handbook root.
expected_output: A failed reconciliation check blocks promotion until an evidence reference exists; after the check passes, the promotion decision is approved.
failure_output: An assertion failure means the gate could approve a failed check, omit evidence, or fail to make the decision deterministic.
interpretation: A passing pipeline does not prove promotion readiness unless every required check and its evidence are resolved under the declared policy.
remediation: Correct the gate policy or evidence binding, rerun the fixture, and attach the resulting record to the release decision.
cleanup: The fixture is in memory and creates no network traffic, credentials, services, or customer data.
---

# Product Atlas continuous-verification release gate

Product Atlas runs unit, security, migration-reconciliation, and deployment checks as named release evidence. This fixture makes reconciliation fail, proves the release stays blocked, requires an evidence reference for that failed signal, then passes the signal and approves the deterministic decision.

Run `python3 verification_fixture.py`. Expected evidence is:

```text
CONTINUOUS_VERIFICATION_FIXTURE_PASS failed-check-blocked evidence-linked promotion-approved
```

Production evidence adds immutable build and source identifiers, signed artifact provenance, check configuration versions, check output references, waiver records, approver identity, change window, deployment and rollback telemetry, and a retained release decision.
