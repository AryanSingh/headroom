<!-- markdownlint-disable MD013 -->

# Verified Launch Readiness Report

**Date:** 2026-07-31
**Final verification:** 2026-08-01
**Recommendation:** Engineering-ready for controlled pilot; broad GA remains contingent on organizational sign-off

## Code and product gates

| Gate | Status | Evidence |
| --- | --- | --- |
| WebSocket capacity | Complete | Configured pre-upstream admission, health/metrics, rejection alert. |
| Retained cache memory | Complete | 64 MiB per-session value budget, 4 MiB entry cap, eviction and telemetry. |
| Billing replay safety | Complete at persistence and hook boundary | Sequential and concurrent duplicate fulfillment returns one license. Failed delivery-hook calls remain retryable, and recorded success is not replayed. |
| Customer email transport | Not implemented in this repository | The current `_send_license_email` hook logs issuance; an external mail provider and its idempotency contract require an owner before paid checkout can rely on email delivery. |
| Dashboard accessibility | Complete for automated gate | Contrast token test plus Axe serious/critical scan, keyboard flows, and inspected visual baseline. |
| Python support claim | Gated | CI smoke matrix covers 3.10, 3.11, 3.12, 3.13, and 3.14. |
| TestClient compatibility | Complete | `httpx2` development dependency; focused suite runs without Starlette's legacy warning. |
| Dashboard supply chain | Complete for current lock | `npm audit` reports zero vulnerabilities. |
| DeepSeek V4 Flash | Complete | Shared-listener header routing and dedicated-listener documentation for any OpenAI-compatible harness. |
| Restore procedure | Already complete | `docs/runbooks/backup-restore.md` exists and records the restore workflow/rehearsal. |
| Error tracking | Already implemented | Optional error-tracking integration exists and is initialized by the server. |

## Remaining pre-customer organizational gates

1. Qualified legal review of `TERMS.md` and any DPA/customer contract.
2. Name alert receivers, routing, on-call owner, and acknowledgement SLA.
3. Exercise a staging test alert through the real receiver path.
4. Name the customer/status communication owner and channel.
5. Confirm support contact details in the pilot materials.
6. Configure and verify an external license-email transport before enabling paid checkout that depends on email delivery.

These cannot be truthfully completed from source code alone.

## GA roadmap, not launch defects

- Direct Stripe checkout fallback and self-serve billing UI.
- Enterprise admin UI for SCIM, fleet, secrets, retention, and webhooks.
- Hosted analytics/digests.
- Multi-replica deployment after external state is available.
- SOC 2/HIPAA/ISO work and certification evidence.

## Corrected generated conditions

The prior report incorrectly listed missing Sentry, missing restore documentation, and missing `subscription.created` fulfillment as launch blockers. Those claims were stale or based on the wrong Stripe lifecycle event. Subscription replay safety and durable hook state are remediated. Real customer email transport remains an explicit organizational and integration gate.

## Reproduction record

```bash
rtk pytest
rtk proxy uvx ruff@0.9.4 check .
rtk proxy uvx ruff@0.9.4 format --check .
rtk proxy .venv/bin/python scripts/mypy_ratchet.py
rtk proxy .venv/bin/python scripts/check_secret_patterns.py
rtk npm test
rtk npm run lint
rtk npm run build
rtk npm run test:e2e -- --reporter=line dashboard/e2e/accessibility.spec.js dashboard/e2e/visual-identity.spec.js
rtk npm audit --audit-level=high
```

The final Python suite passed 9,919 tests with 271 skips. Dashboard unit tests passed 31 tests, Playwright passed 9 tests, lint and build passed, and npm reported zero vulnerabilities. Run the npm commands from `dashboard/`.
