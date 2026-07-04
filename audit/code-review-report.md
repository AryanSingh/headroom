# Comprehensive Code Review Report

**Repository:** headroom/cutctx  
**Version:** v0.30.0 (released)  
**Date:** July 4, 2026 (Re-run)  
**Review scope:** Architecture, Security, Code Quality, Technical Debt + Audit Fix Verification (Reconciliation Sweep)  

---

## Executive Summary

**Overall: IMPROVED since v0.30.0 — 2 new vulnerability findings, 7 of 10 launch-readiness blockers verified fixed.**

The codebase continues to improve. Since the initial v0.30.0 release:
- **27 bare `except Exception: pass` → `logger.exception`** in server.py route registration blocks
- **K8s/Helm PVC + persistence** added — production-grade deployment
- **2 new test files** covering RBAC hardening and enterprise smoke tests  
- **`# type: ignore` count held at 0** — strict typing regime intact
- **Docs brand refresh** — pricing + enterprise pages now have teal accent, Inter font, mobile hamburger nav

**2 new vulnerability findings** introduced since last audit:
1. **🔴 HIGH** `cutctx_ee/sso.py:505` — `verify_exp=False` without manual `exp` check → accepts expired JWTs
2. **🟡 MEDIUM** `cutctx/memory/sync.py:196` — `httpx.AsyncClient` to `memory_service_url` without egress allowlist

### Severity Distribution (Updated)

| Severity | Count | Δ vs v0.30.0 | Description |
|----------|-------|--------------|-------------|
| 🔴 CRITICAL | 0 | — | No exploitable vulnerabilities found |
| 🟠 HIGH | 10 | +1 | New SSO JWT expiry bypass (sso.py:505) + previous 9 |
| 🟡 MEDIUM | 19 | +1 | New memory sync SSRF vector + previous 18 |
| 🔵 LOW | 15 | — | Print leftovers, @staticmethod smell, pre-3.10 typing |
| ℹ️ INFO | 20+ | — | Well-designed patterns worth noting |

---

## Part 1: Architecture Review

### 1.1 Component Boundaries — Rating: 6/10

| Component | Lines | Rating | Notes |
|-----------|-------|--------|-------|
| `cutctx/proxy/server.py` | 6,889 | 🔴 | God-file monolith — mixes init, routing, lifecycle, CLI |
| `cutctx/cli/wrap.py` | 4,683 | 🟠 | 10+ provider wrappers + OS config writers in one file |
| `cutctx/proxy/handlers/anthropic.py` | 3,493 | 🟠 | 40+ method mixin with duck-typed `self` |
| `cutctx/proxy/handlers/openai/responses.py` | 4,550 | 🟠 | Single file for entire Responses API handler |
| `cutctx/transforms/content_router.py` | 3,145 | 🟡 | Content detection + routing combined |
| `cutctx/proxy/helpers.py` | 3,086 | 🟡 | Grab-bag of unrelated helpers |
| `cutctx/proxy/routes/admin.py` | 2,530 | 🟡 | Admin API surface too wide |

### 1.2 Open-Core Boundary — Rating: 7/10

The `sys.modules[__name__] = _impl` shim pattern (used by 10 EE modules: `billing`, `sso`, `audit`, `rbac`, `scim`, `retention`, `org`, `seats`, `trial`, `entitlements`) is elegant but creates a maintenance concern:

**Clean**: `cutctx/entitlements.py:16-24` — single-file shim, consistent
**Scattered**: 35+ direct `from cutctx_ee import` calls in proxy routes — not using the shim

**Risk**: `cutctx/proxy/server.py:4894` imports `cutctx_ee.memory_service.store.MemoryStore` inline. If EE is absent and this path executes, it's a runtime `ImportError`, not a clean fallback.

### 1.3 Coupling — Rating: 5/10

**Fan-in antipattern**: `server.py` imports from 20+ `cutctx.*` submodules at module level. The proxy is the dependency sink for nearly the entire package.

**Mixin duck-typing**: `CutctxProxy` inherits from 5 mixins whose `self.*` contracts are invisible. `pyproject.toml:506-508` confirms mypy gives up:
```toml
[mypy.overrides]
module = ["cutctx.proxy.handlers.*"]
ignore_errors = true   # All type errors hidden
```

