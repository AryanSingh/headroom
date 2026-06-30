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

### Task Ledger

| Task | Status | Evidence | Notes |
|---|---|---|---|
| Establish handoff log and commit discipline | In progress | This file | Must commit immediately after this update |
| Re-verify high-risk runtime paths | Pending |  | Focus on proxy startup, health, stats, routing, streaming |
| Re-verify new USearch and stack-graph work | Pending |  | Do not trust implementation without tests/builds |
| Re-verify dashboard stats and operator surfaces | Pending |  | Must validate UI with live backend payloads |
| Refresh release verdict and remaining risks | Pending |  | Final task after independent verification |

### Next Actions

1. Commit this tracker update as the first checkpoint.
2. Inspect and verify the new USearch and stack-graph changes already present in the worktree.
3. Run targeted compile/tests before making any runtime edits.

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
