# Fresh Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the fresh audit record, close verified resource, billing, accessibility, compatibility, and observability gaps, and support DeepSeek V4 Flash through safe OpenAI-compatible harness routing.

**Architecture:** Add bounds at the owning state containers, make Stripe fulfillment atomic at the database boundary, preserve the dashboard design while strengthening automated gates, and extend the existing per-request upstream resolver with host-specific path policy. Reconcile reports only after code and tests establish the final truth.

**Tech Stack:** Python 3.10-3.14, FastAPI/Starlette, SQLite, pytest, React 19, Playwright, Axe, GitHub Actions, Prometheus.

## Global Constraints

- Preserve the dirty worktree and never revert unrelated edits.
- Write and run a failing test before production behavior changes.
- Keep OpenCode restricted to `/zen/go` while allowing DeepSeek under `api.deepseek.com`.
- Keep the existing dashboard visual language.
- Do not add external alert receivers, legal assertions, pricing changes, or certification claims.
- Verify Ruff with version 0.9.4.

---

### Task 1: WebSocket admission control

**Files:**
- Modify: `cutctx/proxy/ws_session_registry.py`
- Modify: `cutctx/proxy/models.py`
- Modify: `cutctx/proxy/server.py`
- Modify: `cutctx/proxy/handlers/openai/responses.py`
- Modify: `cutctx/proxy/prometheus_metrics.py`
- Test: `tests/test_ws_session_registry.py`
- Test: `tests/test_openai_codex_ws_lifecycle.py`

**Interfaces:**
- Produces: `WebSocketSessionRegistry(max_sessions: int = 0)`, `try_reserve(session_id: str) -> bool`, `release(session_id: str) -> None`, and admission stats.
- Produces: `ProxyConfig.max_ws_sessions: int` and `CUTCTX_MAX_WS_SESSIONS`.

- [x] Write registry tests that fill the cap, reject the next reservation, convert a reservation to an active handle, and release idempotently.
- [x] Run `pytest tests/test_ws_session_registry.py -q` and confirm failures because reservation APIs do not exist.
- [x] Implement reservation and admission accounting in the registry.
- [x] Run the registry suite and confirm it passes.
- [x] Write a handler test proving overload closes with code 1013 and never calls the upstream connector.
- [x] Run the single handler test and confirm it fails because the handler opens upstream before admission.
- [x] Wire config, pre-upstream reservation, final release, health/debug fields, and rejection metrics.
- [x] Run `pytest tests/test_openai_codex_ws_lifecycle.py tests/test_ws_session_registry.py -q`.

### Task 2: Compression-cache byte budgets

**Files:**
- Modify: `cutctx/cache/compression_cache.py`
- Modify: `cutctx/proxy/models.py`
- Modify: `cutctx/proxy/server.py`
- Modify: `cutctx/proxy/prometheus_metrics.py`
- Test: `tests/test_compression_cache.py`
- Test: `tests/test_proxy_dynamic_init.py`

**Interfaces:**
- Produces: `CompressionCache(max_entries=10000, max_size_bytes=67108864, max_entry_size_bytes=4194304)`.
- Produces stats keys: `size_bytes`, `max_size_bytes`, `max_entry_size_bytes`, and `oversize_skips`.

- [x] Write tests for byte-budget LRU eviction, replacement accounting, UTF-8 byte counting, and oversize-entry rejection.
- [x] Run the new tests and confirm failures because byte stats and eviction do not exist.
- [x] Implement byte accounting and dual-limit eviction under the existing lock.
- [x] Run `pytest tests/test_compression_cache.py -q`.
- [x] Write a proxy-construction test proving configured byte limits reach new session caches.
- [x] Run it red, then wire configuration and metrics aggregation.
- [x] Run `pytest tests/test_proxy_dynamic_init.py tests/test_compression_cache.py -q`.

### Task 3: Stripe checkout idempotency

**Files:**
- Modify: `cutctx_ee/billing/license_db.py`
- Modify: `cutctx_ee/billing/stripe_webhook.py`
- Test: `tests/test_capability_extensions.py`
- Test: `cutctx_ee/tests/test_license_db.py`

