# Cutctx Master QA & Audit Test Matrix

This document provides a comprehensive Quality Assurance matrix specifically designed to catch complex architectural bugs, latency cliffs, fallback loops, and integration gaps across all components of the Cutctx ecosystem.

## 1. Architectural & Latency Edge Cases
These tests focus on avoiding hidden latency penalties (e.g., the 40s Kompress fallback or 70ms SQLite purge block) and ensuring graceful degradation.

| Test ID | Area | Scenario | Expected Behavior | Verification Method |
|---------|------|----------|-------------------|---------------------|
| ARCH-01 | Python Compressor | `tree-sitter` dependency missing on source code payload | Fails fast, drops to PASSTHROUGH. **Must not** fall back to ML model (Kompress) for code. | Uninstall `tree-sitter-language-pack`, send 1KB code, verify latency < 100ms. |
| ARCH-02 | Python Compressor | Short code snippets (under 5 lines) causing 0% token savings | `CodeAwareCompressor` yields 0 savings. System skips ML fallback and returns PASSTHROUGH. | Send a 5-line python function, verify Kompress is not downloaded/invoked. |
| ARCH-03 | Rust Core | Heavy read volume concurrently with expired cache entries | SQLite `get()` remains < 1ms. TTL expiration sweeps occur entirely on `put()` or in background. | Benchmark 10k `get` ops on expired keys; p99 latency must remain under 2ms. |
| ARCH-04 | Python ML | Offline / Air-gapped environment execution | If `Kompress` weights are not cached, throws `KompressModelNotCached` gracefully, no 60s timeout loop. | Disable network, send prose payload, verify instant fallback to PASSTHROUGH. |

## 2. CLI, OS Auth, & Environment Integrations
Testing the friction points developers face when installing or using wrappers.

| Test ID | Area | Scenario | Expected Behavior | Verification Method |
|---------|------|----------|-------------------|---------------------|
| CLI-01 | OS Auth | Copilot CLI on Windows | Resolves credentials natively via Windows Credential Manager without repetitive prompt looping. | Clear local CLI auth, trigger Copilot through Cutctx, verify single prompt. |
| CLI-02 | OS Auth | Copilot CLI on Linux | Resolves via `Secret Service` DBus cleanly. | Test on Ubuntu VM with gnome-keyring headless. |
| CLI-03 | Install | Corporate Proxy SSL Failure | `pip install cutctx` works without failing on Rust binary compilation (`CERTIFICATE_VERIFY_FAILED`). | Verify pre-compiled Python wheels exist for MacOS/Linux/Windows on PyPI. |
| CLI-04 | Environment | Global wrapping vs venv | `cutctx wrap` successfully identifies global binaries (e.g., Cursor) even when launched from an isolated `venv`. | Launch wrapper from strict venv, verify Cursor executes correctly. |

## 3. IDE Extensions & Plugins
Ensuring native integrations route traffic successfully without brittle wrapper dependencies.

| Test ID | Area | Scenario | Expected Behavior | Verification Method |
|---------|------|----------|-------------------|---------------------|
| IDE-01 | JetBrains | Plugin Initialization | Automatically injects `HttpConfigurable` JVM proxy settings to route AI Assistant to `localhost:8787`. | Start plugin, monitor network traffic, verify AI Assistant hits local proxy. |
| IDE-02 | JetBrains | Plugin Shutdown | IDE proxy settings cleanly revert to user's original settings upon plugin disable/stop. | Stop plugin, verify native JVM proxy settings restore previous state. |
| IDE-03 | VS Code | Extension Traffic Routing | Native configuration intercepts Github Copilot / Codeium extensions without relying on OS-level `HTTP_PROXY`. | Inspect VS Code developer tools network tab for proxy overrides. |

## 4. Front-End Dashboard & UX
Focusing on data bloat, responsiveness, and user experience.

| Test ID | Area | Scenario | Expected Behavior | Verification Method |
|---------|------|----------|-------------------|---------------------|
| UI-01 | Dashboard | Massive Memory Database (1M+ entries) | UI loads semantic memory tree within 1s. Pagination and search function correctly without crashing browser. | Seed 1M memory nodes, navigate to Memory tab, trace render times. |
| UI-02 | Dashboard | Spend Ledger Charting | D3/Chart.js renders large timeseries data cleanly. No overlapping labels on mobile viewports. | Seed 1 year of daily metrics, open on 375px width device emulator. |
| UI-03 | Accessibility | Keyboard Navigation | All tables, toggles, and modal dialogs are fully navigable via `Tab` key with clear focus rings. | Run Lighthouse Accessibility Audit, manual keyboard sweep. |

## 5. Enterprise & Security Features
Validating the `cutctx_ee` module and air-gapped readiness.

| Test ID | Area | Scenario | Expected Behavior | Verification Method |
|---------|------|----------|-------------------|---------------------|
| EE-01 | Auth | SSO / OIDC Session Expiry | Enterprise dashboard kicks to IDP login gracefully upon token expiration. No infinite refresh loops. | Force expire JWT, attempt API call, verify 302/401 redirect to SSO. |
| EE-02 | RBAC | Developer vs Admin Visibility | 'Developer' role cannot view the Org-level billing and spend ledger APIs. | Log in as Developer, attempt to hit `/api/v1/ledger`, verify 403 Forbidden. |
| EE-03 | Security | LLM Firewall Redaction | Streaming payloads containing PII (e.g., SSN, API Keys) are redacted inline (`[REDACTED]`) without buffering the entire stream. | Send streaming request with fake AWS keys, verify output stream hides them mid-flight. |
| EE-04 | Audit | SQLite WAL Checkpointing | High-volume audit logging (>1000 req/sec) does not lock the DB. WAL checkpointing occurs smoothly in background. | Bombard EE proxy with requests, monitor `audit.db-wal` size and latency variance. |

## QA Execution Plan & Recommendations
1. **Automated Integration Expansion:** Incorporate Tests `ARCH-01` and `ARCH-02` directly into the GitHub Actions CI pipeline to permanently prevent the Kompress-Code fallback regression.
2. **Adversarial Security Testing:** Schedule a red-team penetration test against the `EE-03` LLM Firewall streaming logic, specifically attempting to bypass regex matchers by breaking PII across streaming chunks.
3. **OS-level Automation:** Use GitHub Actions runners (Windows, Ubuntu, MacOS) to automate `CLI-01` and `CLI-02` using simulated credential managers.
