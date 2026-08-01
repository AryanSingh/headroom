# Fresh Audit Remediation Design

## Goal

Reconcile the eight 2026-07-31 audit reports against current repository evidence, fix every verified bounded defect in the approved remediation scope, add safe DeepSeek V4 Flash routing for OpenAI-compatible harnesses, and leave product, legal, and externally owned operations work explicitly classified.

## Constraints

- Preserve all existing uncommitted work and extend the per-request upstream implementation already present in the worktree.
- Require a failing automated test before every production behavior change.
- Preserve the dashboard's current visual system. The only visual token change increases dark-theme tertiary-text contrast.
- Keep connected-mode custom-provider support. Do not turn the egress layer into an implicit deny-all migration.
- Do not invent Alertmanager receivers, legal approval, prices, certification status, or operations ownership.
- Use `ruff==0.9.4` for final lint and format verification.
- Treat the explicit Python support range as 3.10 through 3.14.

## Report reconciliation

Each fresh report will distinguish five states: verified defect, verified coverage gap, stale or already fixed, false positive, and externally owned decision. The reports will cite source paths, reproduction commands, and the remediation state. Unsupported scores and test totals without commands will be removed or qualified.

The reconciliation will correct these false claims: missing error tracking, missing CSP, missing restore playbook, missing rendered `aria-current`, SQL identifier injection, and a required `customer.subscription.created` handler. It will retain the verified WebSocket, compression-cache, contrast, multi-Python, Starlette/httpx2, Axe, and visual-regression gaps. Product and legal recommendations remain backlog items.

## Runtime resource safety

### WebSocket admission

`WebSocketSessionRegistry` will own an optional `max_sessions` limit and a reservation set. `try_reserve(session_id)` will atomically admit or reject before the handler opens the upstream WebSocket. `register(handle)` will convert a reservation into an active session. `release(session_id)` will clear either a reservation or active entry and remain idempotent.

The proxy config will expose `max_ws_sessions`, defaulting to 500. Values at or below zero disable the cap. An overloaded connection will be accepted only long enough to send WebSocket close code 1013 with an actionable reason, without opening an upstream connection. Metrics will record rejected sessions, and health/debug output will expose active, reserved, limit, and rejected counts.

### Compression-cache bytes

`CompressionCache` will accept `max_size_bytes` and `max_entry_size_bytes`. It will count UTF-8 bytes retained by compressed values, reject entries larger than the per-entry limit, and evict least-recently-used entries until both entry and byte limits hold. Replacing an entry will subtract its previous bytes before adding the replacement. Stats will expose retained bytes and oversize skips.

The proxy will supply configurable defaults to every session cache. The default total budget is 64 MiB per session cache and the default entry cap is 4 MiB. Existing entry-count behavior remains intact.

## Billing idempotency

Stripe Checkout fulfillment will remain on `checkout.session.completed`. `LicenseDB.fulfill_checkout(record)` will begin an immediate SQLite transaction, return the existing row when a non-empty subscription ID already exists, and insert the new record otherwise. Concurrent duplicate deliveries will serialize on the write lock and return one stable license key.

`handle_checkout_completed` will call that method and send a license email only when the database created the record. Replayed events return the existing license without sending a duplicate email. One-time sessions without a subscription ID retain their current behavior.

## Dashboard and compatibility gates

The dark-theme `--text-tertiary` token will change to the nearest design-compatible lighter value that clears 4.5:1 on `#0D0F14`. The light-theme token remains unchanged.

The existing Playwright dashboard audit will run Axe through `@axe-core/playwright` on a representative route and fail on serious or critical violations. Existing screenshot capture remains evidence collection; a deterministic screenshot-baseline assertion will cover one stable shell viewport without treating dynamic telemetry as a pixel contract.

The development dependency set will include `httpx2`, eliminating Starlette's legacy fallback warning. CI will add a lightweight Python compatibility job for 3.10, 3.11, 3.12, 3.13, and 3.14. The job will install the package, import core modules, run a focused compatibility suite, and keep the expensive full suite on its existing primary version.

## DeepSeek and harness-neutral upstream routing

Official DeepSeek documentation lists `deepseek-v4-flash` and `deepseek-v4-pro`, with a 1M context window. The model registry already contains these identifiers.

The existing `x-cutctx-base-url` capability will use host-specific default path rules:

- `opencode.ai` permits `/zen/go` and descendants.
- `api.deepseek.com` permits `/` and descendants.

This prevents a root-path allowance for DeepSeek from broadening OpenCode's allowed surface. Operator-provided host/path extensions remain explicit configuration.

Any OpenAI-compatible harness can use one of two supported modes:

1. Shared proxy: point the harness at `http://127.0.0.1:8787/v1`, send its own DeepSeek bearer credential, send `x-cutctx-base-url: https://api.deepseek.com`, and request `deepseek-v4-flash`.
2. Dedicated proxy: start Cutctx with DeepSeek as the process-wide OpenAI-compatible upstream, then point a harness that cannot set custom headers at that private listener.

Tests will prove headerless traffic still uses the process-wide upstream, DeepSeek and default requests remain cache-isolated, the caller credential reaches only DeepSeek, ChatGPT subscription routing cannot be overridden, unsafe IPs remain blocked, and OpenCode paths do not broaden.

## Observability and silent failures

Prometheus output will include WebSocket admission rejections and compression-cache retained bytes. The deployed alert rules will add a WebSocket capacity-pressure rule only if the configured limit is observable in metrics. The rule will include a runbook annotation but no fabricated receiver or owner.

The handful of silent broad exception handlers will receive diagnostics only where the exception represents invalid operator state or lost feature availability. Optional dependency probes that intentionally return unavailable remain quiet or debug-level.

## Verification

Every behavior task follows red-green-refactor. Phase gates include targeted tests, adjacent suites, dashboard test/build/lint/Axe, explicit Python-version compatibility, pinned Ruff check/format, security-focused tests, the full Python suite, and a final diff-based re-audit. The reports will list exact commands and results from the final current state.