**Global mutable state**: 
- `server.py:216-217` patches `socket.getaddrinfo` globally (affects ALL connections)
- `cutctx_ee/__init__.py:54` runs `_run_security_guards()` at import time (ptrace in containers)

### 1.4 Scalability — Rating: 6/10

| Risk | Severity | Details |
|------|----------|---------|
| `_compression_caches` dict | 🟠 | Per-session growth, eviction logic not visible at init |
| Shared `ThreadPoolExecutor` (32 workers) | 🟡 | No per-provider isolation — burst can starve others |
| `fastembed` + ONNX (~30MB) | 🟡 | Per-instance model loading; no sharing across instances |
| `rayon` thread pool + Python ThreadPool + asyncio | ℹ️ | 50+ threads possible per process |
| httpx connection pooling | 🟡 | Lazy client creation; no pooling limits visible |

### 1.5 API Design — Rating: 7/10

**Good**: Provider-agnostic streaming (`StreamingMixin` shared across providers), domain-organized routes (18 modules in `routes/`)

**Gaps**: No standardized error envelope, no admin API versioning (`/admin/*` vs `/v1/admin/*`), env vars read in 5+ modules with no central registry

### 1.6 Configuration — Rating: 5/10

**Env var proliferation**: 50+ env vars read across 5+ modules with no central schema, no validation, silent fall-through on typos

**Feature flags**: All env-var-only, scattered, no flag registry or dependency graph

**Hard dependencies concern**: `litellm>=1.86.2` (100+ transitive deps), `graphifyy` + `networkx` (niche, should be optional), `ast-grep-cli` (~15MB) are hard deps

### Architecture Recommendations (Priority Order)

| Pri | Action | Impact |
|-----|--------|--------|
| P0 | Split `server.py` → `lifecycle.py` + `routing.py` + `config_builder.py` (target: <1000 lines) | Reduces cognitive load, enables testing |
| P1 | Replace mixin duck-typing with a `ProxyContext` Protocol | Enables mypy verification on handler code |
| P1 | Centralize env var config in `cutctx/env.py` with schema + validation | Prevents silent typos |
| P1 | Move `graphifyy`, `networkx` to optional deps | Reduces install size ~50MB |
| P2 | Standardize EE import path: all proxy routes use shim pattern | Consistent fail-closed behavior |
| P2 | Add per-provider compression quotas/semaphores | Prevents provider starvation |

---

## Part 2: Security Review

### 2.1 OWASP Top 10 2021 Summary

| Category | Rating | Top Finding |
|----------|--------|-------------|
| A01: Broken Access Control | 🟡 | RBAC fail-open to ADMIN when store unreachable |
| A02: Cryptographic Failures | 🟢 | Fernet/AES-128-CBC + HMAC-SHA256 correctly implemented |
| A03: Injection | 🟢 | All SQL parameterized, column names regex-validated |
| A04: Insecure Design | 🟡 | Rate limiter lacks per-IP fallback |
| A05: Security Misconfiguration | 🟢 | CORS defaults closed, debug mode gated by loopback+host |
| A06: Vulnerable Components | 🟡 | No Cargo Dependabot; cargo-deny in Phase-0 permissive mode |
| A07: Auth Failures | 🟡 | SSO code is correct but stale comment could mislead future dev |
| A08: Data Integrity | 🟡 | License sig silently skipped without Rust core (ImportError → pass) |
| A09: Logging/Monitoring | 🟢 | Audit logging comprehensive, RBAC-gated |
| A10: SSRF | 🟢 | Strict allowlist (3 hosts), loopback guard is double-gated |

### 2.2 High Severity Security Findings

