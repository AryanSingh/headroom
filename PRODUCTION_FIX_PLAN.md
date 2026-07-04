# Cutctx Production Fix Plan

## Live Verification Tracker

This section is the active handoff log for the independent release verification pass
requested on 2026-06-30. Treat all previously completed work as untrusted until it is
re-verified here.

### Working Rules

- Keep commits small and task-scoped so another agent can resume from git history.
- Prefer verification before modification.
- Treat `cutctx/proxy/server.py` and related routing/startup paths as crash-prone.
- Do not mark a task complete until there is direct evidence in tests, builds, or live checks.

### Current State

- Verification pass started: 2026-06-30
- Branch: `main`
- Worktree status at start of this pass: already dirty from prior tooling
- Existing untrusted changes detected in:
  - proxy/runtime
  - memory/USearch
  - stack-graph files
  - CLI/integrations
  - tests/docs/screenshots

### 2026-07-01 Verification Update
- Restored `cutctx/proxy/routes/admin.py` from the current `HEAD` after a local edit corrupted the admin router scope.
- Confirmed the source tree boots again on `127.0.0.1:8788`.
- Verified live endpoints on the current source proxy:
  - `GET /health` healthy
  - `GET /config/flags` returns live and restart-required flags
  - `GET /policy/status` returns provider decisions
  - `GET /stats` and `GET /stats-history` respond with valid JSON
- Verified build and targeted tests:
  - `cd dashboard && npm run build`
  - `uv run python -m pytest -q tests/test_audio_compressor.py tests/test_inline_audio_messages.py tests/test_proxy_compress_endpoint.py tests/test_handler_outcome_tag_invariant.py tests/test_modality_matrix.py -q`

### Task Ledger

| Task | Status | Evidence | Notes |
|---|---|---|---|
| Establish handoff log and commit discipline | Complete | commit `4fdc265d` | Tracker established and checkpoint committed |
| Re-verify high-risk runtime paths | In progress | `tests/test_proxy_runtime_truthfulness.py` bundle passed | Need more live/manual coverage beyond the core audited slice |
| Re-verify new USearch and stack-graph work | In progress | stack-graph Python-facing tests passed; USearch tests skipped without dependency | Rust build itself not verified because `cargo` is unavailable in this environment |
| Re-verify dashboard stats and operator surfaces | In progress | live `/dashboard` check, stats contract tests, and dashboard Playwright slices passed | Headline/footnote mismatch fixed; `/stats` now surfaces Graphify, stack-graph, USearch, and routing capability truth |
| Refresh release verdict and remaining risks | Pending |  | Final task after independent verification |

### Next Actions

1. Continue the widened runtime verification: provider routing, health, stats, and dashboard-facing contracts.
2. Validate whether the new stack-graph/USearch work is actually release-ready or merely test-green in a partial environment.
3. Audit the dashboard/operator surfaces live and record any broken stats or capability drift.

### Active Findings

- The live dashboard was mixing lifetime token totals with current-session
  percentage/request footnotes. Fixed in `dashboard/src/pages/Overview.jsx`
  and covered by `tests/test_dashboard_overview_lifetime_headline.py`.
- The active `/admin/config/flags` route was still using the legacy
  `x-cutctx-admin-key` header and did not initialize episodic memory when
  toggled on. Fixed in `cutctx/proxy/server.py` so the active route now accepts
  bearer auth, `x-cutctx-admin-key`, and the legacy header for compatibility.
- Several stray script-style Playwright files were present in `tests/` and
  depended on `localhost:5173`. Those were replaced/removed in favor of
  deterministic route-mocked coverage.
- Live savings on the currently running proxy are still dominated by provider
  prompt cache. The current `persistent_savings` payload shows
  `model_routing_savings_usd=0.0` and `self_hosted_prefix_cache_savings_usd=0.0`
  for this session, so "all savings sources firing in real traffic" remains
  unproven in this environment.

### Current Release Call

- Not yet independently proven as "best in class" or "best in market".
- Not ready for a fully trust-based READY verdict while:
  - the worktree remains heavily dirty from unrelated in-flight changes
  - Rust/cargo-backed verification is not reproducible in this environment
  - live traffic in this environment does not show model-routing or self-hosted
    prefix-cache savings actually firing
- Reasonable candidate for a constrained OSS release only after:
  - the worktree is cleaned and release scope is frozen
  - the running proxy is restarted onto the verified code
  - Rust build/test verification is reproduced on a machine with `cargo`
  - release messaging is precise about which savings sources are proven live

