# CutCtx Security Analysis

**Date:** 2026-07-08  
**Analyst:** Oracle (automated)  
**Scope:** Authentication, authorization, key management, network security, data protection, dependency vulnerabilities

---

## CRITICAL

### 1. Hardcoded OpenAI API Key in `.env.local` (Line 26)

**File:** `.env.local:26`  
**Risk:** A real OpenAI API key (`sk-proj-nmPPq82Vld...`) is committed to the repository. Even though `.env.local` is in `.gitignore`, it exists in the working tree and may have been committed historically or leaked via backup. This key has not been rotated.

**Impact:** Direct financial loss, unauthorized API usage, potential data exfiltration if the key has broader permissions.

**Remediation:** Immediately rotate this key in the OpenAI dashboard. Remove the key from the file. Audit git history for prior commits containing this value.

---

### 2. Neo4j Default Password in `docker-compose.yml` (Line 42)

**File:** `docker-compose.yml:42`  
**Risk:** `NEO4J_AUTH=${NEO4J_AUTH:-neo4j/REPLACE_WITH_STRONG_PASSWORD}` — the fallback is a placeholder string, but if `NEO4J_AUTH` is unset in production, the Neo4j instance starts with a known, guessable password. Neo4j Bolt (7687) and HTTP (7474) ports are exposed on all interfaces.

**Impact:** Unauthorized graph database access, potential data exfiltration or injection.

**Remediation:** Remove the default fallback. Fail startup if `NEO4J_AUTH` is not set. Restrict port exposure to internal networks only.

---

## HIGH

### 3. OAuth2 TLS Bypass via `CUTCTX_OAUTH2_ALLOW_INSECURE`

**File:** `plugins/cutctx-oauth2/src/cutctx_oauth2/__init__.py:66-72`  
**Risk:** The `CUTCTX_OAUTH2_ALLOW_INSECURE` env var disables TLS certificate verification on the OAuth2 token endpoint. While logged as a warning, there is no production guard preventing this from being set. An attacker who controls environment variables can downgrade token exchange to plaintext.

**Impact:** Token interception, credential theft, man-in-the-middle attacks.

**Remediation:** Remove this escape hatch in production builds, or require a secondary confirmation (e.g., compile-time flag). At minimum, emit an audit event and refuse to start in production mode.

---

### 4. OIDC Signature Verification Conditional on PyJWT

**File:** `docs/security/SOC2_CONTROLS.md:22`  
**Risk:** The OIDC/JWKS validator in `cutctx_ee/sso.py` bypasses signature verification if `PyJWT` is not installed. This is a fail-open pattern: a missing dependency silently disables cryptographic validation of identity tokens.

**Impact:** Authentication bypass, identity spoofing, unauthorized access to Enterprise features.

**Remediation:** Fail closed — refuse to validate OIDC tokens if PyJWT is unavailable. Add a startup check that validates the dependency chain.

---

### 5. `CUTCTX_ALLOW_DEBUG=1` in `.env.local` (Line 36)

**File:** `.env.local:36`  
**Risk:** Anti-debug protections are disabled. While intended for local development, if this env var leaks into a production deployment (e.g., via container image layers or CI), the binary hardening in `protection.rs` becomes inert.

**Impact:** Easier reverse engineering, license key extraction, tampering.

**Remediation:** Ensure production container images and deployment manifests never include this variable. Add a CI lint check that rejects `CUTCTX_ALLOW_DEBUG=1` in release artifacts.

---

### 6. Admin API Key Logging Risk

**File:** `docs/security/SOC2_CONTROLS.md:28`  
**Risk:** The SOC2 controls doc notes that the admin API key was previously logged in plaintext. While commit `fe32040` moved it to stderr, stderr output is often captured by container runtimes and log aggregators. The key is still printed, just not via the Python logger.

**Impact:** Credential exposure in centralized logging infrastructure.

