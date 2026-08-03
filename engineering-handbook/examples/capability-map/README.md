---
id: EX-CH02-CAPABILITY-MAP
kind: worked-example
chapter: CH-02
standards: [NIST-SSDF-1.1, OWASP-SAMM-2.1]
preconditions: [Atlas Subscription fixture, deployment manifest, route inventory, feature-flag snapshot]
placement: engineering-handbook/examples/capability-map
dependencies: [repository search tool, local fixture environment, read-only telemetry export]
invocation: rtk rg -n "upgrade|subscription|retry" src tests docs
expected_output: A capability row links dashboard route, billing API, provider adapter, subscription table, event, owner, and tests.
failure_output: The retry worker has no current owner, alert, or contract test.
interpretation: The path is a high-priority unknown because duplicate charges have direct customer impact.
remediation: Assign owner, add retry/idempotency verification, add alert evidence, and refresh the map.
cleanup: Remove local exports containing fixture identifiers and retain only sanitized evidence links.
---

# Capability-map example: Atlas Subscription upgrade

## Capability row

| Field | Product Atlas evidence |
| --- | --- |
| Outcome | Account owner upgrades from Starter to Growth. |
| Entry point | Dashboard `/settings/billing`; `POST /v1/subscriptions/upgrade`. |
| Authorization | Account-owner role and account-scoped subscription lookup. |
| Data | Subscription, invoice, payment intent; financial data classification. |
| Dependencies | Payment provider, event queue, retry worker, email provider. |
| Observed signal | `subscription.upgrade.completed` event and billing success metric. |
| Owner | Billing Platform team; product owner for pricing. |
| Verification | API contract, provider sandbox, idempotency test, retry-worker alert. |
| Status | Partially verified: retry-worker recovery is unknown. |

## Discovery decision

The team does not call the workflow release-ready until the retry worker has a
named owner, a duplicate-charge test, and an alert with a rehearsed runbook.
The map converts that missing evidence into `MAP-ATLAS-01`, rather than silently
removing the worker from scope.