### Evidence Log

#### 2026-06-30 1st verification checkpoint

- `python3 -m py_compile cutctx/memory/backends/usearch_store.py`
  - passed
- `uv run python -m pytest -q tests/test_stack_graph_resolver.py tests/test_stack_graph_reachability.py tests/test_usearch_backend.py`
  - result: `35 passed, 27 skipped`
  - note: all USearch backend tests were skipped because `usearch` is not installed in this environment
- `uv run python -m pytest -q tests/test_proxy_runtime_truthfulness.py tests/test_provider_proxy_routes.py tests/test_proxy_dashboard_stats_cache.py tests/test_proxy_savings_history.py tests/test_proxy_compress_endpoint.py tests/test_proxy_anthropic_compression_diagnostics.py tests/test_graphify_index.py tests/test_cli_capabilities.py tests/test_memory_sync.py`
  - result: `114 passed, 3 warnings`
- `cargo test -p cutctx-core ...`
  - not runnable here because `cargo` is not installed in the current environment

#### 2026-06-30 2nd verification checkpoint

- Live dashboard check on `http://127.0.0.1:8787/dashboard`
  - before fix: headline showed lifetime tokens saved with misleading
    session-level reduction/request footnotes
  - after fix: headline and supporting metrics align on the same lifetime data source
- `uv run python -m pytest -q tests/test_docs_page.py tests/test_docs_proxy.py tests/test_proxy_dynamic_init.py tests/test_openai_responses_subscription_compat.py`
  - result: `6 passed, 1 skipped`
- `uv run python -m pytest -q tests/test_dashboard_overview_lifetime_headline.py tests/test_dashboard_surfaces_playwright.py tests/test_dashboard_savings_by_model.py tests/test_provider_codex_runtime.py tests/test_provider_gemini_runtime.py tests/test_openai_codex_routing.py`
  - result: `23 passed`
- Verified and fixed active `/admin/config/flags` behavior
  - old active route accepted only `x-cutctx-admin-key` and did not create
    `proxy.episodic_tracker`
  - current active route accepts bearer auth, `x-cutctx-admin-key`, and legacy
    `x-cutctx-admin-key`, and dynamically initializes episodic memory

#### 2026-06-30 3rd verification checkpoint

- `uv run python -m pytest -q tests/test_product_capabilities.py tests/test_modality_matrix.py tests/test_docs_truthfulness.py tests/test_graphify_index.py tests/test_proxy_dashboard_stats_cache.py tests/test_request_outcome.py tests/test_smart_orchestrator_bdd.py`
  - result: `148 passed`
- `uv run python -m pytest -q tests/test_dashboard_capabilities_toggles_e2e.py tests/test_dashboard_governance_e2e.py tests/test_proxy_warmup.py tests/test_memory_sync.py tests/test_cli_capabilities.py tests/test_proxy_runtime_truthfulness.py`
  - result: `47 passed`
- `uv run python -m pytest -q tests/test_proxy_dashboard_stats_cache.py tests/test_product_capabilities.py tests/test_modality_matrix.py tests/test_docs_truthfulness.py tests/test_graphify_index.py tests/test_request_outcome.py tests/test_smart_orchestrator_bdd.py tests/test_dashboard_capabilities_toggles_e2e.py tests/test_dashboard_governance_e2e.py`
  - result: `150 passed`
- Stats contract improvement verified with `TestClient`
  - `feature_availability` now includes `knowledge_graph`, `stack_graph`,
    `usearch`, and `model_routing` capability truth in the lightweight app path
- Live proxy snapshot at `http://127.0.0.1:8787/stats?cached=1`
  - Graphify capability is visible (`feature_availability.knowledge_graph`)
  - running instance still reports `model_routing_savings_usd=0.0` and
    `self_hosted_prefix_cache_savings_usd=0.0`
  - note: the already-running proxy process must be restarted to pick up the
    latest `/stats` code changes from this pass

**Date:** 2026-06-30  
**Version target:** v0.29.0 → v0.29.1 (production release)  
**Scope:** Fixes verified against current codebase — items from the v0.27.0 release report that are **already fixed** are excluded.

---

## Status of Previously Reported Issues

These were flagged as critical/high in `RELEASE_REPORT.md` (2026-06-24) but are **already fixed** in the current codebase — no action needed:

