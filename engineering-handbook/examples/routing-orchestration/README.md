---
id: EX-CH08-ROUTING
kind: worked-example
chapter: CH-08
standards: [NIST-SSDF-1.1, NIST-AI-RMF-1.0, OWASP-ASVS-5.0.0]
preconditions: [Atlas EU tenant fixture, versioned routing policy, simulated preferred-provider outage]
placement: engineering-handbook/examples/routing-orchestration
dependencies: [local route evaluator, deterministic provider fixtures]
invocation: Evaluate EU invoice extraction with capacity available, budget exhaustion, and preferred-provider timeout.
expected_output: Approved EU route is selected when available; budget exhaustion queues work; outage never selects a disallowed region.
failure_output: A fallback selects a US-only provider, loses tenant scope, or changes a finance action from review to execute.
interpretation: Boundary-preserving queueing is safer than an unapproved fallback; each result must name its policy revision and reason code.
remediation: Add non-negotiable predicates to the policy evaluator, remove hidden defaults, and add regression fixtures.
cleanup: Remove fixture traces and reset the local provider simulator.
---

# Product Atlas routing evidence

Atlas classifies invoice extraction as `restricted-eu`, permits `eu-fast-v2` and `eu-accurate-v1`, and never permits `us-general-v3`. When `eu-fast-v2` is unavailable, `eu-accurate-v1` may be selected only if its latency budget remains acceptable; otherwise Atlas queues the job.

| Fixture | Expected decision | Required evidence |
| --- | --- | --- |
| Normal capacity | `eu-fast-v2`, reason `policy-match` | policy `2026.08.1`, tenant, correlation ID |
| Standard budget exhausted | queue, reason `budget-held` | budget snapshot and non-mutating job ID |
| Preferred provider timeout | `eu-accurate-v1` or queue | residency predicate and timeout trace |
| EU capacity absent | queue, reason `eu-approved-capacity-unavailable` | denied-provider list excludes US route |

The release evidence includes a route decision record per fixture and a rollback proof that disables `eu-fast-v2` without changing the allowlist.

## Executable fixture

Run the deterministic routing policy fixture with the handbook example runner
(`python3 automation/check_examples.py engineering-handbook`) or directly from
this directory:

```shell
python3 routing_orchestration_fixture.py
```

The fixture resolves a restricted-EU job under policy revision `2026.08.1`
across four scenarios: preferred provider available, preferred provider timed
out with an in-bound fallback, fallback over the cost budget, and no approved
capacity at all. Expected output on stdout, exactly:

```text
ROUTING_FIXTURE_PASS policy-match latency-bounded-fallback budget-held-fail-closed
```

The fixture is pure standard library with deterministic in-memory providers; it
makes no network calls. Failure interpretation: a non-zero exit means a fallback
selected a disallowed region, a route exceeded its cost or latency bound, or a
job executed instead of queueing when no approved provider fit. Cleanup: the
fixture creates no files or external resources, so no cleanup step is required.
