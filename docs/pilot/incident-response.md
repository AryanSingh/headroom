# Pilot Incident Response

## 1. Assign ownership

Record the incident owner, customer communication owner, severity, start time,
affected users, and affected deployment.

## 2. Containment

- Revoke or rotate exposed Cutctx and provider credentials.
- Disable model routing or compression when either feature may alter request
  correctness.
- Route the customer directly to the provider when the approved bypass is
  safer than continued proxy use.
- Stop writes before handling suspected state corruption.

## 3. Evidence

Capture version and image digest, health output, request IDs, redacted logs,
metrics, recent deploy events, storage integrity results, and the exact recovery
commands used. Preserve timestamps in UTC.

## 4. Recovery

Use the backup-restore or upgrade-rollback runbook. Verify `/livez`, `/readyz`,
license status, one OpenAI request, and one Anthropic request before reopening
traffic.

## 5. Customer communication

State the impact, containment action, current service state, next update time,
and any customer action. Do not speculate about root cause before evidence
supports it.

## 6. Closure

Document root cause, corrective action, regression test, customer confirmation,
and the owner and due date for each remaining risk.

