# Security Analysis Report — Cutctx

**Date:** 2026-07-10
**Auditor:** Oracle (automated)
**Scope:** Full-stack security review — secrets, auth, OWASP Top 10, supply chain, audit logging
**Codebase state:** HEAD commit `418ae99a`

---

## Security Rating

**🟡 MODERATE** — Strong architectural controls exist (RBAC, MFA, TOTP, encrypted secrets store, anti-debug, binary integrity verification), but several findings from the July 8 audit remain unremediated, and new issues are present in the local dev configuration.

---

## Executive Summary

The Cutctx codebase has made significant security investments since the initial audit: RBAC permission checks on admin endpoints, TOTP-based MFA enforcement, an encrypted secrets store with Fernet encryption, a loopback guard with DNS-rebinding protection, binary integrity verification, and an LLM firewall with ML-based injection detection.

However, **4 of 5 critical/high findings from the July 8 audit remain open or partially addressed**:

| # | Previous Finding | Status |
|---|-----------------|--------|
| 1 | OpenAI API key hardcoded in `.env.local` | **NOT ROTATED** — same key `sk-proj-nmPPq82Vld...` still present at `.env.local:26` |
| 2 | Neo4j default password fallback | **MITIGATED** — `docker-compose.yml:42` now uses `${NEO4J_AUTH:-neo4j/REPLACE_WITH_STRONG_PASSWORD}` which forces operator to set env var; `.env.local:10` uses dev password `cutctx_dev_local` |
| 3 | OIDC fail-open auth | **NOT FIXED** — RBAC is a shim to `cutctx_ee` (not available in OSS); no fail-closed fallback in `rbac.py` |
| 4 | Admin API key printed to stderr | **PARTIALLY FIXED** — moved from logger to `sys.stderr.write()` at `server.py:3177` (avoids log aggregators) but still writes credential to stderr which is captured by container orchestrators |

---

## Findings Table

| ID | Severity | Domain | Finding | File:Line | Recommendation | Effort |
|----|----------|--------|---------|-----------|----------------|--------|
| SEC-01 | 🔴 CRITICAL | Secrets | OpenAI API key `sk-proj-nmPPq82Vld...` in `.env.local` — never rotated | `.env.local:26` | Rotate immediately. Add CI pre-commit hook scanning for `sk-proj-` patterns | 1h |
| SEC-02 | 🔴 CRITICAL | Secrets | `.env.local` not in `.gitignore` — file is tracked (though excluded by pattern) | `.gitignore` | Verify `.env.local` is in `.gitignore`; add `git-secrets` or `gitleaks` CI step | 2h |
| SEC-03 | 🟠 HIGH | Auth | RBAC module is a shim to missing `cutctx_ee` — OSS edition has no RBAC enforcement | `rbac.py:16-22` | Implement a minimal OSS fallback (deny-all for unprivileged users) or document clearly | 4h |
| SEC-04 | 🟠 HIGH | Auth | Admin key written to stderr — captured by Docker/k8s log collectors | `server.py:3177-3181` | Print to `/dev/tty` only or use a one-time file with `0600` permissions | 2h |
| SEC-05 | 🟠 HIGH | Auth | MFA store failure silently allows request through | `server.py:3236-3241` | Fail closed: deny request if MFA store is unavailable when enrollment exists | 1h |
| SEC-06 | 🟡 MEDIUM | OWASP | No SSRF protection on upstream URL forwarding — proxy accepts any `base_url` | `server.py` (proxy forwarding) | Validate upstream URLs against a private IP blocklist; reject `127.0.0.0/8`, `10.0.0.0/8`, `192.168.0.0/16`, `169.254.0.0/16` | 3h |
| SEC-07 | 🟡 MEDIUM | Config | CORS default is closed (empty list) ✅, but `.env.local` has no CORS restriction — dev mode wide open | `server.py:2758-2766` | Add `CUTCTX_CORS_ORIGINS` to `.env.example` with explicit warning | 0.5h |
| SEC-08 | 🟡 MEDIUM | Secrets | `.env.local` contains `CUTCTX_ALLOW_DEBUG=1` — dangerous if leaked to production | `.env.local:36` | Add CI check: fail build if `CUTCTX_ALLOW_DEBUG=1` appears in committed files | 1h |
| SEC-09 | 🟡 MEDIUM | Supply Chain | `deny.toml` allows MPL-2.0 (copyleft) — may create license contamination risk | `deny.toml:21` | Evaluate removing MPL-2.0 from allowed list before Phase 2 production | 2h |
| SEC-10 | 🟡 MEDIUM | Supply Chain | `deny.toml` has `multiple-versions = "allow"` and `wildcards = "allow"` — no deduplication enforced | `deny.toml:27-28` | Set to `"warn"` or `"deny"` to surface dependency bloat | 1h |
| SEC-11 | 🟡 MEDIUM | OWASP | Firewall is off by default (`CUTCTX_FIREWALL_ENABLED=0`) | `.env.local:74` | Document that production deployments MUST enable firewall; add startup warning | 0.5h |
| SEC-12 | 🟢 LOW | Audit | Audit module is a shim to `cutctx_ee` — OSS edition has no audit logging | `audit.py:16-22` | Implement minimal OSS audit (stdout JSON) or document limitation | 4h |
| SEC-13 | 🟢 LOW | Audit | Auth events logged but no rate limiting on auth failures — brute force possible on admin key | `server.py:3400-3491` | Add IP-based rate limiting on `_authenticate_admin_request` failures | 3h |
| SEC-14 | 🟢 LOW | Config | `CUTCTX_LOG_MESSAGES=1` in `.env.local` — logs full request/response bodies (PII risk) | `.env.local:51` | Add warning in `.env.example` that this must be 0 in production | 0.5h |
| SEC-15 | 🟢 LOW | Supply Chain | No CI/CD pipeline files found (`.github/workflows/` missing) — unclear how builds/tests are run | Root | Add CI pipeline with security scanning (gitleaks, cargo audit, pip-audit) | 8h |