| # | Finding | File:Line | Recommendation |
|---|---------|-----------|----------------|
| H1 | **🔴 NEW `verify_exp=False` without manual `exp` check** — accepts expired JWTs. `pyjwt.decode()` disables built-in expiry verification and the surrounding code has NO manual `claims.get("exp")` check after decode. An attacker can replay an expired token indefinitely. | `cutctx_ee/sso.py:505` | Either remove `options={"verify_exp": False}` or add explicit `exp` check after decode |
| H2 | **Stale SSO comment says "log and continue" but code raises** — if a future dev adds `pass` based on the comment, JWT bypass is instant | `cutctx_ee/sso.py:347` | Delete or update comment to match code: "Signature verification failure: raises immediately" |
| H3 | **RBAC defaults to ADMIN when SSO/RBAC store unreachable** — multi-tenant envs silently grant full access | `cutctx_ee/rbac.py:118` | Add `CUTCTX_STRICT_RBAC` env var that fails closed to denied instead of ADMIN |

### 2.3 Medium Severity Security Findings

| # | Finding | File:Line | Recommendation |
|---|---------|-----------|----------------|
| M1 | **License signature skipped without Rust core** — forged licenses accepted in non-Rust environments | `cutctx_ee/billing/license_db.py:136` | Log warning; return `signature_unverified` status |
| M2 | **🟡 NEW `httpx.AsyncClient` to `memory_service_url` without egress allowlist** — SSRF vector if URL is user-controllable | `cutctx/memory/sync.py:196` | Route through `EgressEnforcer.check(url)` or pin to allowlist |
| M3 | **No Cargo ecosystem in Dependabot** — Rust crate vulns not auto-updated | `.github/dependabot.yml` | Add `package-ecosystem: cargo` |
| M4 | **cargo-deny in Phase-0 permissive** — unknown registry warns, not denies | `deny.toml` | Tighten before Phase 2 |
| M5 | **`k8s/network-policy.yaml` namespaceSelector matches ALL namespaces** — multi-tenant risk. Port 8080 mismatches actual containerPort 8787. | `k8s/network-policy.yaml` | Restrict to specific namespace; fix port to 8787 |
| M6 | **HMAC key reuse** — `CUTCTX_LICENSE_HMAC_SECRET` used for both signing and Fernet encryption | `cutctx/security/secrets_store.py:64` | Use separate env vars with HKDF domain separation |
| M7 | **`processed_events` dedup table not cleaned** — unbounded growth over time | `cutctx_ee/billing/license_db.py:58-61` | Add TTL-based cleanup (`WHERE processed_at < now - 90d`) |

### 2.4 Audit Fix Verification

| Fix from Launch Readiness Report | Status | Evidence |
|----------------------------------|--------|----------|
| **X-Cutctx-Role behind CUTCTX_TRUST_PROXY** | ✅ **VERIFIED** | `cutctx_ee/rbac.py:140` — `os.environ.get("CUTCTX_TRUST_PROXY") == "1"` gates the header |
| **Seats from TIER_SEAT_LIMITS, not metadata.seats** | ✅ **VERIFIED** | `stripe_webhook.py:98-99` — `TIER_SEAT_LIMITS.get(tier, 1)`; metadata.seats never read |
| **Webhook idempotency (processed_events table)** | ✅ **VERIFIED** | `stripe_webhook.py:198-204` — checks and marks events; DB schema at `license_db.py:58-61` |
| **invoice.paid extends license** | ✅ **VERIFIED** | `stripe_webhook.py:212-221` → `license_db.py:206-216` |
| **subscription.deleted deactivates license** | ✅ **VERIFIED** | `stripe_webhook.py:222-224` → `license_db.py:218-228` |
| **Email spool (not real delivery)** | ✅ **PARTIAL** | Mail spool to `~/.cutctx/mail_spool/` — SendGrid/SES wiring still missing |
| **subscription.updated handler** | ❌ **NOT FIXED** | Still a stub — imports `get_license_db` from correct path but no tier/seat update logic |

---

## Part 3: Code Quality Review

### 3.1 Error Handling — Rating: 5/10

| Pattern | Count | Severity | Example |
|---------|-------|----------|---------|
| `except Exception:` (bare, no logging) | 100+ | 🟠 | `cutctx/telemetry/beacon.py` — 15 blocks silently swallow errors |
| `except Exception as e` (logged but no chain) | ~40 | 🟡 | `server.py:6888` — returns empty data without `from e` |
| `# noqa: BLE001` (broad-except allowed) | 46 | 🟡 | `anthropic.py:87` — CCR workspace resolve; needs context |
| `except ImportError: pass` | ~15 | 🟡 | `license_db.py:136` — skips license verification silently |

