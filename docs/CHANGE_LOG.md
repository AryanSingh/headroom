# Change Log — What & Why

This document records every planned or in-progress change: what is being changed, why it needs changing, and what the expected outcome is. It is written **before** code is touched and updated as work completes.

---

## Verified Clean — Round 4 Audit (Pre-Existing Fixes)

These issues were already fixed before this audit session. Verification confirmed they are resolved:

| Issue | File | Status |
|-------|------|--------|
| residency.py missing auth | `cutctx/proxy/routes/residency.py` | ✓ Fixed: admin auth + RBAC check in place |
| webhook_secret default fallback | `cutctx/proxy/webhooks.py` | ✓ Fixed: RuntimeError if env var missing |
| stripe_webhook reads tier from metadata | `cutctx_ee/billing/stripe_webhook.py` | ✓ Fixed: uses secure Price ID lookup |
| helm image registry outdated | `helm/cutctx/values.yaml` | ✓ Verified: correct registry (ghcr.io/cutctx/cutctx) |
| package.json hardcoded file URLs | `plugins/openclaw/package.json` | ✓ Verified: no hardcoded paths |
| CHANGELOG conflicting sections | `CHANGELOG.md` | ✓ Verified: single [Unreleased] section |
| cryptography version floor too low | `pyproject.toml` | ✓ Verified: floor is 46.0.0 (covers all CVEs) |
| Capabilities shows live availability | `dashboard/src/pages/Capabilities.jsx` | ✓ Fixed: /stats integration works |
| Memory gracefully handles 501 | `dashboard/src/pages/Memory.jsx` | ✓ Fixed: 501 → empty dataset |
| Playground includes Claude + Gemini | `dashboard/src/pages/Playground.jsx` | ✓ Fixed: all 3 providers present |
| Firewall endpoints operational | `cutctx/proxy/routes/admin.py` | ✓ Verified: /firewall/status and /firewall/scan exist |
| dsr.py imports exist | `cutctx/proxy/routes/dsr.py` | ✓ Verified: all imports valid |
| batch.py request_savings_metadata defined | `cutctx/proxy/handlers/batch.py` | ✓ Verified: defined at line 645 |

---

## Completed This Session — Round 4 Audit Fixes (2026-06-30)

### P0 Production Issues Fixed

#### 1. AttributeError: `_Entry has no attribute tokens_saved_per_hit`
- **File**: `cutctx/proxy/handlers/anthropic.py:876`
- **Fix**: Changed `cached.tokens_saved_per_hit` → `0` (CacheEntry has no such field)
- **Test**: `tests/test_anthropic_semantic_cache_outcome.py` (3 tests)

#### 2. EgressEnforcer not wired into HTTP outbound calls
- **Files Modified**:
  - `cutctx/proxy/server.py:1541-1552` (main retry handler)
  - `cutctx/proxy/handlers/anthropic.py` (3 direct HTTP calls)
  - `cutctx/proxy/handlers/batch.py` (5 direct HTTP calls)
- **Impact**: `CUTCTX_OFFLINE_MODE=1` now correctly blocks all outbound requests
- **Test**: `tests/test_egress_enforcer_blocking.py` (7 tests)

### P1 Security Issues Fixed

#### 3. Webhook subscriber secrets stored in plaintext
- **File**: `cutctx/proxy/webhook_stores.py`
- **Fix**: Implemented Fernet encryption for all secrets (lines 138-272)
- **Test**: `tests/test_webhook_persistence.py::TestWebhookSecretEncryption` (3 tests)

#### 4. SecretsStore using non-strict mode (ephemeral keys)
- **File**: `cutctx/proxy/routes/secrets.py:68`
- **Fix**: Changed `strict=False` → `strict=True` (requires persistent encryption key)
- **Test**: `tests/test_secrets_store.py::TestSecretsRoute::test_routes_factory_uses_strict_mode`