| Reported Issue | Location | Verdict |
|---|---|---|
| RBAC fail-open on init | `server.py:3042–3079` | Fixed — raises HTTP 503 when `_rbac_checker_ref is None` |
| Neo4j default password `"password"` | `direct_mem0.py:103`, `mem0.py:64`, `easy.py:151`, `memory_handler.py:161` | Fixed — auto-generates `secrets.token_urlsafe(16)` with warning |
| Webhook secret plaintext storage | `webhook_stores.py:149–186` | Fixed — Fernet-encrypted, masked in `to_dict()` |
| FTS5 SQL injection in `where_sql` | `memory/adapters/fts5.py:225–265` | False positive — hardcoded clause strings + parameterized `?`; `nosec B608` is correct |
| JSON metadata key injection | `memory/adapters/sqlite.py:30–45` | Fixed — `_validate_metadata_key()` enforces `[a-zA-Z0-9_-]` only |
| CORS wildcard open | `server.py:2350–2395` | Correct design — wildcard only if `CUTCTX_CORS_ORIGINS=*` is explicitly set |
| Gemini savings TODO | `proxy/handlers/gemini.py:635–660` | Resolved — uses `original_tokens` with explanatory comment |
| SmartCrusher `NotImplementedError` | `transforms/smart_crusher.py:265–285` | Intentional fail-loud for unsupported custom scorer args; not a bug |
| `CUTCTX_ALLOW_DEBUG` auth bypass | `security/antidebug.py:25–50` | Not a bypass — disables ptrace check only; loopback-only guard ignores flag if non-loopback addrs present |

---

## Real Remaining Issues

### Phase 1 — Security (Priority: ship-blocker, ~1 day)

---

#### 1.1 Loopback Open Paths Include Non-Health Endpoints

**File:** `cutctx/proxy/server.py`  
**Line:** 213

**Current code:**
```python
_LOOPBACK_OPEN_PATHS = frozenset({"/livez", "/readyz", "/metrics", "/dashboard", "/api/savings", "/api/models"})
```

**Problem:** `/dashboard`, `/api/savings`, and `/api/models` bypass auth for any unauthenticated GET/HEAD from 127.0.0.1. In a multi-tenant or containerized deployment, anything on the same host can read these endpoints without credentials.

**Fix:**
```python
_LOOPBACK_OPEN_PATHS = frozenset({"/livez", "/readyz", "/metrics"})
```

`/dashboard`, `/api/savings`, `/api/models` should require a valid auth token even from loopback. The RBAC checker already handles authenticated loopback requests correctly.

**Verification:** `curl -s http://localhost:4000/dashboard` should return 401 after fix.

---

#### 1.2 LIKE Wildcard Injection in Entity Reference Filter

**File:** `cutctx/memory/adapters/sqlite.py`  
**Lines:** 490–496

**Current code:**
```python
if filter.entity_refs is not None and len(filter.entity_refs) > 0:
    entity_conditions = []
    for entity_ref in filter.entity_refs:
        # Use JSON contains check
        entity_conditions.append("entity_refs LIKE ?")
        params.append(f'%"{entity_ref}"%')
```

**Problem:** If `entity_ref` contains `%` or `_`, it becomes a LIKE wildcard. A value like `foo%` will match any entity reference starting with `foo`, leaking memory entries across agents/users that share a SQLite store.

**Fix:**
```python
def _escape_like(value: str, escape_char: str = "\\") -> str:
    return value.replace(escape_char, escape_char * 2).replace("%", f"{escape_char}%").replace("_", f"{escape_char}_")

# In the filter block:
for entity_ref in filter.entity_refs:
    entity_conditions.append(f'entity_refs LIKE ? ESCAPE "\\"')
    params.append(f'%"{_escape_like(entity_ref)}"%')
```

Add `_escape_like` as a module-level helper near the top of `sqlite.py`. The `ESCAPE "\\"` clause tells SQLite which character to treat as the escape prefix.

**Verification:** Test with `entity_ref = "test%injection"` — should return zero results when no entity named exactly `test%injection` exists.

---

#### 1.3 Kompress ONNX No Maximum Input Guard (DoS Vector)

**File:** `cutctx/transforms/kompress_compressor.py`  
**Lines:** 781–789

**Current code:**
```python
words = content.split()
n_words = len(words)

if n_words < 10:
    return self._passthrough(content, n_words)

try:
    model, tokenizer, backend = _load_kompress(...)
```

**Problem:** No upper bound on input size. Content with 50,000+ words is fed directly into ONNX inference, causing 45+ second processing times and blocking the inference semaphore for all other requests. This is a trivial DoS vector for any authenticated user.