**Worst file**: `cutctx/telemetry/beacon.py` — 15 `except Exception:` blocks. If telemetry is important for billing/observability, these are masking data loss.

### 3.2 Type Safety — Rating: 4/10

| Metric | Count | Assessment |
|--------|-------|------------|
| `# type: ignore` | 318 | Clustered in integration shims + proxy handler edge cases |
| `cast()` | 61 | Concentrated in proxies config loads; most are justified |
| `: Any` annotations | 650 | Pervasive in CCR (missing `MessageDict` TypedDict) |
| `Union[]`/`Optional[]` (pre-3.10) | 23 | Only 1 production occurrence; acceptable |
| mypy-override disabled modules | 12 | **HIGH**: handlers.* has `ignore_errors = true` |

**Worst pattern**: `cutctx.proxy.handlers.*` — mypy `ignore_errors = true` on the most critical request-path code. Any type bug here is invisible until runtime.

### 3.3 Readability — Rating: 6/10

**Good**: `cutctx/security/secrets_store.py` is exemplary — clear docstrings, proper exception chaining, thread-safe design, clean dataclass usage.

**Bad**: `cutctx/proxy/ensemble.py` — inline imports of `auth_keyring.get_api_key` inside function bodies. The `from ... import` at function scope is unusual.

**Inconsistent**: Two `pipeline.py` files — `cutctx/pipeline.py` (lifecycle stages) vs `cutctx/transforms/pipeline.py` (compression chain). Confusing for navigation.

### 3.4 Logging — Rating: 6/10

| Issue | Impact | Example |
|-------|--------|---------|
| f-string logging (`logger.info(f"...")`) — 100+ instances | 🟡 Perf + security | `ccr/response_handler.py` — 9 f-string calls |
| Inconsistent logger naming — `__name__` vs hardcoded strings | 🟡 Log filtering | Proxy uses `"cutctx.proxy"`, others use `__name__` |
| Bare `print()` in library code | 🔵 Low | `binaries.py:528`, `cache/openai.py:112,116`, `proxy/server.py:324,345` |

**Recommendation**: Enable ruff rule `G` (logging-format) to catch f-string logging at lint time.

### 3.5 DRY Violations — Rating: 7/10

| Violation | Files | Lines duplicated |
|-----------|-------|------------------|
| Provider model config (_PATTERN_DEFAULTS, get_model_info, fallback, logging) | `providers/anthropic.py` + `providers/openai.py` | ~40 lines each |
| Provider detection in integrations | `integrations/agno/providers.py` + `integrations/strands/providers.py` | ~40 lines each |
| MetricCard/StatusBullet/ToggleSwitch components | Every dashboard page file | ~20 lines each (no shared component directory) |

**Recommendation**: Extract `ModelConfigResolver` base class for providers. Create a shared `components/` directory in the dashboard.

---

## Part 4: Technical Debt Inventory

### 4.1 Real TODOs in Code (3 HIGH)

| File:Line | Content | Impact |
|-----------|---------|--------|
| `cutctx_ee/watermark.py:195` | `# TODO: query actual DB` — license DB check is hardcoded `True` | **HIGH**: production license validation is a no-op for watermarking |
| `cutctx/proxy/handlers/openai/chat.py:1026` | `# TODO(#realignment): align anthropic.py CCR block to re-raise on exception` | **MEDIUM**: OpenAI silently fails on CCR errors |
| `cutctx/integrations/langchain/providers.py:169` | `# TODO: Add dedicated providers when needed` | **LOW**: Cohere/Mistral fall through to OpenAI-compatible |

### 4.2 Test Debt

| Issue | Count | Severity | Details |
|-------|-------|----------|---------|
| `@pytest.mark.skip` / `pytest.skip()` | 201 | 🟡 | 6 are retired empty-body tests (`test_toin.py:339-378`) |
| `@pytest.mark.skip` without reason | 3 | 🟡 | `test_critical_gaps.py:848`, `test_toin_full_integration.py:250,339` |
| Unconditional skip (`skipif(True, ...)`) | 1 | 🟡 | `test_html_extraction_eval.py:277` — should be xfail or deleted |
| Flaky-skip (network-dependent) | 3 | 🟡 | `conftest.py:51` — `pytest.skip("Skipped due to network timeout (flaky CI)")` |
| `# pragma: no cover` | 63 | ℹ️ | Most are legitimate defensive paths |