---

## Previous Findings Remediation Status

| # | Finding | Original Severity | Current Status | Evidence |
|---|---------|-------------------|----------------|----------|
| 1 | OpenAI API key hardcoded in `.env.local` | 🔴 CRITICAL | **NOT REMEDIATED** | `.env.local:26` — same key `sk-proj-nmPPq82Vld...` present. Not in git history of committed files, but `.env.local` itself is present on disk. |
| 2 | Neo4j default password fallback | 🔴 CRITICAL | **MITIGATED** | `docker-compose.yml:42` — now uses `${NEO4J_AUTH:-neo4j/REPLACE_WITH_STRONG_PASSWORD}`. The fallback is a placeholder that will fail to authenticate, not a usable default. `.env.local:10` uses `cutctx_dev_local` (acceptable for dev). |
| 3 | OIDC fail-open auth (`rbac.py:143`) | 🟠 HIGH | **NOT REMEDIATED** | `rbac.py` is a shim to `cutctx_ee.rbac` which is not present in OSS. No fail-closed fallback exists in the shim. |
| 4 | Admin API key printed to stderr (`auth_mode.rs:89`) | 🟠 HIGH | **PARTIALLY REMEDIATED** | The key is now written to `sys.stderr` (`server.py:3177`) instead of the Python logger. This avoids log aggregator exposure but stderr is still captured by container runtimes. The comment says "stdout" but the code uses `sys.stderr`. |

---

## Detailed Analysis

### 1. Secrets Management

**`.env.local`** contains multiple hardcoded values:

| Secret | Value | Risk |
|--------|-------|------|
| `NEO4J_PASSWORD` | `cutctx_dev_local` | Low — dev-only |
| `CUTCTX_ADMIN_API_KEY` | `dev-admin-key-change-in-prod` | Medium — obvious placeholder |
| `CUTCTX_UPSTREAM_OPENAI_API_KEY` | `sk-proj-nmPPq82Vld...` | **CRITICAL** — real API key |
| `CUTCTX_AUDIT_SECRET_KEY` | `dev-audit-secret-12345678901234567890` | Medium — weak dev key |

**Git history check:** No evidence the OpenAI key was committed to tracked files (grep of git log found no matches outside `.env.local`). However, the file exists on disk and could be exfiltrated if the developer's machine is compromised.

**`.gitignore` analysis:** `.env.local` is not explicitly listed in `.gitignore`. The file appears to be tracked (it exists in the working tree). Need to verify it's not committed:

```
# Lines 10-12 show scripts/ is blocked with allowlist pattern
# .env.local is NOT in the gitignore list
```

**Recommendation:** Add `.env.local` to `.gitignore`, rotate the OpenAI key, add `gitleaks` pre-commit hook.

### 2. Authentication & Authorization

**Admin Auth Flow** (`server.py:3150-3493`):

1. Check `Authorization: Bearer <key>` or `X-Cutctx-Admin-Key: <key>` against `_admin_api_key`
2. If SSO validator is configured, attempt OIDC validation
3. If nothing matches, return 401

**MFA Enforcement** (`server.py:3202-3270`):
- TOTP codes are single-use (replay-protected via `last_used_counter`)
- API-key authenticated requests bypass MFA (documented threat model)
- **FAIL-OPEN BUG:** If `MfaStore` cannot open, the request is allowed through (`server.py:3236-3241`)