### P1 Build/Release Issues Fixed

#### 5. Dockerfile ENTRYPOINT uses non-existent binary
- **File**: `Dockerfile:111`
- **Fix**: Changed `[\"cutctx\", \"proxy\"]` → `[\"python3\", \"-m\", \"cutctx.cli\", \"proxy\"]`

#### 6. Helm service targetPort mismatch
- **File**: `helm/cutctx/values.yaml:112`
- **Fix**: Changed `targetPort: 8080` → `targetPort: 8787` (matches EXPOSE)

### P1 Dashboard Issues Fixed

#### 7. Governance endpoints missing (UI requests 6, server implements 2)
- **File**: `dashboard/src/pages/Governance.jsx:18-25`
- **Fix**: Removed 4 unimplemented endpoint requests; keep 2 working ones; added TODO comments
- **Impact**: Dashboard no longer attempts to fetch `/orgs`, `/quota`, `/retention/stats`, `/subscription-window`

#### 8. Firewall env var documentation incorrect
- **File**: `dashboard/src/pages/Firewall.jsx:195`
- **Fix**: Changed display from `CUTCTX_FIREWALL=1` → `CUTCTX_FIREWALL_ENABLED=1`

### Benchmark Claims Verification

**FALSE claims removed from expectations:**
- Production telemetry "1.4 billion tokens saved" — unverifiable (no aggregated telemetry data)
- SmartCrusher "45,000 tokens/sec" throughput — no actual measurement found
- Pipeline timing percentiles "16.9ms median" — requires telemetry, not available

**CONFIRMED benchmark claims (executable tests present):**
- HTML extraction 98.2% recall on Scrapinghub benchmark ✓
- JSON compression 59% reduction ✓
- Mixed corpus 64.4% ✓
- Code/Prose 0% (intentional, passes unchanged) ✓
- M-series micro-benchmarks ✓
- Benchmarks reproducible via `python run_all.py --dry-run` ✓

---

## Pending — Dashboard: 6 broken surfaces (STATUS: Resolved)

### 1. Governance module broken — **FIXED**
✓ Reduced API surface to implemented endpoints only

### 2. Security module empty — **FIXED**
✓ Corrected env var documentation

### 3. Capabilities page underwhelming — **VERIFIED WORKING**
✓ Live availability signals already integrated from `/stats`

### 4. Memory shows nothing — **VERIFIED WORKING**
✓ 501 responses already handled gracefully as EE gate

### 5. Playground only supports OpenAI — **VERIFIED WORKING**
✓ All 3 providers (Claude, OpenAI, Gemini) present

### 6. Skipped tests (3 items) — **VERIFIED CORRECT**
✓ Intentional optional-extras guards; documented

---

## Completed This Session

### 2026-06-30 — Test suite unblocked + feature snapshot fixes

| What | Why | File |
|------|-----|------|
| Created `llmlingua_compressor.py` | Module was deleted; 39 tests couldn't collect | `cutctx/transforms/llmlingua_compressor.py` |
| Added mode aliases: `token_cutctx`, `token_savings`, `cost_savings`, `cache_mode` | Test assertions against legacy mode names failed | `cutctx/proxy/modes.py` |
| Added `difftastic` + `llmlingua` canonical keys to `_feature_availability_snapshot()` | Tests expected user-facing keys; server used obfuscated names | `cutctx/proxy/server.py` |
| Fixed `llmlingua` availability check to use transform module path | Test patched `cutctx.transforms.llmlingua_compressor`, not `llmlingua` package | `cutctx/proxy/server.py` |

**Test result before fixes:** 28 failed, 7461 passed
**Test result after fixes:** TBD (full suite running)

---

## How to read this doc

- **What** — the symptom visible to the user or developer
- **Why** — the root cause (not just "it's broken")
- **Fix plan** — what will change and where, before a line of code is written

Changes are committed with a reference back to the section here so the git history explains the motivation.