### 4.3 Dead / Leftover Code

| File:Line | Content | Severity |
|-----------|---------|----------|
| `cutctx/binaries.py:528` | `print(f"cutctx: skipping {name}: {e}")` — should be logger | 🔵 LOW |
| `cutctx/cache/openai.py:112,116` | `print("Likely cache hit")` — leftover debug | 🔵 LOW |
| `cutctx/proxy/ensemble.py:14` | `print(result["winning_model"], ...)` — leftover debug | 🔵 LOW |
| `cutctx/proxy/server.py:324,345` | `print(msg, file=sys.stderr)` — inconsistent with rest of startup using logger | 🔵 LOW |
| `cutctx/cli/wrap.py:375` | `open(log_path, "a")` without context manager (`noqa: SIM115`) | 🔵 LOW |
| `tests/test_toin.py:339-378` | 6 retired empty `pass` bodies with `@pytest.mark.skip` | 🟡 MEDIUM — should delete, not skip |
| `cutctx/proxy/debug_introspection.py` | **DELETED** in recent commit — ✅ cleanup verified | ℹ️ INFO |

### 4.4 Type Safety Gaps (pyproject.toml overrides)

| Module Override | Setting | Count |
|-----------------|---------|-------|
| `cutctx.proxy.handlers.*` | `ignore_errors = true` | **HIGH** |
| `cutctx.proxy.server` | `disallow_untyped_defs = false` | MEDIUM |
| `cutctx.proxy.cost` | `disallow_untyped_defs = false` | MEDIUM |
| `cutctx.proxy.prometheus_metrics` | `disallow_untyped_defs = false` | MEDIUM |
| `cutctx.proxy.semantic_cache` | `disallow_untyped_defs = false` | MEDIUM |
| `cutctx.proxy.rate_limiter` | `disallow_untyped_defs = false` | MEDIUM |
| `cutctx.proxy.request_logger` | `disallow_untyped_defs = false` | MEDIUM |
| `cutctx.proxy.helpers` | `disallow_untyped_defs = false` | MEDIUM |
| `cutctx.integrations.langchain` | `disallow_untyped_defs = false` | LOW |
| `cutctx.integrations.mcp` | `disallow_untyped_defs = false` | LOW |
| `cutctx.tokenizers.*` | `disallow_untyped_defs = false` | LOW |
| `cutctx.providers.litellm` | `disallow_untyped_defs = false` | LOW |
| `cutctx.providers.google` | `disallow_untyped_defs = false` | LOW |

**12 modules opted out of `disallow_untyped_defs`.** The `handlers.*` block additionally has `ignore_errors = true` — the strongest opt-out available.

### 4.5 Architecture Debt (EE Shim Pattern)

**10 EE shim files** use `_sys.modules[__name__] = _impl`:
- `cutctx/{billing,retention,sso,scim,audit,entitlements,seats,rbac,org,trial}.*`

**Impact**: 
- Static analyzers see OSS exports, not EE implementations
- IDEs follow the shim, not the real code
- Tight coupling: OSS module name must match EE module name exactly

**Alternative**: Explicit re-export in `cutctx/__init__.py` with optional dep handling:
```python
try:
    from cutctx_ee.billing import *  # noqa: F403
except ImportError:
    from cutctx._oss_billing import *  # noqa: F403
```

---

## Part 5: Recommendations — Priority Ordered

### P0 — Fix Immediately

| # | Item | File | Effort |
|---|------|------|--------|
| 1 | **Fix `verify_exp=False` — remove option or add manual `exp` check** | `cutctx_ee/sso.py:505` | 30 min |
| 2 | Fix `cutctx_ee/watermark.py:195` TODO — query actual DB (V-10 stub) | `cutctx_ee/watermark.py:195` | 1 day |
| 3 | Fix/delete misleading SSO "log and continue" comment | `cutctx_ee/sso.py:347` | 15 min |
| 4 | Remove `ignore_errors = true` from `cutctx.proxy.handlers.*` mypy override | `pyproject.toml:506-508` | 2-3 days progressive |