**Fix** — add immediately after the `n_words < 10` check:
```python
if n_words < 10:
    return self._passthrough(content, n_words)

# Guard against ONNX inference timeout / DoS on very large inputs.
# 80,000 words ≈ 600KB of text; above this, passthrough is safer than a 45s+ stall.
_MAX_KOMPRESS_WORDS = int(os.environ.get("CUTCTX_KOMPRESS_MAX_WORDS", "80000"))
if n_words > _MAX_KOMPRESS_WORDS:
    logger.warning(
        "kompress: input (%d words) exceeds CUTCTX_KOMPRESS_MAX_WORDS=%d, passing through",
        n_words,
        _MAX_KOMPRESS_WORDS,
    )
    return self._passthrough(content, n_words)
```

The env var allows operators to tune the limit without a code change. The same guard should be added at line 1030 in `compress_batch` where `len(words) < 10` already exists.

**Verification:** Submit a 100,000-word payload to `/v1/compress` with `model=kompress` — should return in <1s with passthrough result.

---

#### 1.4 Add CUTCTX_ALLOW_DEBUG Startup Warning

**File:** `cutctx/proxy/server.py`  
**Location:** `startup()` method, after line 1183 (`logger.info("Cutctx Proxy started")`)

**Problem:** When `CUTCTX_ALLOW_DEBUG=1` is set, there is no visible warning in proxy startup output. Operators may inadvertently run production with this flag set.

**Fix** — add after the "Cutctx Proxy started" log line:
```python
import os as _os
if _os.environ.get("CUTCTX_ALLOW_DEBUG", "").strip() in ("1", "true", "yes"):
    logger.warning(
        "⚠️  CUTCTX_ALLOW_DEBUG is set — ptrace/debugger guard is DISABLED. "
        "Do NOT run in production with this flag."
    )
```

(`os` is already imported at the module level — remove the alias import and use the existing `os` reference.)

---

### Phase 2 — Code Quality (~1 day)

---

#### 2.1 Ruff Lint Errors

**Run:**
```bash
cd /path/to/cutctx
ruff check --fix cutctx/
ruff check cutctx/  # review any remaining that require manual fix
```

The majority of the ~275 errors are auto-fixable (unused imports, whitespace, formatting). Manually fix any remaining `E501` (line length) or `SIM` (simplification) warnings that ruff doesn't auto-resolve.

Commit separately from logic changes for clean git history.

---

#### 2.2 42 Test Failures — Rename Artifact Imports

**Root cause:** Tests import `CutctxMode`, `CutctxConfig`, or `CutctxTracer` but these were renamed/moved. The symbol is not found at the import path the test references.

**Find affected tests:**
```bash
grep -rn "CutctxMode\|CutctxConfig\|CutctxTracer" tests/ --include="*.py" -l
```

**Files confirmed affected:**
- `tests/conftest.py`
- `tests/test_cache/test_client_integration.py`
- `tests/test_observability_tracing.py`
- `tests/test_integrations/langchain/test_chat_model.py`
- `tests/test_integrations/agno/test_model.py`
- `tests/test_integrations/agno/test_hooks.py`
- `tests/test_compression_decision.py`
- `tests/integrations/test_strands/test_model.py`
- `tests/integrations/test_strands/test_model_unit.py`
- `tests/integrations/test_strands/test_hooks_unit.py`

**Fix:** For each file, update the import path to the current module location. Run `python -c "from cutctx import CutctxMode"` (and similar) to confirm the correct import path, then do a project-wide find-and-replace.

---

#### 2.3 22 Test Failures — Rust Parity Golden Fixture Drift

**Root cause:** Rust core output has changed (likely compression ratio tuning or output formatting) but Python-side golden fixtures haven't been regenerated.

**Fix:**
```bash
# Regenerate golden fixtures
pytest tests/ -k "rust_parity or golden" --snapshot-update
# Review the diff before committing
git diff tests/
```

If `--snapshot-update` isn't the project's convention, look for a `make update-fixtures` or similar target in the `Makefile`.

---

### Phase 3 — Test Coverage (~1–2 days)

---

#### 3.1 7 DSR/Dashboard MCP Test Failures — App Init

These tests fail because the test app context isn't initialized correctly for the DSR or dashboard MCP handler. Check the fixture in the relevant test file for a missing `await app.startup()` or unconfigured `_rbac_checker_ref`. Fix the test fixture, not the application code.