**Interfaces:**
- Produces: `LicenseDB.fulfill_checkout(record: object) -> tuple[object, bool]`, where the boolean is true only for a newly inserted record.

- [x] Write a database test that calls fulfillment twice with the same subscription ID and asserts one row and one stable license key.
- [x] Write a concurrent two-connection test that asserts the same invariant.
- [x] Run both tests and confirm failure because fulfillment is keyed only by random license key.
- [x] Implement an immediate transaction that reuses an existing subscription record or inserts once.
- [x] Run the database tests.
- [x] Write webhook tests asserting one stable key, failed delivery-hook retry, and no replay after recorded success.
- [x] Run them red, then add schema-level subscription uniqueness and transactional outbox state around `handle_checkout_completed`.
- [x] Run `pytest tests/test_capability_extensions.py cutctx_ee/tests/test_license_db.py -q`.

### Task 4: Dashboard contrast, Axe, and visual regression

**Files:**
- Modify: `dashboard/src/index.css`
- Modify: `tests/test_dashboard_audit.py`
- Modify: `dashboard/package.json` only if a script is required for the stable visual gate.
- Test: `dashboard/tests/*.test.js` or the existing Python Playwright audit.

**Interfaces:**
- Preserves all layout, typography, spacing, motion, and component structure.
- Produces dark-theme tertiary contrast of at least 4.5:1 on `#0D0F14`.

- [x] Add a token-level contrast assertion for `--text-tertiary` and confirm it fails at approximately 4.3277:1.
- [x] Change only the dark-theme tertiary token to the nearest existing-system-compatible lighter value that passes.
- [x] Run the contrast assertion and dashboard unit tests.
- [x] Verify the existing Axe Playwright assertion on the stable dashboard shell and correct the audit's false claim that Axe was absent.
- [x] Keep serious and critical Axe violations as test failures.
- [x] Add one stable shell screenshot assertion backed by deterministic mocked telemetry.
- [x] Run dashboard tests, Playwright audit, lint, and production build.
- [x] Inspect the rendered dashboard at desktop and mobile widths and record screenshots in ignored artifact paths.

### Task 5: Starlette/httpx2 and Python compatibility CI

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_imports.py` or a new focused compatibility test file.

**Interfaces:**
- Adds `httpx2` to development/test dependencies.
- Adds a Python 3.10, 3.11, 3.12, 3.13, and 3.14 compatibility matrix without duplicating the full suite.

- [x] Add a warning-as-error test command for `StarletteDeprecationWarning` and confirm the current environment fails.
- [x] Add the minimum compatible `httpx2` development dependency and install it in the active test environment.
- [x] Re-run the warning-as-error check and focused TestClient tests.
- [x] Add a matrix job that installs the package, imports the proxy and model registry, and runs focused compatibility tests.
- [x] Validate workflow syntax and run the focused tests on locally installed Python 3.11, 3.12, 3.13, and 3.14; retain Python 3.10 in CI because it is not installed locally.

### Task 6: DeepSeek V4 Flash shared-upstream support

**Files:**
- Modify: `cutctx/proxy/openai_upstream.py`
- Modify: `tests/test_openai_per_request_base_url.py`
- Modify: `docs/content/docs/model-routing-presets.mdx` or the nearest OpenAI-compatible upstream guide.

**Interfaces:**
- Produces host-specific default upstream rules for `opencode.ai:/zen/go` and `api.deepseek.com:/`.
- Documents shared-listener and dedicated-listener harness configuration for `deepseek-v4-flash`.

- [x] Write resolver tests accepting `https://api.deepseek.com` and `/v1`, while rejecting root-level OpenCode paths.
- [x] Run them and confirm DeepSeek fails host/path validation.
- [x] Replace the default host/path cross-product with host-specific default path rules and keep explicit environment extensions compatible.
- [x] Run resolver tests.
- [x] Add handler tests for DeepSeek credential forwarding, default-upstream isolation, ChatGPT override refusal, cache separation, and model preservation.
- [x] Run `pytest tests/test_openai_per_request_base_url.py -q`.
- [x] Document configuration for harnesses with and without custom-header support, including the requirement that the caller owns the DeepSeek credential.

