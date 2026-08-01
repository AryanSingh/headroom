<!-- markdownlint-disable MD013 -->

# Verified Bug Report

**Date:** 2026-07-31
**Final verification:** 2026-08-01
**Scope:** Fresh audit reports at revision `df19c035`, independently reproduced against the working tree
**Rule:** A report assertion is not accepted without a source path, executable reproduction, or test

## Outcome

The generated report mixed four real defects with stale, incorrect, and architectural observations. The verified runtime defects are remediated with regression tests.

| Original item | Verdict | Action |
| --- | --- | --- |
| WebSocket sessions unbounded | Confirmed | Fixed. Admission is reserved before upstream connect, defaults to 500 sessions, returns close code 1013 at capacity, cleans reservations idempotently, and exports rejection telemetry. |
| Compression cache lacks byte limits | Confirmed | Fixed. Each session cache now has a 64 MiB retained-value budget and 4 MiB entry cap, UTF-8 byte accounting, LRU byte eviction, oversize skips, and metrics. |
| Auth requires progressive backoff | Not a demonstrated application defect | Existing admin-auth failures are rate-limited per IP and bucket memory is bounded. A many-source distributed attack belongs at the ingress/WAF layer; exponential per-IP delay would not stop the reported 1,001-IP scenario. |
| Missing `subscription.created` handler | Incorrect diagnosis | Stripe Checkout fulfillment correctly occurs on `checkout.session.completed`. The real bugs were duplicate fulfillment and non-durable delivery-hook state. A partial unique index now protects subscription identity, and a transactional outbox retries failed hook calls. |
| F-string SQL | Reviewed, not exploitable as reported | Interpolated values are fixed predicates, placeholder counts, or validated integers; attacker-controlled identifiers were not found. No speculative rewrite made. |
| Dark tertiary contrast | Confirmed | Fixed by lightening `#6F788C` to `#737C90`, which clears 4.5:1 on the darkest panel surface actually using the token. The generated recommendation to “darken” it was directionally wrong. |
| Only Python 3.12 in primary CI | Confirmed coverage gap | Added a focused 3.10–3.14 compatibility matrix while retaining the full suite on the primary version. |
| Starlette TestClient warning | Confirmed | Added `httpx2>=2.9.1` to development dependencies; focused compatibility tests run without the Starlette legacy-backend warning. |
| HPA min=max=1 | Intentional constraint | The deployment uses ReadWriteOnce local state. Horizontal scaling without externalizing that state would be unsafe, so the HPA remains single-replica by design. |

## Additional verified defect found during remediation

`CompressionCache.get_stats()` exposes `tokens_saved`, but the aggregate stats route read `total_tokens_saved`, silently reporting zero. Aggregation now uses the real key and also exposes retained bytes and oversize skips.

## Added regression coverage

- Registry reservation, cap, conversion, and cleanup tests.
- Handler-level proof that capacity rejection happens before `websockets.connect`.
- UTF-8 cache-byte accounting, LRU byte eviction, oversize replacement preservation, and proxy-config propagation.
- Sequential and concurrent SQLite checkout replay tests.
- Webhook replay proof: one license key, failed-hook retry, and no hook replay after recorded delivery.
- DeepSeek V4 Flash routing through the official OpenAI-compatible endpoint.
- WCAG token contrast assertion and deterministic Playwright screenshot baseline.
- CI/static assertions for Python-version coverage, `httpx2`, and WebSocket saturation alerting.

## Residual actionable work

No verified application bug from the generated report remains open. Operational receiver configuration, legal review, multi-replica external state, and broader product features remain separately tracked as external or roadmap work.

## Reproduction record

Run from the repository root:

```bash
rtk pytest tests/test_ws_session_registry.py tests/test_openai_codex_ws_lifecycle.py tests/test_compression_cache.py tests/test_proxy_dynamic_init.py cutctx_ee/tests/test_license_db.py tests/test_capability_extensions.py tests/test_dashboard_audit.py tests/test_openai_per_request_base_url.py tests/test_proxy_cache_ttl_metrics.py tests/test_proxy_healthchecks.py tests/test_release_workflows.py tests/test_secret_pattern_hook.py cutctx/tests/test_billing_integration.py tests/test_generate_hosted_compression_smoke.py
rtk pytest
```

The targeted run passed 359 tests before the final outbox hardening. The final full run passed 9,919 tests and skipped 271; no test failed.