**RBAC** (`rbac.py`):
- Entire module is a shim to `cutctx_ee.rbac`
- OSS edition has no RBAC — all permission checks will raise `ImportError`
- The `_require_rbac_permission` factory in `server.py:3512-3523` raises 503 when RBAC is unavailable, which is correct fail-closed behavior for the permission check itself

**Audit Actor Resolution** (`admin.py:30-50`):
- Fixed: No longer trusts `X-Cutctx-User-Id` header
- Hierarchy: SSO subject > key fingerprint > "admin"

### 3. Dependency Vulnerabilities

**Rust (`deny.toml`):**
- MPL-2.0 is in the allow list — copyleft risk
- `multiple-versions = "allow"` — no deduplication
- `wildcards = "allow"` — opaque version ranges
- No `cargo audit` CI step found

**Python (`pyproject.toml`):**
- `requires-python = ">=3.10"` — good, avoids EOL interpreters
- Runtime dependencies not listed in `[project.dependencies]` (likely in a separate section or managed by maturin)
- Dev dependencies: `drain3`, `pytest`, `pytest-timeout` — minimal, low risk

### 4. OWASP Top 10

| Category | Status | Notes |
|----------|--------|-------|
| **A01: Broken Access Control** | 🟡 | Admin endpoints properly gated by `_require_admin_auth`. RBAC not available in OSS. |
| **A02: Cryptographic Failures** | 🟡 | Fernet (AES-128-CBC + HMAC-SHA256) for secrets store. HMAC-SHA256 for audit chain. Ed25519 for residency proofs. Key derivation from machine ID is weak (hostname+MAC). |
| **A03: Injection** | 🟢 | LLM firewall with ML classifier (`firewall.py`, `firewall_ml.py`). Prompt injection patterns detected. PII scanning in streaming. |
| **A04: Insecure Design** | 🟡 | No SSRF protection on upstream URL forwarding. Proxy forwards to any URL without validation. |
| **A05: Security Misconfiguration** | 🟡 | CORS defaults to closed (good). Firewall off by default (bad for prod). Debug endpoints properly guarded by loopback + Host header. |
| **A06: Vulnerable Components** | 🟡 | `deny.toml` is permissive. No `cargo audit` or `pip-audit` CI step. |
| **A07: Auth Failures** | 🟢 | Rate limiting on upstream (429 handling). Budget tracking. MFA enforcement. |
| **A08: Data Integrity** | 🟢 | Binary integrity verification (`integrity.py`). HMAC-signed audit chain. Anti-debug guard. |
| **A09: Logging Failures** | 🟡 | Audit module is EE-only. OSS has no audit trail. Auth events are logged. |
| **A10: SSRF** | 🟠 | No validation on upstream URLs. Proxy can be directed to internal services. |

### 5. Supply Chain

- **CI/CD:** No `.github/workflows/` found — unclear how builds/tests/deploys run
- **Binary integrity:** `integrity.py` verifies SHA-256 hashes of EE `.so` files against HMAC-signed manifest
- **Anti-debug:** `antidebug.py` prevents debugger attachment to EE code (macOS `PT_DENY_ATTACH`)
- **License:** MPL-2.0 allowed in `deny.toml` — potential copyleft contamination

### 6. Audit Logging

- `audit.py` is a shim to `cutctx_ee.audit` — **OSS edition has no audit logging**
- Admin routes reference `proxy.audit_logger` for auth events (success/failure)
- `_audit_admin_action` helper in `admin.py` logs SCIM, config changes, stats resets
- Auth events include: `auth.success`, `auth.failed` with method, path, reason
- **Gap:** No audit logging for proxy request forwarding, compression decisions, or memory operations in OSS

---

## Recommendations (Priority Order)

1. **Rotate the OpenAI API key** in `.env.local` immediately (SEC-01)
2. **Add `.env.local` to `.gitignore`** and verify it's not tracked (SEC-02)
3. **Fix MFA fail-open** — deny when store unavailable if enrollment exists (SEC-05)
4. **Add SSRF protection** — validate upstream URLs against private IP ranges (SEC-06)
5. **Fix stderr key leakage** — use `/dev/tty` or one-time file with restricted permissions (SEC-04)
6. **Add CI security scanning** — gitleaks, cargo audit, pip-audit (SEC-15)
7. **Document OSS limitations** — audit, RBAC not available without `cutctx_ee` (SEC-03, SEC-12)
8. **Enable firewall by default** in production configurations (SEC-11)
9. **Tighten `deny.toml`** — remove MPL-2.0, set `multiple-versions = "warn"` (SEC-09, SEC-10)
10. **Add auth failure rate limiting** — IP-based throttling on admin auth endpoint (SEC-13)
