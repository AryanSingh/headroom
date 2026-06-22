# Cutctx Production & Release Audit — Round 4 (2026-06-22)

**Date:** 2026-06-22
**Branch:** `main`
**HEAD:** `b3a06dbd`
**Previous score (Round 2, 2026-06-21):** Production 90/100, Enterprise 82/100, OSS 92/100

---

## Executive Summary

**Verdict: NO-GO for any release channel.** A massive rebrand shell-leak + 3 latent P0 security regressions + a broken Docker/Helm release surface + a working tree full of uncommitted code combine to make this branch unsafe to ship in any form. **CONDITIONAL-GO for internal staging deploy** (single-replica, no external traffic, no GDPR-regulated data) after the 8 fixes in §5 are applied.

| Channel | Decision | Top blocker |
|---|---|---|
| **PyPI OSS (`cutctx-ai`)** | NO-GO | `pip wheel` fails (target/ pollution); CHANGELOG has 3 conflicting `[Unreleased]` sections; no v0.26.0 tag ever published |
| **Docker Hub (`ghcr.io/cutctx/cutctx`)** | NO-GO | ENTRYPOINT `headroom proxy` is broken (binary doesn't exist); image registry still `ghcr.io/aryansingh/headroom` |
| **Helm chart (`helm/headroom/`)** | NO-GO | Port 8080 ≠ image 8787; chart name + image registry on old brand |
| **npm openclaw plugin** | NO-GO | Hard-coded `file:` URL in `package.json`; `verify-versions.py` fails on HEAD |
| **GitHub release** | NO-GO | Working tree dirty (23 modified + 18 untracked); no tag; CHANGELOG lies about v0.26.0 |
| **Internal staging deploy** | CONDITIONAL-GO | After 8 fixes in §5. Single-replica only. No PII. |
| **Private EE PyPI (`headroom-ee`)** | NO-GO | `headroom_ee/__init__.py` says "Cutctx Labs" but `headroom_ee/LICENSE` says "Headroom Labs / Payzli Inc." — direct legal conflict; publish-ee.yml has stale comment |

**Round 4 vs Round 2:**

| Score | Round 2 (2026-06-21) | Round 4 (2026-06-22) | Delta |
|---|---|---|---|
| **Production readiness** | 90/100 | **62/100** | **-28** |
| **Enterprise readiness** | 82/100 | **55/100** | **-27** |
| **OSS readiness** | 92/100 | **70/100** | **-22** |
| **Tests** | 7154 pass / 132 fail | **7198 pass / 92 fail** | +44 net new passing |
| **P0 count** | 7 (all closed) | **14** (3 false-closed, 6 new regressions, 5 rebrand) | +7 |

The -28 production score is the result of three compounding factors that didn't exist in Round 2:

1. **The 1024-file fast-forward merge from `moat-b1` → `main` pulled in code that had not been audited in Round 2** — Round 2's polish was on the c1/c4 audit-deep work, not on the 515 untracked rebrand files in the working tree.
2. **Round 3's P0 "GDPR fix" (`c556e5bb`) was a false close** — `query_spend`/`delete_spend_for_user`/`delete_for_actor` do not exist; DSR silently no-ops for spend + audit log. This is GDPR non-compliance.
3. **The rebrand shell-leak is now actively breaking things**, not just being a naming inconsistency. The Docker ENTRYPOINT invokes a binary that doesn't exist anymore; the Helm chart uses an image that doesn't exist on the new registry; the openclaw plugin has a hard-coded path from a single developer's machine.

---

## Test Suite Health (Lane: exp-5)

**Totals:** 7,546 collected / 7,198 passed / 92 failed / 256 skipped / 0 errored / 17 warnings
**Pass rate:** 95.4% (was 98.2% in Round 2)
**Wall time:** 5m 35s

### Failures by category

| Category | Count | Severity | Fix type |
|---|---|---|---|
| **Real regressions in production code** | 6 | P0 | Developer fix (not mechanical) |
| **Rebrand shell-leak (test imports + string assertions)** | 58 | P0 | Mechanical alias additions (~30 min) |
| **Playwright dashboard env-dep (no server on :8787)** | 5 | P1 | Add `pytest --serve-dashboard` fixture |
| **Test isolation bug** | 1 | P2 | Reset secrets store between tests |

### The 6 real regressions (P0) — most important findings in the entire audit

These are real bugs in production code, not test bugs. They were introduced by recent commits and were not caught by Round 2.

| # | Location | Symptom | Root cause | Round 2 status |
|---|---|---|---|---|
| 1 | `headroom/proxy/handlers/anthropic.py:875` | `AttributeError: '_Entry' object has no attribute 'tokens_saved_per_hit'` | Commit `2d9316ea9` references field that doesn't exist on `_Entry` | NEW (post-Round-2) |
| 2 | `headroom/proxy/handlers/batch.py:768` | `NameError: name 'request_savings_metadata' is not defined` | Local var never assigned in `handle_google_batch_results` | NEW (post-Round-2) |
| 3 | `headroom/proxy/server.py:605` (uncommitted) | `TypeError: ...got an unexpected keyword argument 'default_ttl'` | New code calls `get_compression_store(default_ttl=...)` but tests expect 3-arg signature | NEW (uncommitted, in rebrand set) |
| 4 | `tests/test_proxy_ccr.py:71,82,267` | `1800 != 300` | Test expects `ccr_store_ttl_seconds=300` but production default is `1800` | NEW (config drift) |
| 5 | `tests/test_transforms/test_content_router.py:206,378` | `enable_code_aware` is `True` but test asserts `False` | Test expects default-off; code defaults to on | NEW (deliberate flip, no docstring) |
| 6 | `tests/test_capability_extensions.py:221` | `assert False is True` (`result["valid"]`) | License DB upsert/get returning `valid=False` — license/sig path bug | NEW |

**P0 #1 and #2 are the most dangerous** — they're NameError/AttributeError on hot paths (Anthropic cache telemetry, Google batch). They would 500 in production for any Anthropic or Google Batch customer.

### The 58 rebrand shell-leak failures (P0, mechanical)

Same root cause: the Round 3 rebrand renamed symbols (e.g. `HeadroomHookProvider` → `CutctxHookProvider`) and the `7795ffb6` fix only patched 15 of 58 test files. Two distinct failure modes:

- **`ImportError: cannot import name 'CutctxHookProvider'`** (30 tests in `tests/integrations/test_strands/test_hooks_unit.py`). The strands integration is dead; needs `CutctxHookProvider = HeadroomHookProvider` alias added to `headroom/integrations/strands/__init__.py`. **Mirror the `HeadroomProxy = CutctxProxy` fix from `7795ffb6`.**
- **`NameError: name 'HeadroomX' is not defined`** (28 tests across agno, langchain, observability, MCP server). Test files import the old `Headroom*` name. Either rename tests to `Cutctx*` or add aliases in the integration `__init__.py`s.

**Recommended fix pattern:** Add `HeadroomX = CutctxX` aliases in the four public `__init__.py` files (headroom, headroom/observability, headroom/integrations/__init__.py, headroom/integrations/strands/__init__.py) for every class/function that doesn't have one yet. The aliases already exist for 13 of 19 — only 6 are missing.

### Test gaps worth filling

- `test_hooks_unit.py` import resolution test (catches missing aliases)
- Naming-convention conformance test (walks public API, asserts no symbol begins with `Headroom*` — only `Cutctx*` is canonical)
- `test_proxy_ccr.py` TTL matrix test (pins the contract between `CutctxConfig.ccr_store_ttl_seconds` and the CCR singleton's actual TTL)
- Regression test for `_Entry.tokens_saved_per_hit` (would have caught the Anthropic 500)

---

## Build & Artifact Health (Lane: exp-4)

**🚨 P0: `pip wheel` fails.** The wheel build is broken in the current working tree. The failure is not a toolchain issue but a working-tree hygiene issue: `target/` (1.8 GB of Rust artifacts) is not excluded from the sdist input that `pip wheel` materializes. Maturin's `[tool.maturin] exclude = ["headroom_ee/**/*", "packaging/**/*"]` does **not** exclude `target/**`. Result: `shutil.Error: [Errno 28] No space left on device`.

The fix is to add `target/` to `.gitignore` (it's not actually missing — `.gitignore` lists it; it just hasn't been deleted) AND to add it to `[tool.maturin] exclude` AND to `.dockerignore`. All three.

**🚨 P0: Docker ENTRYPOINT broken.** `Dockerfile:74,98,121` references `/usr/local/bin/headroom` and `ENTRYPOINT ["headroom", "proxy"]`, but no `headroom` script exists in `pyproject.toml` — only `cutctx`. The distroless stage works (`["python3", "-m", "headroom.cli", "proxy"]`) but the `runtime-slim-base` stage (the default published image per `Dockerfile:125`) is broken. Any `docker pull` + `docker run` will fail with "headroom: command not found" at container start.

**P1: Version drift.** `pyproject.toml [project].version` says `0.26.0`. `headroom._version.__version__` at runtime says `0.27.0` (auto-computed from git commits since last tag). `git tag -l` is empty. The CHANGELOG says v0.26.0 was released on 2026-06-19 but **no tag was ever pushed** — see Release Health § below.

**P1: `.dockerignore` gaps.** Does not exclude `target/`, `dist/`, `cutctx/`, `helm/cutctx/`, `~`, `extensions/`, `compress.skill`, `adversarial_*.py`, root `test_*.py` / `harness_test.py`. These are COPYd into the build context, slowing `docker build` and risking the same disk-exhaustion as `pip wheel`.

**P1: Helm port mismatch.** `helm/headroom/values.yaml:31` has `port: 8080`; Dockerfile `EXPOSE 8787`; compose `8787:8787`. The chart would deploy a service on 8080 that the image doesn't bind to.

**P1: Helm image registry on old brand + personal namespace.** `helm/headroom/values.yaml:8` says `repository: ghcr.io/aryansingh/headroom`. Should be the new `cutctx/cutctx` org.

**P1: `cutctx/` stale rebrand shell-leak dir.** `cutctx/__init__.py` is a working alias shim, but `cutctx/__pycache__/` is committed-able garbage. Either delete or add to `.gitignore`. Documented in §Rebrand.

**P1: `packaging/headroom-ee/setup.py` is untracked but checked-in-shape.** Git won't preserve it. Either track it or delete it.

### Pre-existing artifacts in `dist/`

| File | Size | Date |
|---|---|---|
| `cutctx_ai-0.25.0-cp310-abi3-macosx_11_0_arm64.whl` | 17.4 MB | Jun 19 23:49 |
| `cutctx_ai-0.26.0-cp310-abi3-macosx_11_0_arm64.whl` | 17.5 MB | Jun 22 00:14 |
| `cutctx_ai-0.26.0.tar.gz` | 1.9 MB | Jun 22 00:12 |

These are local-only artifacts from prior builds. The 0.25.0 / 0.26.0 wheels predate the v0.26.0 release claim. `dist/` is committed and should be in `.gitignore`.

---

## Security Surface (Lane: exp-6)

**🚨 Three Round 3 P0s are still open. Two were false-closed.**

| Round 3 ID | Title | Round 4 status | Impact |
|---|---|---|---|
| Blocker 2 | GDPR DSR endpoints missing | **STILL OPEN — false close** | Spend + audit data is retained; GDPR non-compliant |
| Blocker 3a | Air-gap a no-op | **STILL OPEN — false close** | `EgressEnforcer` not wired into outbound HTTP; `HEADROOM_OFFLINE_MODE=1` is theatrical |
| Blocker 3b | Real secrets backend | **PARTIALLY OPEN** | Strict mode bypassed by `routes/secrets.py:67` factory (silently downgrades to process-unique key) |
| Blocker 4 | SSO requires PyJWT | ✅ CLOSED | |
| Blocker 6 | Audit actor forgery | ✅ CLOSED | |
| Blocker 9 | Dev-secret-key audit chain | ✅ CLOSED | |
| High-12 | TOTP MFA | ✅ CLOSED | |
| High-15 | Webhook dispatcher | **PARTIALLY OPEN** | Subscriber secrets in plaintext SQLite |
| High-21 | Auth gates on 5 route modules | **PARTIALLY OPEN** | `residency.py` not gated |
| Medium-29 | RBAC persistence | ✅ CLOSED | |
| Medium-32 | Audit chain verify | ✅ CLOSED | |
| Medium-33 | Audit attribution | ✅ CLOSED | |

### P0 (3 new + 2 false-closed = 5 total)

1. **DSR `delete` + `export` runtime-broken (false close of `c556e5bb`).** `headroom/proxy/routes/dsr.py:181,263,276` import `query_spend`, `delete_spend_for_user`, `delete_for_actor` — none of which exist. The try/except swallows the ImportError and the response says `"EE module not installed"` even though the EE module is installed. DSR works for memory (Round 3 fix is valid for memory), but **silently fails for spend ledger + audit log**. GDPR non-compliant. Verified by running the imports directly.

2. **`EgressEnforcer` not wired into outbound HTTP path (false close of Round 3 air-gap).** `headroom/proxy/egress.py` has the enforcer. The docstring at line 30-33 claims `EgressEnforcer.check()` is called before opening an HTTP connection to a provider. **It isn't.** `headroom/proxy/routing/failover.py` contains no call to `get_egress_enforcer()`. Neither does `server.py` or `handlers/streaming.py`. The only consumer is `routes/airgap.py` for dry-run queries, not enforcement. `HEADROOM_OFFLINE_MODE=1` only checks `HF_HUB_OFFLINE` and `HEADROOM_LICENSE_HMAC_SECRET` (`airgap.py:16-30`); it does NOT block outbound HTTP. Customers who deployed in air-gap mode believing their data was contained are wrong.

3. **Stripe tier-from-metadata P0 (new finding).** `headroom_ee/billing/stripe_webhook.py:86` reads `tier` from `event_data["object"]["metadata"]`. Metadata is **client-controllable in the Stripe Checkout UI**. An attacker who can create a Stripe Checkout session with `metadata.tier=enterprise` gets an enterprise license. Fix: validate the tier by looking up the Price ID, not by reading the metadata string.

4. **Residency route is unauthenticated data leak (new finding).** `headroom/proxy/routes/residency.py:26-87` has no auth dependencies. `server.py` mounts it with the comment "kept unauthenticated by design (the attestation is itself signed)". This is wrong: a signed attestation without recipient binding is a public statement, and `tenant_id` is a query param an attacker can set to `"acme-corp"` and harvest the chain tail hash. Leaks: data-regions list, egress blocklist, audit chain tail hash (operational state — last event ID). **Fix:** add `require_admin_auth` + a new `residency.read` RBAC permission.

5. **DSR import fail-silent (covered in #1) — listed separately for explicit scoring.**

### P1 (4)

- Webhook default secret `headroom-dev-secret` (`webhooks.py:216`); any env without `HEADROOM_WEBHOOK_SECRET` ships with a publicly-known HMAC secret.
- Webhook subscriber secrets in plaintext SQLite (`webhook_stores.py:18` schema: `secret TEXT` no encryption).
- `secrets_store` strict mode bypassed by `routes/secrets.py:67` (factory unconditionally calls `SecretsStore(strict=False)`).
- `cryptography>=41.0.0` floor too low; 4+ CVEs since 41.0.0. Recommend `~=46.0`.

### P2 (5)

- Audit log not DB-level append-only (regular SQLite, no REVOKE DELETE; `retention.py:233` runs `DELETE FROM audit_events WHERE timestamp < ?` — explicit non-append-only by design).
- License DB at `~/.headroom/licenses.db` with no permissions (readable by any local user).
- `secrets_store` strict mode is silently bypassed by router (P1 above, also relevant for P2).
- Spend ledger cross-tenant scope grant (potential for one tenant to query another's spend).
- `state_crypto.py:46-50` — fingerprint binding uses `uuid.getnode()` (48-bit MAC, trivially spoofed).

### Crypto hygiene (P2)

`pyproject.toml` floors should be tightened:
- `cryptography>=41.0.0` → `~=46.0` (security-sensitive)
- `PyJWT[crypto]>=2.8.0` → `~=2.11` (security-sensitive)
- `fastapi>=0.100.0` → `>=0.115.0` (fixes CVE-2024-47874)

`uv.lock` already pins specific versions; the loose floors are an aspirational contract issue, not an immediate CVE.

---

## Release Health (Lane: exp-7)

### The 8 P0 release blockers

1. **No git tag for v0.26.0 ever published.** `git tag -l` returns empty. The CHANGELOG entry dated 2026-06-19 describes work that was committed but never tagged. `dist/` artifacts are local-only. The release was a CHANGELOG write, not an actual release.

2. **CHANGELOG has 3 `[Unreleased]` sections + 2 conflicting formats.** Lines 9, 250, 357. The narrative format (`## [v0.26.0] — 2026-06-19`) collides with the release-please auto-generated format (`## [0.25.0](...compare link) (2026-06-12)`). The release-please bot will clobber hand edits on the next PR merge.

3. **`verify-versions.py` fails on HEAD.** `plugins/openclaw/package.json:32` has `cutctx-ai^file:../../../../../../../../tmp/headroom-release-audit/cutctx-ai-0.26.0.tgz` — a hard-coded absolute `file:` URL from a developer's machine. Shipping a release with this would break `npm install` for any fresh consumer of the openclaw plugin.

4. **README and install scripts have 4+ instances of typo `AryanSingh/cutcxt`.** The dirty diff only fixes 1 line in pyproject. The 4 instances in `README.md` lines 14, 15, 16, 17 are still there. (`cutcxt`, not `cutctx` — `c-x-t` instead of `c-t-x`.) Plus more in `scripts/install.sh`, `scripts/install.ps1`, `helm/headroom/Chart.yaml:15`.

5. **Working tree is dirty.** 23 modified + 18 untracked. Cannot release from this state. The uncommitted rebrand work is the largest single block; see §Rebrand for the breakdown.

6. **K8s image registry drift.** `k8s/deployment.yaml:42` says `ghcr.io/aryansingh/headroom:v0.26.0`. `scripts/install.sh:5` and `install.ps1:3` say `ghcr.io/chopratejas/headroom:latest`. `docker.yml` is undefined. Three different image registries in three different files. Should be `ghcr.io/cutctx/cutctx:0.26.0` (or similar — pick one).

7. **`SECURITY.md` Supported Versions table is wrong.** Lists `0.2.x` and `0.1.x` (pre-rebrand historical versions). Should list `0.25.x` and `0.26.x` with support windows.

8. **EE LICENSE brand name conflict (legal risk).** `headroom_ee/LICENSE:3` says "Copyright (c) 2025-2026 Headroom Labs". `headroom_ee/__init__.py:2` says "Copyright (c) 2025-2026 Cutctx Labs". `LICENSE-COMMERCIAL:4` and `headroom_ee/LICENSE:5` both say "Legal entity: Payzli Inc. (operating as Headroom Labs)". The legal entity is Payzli Inc. (parent), operating as Headroom Labs (sub-brand) — but the codebase has rewritten `__init__.py` to claim Cutctx Labs. This is a corporate-identity mismatch, not just branding.

### The 10 P1 release issues

1. `version-sync.py` and `verify-versions.py` are incomplete — don't cover `helm/Chart.yaml`, `k8s/deployment.yaml`, `packaging/headroom-ee/pyproject.toml`, or `.release-please-manifest.json`. A version bump that misses any of these is a P1 release bug.
2. `packaging/headroom-ee/setup.py` is untracked (git won't preserve it).
3. No SBOM (no CycloneDX, no SPDX). `add_spdx.py` is a 152-byte stub.
4. Two license-token formats coexist (HMAC-SHA256 from `generate_license.py` + Ed25519 from `license_keygen.py` + `license_token.py`). Verify the Rust proxy (`crates/headroom-core/src/licensing.rs` — file is untracked) actually validates the Ed25519 path.
5. `docs/policies.md` and `docs/audit-compliance.md` are 1KB stubs — not suitable as public-facing compliance docs.
6. `llms.txt` references `[all]` extra that doesn't exist in pyproject.toml.
7. `docs/` and `wiki/` overlap significantly (getting-started, proxy, MCP, config in both). One should be deprecated.
8. `dist/` is committed (4 stale wheel/sdist artifacts). Should be in `.gitignore`.
9. `crates/headroom-core/src/licensing.rs` is untracked — Rust-side license enforcement code not committed.
10. No automated OSS dependency-license / vulnerability scanning workflow.

### Tag / GitHub release state

- `git tag -l`: empty (0 tags).
- Last 30 commits show 8 `feat(audit-deep)` + 3 `fix(audit-deep)` + 2 `feat(security)` + 1 `fix(security)` + 2 rebrand `fix(rebrand)` + 1 docs(audit) since the alleged 2026-06-19 release. None of this is in the CHANGELOG's v0.26.0 entry.
- No GitHub release artifacts in `dist/`.

### What changed since Round 2

| Item | Round 2 status | Round 4 status |
|---|---|---|
| MFA on admin | DEFERRED | ✅ SHIPPED (`58e5495d`) |
| SAML SSO | DEFERRED | ❌ Still deferred |
| Webhook subscription persistence + DLQ | DEFERRED | ✅ SHIPPED (`811931e7`) |
| RBAC persistence | DEFERRED | ✅ SHIPPED (`ddef51a1`) |
| Audit enum coverage | DEFERRED | ✅ SHIPPED (47 actions) |
| Streaming typed per-source field wiring | DEFERRED | ✅ SHIPPED (`34c936d8`) |
| Native binary Prometheus exporter | DEFERRED | ❌ Still deferred |
| LLM firewall opt-in (re-enable for cloud) | DEFERRED | ✅ SHIPPED (warning added) |
| Go + Java SDK rebrand | DEFERRED | ❌ **Still deferred — Java SDK still on `com.headroom.HeadroomClient`** |
| Dashboard live feed drawer Esc-to-close | DEFERRED | ✅ SHIPPED (`a3d2e7bc`) |
| I18n for hardcoded strings | DEFERRED | ❌ Still deferred |
| Backups for new SQLite stores | DEFERRED | ❌ Still deferred |
| `cutctx learn_share` orphan | P0 | ❌ Still listed as orphaned |
| DSR cascade | OPEN | ❌ **False-closed by `c556e5bb`; actually still broken** |
| Air-gap enforcement | OPEN | ❌ **False-closed; `EgressEnforcer` not wired** |

---

## Rebrand Shell State (Lane: exp-8)

The rebrand from `headroom` to `cutctx` is **partially complete**. Python package name and CLI binary are done. Supporting surfaces (install scripts, Docker, Helm, K8s, legal entity, GitHub URLs) are still on the old brand or worse.

### What's done ✓

- `pyproject.toml [project].name` = `cutctx-ai`
- CLI entry point: `cutctx = "headroom.cli:main"`
- `cutctx --version` works; `headroom --version` is gone
- `import headroom` and `import cutctx` both work (shim)
- `cutctx/` alias package at root
- Rust binary: `[[bin]] name = "cutctx"`
- `licensing.rs` is untracked but `pub mod licensing;` in `lib.rs:4` wires it in
- 13 backward-compat aliases: `HeadroomConfig`, `HeadroomClient`, `HeadroomMode`, `HeadroomProxy`, `HeadroomTracer`, `HeadroomOtelMetrics`, `HeadroomHookProvider`, `HeadroomStrandsModel`, `HeadroomBundle`, `get_headroom_provider`, `get_headroom_tracer`, `reset_headroom_tracing`, `CutCtxConfig`, `CutCtxMode`, `CutCtxClient`, `CutCtxError`, `CutCtxTracer`, `CutCtxOtelMetrics`
- `sdk/{python,typescript,go}/` (no `headroom` suffix)
- `plugins/cutctx-plugin/` (new brand)
- `extensions/{vscode,jetbrains}/` (vscode `name: cutctx-ai`, jetbrains `dev.cutctx.*`)
- `PRIVACY.md` / `TERMS.md` (CutCtx Labs)

### What's partial ⚠ (P0)

| Surface | State | Detail |
|---|---|---|
| `headroom_ee/__init__.py` vs `headroom_ee/LICENSE` | **P0 — legal conflict** | `__init__.py` says "Cutctx Labs"; `LICENSE` says "Headroom Labs / Payzli Inc." |
| `LICENSE-COMMERCIAL` and `NOTICE` | **P0** | Still on old brand |
| `plugins/headroom-agent-hooks/hooks/hooks.json` | **P0 — runtime broken** | Invokes gone `headroom` binary |
| `plugins/headroom-oauth2/pyproject.toml` | **P0** | Package name `cutctx-oauth2` but URLs `chopratejas/headroom` |
| `Dockerfile` lines 74, 98, 121 | **P0 — runtime broken** | `headroom proxy` ENTRYPOINT, no such binary |
| `docker-compose.yml:2` | **P0** | Service `headroom-proxy` |
| `docker-bake.hcl` | **P0** | `HEADROOM_EXTRAS` build args (8 of 8) |
| `k8s/deployment.yaml:42` | **P0** | `ghcr.io/aryansingh/headroom:v0.26.0` |
| `helm/headroom/values.yaml:8` | **P0** | Image registry old brand + personal ns |
| `helm/headroom/Chart.yaml:2,13,15,18` | **P0** | `name: headroom`, `home: headroom.dev`, `email: hello@headroom.dev`, sources typo `AryanSingh/cutcxt` |
| `scripts/install.sh:5,54,55,65,568,944` | **P0** | Image `ghcr.io/chopratejas/headroom`; wrapper `headroom`; URLs typo `AryanSingh/cutcxt` |
| `scripts/install.ps1:3,67-70` | **P0** | Same pattern |
| `.release-please-config.json:14` | **P0** | `package-name: headroom-ai` |
| `Cargo.toml:24` | **P0** | `repository: github.com/chopratejas/headroom` |
| 4 different GitHub orgs | **P0** | `cutctx` (canonical), `AryanSingh` (typo), `chopratejas` (stale), `aryansingh` (k8s) |
| 6+ instances of typo `AryanSingh/cutcxt` | **P0** | (cutcxt, not cutctx) |
| `sdks/{go-headroom,java-headroom}/` | **P0** | Java SDK still on `com.headroom.HeadroomClient` |
| `helm/headroom/templates/*` | **P0** | All template helpers `{{ include "headroom.fullname" . }}` — ~30 occurrences |

### What's not started ✗

- `helm/cutctx/` chart does not exist
- `docs/legal/PRIVACY_POLICY_DRAFT.md` and `docs/legal/TERMS_OF_SERVICE_DRAFT.md` do not exist
- No rebrand of `headroom_ee/` directory itself (only docstring updated)
- `headroom-oauth2` URL fix (3 occurrences of `chopratejas/headroom`)

### The systemic meta-problem

The rebrand is **fractally incomplete** — the same pattern of "started but not finished" appears at every layer:
- **Python source**: `headroom` modules not renamed; only `cutctx/` shim added
- **EE package**: `__init__.py` says new brand; `LICENSE` says old brand
- **Rust**: binary renamed; crate not renamed
- **Docker**: ENTRYPOINT points to old binary
- **Helm**: chart name + image both on old brand
- **K8s**: image on old brand + personal namespace
- **Install scripts**: image on different old brand + old owner
- **Plugins**: 2 of 3 have hooks invoking the gone binary
- **SDKs**: Python/TS/Go rebadged; Java still on `com.headroom`
- **GitHub URLs**: 4 different orgs, 6+ typos

This is not 30 separate problems; it's **one problem** (the rebrand was started as 30 separate small tasks instead of one atomic commit). The fix is the same at every layer: pick the canonical answer (cutctx, cutctx-ai, ghcr.io/cutctx/cutctx, `com.cutctx.HeadroomClient`→`com.cutctx.CutctxClient`, etc.) and apply it consistently. The rebrand work exists in the working tree (23 modified + 18 untracked files) — committing it atomically as one commit will resolve the majority of the rebrand-shell-leak issues.

---

## Hidden Risks (the things the 5 reports mostly missed)

### 1. The working tree is a ticking bomb

23 modified + 18 untracked = **41 files** of uncommitted code sitting in the working tree, with **conflicting changes** between the rebrand set and the in-tree rebrand:
- `crates/headroom-core/src/licensing.rs` is untracked (new file)
- `headroom_ee/__init__.py` was modified to say "Cutctx Labs" but the sibling `LICENSE` still says "Headroom Labs"
- `Cargo.lock` has 17 uncommitted modifications (added `hex`, `hmac 0.12.1` deps to `headroom-core`)
- `pyproject.toml` says version `0.26.0` but the runtime computes `0.27.0` because of the uncommitted commits

If anyone runs `git reset --hard` or `git checkout -- .` they lose 41 files of work. If anyone runs `git stash` and then `git stash pop` after a pull, they may get conflicts. The only safe state is to commit this in one atomic commit and move on.

### 2. The 6 production regressions are independent of the rebrand

The P0 bugs in `anthropic.py:875`, `batch.py:768`, and the others are **real production bugs** in `headroom/proxy/handlers/*` — not caused by the rebrand, not fixed by completing the rebrand, not caught by Round 2. They were introduced by recent commits. Anthropic cache telemetry (P0 #1) and Google Batch handler (P0 #2) would 500 in production for any customer using those features. **These are ship-blockers for the OSS release and the internal deploy.** The rebrand work has masked them; once the rebrand is finished, the test suite needs to pass at 99%+ before release.

### 3. The 2 false-closed P0s are a process failure

Round 3's "P0 GDPR fix" (`c556e5bb`) was merged after only running the in-memory portion of DSR. The spend + audit branches were never tested. The try/except in `dsr.py:191,265,280` masks the ImportError as `"EE module not installed"` even when the EE module is installed. **Root cause: tests covered the happy path of the fix, not the broken-import path.** Recommended process change: any commit that claims to fix a P0 must include a test that fails without the fix and passes with the fix. This would have caught #1 in `c556e5bb` review.

### 4. The Round 4 score (-28 production) is partly an artifact of doing a more honest audit

Round 2 said 90/100 production. Round 4 says 62/100. The -28 is not because the code got worse; it's because Round 4 looked at 4 things Round 2 didn't:
- The 1024-file merge brought in code that wasn't in Round 2's scope
- The rebrand shell-leak has crossed from "naming inconsistency" to "actively breaking things"
- The 6 production regressions are real bugs, not gaps
- The 2 false-closed P0s are now demonstrably broken

The codebase is not 28 points worse; the audit is 28 points more honest. The next round that runs will probably land in the 75-85 range once the 8 fixes below are applied.

---

## Recommended Action Plan (8 fixes, ~2 days)

In priority order. Each item: 1-line fix, 1-line time estimate, 1-line "what this unblocks".

### Fix 1: Commit the in-tree rebrand atomically (~30 min)

Add all 23 modified + 18 untracked files in a single commit titled `chore(rebrand): in-tree rebrand shell — cutctx consolidation`. Resolve the `headroom_ee/LICENSE` vs `__init__.py` brand conflict first (the `__init__.py` "Cutctx Labs" claim is the new intent; rewrite `LICENSE` to match, or revert `__init__.py` to match `LICENSE`). **Unblocks:** clears the dirty tree; unblocks every subsequent step.

### Fix 2: Fix the 6 production regressions in 3 commits (~3 hours)

- `anthropic.py:875` — add `tokens_saved_per_hit` to `_Entry` (or remove the reference; check what the field was supposed to compute).
- `batch.py:768` — define `request_savings_metadata` before use; check the analogous working code in `streaming.py:767,1623,1870` for the correct pattern.
- `server.py:605` — confirm the `default_ttl` parameter is intentional; if yes, update the test mock; if no, remove the kwarg.
- `test_proxy_ccr.py` — pin the TTL contract; either fix the test or change the default to 300.
- `test_transforms/test_content_router.py` — document the default-on decision in a docstring; flip the test to match.
- `test_capability_extensions.py:221` — debug the license DB upsert/get path; likely a missing signature step.

**Unblocks:** test suite goes from 92 fails to ~34 (only the 28 rebrand shell-leaks + 5 Playwright + 1 test isolation bug remain).

### Fix 3: Add the missing rebrand aliases (~30 min)

Mirror the `7795ffb6` pattern. Add to `headroom/integrations/strands/__init__.py`, `headroom/integrations/agno/__init__.py` (if it exists), and the four other public `__init__.py` files: `HeadroomHookProvider = CutctxHookProvider`, `HeadroomChatModel = CutctxChatModel`, `HeadroomConfig = CutctxConfig` (already done), `HeadroomRetriever = CutctxRetriever`, etc. **Unblocks:** test suite goes to 92 → 64 → 5 (Playwright) + 1 (isolation) = 6 fails.

### Fix 4: Fix DSR + air-gap + Stripe tier + residency (~4 hours)

- `headroom/proxy/routes/dsr.py:181,263,276` — replace the missing-function calls with the correct API surface from `headroom_ee.ledger.query.LedgerQuery` and `headroom_ee.audit.AuditLogger`. Add a regression test that fails on the broken version.
- `headroom/proxy/routing/failover.py` — call `get_egress_enforcer().check(host)` before opening any outbound HTTP connection. Wire the same into `handlers/streaming.py` and any other outbound call site.
- `headroom_ee/billing/stripe_webhook.py:86` — look up the Price ID from the line items and derive the tier from the canonical mapping; reject any webhook where the metadata tier doesn't match the Price-derived tier.
- `headroom/proxy/routes/residency.py:26-87` — add `Depends(require_admin_auth) + Depends(require_rbac_permission("residency.read"))`. Add `residency.read` to `PERMISSION_MAP` in `headroom_ee/rbac.py`.

**Unblocks:** GDPR compliance; closes the 2 false-closed Round 3 P0s; closes 1 new P0; closes 1 P1 (data leak).

### Fix 5: Fix Docker + Helm + K8s + install scripts (~2 hours)

- `Dockerfile:74,98` — replace `headroom proxy` with `cutctx proxy` (or use the distroless form `[python3, -m, headroom.cli, proxy]`).
- `Dockerfile:93,116` + `helm/headroom/values.yaml:31` — pick one port (recommend 8787) and use it everywhere.
- `helm/headroom/values.yaml:8` + `k8s/deployment.yaml:42` + `scripts/install.{sh,ps1}` — use `ghcr.io/cutctx/cutctx:0.26.0`.
- `helm/headroom/Chart.yaml:2,13,15,18` — `name: cutctx`, `home: cutctx.dev`, `email: hello@cutctx.dev`, sources: `github.com/cutctx/cutctx`.
- `helm/headroom/templates/*` — s/headroom/cutctx/ in all template helpers.
- `docker-compose.yml:2` — `service: cutctx-proxy`.
- `Makefile` — s/headroom_ai/cutctx_ai/, s/headroom-proxy/cutctx-proxy/.
- `.dockerignore` — add `target/`, `dist/`, `cutctx/`, `~`, `extensions/`, `compress.skill`, `adversarial_*.py`.
- `pyproject.toml [tool.maturin]` — add `target/**`, `dist/**` to `exclude`.

**Unblocks:** Docker Hub release; Helm release; K8s release; any consumer using install.sh.

### Fix 6: Fix the version sync chain (~1 hour)

- `.release-please-config.json:14` — `package-name: cutctx-ai`.
- `Cargo.toml:24` — `repository: github.com/cutctx/cutctx`.
- `plugins/openclaw/package.json` — replace `file:../../../../../../../../tmp/headroom-release-audit/cutctx-ai-0.26.0.tgz` with `^0.26.0`.
- `scripts/version-sync.py` — extend to cover `helm/headroom/Chart.yaml`, `k8s/deployment.yaml`, `packaging/headroom-ee/pyproject.toml`, `.release-please-manifest.json`.
- `scripts/verify-versions.py` — same extension; also normalize the openclaw `file:` URL detection.
- Run `verify-versions.py` and `version-sync.py --bump patch` until both pass.

**Unblocks:** any version bump; any release.

### Fix 7: Reconcile the CHANGELOG + tag v0.26.0 (~1 hour)

Three options:
- **(a)** Cut a v0.26.0 tag from `b3a06dbd` (current HEAD), rebase the v0.26.0 CHANGELOG entry to match the actual 30 commits, and re-derive the runtime version to `0.26.0`. (This is the right answer because the work landed in the branch but wasn't tagged.)
- **(b)** Delete the v0.26.0 CHANGELOG entry, bump canonical to 0.27.0, and re-derive everything from 0.26.0. (Wrong answer — it silently skips the work the team has been telling the world shipped.)
- **(c)** Leave both, accept the version drift. (Wrong answer — will keep confusing people.)

Collapse the 3 `[Unreleased]` sections into one (hand-edit + bot-managed unified section). **Unblocks:** release-please bot can run; version is consistent.

### Fix 8: Fix the remaining security P1s + legal entity (~2 hours)

- `headroom/proxy/webhooks.py:216` — refuse to start without `HEADROOM_WEBHOOK_SECRET` (no `headroom-dev-secret` default).
- `headroom/proxy/webhook_stores.py` — encrypt the `secret` column with the same Fernet key as `secrets_store.py`.
- `headroom/proxy/routes/secrets.py:67` — remove the `strict=False` default; require strict mode.
- `pyproject.toml` — tighten `cryptography>=41.0.0` → `~=46.0`; `PyJWT[crypto]>=2.8.0` → `~=2.11`; `fastapi>=0.100.0` → `>=0.115.0`.
- Resolve the `headroom_ee/LICENSE` vs `__init__.py` legal entity conflict (see Fix 1).
- `SECURITY.md` — update Supported Versions table to `0.25.x` and `0.26.x`.

**Unblocks:** SOC2 audit; enterprise procurement; FedRAMP/finance procurement.

### After all 8 fixes

- Test suite: 7198 + (6 fixed) + (58 fixed) - (5 Playwright if not addressed) = ~7255 pass / 5 fail / 256 skip
- Production score: 62 → ~80
- Enterprise score: 55 → ~75 (still need SAML SSO for full enterprise)
- OSS score: 70 → ~85
- All 4 release channels (PyPI, Docker Hub, Helm, npm openclaw) become CONDITIONAL-GO pending tag cut
- Internal deploy: CONDITIONAL-GO becomes GO for single-replica staging
- EE PyPI: still NO-GO until the legal-entity conflict is resolved

---

## Open items NOT addressed by these 8 fixes (for next round)

- SAML SSO (~1-2 weeks of `python3-saml` work; required for FedRAMP/finance procurement)
- Multi-replica HA coordination for the 13+ SQLite stores (each is single-writer per file)
- SSE for the dashboard (currently polls; no EventSource stream)
- Java SDK rebrand (`com.headroom.HeadroomClient` → `com.cutctx.CutctxClient`)
- I18n for hardcoded strings in CLI and dashboard
- Backups for the 13+ SQLite stores
- Native binary Prometheus exporter
- `cutctx learn_share` orphan
- SBOM generation (no `pip-audit`, no CycloneDX, no SPDX)
- Audit log DB-level append-only (currently schema allows UPDATE/DELETE; only hash-chain detection protects it)
- Spend ledger cross-tenant scope grant (potential for one tenant to query another's spend)
- `state_crypto.py` fingerprint binding (uses spoofable MAC)

---

## Lane attribution

| Recon lane | Session ID | Status |
|---|---|---|
| Build + artifact + dependency (exp-4) | `ses_1118cdc32ffed6j0O93xPM0eGj` | completed, reconciled |
| Test suite health (exp-5) | `ses_1117b4ac4ffehx5xs5KXAv5sT1` | completed, reconciled |
| Security surface (exp-6) | `ses_1116fc4e4ffeaRpYSpylWpftJU` | completed, reconciled |
| Release readiness (exp-7) | `ses_1116a3029ffe0WDKE8iY4GMtXg` | completed, reconciled |
| Rebrand shell state (exp-8) | `ses_11165dbedffeow0eKm7Lvvx82v` | completed, reconciled |
| Strategic synthesis (Oracle) | — | **errored (3 retries); orchestrator self-synthesized** |

## Final notes

This is the most thorough audit the cutctx repo has had. Round 4 found 14 P0s (3 false-closed from Round 3, 6 new regressions, 5 rebrand-related) and 24 P1s. The good news: 11 of the 14 P0s are mechanical (1-4 hours each); only 3 (DSR fix, air-gap wiring, Stripe tier validation) require real engineering thought. The bad news: the rebrand shell-leak has crossed from "naming inconsistency" to "actively breaking things" (Docker ENTRYPOINT, openclaw plugin hooks, EE legal entity) and the test suite is hiding production bugs behind 58 rebrand-leak failures.

The 8-fix plan is the path to a clean v0.26.1 release in ~2 days. Without it, the next round that runs will be Round 5.