**Remediation:** Never print the admin key. Display a truncated hash or "key set" confirmation only. If the key must be shown once, use a secure output channel (e.g., written to a file with `0600` permissions).

---

## MEDIUM

### 7. `deny.toml` Allows Wildcards and Multiple Dependency Versions

**File:** `deny.toml:27-28`  
**Risk:** `multiple-versions = "allow"` and `wildcards = "allow"` weaken dependency auditing. Duplicate crate versions increase attack surface and may mask vulnerable transitive dependencies.

**Impact:** Increased risk of known vulnerabilities in duplicate dependencies going undetected.

**Remediation:** Set `multiple-versions = "warn"` or `"deny"` and `wildcards = "warn"` before production release.

---

### 8. `CUTCTX_LOG_MESSAGES=1` in `.env.local` (Line 51)

**File:** `.env.local:51`  
**Risk:** Full request/response logging is enabled. If this setting persists in a deployed environment, sensitive prompt content (classified as "Restricted" per the security policy) may appear in log files.

**Impact:** Data classification violation, PII exposure in logs.

**Remediation:** Default to `CUTCTX_LOG_MESSAGES=0` in all environments. Add a CI check that flags `LOG_MESSAGES=1` in production configs.

---

### 9. Qdrant and Neo4j Ports Exposed Without Authentication

**File:** `docker-compose.yml:24-47`  
**Risk:** Qdrant (6333/6334) and Neo4j (7474/7687) ports are mapped to host interfaces with no network isolation. Qdrant has no API key configured by default.

**Impact:** Unauthorized access to vector and graph databases from the host network.

**Remediation:** Use Docker internal networking (remove `ports` mappings), or bind to `127.0.0.1` only. Enable Qdrant API key authentication.

---

### 10. `cutctx_ee` Modules Use `sys.modules` Rebinding

**Files:** `cutctx/rbac.py:24`, `cutctx/sso.py:24`  
**Risk:** The shim pattern replaces the module object at runtime via `sys.modules[__name__] = _impl`. While functional, this can confuse static analysis tools and may introduce import-order vulnerabilities if the proprietary module is not integrity-checked.

**Impact:** Potential for module substitution attacks if the `cutctx_ee` package is compromised.

**Remediation:** Consider adding a cryptographic integrity check (hash verification) on the imported `_impl` module at startup.

---

## LOW

### 11. `protection.rs` Anti-Debug is Advisory Only

**File:** `crates/cutctx-proxy/src/protection.rs`  
**Risk:** Debugger detection logs events but does not terminate or degrade service. A sophisticated attacker can attach a debugger without operational consequence.

**Impact:** Reduced deterrence against reverse engineering.

**Remediation:** Acceptable for open-core model. Document the tradeoff explicitly.

---

### 12. GitGuardian Allowlist Contains Real-Shaped Tokens

**File:** `.gitguardian.yaml`  
**Risk:** The allowlist includes fixture tokens that are syntactically valid (e.g., `sk-ant-api03-payg-fixture`). While documented as test fixtures, future contributors may extend this list carelessly.

**Impact:** Potential for real secrets to be masked by overly broad allowlist entries.

**Remediation:** Enforce a policy that any new GitGuardian allowlist entry requires security team approval. Consider using hash-based matching instead of substring matching.

---

## Summary

| Severity | Count | Key Themes |
|----------|-------|------------|
| CRITICAL | 2 | Hardcoded secrets, default credentials |
| HIGH | 4 | TLS bypass, fail-open auth, debug exposure, credential logging |
| MEDIUM | 4 | Weak dependency policy, log PII risk, unauthenticated DB ports, module substitution |
| LOW | 2 | Advisory anti-debug, secret scanning allowlist |

**Immediate Actions Required:**
1. Rotate the exposed OpenAI API key
2. Remove Neo4j default password fallback
3. Audit `.env.local` into `.gitignore` and verify no prior commits contained secrets
4. Add CI guards for `CUTCTX_ALLOW_DEBUG` and `LOG_MESSAGES` in production configs