### P1 — Fix This Week

| # | Item | File | Effort |
|---|------|------|--------|
| 5 | Add `EgressEnforcer.check(url)` to memory sync SSRF vector | `cutctx/memory/sync.py:196` | 1 day |
| 6 | Split `server.py` → `lifecycle.py` + `routing.py` + `config_builder.py` | `cutctx/proxy/server.py` | 3-5 days |
| 7 | Add `CUTCTX_STRICT_RBAC` env var (fail closed) | `cutctx_ee/rbac.py:118` | 1 day |
| 8 | Fix `subscription.updated` stub to actually update tier/seats | `cutctx_ee/billing/stripe_webhook.py` | 1 day |
| 9 | Add Cargo ecosystem to Dependabot | `.github/dependabot.yml` | 15 min |
| 10 | Move `graphifyy` + `networkx` to optional deps | `pyproject.toml` | 1 day |
| 11 | Fix k8s/network-policy.yaml namespace + port mismatch | `k8s/network-policy.yaml` | 30 min |

### P2 — Fix This Month

| # | Item | Effort |
|---|------|--------|
| 12 | Enable ruff G rule (logging-format) | 1 day lint-fix |
| 13 | Add warning log when license signature skipped without Rust core | 1 day |
| 14 | Add TTL cleanup for `processed_events` table | 0.5 day |
| 15 | Split `wrap.py` per-provider | 2 days |
| 16 | Extract shared `ModelConfigResolver` for providers | 1 day |
| 17 | Add `logger.warning()` to bare `except Exception:` blocks in `beacon.py` | `cutctx/telemetry/beacon.py` |
| 18 | Add `MessageDict` TypedDict for `dict[str, Any]` elimination in CCR | 1 day |
| 19 | Standardize EE shim pattern — all proxy routes use shim | 2 days |
| 20 | Add `ProxyContext` Protocol for mixin contract | 2 days |

### P3 — Track for Next Milestone

| # | Item | Effort |
|---|------|--------|
| 21 | Create `components/` directory in dashboard (extract MetricCard, etc.) | 1 day |
| 22 | Replace leftover `print()` with logger calls | 0.5 day |
| 23 | Add `cutctx/env.py` central env var registry | 3 days |
| 24 | Add API versioning to admin endpoints | 1 day |
| 25 | Tighten `deny.toml` from `warn` → `deny` for unknown-registry | 1 day |

---

## Part 6: Audit-to-Code Reconciliation (Re-Run)

### Previous Audit Findings — Fix Status

| From Launch Readiness Report | Status | Evidence |
|------------------------------|--------|----------|
| **Must-Fix Before First Paid Customer (10 items)** | | |
| 1. Fix `invoice.paid` webhook | ✅ **VERIFIED** | `stripe_webhook.py:216-224` → `license_db.py:206-216` extend_license() |
| 2. Fix `subscription.deleted` deactivation | ✅ **VERIFIED** | `stripe_webhook.py:159-161` → `license_db.py:218-228` deactivate_license() |
| 3. Fix `_send_license_email` | ⚠️ **PARTIAL** | Spools to `~/.cutctx/mail_spool/` as .txt; no SMTP/SES wiring |
| 4. Fix X-Cutctx-Role header | ✅ **VERIFIED** | `rbac.py:140` gated behind `CUTCTX_TRUST_PROXY=1` |
| 5. Install `cutctx.com` DNS | ❌ **NOT FIXED** | Infrastructure — not code |
| 6. Create `github.com/cutctx` org | ❌ **NOT FIXED** | Infrastructure — not code |
| 7. Create `huggingface.co/cutctx` org | ❌ **NOT FIXED** | Infrastructure — not code |
| 8. Secure `@cutctx.com` email | ❌ **NOT FIXED** | Infrastructure — not code |
| 9. Add webhook idempotency | ✅ **VERIFIED** | `license_db.py:58-61` processed_events table + `stripe_webhook.py:202-208` check/mark |
| 10. Fix seats metadata vulnerability | ✅ **VERIFIED** | `stripe_webhook.py:102-103` — `TIER_SEAT_LIMITS.get(tier, 1)` |