### Task 7: Observability and targeted silent-failure diagnostics

**Files:**
- Modify: `cutctx/proxy/prometheus_metrics.py`
- Modify: `k8s/prometheus-rules.yaml`
- Modify: `docs/runbooks/ops-alert-inventory.md`
- Modify: `cutctx/proxy/server.py`
- Test: `tests/test_prometheus_metrics.py`
- Test: focused server diagnostics tests.

**Interfaces:**
- Exposes `cutctx_ws_sessions_rejected_total`, configured WS capacity, and compression-cache retained bytes.
- Adds a WebSocket capacity-pressure alert with a repository runbook link and no receiver assumptions.

- [x] Write metric rendering tests and confirm the new series are absent.
- [x] Implement counters/gauges and run metric tests.
- [x] Add a Prometheus rule test for WebSocket pressure and include `runbook_url`.
- [x] Add diagnostics tests for invalid intercept-bypass JSON and unavailable learned compression profiles.
- [x] Run them red, add warning/debug logs without changing fallback behavior, then run them green.
- [x] Update the alert inventory with deployed versus externally blocked coverage.

### Task 8: Reconcile all fresh audit reports

**Files:**
- Modify: `audit/bug-report.md`
- Modify: `audit/code-review-report.md`
- Modify: `audit/security-report.md`
- Modify: `audit/launch-readiness-report.md`
- Modify: `audit/ui-review-report.md`
- Modify: `audit/product-manager-report.md`
- Modify: `audit/commercialization-report.md`
- Modify: `audit/competitor-report.md`

**Interfaces:**
- Each report records evidence status, exact reproduction commands, remediation state, and external ownership.

- [x] Replace stale and false findings with the reconciled evidence from the design document and current implementation.
- [x] Remove unsupported scores or explain the scoring rubric and checked scope.
- [x] Record exact final test commands instead of an unreproducible aggregate.
- [x] Preserve product, legal, and operations decisions as explicit backlog items rather than code defects.
- [x] Run markdown and link checks available in the repository.

### Task 9: Full verification and re-audit

**Files:**
- Modify only files required by verified failures.

- [x] Run all targeted suites from Tasks 1-7.
- [x] Run the full Python test suite with the repository's intended interpreter and record pass, skip, warning, and duration totals.
- [x] Run dashboard unit tests, lint, build, Axe, and visual checks.
- [x] Run `uvx ruff@0.9.4 check .` and `uvx ruff@0.9.4 format --check .`.
- [x] Clear stale mypy cache and run the project-supported typing gate.
- [x] Run security-focused tests and secret-pattern checks.
- [x] Inspect `git diff --check`, review the complete diff, and verify every approved requirement has direct evidence.
- [x] Update the Deepwork state and audit reports with final results.

### Task 10: Remediate final adversarial review findings

**Files:**
- Modify: `cutctx_ee/billing/license_db.py`
- Modify: `cutctx_ee/billing/stripe_webhook.py`
- Modify: `cutctx_ee/tests/test_license_db.py`
- Modify: `tests/test_capability_extensions.py`
- Modify: `dashboard/e2e/visual-identity.spec.js`
- Modify: `dashboard/tests/design-tokens.test.js`

- [x] Add a partial unique index for nonempty Stripe subscription IDs.
- [x] Revoke and deactivate historical noncanonical duplicates while preserving their rows for operator review.
- [x] Reject conflicting direct upserts instead of creating active orphan entitlements.
- [x] Queue delivery-hook work in the license transaction and retry failed or stale claims.
- [x] Fence delivery claims so expired workers cannot acknowledge or release a newer lease.
- [x] Document that the current delivery hook is log-only and external email still needs a provider-side idempotency contract.
- [x] Remove the E2E side effect that overwrote a tracked documentation screenshot.
- [x] Run the post-hardening full suite: 9,919 passed, 271 skipped, 0 failed.
- [x] Obtain Terra re-review with no actionable findings remaining.