---

#### 3.2 4 Playwright Test Failures — Missing Chromium

```bash
playwright install chromium
```

Then re-run the Playwright suite. If CI doesn't have a display, prefix with `xvfb-run -a`.

---

#### 3.3 12 Miscellaneous Pre-existing Failures

Run with `-v` to get individual failure messages:
```bash
pytest tests/ -x --ignore=tests/playwright -q 2>&1 | grep FAILED
```

Triage each — most are likely fixture setup or missing optional dependencies. Fix or `pytest.mark.skip` with a tracked issue for anything that requires a larger refactor.

---

### Phase 4 — Documentation (0.5 day)

---

#### 4.1 CORS Production Guidance

Add to `docs/deployment.md` (or equivalent operator guide):

> **Required for production:** Set `CUTCTX_CORS_ORIGINS` to your frontend domain(s), e.g.:
> ```
> CUTCTX_CORS_ORIGINS=https://app.yourcompany.com
> ```
> If `CUTCTX_CORS_ORIGINS` is not set, CORS is restrictive by default. Setting it to `*` permits all origins and should only be used in controlled internal environments.

---

#### 4.2 CUTCTX_ALLOW_DEBUG Operator Documentation

Add to `docs/configuration.md` or the env-vars reference:

> **`CUTCTX_ALLOW_DEBUG`** (default: unset)  
> When set to `1`, disables the ptrace/debugger presence check. Intended for local development and CI profiling only. The proxy will log a warning at startup if this flag is detected. **Never set in production.**

---

#### 4.3 Update CHANGELOG.md

Add a `v0.29.1` entry covering:
- Loopback path tightening (`/dashboard`, `/api/savings`, `/api/models` now require auth)
- LIKE wildcard escape for entity reference filters
- Kompress max-input guard (`CUTCTX_KOMPRESS_MAX_WORDS`, default 80,000)
- `CUTCTX_ALLOW_DEBUG` startup warning
- Ruff lint cleanup
- Test suite: fixed 42 rename-artifact import failures, 22 golden fixture updates

---

## Summary

| # | Item | File | Lines | Effort | Severity |
|---|---|---|---|---|---|
| 1.1 | Trim loopback open paths | `proxy/server.py` | 213 | 1 line | **Critical** |
| 1.2 | LIKE wildcard escape | `memory/adapters/sqlite.py` | 490–496 | ~8 lines | **Critical** |
| 1.3 | Kompress max-input DoS guard | `transforms/kompress_compressor.py` | 784, 1030 | ~10 lines | **High** |
| 1.4 | ALLOW_DEBUG startup warning | `proxy/server.py` | ~1184 | ~6 lines | Medium |
| 2.1 | Ruff lint fixes | `cutctx/**` | many | `ruff --fix` | Medium |
| 2.2 | Rename artifact import fixes | `tests/**` (10 files) | — | ~1 hr | Medium |
| 2.3 | Rust parity fixture regen | `tests/**` | — | `--snapshot-update` | Medium |
| 3.1 | DSR/dashboard test fixtures | `tests/**` | — | ~2 hrs | Low |
| 3.2 | Playwright Chromium install | CI config | — | 1 command | Low |
| 3.3 | Misc 12 test failures | `tests/**` | — | triage | Low |
| 4.x | Docs: CORS, ALLOW_DEBUG, CHANGELOG | `docs/`, `CHANGELOG.md` | — | ~2 hrs | Low |

**Phase 1 (items 1.1–1.4) is the only hard blocker for production release.** The code changes are small (<30 lines total). Phases 2–4 should be completed before a public commercial announcement but are not deployment-blockers.

## 2026-06-30 Incident Addendum

- User-reported symptom: Cutctx-enabled traffic returned `{"detail":"Bad Request"}`. Disabling Cutctx removed the failure.
- Most likely cause in the current worktree was the uncommitted ChatGPT Codex `Responses` compatibility change in [cutctx/proxy/handlers/openai/responses.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/handlers/openai/responses.py).
- The risky behavior change was:
- removing `stream` from the ChatGPT subscription unsupported-field strip list
- removing the defensive `is_chatgpt_auth -> stream = False` override for HTTP `Responses` traffic
- That path previously documented that chatgpt.com can reject HTTP `stream:true` with a bare `400`, so the safer assumption is to keep the non-streaming HTTP path unless re-verified live.
- Fix applied:
- restored `stream` to `_CHATGPT_SUBSCRIPTION_UNSUPPORTED_RESPONSE_FIELDS`
- restored the defensive `stream = False` behavior for `is_chatgpt_auth`
- updated compatibility coverage in [tests/test_openai_responses_subscription_compat.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/tests/test_openai_responses_subscription_compat.py)
- Verification:
- `uv run python -m pytest -q tests/test_openai_responses_subscription_compat.py` → `4 passed`
- `uv run python -m pytest -q tests/test_provider_codex_runtime.py -k 'responses or codex'` → `5 passed`
- Separate note: the stack-graph pre-compress hook remains a performance-risk area, but it is a weaker match for this specific plain-400 symptom than the `Responses` request-shape regression above.