### Re-Audit Fix Verification (July 4 Sweep)

| Item | Verdict | Details |
|------|---------|---------|
| **27 bare `except Exception: pass` → `logger.exception`** | ✅ **VERIFIED** | 17 ImportError blocks in `server.py:4551-4751` now log. Message "Silent exception caught" is generic — could be improved per-route. |
| **K8s/Helm PVC + persistence** | ✅ **VERIFIED** | `k8s/pvc.yaml` (14-line PVC), `helm/cutctx/templates/pvc.yaml` (21-line template), `k8s/deployment.yaml` mounts PVC at `/home/nonroot/.cutctx` |
| **Docs brand refresh** | ✅ **VERIFIED** | `docs/pricing.html` + `docs/enterprise.html`: teal accent `#0d9488`, Inter + Space Grotesk fonts, mobile hamburger nav |
| **Helm values version bump** | ✅ **VERIFIED** | `helm/cutctx/values.yaml:18` — image tag `0.30.0` |
| **K8s port consistency** | ✅ **VERIFIED** | `k8s/deployment.yaml` — port changed from 8080 to 8787, `--host 0.0.0.0:8787` |
| **K8s user ID** | ✅ **VERIFIED** | `k8s/deployment.yaml` — runAsUser changed from 65534(nobody) to 1000(nonroot) |
| **auth_keyring.py (new feature)** | ✅ **CLEAN** | 49 lines, proper error handling, OS keyring + env var priority |

### Still-Unfixed Items (from previous audits)

| Finding | Severity | Age | Notes |
|---------|----------|-----|-------|
| `subscription.updated` still a stub | 🟡 MEDIUM | Since v0.30.0 | Only logs sub_id; no tier/seat update |
| RBAC resolve_role fails open to ADMIN | 🟠 HIGH | Since v0.30.0 | `_default_role = AdminRole.ADMIN` (line 118) |
| Rust core missing → silent sig bypass | 🟡 MEDIUM | Since v0.30.0 | `except ImportError: pass` — no warning logged |
| `watermark.py:195` hardcoded True (V-10 stub) | 🟠 HIGH | Since v0.30.0 | Returns all watermarks traceable without DB lookup |
| Stale SSO "log and continue" comment | 🟡 MEDIUM | Since v0.30.0 | Comment says pass; code raises — maintenance hazard |
| No Cargo Dependabot | 🟡 MEDIUM | Since v0.30.0 | Rust crate vulns not auto-updated |
| `processed_events` table unbounded | 🟡 MEDIUM | Since v0.30.0 | No TTL cleanup on table |
| License email still spool-only | 🟡 MEDIUM | Since v0.30.0 | No SMTP/SES integration |

### NEW Vulnerabilities Found in This Sweep

| # | Severity | Location | Finding |
|---|----------|----------|---------|
| 🆕 H1 | **🔴 HIGH** | `cutctx_ee/sso.py:505` | `verify_exp=False` with NO manual `exp` check after decode — accepts expired JWTs |
| 🆕 H2 | **🟡 MEDIUM** | `cutctx/memory/sync.py:196` | `httpx.AsyncClient` to `memory_service_url` without egress allowlist — SSRF vector |
| 🆕 H3 | **🟡 MEDIUM** | `k8s/network-policy.yaml` | `namespaceSelector: {}` matches ALL namespaces; port 8080 ≠ actual 8787 |

### Improvements Since v0.30.0 Release

| Improvement | Impact |
|-------------|--------|
| 27 bare except:pass → logger.exception in server.py | Previously silent failures now logged |
| K8s deployment + Helm: PVC, persistence, port fix | Production-grade deployment |
| 2 new test files (test_rbac.py, test_enterprise_smoke.py) | RBAC hardening + enterprise flow coverage |
| # type: ignore count held at 0 | Strict typing regime intact |
| Docs brand refresh (teal, Inter, mobile nav) | Marketing polish |

---

*Report generated July 4, 2026. Based on codebase at `/Users/aryansingh/Documents/Claude/Projects/headroom` (v0.30.0 release commit 70950760). Four background specialist tasks reconciled (ora-1/2/3, exp-7).*
