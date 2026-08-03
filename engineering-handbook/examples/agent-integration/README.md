---
id: EX-CH07-INTEGRATION
kind: worked-example
chapter: CH-07
standards: [OWASP-ASVS-5.0.0, OWASP-API-TOP10-2023, NIST-SSDF-1.1]
preconditions: [local expense-provider webhook fixture, Atlas finance approval fixture, isolated tenant identity]
placement: engineering-handbook/examples/agent-integration
dependencies: [local callback fixture, signature helper, audit-record store]
invocation: Submit valid, altered-body, replayed-event, revoked-consent, and approval-required expense-export events.
expected_output: Valid signed event creates a preview only; altered/replayed event is rejected; delivery waits for named finance approval.
failure_output: Altered body is accepted, duplicate event triggers another delivery, or agent dispatches without approval.
interpretation: Any unverified or unapproved high-impact action is a blocking authority-boundary failure.
remediation: Verify original-body signature, scope replay keys by tenant/environment, and enforce approval token at execution boundary.
cleanup: Delete fixture export, revoke fixture consent, and retain sanitized audit record only.
---

# Product Atlas agent integration evidence

Atlas Expense receives provider callbacks and exposes an export tool. A valid
callback prepares a CSV preview; it cannot deliver funds or export until finance
approves a named preview. The evidence packet records provider environment,
tenant, event ID, signature verdict, tool schema version, approval ID, and
correlation ID without storing tokens or raw expense payloads.

## Executable fixture

Run the deterministic integration fixture with the handbook example runner
(`python3 automation/check_examples.py engineering-handbook`) or directly from
this directory:

```shell
python3 agent_integration_fixture.py
```

The fixture recomputes the tenant HMAC over the canonical JSON body, replays a
processed event, mutates the body, and attempts an execution without an
approval token. Expected output on stdout, exactly:

```text
AGENT_INTEGRATION_FIXTURE_PASS hmac-verified altered-rejected replay-rejected authority-boundary-enforced
```

The fixture is pure standard library with in-memory secrets and a replay ledger;
it makes no network calls. Failure interpretation: a non-zero exit means an
altered body passed verification, a replayed event caused a second delivery, or
an agent executed an export without the finance approval token. Cleanup: the
fixture creates no files or external resources, so no cleanup step is required.