## 2026-07-01 Runtime App Verification Addendum

- Drove verification through the local CLI path:
- `CUTCTX_ADMIN_API_KEY=test-admin-key uv run python -m cutctx.cli.main proxy --host 127.0.0.1 --port 4011 --no-optimize --no-cache --no-rate-limit --workers 1`
- Found a structural regression in [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/cutctx/proxy/server.py):
- the file defines `create_app` twice
- Python exports the second definition (`co_firstlineno=4753`)
- that exported runtime app had dropped `/debug/tasks`, `/debug/ws-sessions`, and `/debug/warmup`
- the same exported runtime app also left `/stats`, `/stats-history`, and `/dashboard` publicly readable even when `CUTCTX_ADMIN_API_KEY` was set
- Fixes applied to the exported runtime `create_app`:
- restored `/debug/tasks`, `/debug/ws-sessions`, and `/debug/warmup`
- restored the runtime payload helper used by `/debug/warmup`
- added a shared admin-auth check for `/stats`, `/v1/stats`, `/stats-history`, `/dashboard`, and `/stats/reset`
- added regression coverage in [tests/test_runtime_app_admin_auth.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/tests/test_runtime_app_admin_auth.py)
- Verification:
- `uv run python -m pytest -q tests/test_runtime_app_admin_auth.py tests/test_proxy_debug_endpoints.py tests/test_security_validations.py tests/test_openai_responses_subscription_compat.py` → `47 passed`
- `python3 -m py_compile cutctx/proxy/server.py` → passed
- live restarted CLI proxy checks:
- `/stats` without admin key → `401`
- `/dashboard` without admin key → `401`
- `/stats` with `X-Cutctx-Admin-Key` → `200`
- `/dashboard` with `X-Cutctx-Admin-Key` → `200`
- `/debug/warmup` on loopback → `200`

## 2026-07-01 Broad Sweep Addendum

- Continued a broad non-Playwright `pytest -x` sweep after the runtime-app fixes.
- Confirmed the sweep moved materially farther after each repair:
- first blocker fixed: runtime `/debug/*` routes missing from exported `create_app`
- next blocker fixed: exported app left `/stats`, `/stats-history`, and `/dashboard` public despite admin key
- next blocker fixed: exported app dropped `/v1/retrieve`, `/v1/retrieve/stats`, and `GET /v1/retrieve/{hash}` CCR surfaces
- next blocker fixed: `cutctx unwrap codex` safe no-op with explicit `CODEX_HOME` still emitted unrelated proxy-port warning
- next blocker fixed: exported `/stats` and `/admin/config/flags` lacked the `config.orchestrator` contract the dashboard tests expect
- Additional regression coverage added:
- [tests/test_runtime_app_admin_auth.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/tests/test_runtime_app_admin_auth.py)
- [tests/test_sqlite_like_escaping.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/tests/test_sqlite_like_escaping.py)
- [tests/test_transforms/test_kompress_max_words.py](/Users/aryansingh/Documents/Claude/Projects/cutctx/tests/test_transforms/test_kompress_max_words.py)
- Verification slices now green:
- `uv run python -m pytest -q tests/test_runtime_app_admin_auth.py tests/test_proxy_debug_endpoints.py tests/test_security_validations.py tests/test_openai_responses_subscription_compat.py` → `47 passed`
- `uv run python -m pytest -q tests/test_sqlite_like_escaping.py tests/test_transforms/test_kompress_max_words.py tests/test_security_validations.py tests/test_transforms/test_kompress_compressor.py` → `43 passed`
- `uv run python -m pytest -q tests/test_dashboard_orchestrator.py tests/test_cli/test_wrap_codex.py::test_unwrap_codex_is_safe_noop_with_explicit_codex_home tests/test_ccr_row_drop_store_bridge.py::test_v1_compress_then_v1_retrieve_resolves_marker_hash` → `3 passed`
- Broad sweep evidence after these fixes:
- `uv run python -m pytest tests/ -x --ignore=tests/playwright -q` reached `1962 passed, 48 skipped` before the orchestrator contract failure, which is now fixed


