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

---

# Codex multi-agent dispatch bridge mismatch

**Date:** 2026-08-04
**Scope:** Codex desktop task running from this workspace, with Cutctx configured as its OpenAI-compatible endpoint
**Status:** Reproduced; root cause isolated to the Codex orchestration layer. No project code or configuration was modified.

## Finding

`spawn_agent` is advertised to this task but the runtime that receives the
dispatch request does not implement it. The request fails before an agent is
created with:

```text
unsupported call: spawn_agent
```

This is a **tool-registry/handler mismatch**: the task context declares the
collaboration tool, while its backing orchestration bridge rejects that tool
name. It is not a Cutctx proxy failure.

### Reproduction steps

1. Open this Codex task in the `headroom` workspace.
2. Confirm `/Users/aryansingh/.codex/config.toml` contains:

   ```toml
   [features]
   multi_agent = true
   ```

3. Request a minimal, read-only child agent via `spawn_agent` (the attempted
   task was to calculate `(37 * 48) + (125 * 16) - 91`).
4. Observe the immediate bridge response: `unsupported call: spawn_agent`.

### Expected vs actual

| Expected | Actual |
| --- | --- |
| With `multi_agent = true` and `spawn_agent` advertised in the task, Codex creates the child agent and returns its task identifier. | The orchestration bridge rejects the call as unsupported; no child agent exists and no workspace state changes. |

### Evidence

| Check | Result | Implication |
| --- | --- | --- |
| Direct dispatch | `unsupported call: spawn_agent` | Failure occurs at the host-side collaboration call boundary. |
| Current Codex configuration | `[features] multi_agent = true` | The documented local feature gate is enabled. |
| Pre-Cutctx config snapshot | Also contains `multi_agent = true` | Cutctx did not add, remove, or alter the agent feature flag. |
| `cutctx/cli/wrap.py::_inject_codex_provider_config` | Writes only `openai_base_url`, `base_url`, and `supports_websockets` in the shown injected block | The wrapper changes model transport configuration, not Codex collaboration-tool registration. |
| `GET http://127.0.0.1:8787/livez` | Proxy healthy; upstream readiness healthy | No proxy outage or rejected-session condition is present. |
| Proxy runtime health | `codex_ws_gated: false` | The proxy reports no Codex WebSocket gating. |

## Severity

**Medium (developer-workflow blocking).** Any task depending on child-agent
delegation cannot run. The fault does not affect repository data integrity,
does not create an orphan process, and does not affect normal single-agent
work.

## Suggested fix

The owning Codex runtime should make its advertised tool set match the enabled
handlers: either register the `spawn_agent` dispatch handler for this task or
omit the tool from the task context when multi-agent dispatch is unavailable.

For the local user, restart Codex and create a new task so the desktop runtime
reloads `/Users/aryansingh/.codex/config.toml`. If a fresh task still returns
the same error, capture the task ID, the exact `unsupported call: spawn_agent`
response, and the Codex desktop version (`/Users/aryansingh/.codex/version.json`
reported `0.145.0` as the latest known version) in a Codex support report.
Changing Cutctx settings is not a justified remediation because the failure
precedes proxy/model traffic.

## Boundary and reliability checks

- **Input validation:** The dispatch used a valid lowercase task name and a
  small plain-text instruction, so no argument-size or schema boundary was
  reached.
- **Concurrency/race condition:** The first dispatch failed synchronously;
  no agent ID, running child, reservation, or cleanup path was created. A
  concurrent-dispatch test would not isolate a different component and was not
  run.
- **Timeout/resource cleanup:** The call returned immediately rather than
  timing out. No child process or workspace modification resulted.
- **Error handling:** The error is explicit but not actionable: it contradicts
  the tool advertised to the model. The suggested runtime fix makes this state
  impossible rather than asking callers to retry blindly.