#### 2026-07-01 checkpoint
- Broad non-Playwright suite was re-run from scratch and previous blockers were fixed rather than waived.
- Confirmed/fixed in the exported runtime `create_app()`:
- mounted missing modular routes so runtime app now exposes tested admin/privacy surfaces:
  - `/v1/dsr/*`
  - `/v1/residency/*`
  - `/v1/airgap/*`
  - `/v1/rate_limit/*`
  - `/v1/rbac/*`
  - `/v1/secrets/*`
  - `/v1/sso/*`
  - `/v1/memory/*`
  - `/v1/spend/*`
  - `/v1/policies/*`
  - `/v1/admin/mfa/*`
- DSR blocker root cause was real runtime-surface drift:
  - `/v1/dsr/*` fell through to catch-all passthrough before fix.
- Route-module failures were real runtime-surface drift too:
  - modular routers existed and had tests, but the exported runtime app had not mounted them.
- Active runtime factory uses `_require_local_admin_auth`, not the older `_require_admin_auth`.
  - Mounts were adjusted to use the active helper.
- The global RBAC dependency helper in current file shape is not trustworthy for the exported runtime app:
  - it references `_authenticate_admin_request`, which raised `NameError` in route-module requests.
  - as a correctness-first stopgap for the exported runtime app, the newly mounted modular routers currently use working admin auth and `require_rbac_permission=None` rather than a broken RBAC dependency path.
- Test pollution blocker fixed:
  - `tests/test_proxy_dynamic_init.py` had been mutating `sys.modules` at import time with `MagicMock()` replacements for episodic-memory modules.
  - That contaminated later tests and caused `tests/test_episodic_memory_extractor.py::TestEpisodicMemoryStore::test_save_and_load` to import mocks instead of the real store.
  - test rewritten so mocks are scoped with `monkeypatch` inside the test.

#### 2026-07-01 evidence added
- `uv run python -m pytest -q tests/test_dsr_endpoints.py tests/test_route_modules.py tests/test_memory_service_routes.py`
  - `33 passed`
- `uv run python -m pytest -q tests/test_proxy_dynamic_init.py tests/test_episodic_memory_extractor.py::TestEpisodicMemoryStore::test_save_and_load`
  - `2 passed`
- Fresh broad suite restart after those fixes progressed past:
  - route modules
  - DSR
  - episodic memory
  - Graphify index tests
  - into later integration surfaces (`~37%` at last checkpoint)

#### 2026-07-01 runtime stats/health recovery
- Exported runtime `create_app()` now restores tested `/health`, `/livez`, `/readyz`, and `/stats` contracts instead of the reduced runtime-only payload.
- Repaired runtime health surfaces:
  - restored `checks`, `runtime`, `rust_core`, `rust_core_error`, deployment metadata, and backwards-compatible `config`
  - re-added local upstream readiness probe/cache and wired `/readyz` plus `/health` to refresh it
  - restored rust-core degraded-mode reporting through `_check_rust_core()`
- Repaired CCR runtime surfaces:
  - `/v1/retrieve/stats` now serializes `recent_retrievals` safely
  - `/v1/retrieve` and `GET /v1/retrieve/{hash}` preserve expected full/query response shape and expired-vs-missing detail
- Repaired runtime `/stats` payload drift:
  - restored `compression_cache`
  - restored `savings.per_project`
  - preserved `otel` and `langfuse`
- Focused verification added:
  - `uv run python -m pytest -q tests/test_proxy_ccr.py -k 'stats_tracks_retrievals or stats_empty_store or stats_exposes_env_configured_ttl or stats_with_entries'` -> `4 passed`
  - `uv run python -m pytest -q tests/test_proxy_compression_executor.py::test_compression_executor_metrics_appear_in_runtime_payload tests/test_rust_core_smoke.py tests/test_proxy_healthchecks.py` -> `14 passed`
  - `uv run python -m pytest -q tests/test_proxy_modes.py::test_stats_reports_configured_mode_for_compression_cache` -> `1 passed`
  - `uv run python -m pytest -q tests/test_proxy_project_savings.py::test_funnel_attributes_savings_from_context_and_stats_exposes_them` -> `1 passed`
- Broad non-Playwright backend sweep evidence:
  - `uv run python -m pytest tests/ -x --ignore=tests/playwright -q` reached `75%` with `5687 passed` and `213 skipped` before the `savings.per_project` blocker
  - `savings.per_project` blocker is now fixed; a fresh broad rerun is currently in progress from latest workspace state

#### 2026-07-01 release-readiness checkpoint
- Broad non-Playwright backend suite now passes from current workspace state:
  - `uv run python -m pytest tests/ -x --ignore=tests/playwright -q`
  - result: `7565 passed, 285 skipped, 22 warnings`
- Dashboard production build passes:
  - `cd dashboard && npm run build`
- Additional late-suite `/stats` and release metadata fixes completed during final sweep:
  - restored telemetry beacon initialization in exported runtime `create_app()` so `CUTCTX_SDK` defaults/overrides are reflected correctly
  - restored root `/stats` fields:
    - `compressions_by_strategy`
    - `tokens_saved_by_strategy`
    - `anon_telemetry_shipping`
  - aligned `.release-please-manifest.json` with `pyproject.toml` version `0.29.0`
- Remaining warnings in the broad suite are non-fatal and mostly third-party deprecations / async mock warnings; no failing test remained after final sweep

#### 2026-07-01 optional-stack and audio follow-up
- Replaced `cutctx/transforms/audio_compressor.py` stub with a real WAV-oriented compressor primitive:
  - trims leading/trailing silence
  - downmixes stereo to mono
  - downsamples to a target speech-friendly sample rate
  - only returns compressed output when savings are meaningful
- Added targeted verification in `tests/test_audio_compressor.py`
  - invalid base64 fallback
  - threshold bypass
  - real byte-reducing compression path
- Installed optional packages in the project venv and converted some prior skips into executed coverage:
  - `usearch`
  - `mistral-common`
  - `strands-agents`
- Verified newly unskipped or relevant optional suites:
  - `uv run python -m pytest -q tests/test_usearch_backend.py tests/test_tokenizers.py -k 'usearch or mistral'` -> `42 passed`
  - `uv run python -m pytest -q tests/test_audio_compressor.py tests/test_modality_matrix.py tests/test_docs_truthfulness.py tests/test_usearch_backend.py tests/test_tokenizers.py` -> `110 passed`
- Strands integration no longer blocked by missing local package; current remaining skip reason is external credentials only:
  - `uv run python -m pytest -q tests/integrations/test_strands/test_hooks.py -rs`
  - result: `9 skipped`, all due to `AWS credentials not available`
- Remaining major skipped categories are now predominantly credential-gated live integrations:
  - OpenAI
  - Anthropic
  - Gemini
 - AWS Bedrock / Strands
- Current follow-up status on dashboard stats + audio:
 - Dashboard local-dev stats path hardened in `dashboard/src/lib/api.js`.
 - When `VITE_CUTCTX_PROXY_URL` points at localhost on a different origin than the Vite app, the dashboard now falls back to same-origin relative requests so the Vite proxy can serve `/stats`, `/health`, and `/stats-history` without CORS breakage.
 - Audio capability is now split and documented truthfully:
 - Dedicated `/v1/audio/*` routes remain strict pass-through for fidelity/security.
 - Inline WAV audio embedded inside multimodal chat payloads now has a concrete optimization path via `cutctx/transforms/audio_messages.py`.
 - Live handler wiring added in:
 - `cutctx/proxy/handlers/openai/chat.py`
 - `cutctx/proxy/handlers/anthropic.py`
 - `cutctx/proxy/handlers/openai/compress.py`
 - Focused verification for that work:
 - `uv run python -m py_compile cutctx/proxy/handlers/anthropic.py cutctx/proxy/handlers/openai/chat.py cutctx/proxy/handlers/openai/compress.py cutctx/transforms/audio_messages.py cutctx/proxy/models.py`
 - `uv run python -m pytest -q tests/test_audio_compressor.py tests/test_inline_audio_messages.py tests/test_proxy_compress_endpoint.py tests/test_handler_outcome_tag_invariant.py tests/test_modality_matrix.py -q` -> `49 passed`
 - `uv run python -m pytest -q tests/test_dashboard_overview_lifetime_headline.py tests/test_dashboard_savings_by_model.py tests/test_dashboard_surfaces_playwright.py -q` -> `3 passed`
 - `cd dashboard && npm run build` -> passed
