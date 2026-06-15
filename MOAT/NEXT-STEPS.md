# Headroom — Next Steps: Phase 1 Execution Plan

**Licensing & Entitlement Hardening (MOAT Workstream C, PRs C1–C3)**

**Date:** 2026-06-16
**Status:** Ready for implementation
**Audience:** written to be handed directly to coding agents. One PR = one branch = one worktree; every PR lists exact files, schemas, crypto, tests, and acceptance criteria.

> This is the actionable execution plan for the **first build milestone** after the open-core relicensing + `headroom_ee` split. It deliberately covers only Phase 1. The broader moat specs live in [`01-data-flywheel.md`](01-data-flywheel.md), [`02-memory-switching-costs.md`](02-memory-switching-costs.md), [`03-control-plane-of-record.md`](03-control-plane-of-record.md), [`04-counter-positioning.md`](04-counter-positioning.md). Read [`00-overview.md`](00-overview.md) first.

---

## 1. Why this is Phase 1

Licensing is the **unblocker**:

- It closes the original revenue-blocking security holes (forgeable license, resettable trial, editable seats).
- It is the **auth substrate** the data-flywheel insight service (`01` PR-A7) and the team-memory service (`02` PR-B1) both depend on — neither can ship without trusted org identity + entitlement.
- It builds directly on code we just moved into the proprietary `headroom_ee` package, so it is concrete and grounded.

**Phase 1 goal:** replace the symmetric-HMAC license with **asymmetric (Ed25519) signed tokens**, add **online activation + revocation**, and make **seat and trial state server-authoritative** — while keeping existing HMAC-issued keys working during migration.

---

## 2. Current state (grounded — verified 2026-06-16)

**Licensing today is HMAC-symmetric.** Key facts the implementing agent must build on:

- **Rust verifier:** `crates/headroom-proxy/src/config.rs`
  - `LicenseTier` enum (`OpenSource | Team | Business | Enterprise`).
  - `LicenseTier::from_license_key(key)` → if env `HEADROOM_LICENSE_HMAC_SECRET` is set, calls `from_license_key_hmac` (HMAC-SHA256 over `{prefix}-{payload}`, signature appended as `.{hmac_hex}`); otherwise falls back to `from_license_key_prefix` (**INSECURE**: any `team-…` string → Team tier).
  - Deps already present: `hmac = "0.12"`, `sha2 = "0.10"` (`crates/headroom-proxy/Cargo.toml`). **No `ed25519-dalek` yet.**
- **Issuer + DB (now proprietary):** `headroom_ee/billing/license_db.py` — SQLite `licenses(license_key, tier, customer_email, seats, stripe_customer_id, stripe_subscription_id, created_at, expires_at, active)`; `get_license_db()`, `LicenseDB.upsert()`. Shim at `headroom/billing/` re-exports it.
- **Issuer tooling:** `scripts/generate_license.py` (HMAC-SHA256, payload = base64url JSON `{org, seats, expiry}`), `scripts/issue_license_from_webhook.py` (Stripe). Both allowlisted in `.gitignore` under `scripts/*`.
- **Entitlements / trial / seats (now proprietary, in `headroom_ee/`):** `headroom_ee/entitlements.py` (`EntitlementTier`, `FEATURE_TIERS`, `EntitlementChecker`), `headroom_ee/trial.py` (`TrialManager`, Fernet local state via `headroom/security/state_crypto.py`), `headroom_ee/seats.py` (`SeatManager`, Fernet local state). Apache shims at the old `headroom/…` paths.
- **Management API surface:** `headroom/proxy/routes/license_validation.py` (exists), `headroom/proxy/routes/admin.py` (admin router); contract drafted in `artifacts/openapi-management.yaml`.
- **Local-state crypto:** `headroom/security/state_crypto.py` (`read_encrypted_json` / `write_encrypted_json`, machine-derived Fernet).

**Gaps Phase 1 closes:** symmetric secret is forgeable if leaked + has no revocation/activation; `from_license_key_prefix` grants Team to any string; trial/seat truth is client-side (Fernet only obfuscates).

---

## 3. Operating rules for the implementing agent

1. **One PR = one branch = one worktree.** Branch names given per PR (`moat-c1-…`). Never mix PRs.
2. **Respect the dependency graph** (§5). Parallelize anything off the critical path.
3. **Every PR ends green:** `make ci-precheck`, `cargo test -p headroom-proxy`, and `pytest` for touched Python. The CI leak guard (`scripts/assert_oss_wheel_clean.py`) must stay green — never add commercial code to the OSS wheel.
4. **Commercial vs open boundary (enforced):** new server-side licensing logic, key issuance, activation/seat/trial servers, and revocation live in **`headroom_ee/`** (proprietary, `LicenseRef-Headroom-Commercial` SPDX header). Only the **client verifier** (offline token check, public keys, CLI plumbing) and the **Rust proxy verify path** stay Apache. When unsure, consult `LICENSING.md`.
5. **Secrets never in the repo.** The Ed25519 **private** signing key lives only in issuer env/KMS. Only **public** keys are embedded in the client/proxy. A CI secret-scan test must assert no private key material is committed.
6. **Backward compatibility:** existing HMAC-issued keys must keep validating until a dated deprecation. Never hard-break a paying customer mid-subscription.
7. **Determinism on the request path:** license verification is offline and pure given the token + cached CRL; no network call per request (activation/CRL refresh happens out-of-band with a grace window).
8. **Flag-default-safe:** the insecure prefix fallback is removed from release builds; any dev escape hatch is behind `HEADROOM_DEV_INSECURE_LICENSE=1` and compiled out of `--release`.

---

## 4. Step 0 — Land in-flight work before building (gate)

Do this before opening any Phase 1 PR:

1. **Push `main`** (commits `25fad54` types fix, `17b9f33` leak guard). `git pull --rebase` first if the remote advanced.
2. **Confirm CI is green** on the push: `lint` (ruff/mypy), `build-wheel`, the new **leak-guard** step, and the test shards. Fix any red before starting.
3. **Tag a baseline:** `git tag pre-licensing-baseline` so the migration has a rollback point.

---

## 5. Phase 1 dependency graph

```
P1-0 dev-env bring-up ──> P1-1 Ed25519 verify (Rust) ──> P1-2 Ed25519 issuer (Python)
                                  │                              │
                                  │                              ├──> P1-3 license DB schema
                                  │                              │         │
                                  └──────────────────────────────┴──> P1-4 activation + CRL endpoints
                                                                         │
                                              P1-5 seat lease ◄──────────┤
                                              P1-6 server-side trial ◄────┤
                                                                         ▼
                                                            P1-7 management service assembly
                                                                         ▼
                                                            P1-8 E2E + migration + docs
```

Critical path: P1-0 → P1-1 → P1-2 → P1-4 → P1-7 → P1-8. P1-3 parallel after P1-2. P1-5/P1-6 parallel after P1-4.

---

## 6. PR-by-PR plan

### P1-0 — Agent dev-environment bring-up (no product change)
**Branch:** `moat-c1-0-devenv`
**Risk:** NONE (docs + a make target)
**Depends on:** Step 0

**Why:** the implementing agent must be able to actually build and test. The OSS package builds via maturin; `headroom_ee` is a uv workspace member.

**Scope / files**
- **Add** `docs/dev-setup-ee.md`: the exact bring-up:
  - `uv sync --extra ee` (installs the OSS client + the commercial `headroom-ee` workspace member editable)
  - `maturin develop --profile dev` (builds `headroom._core` into the venv)
  - `pytest tests/test_cli/test_license_cli.py -q` and `cargo test -p headroom-proxy` as smoke checks
  - note: `headroom_ee` is importable in dev because the OSS package uses `python-source = "."`; `pytest pythonpath="."` covers CI.
- **Modify** `Makefile`: add `dev-ee` target running the two install commands above.

**Acceptance**
- On a clean checkout, `make dev-ee` yields a venv where `python -c "import headroom_ee, headroom; from headroom.entitlements import EntitlementChecker"` succeeds and `cargo test -p headroom-proxy` runs.

---

### P1-1 — Ed25519 license token format + Rust verifier
**Branch:** `moat-c1-1-ed25519-verify`
**Risk:** HIGH (gates all paid features; security-critical)
**Depends on:** P1-0

**Token format (`hrk1`):**
```
hrk1.<b64url(claims_json)>.<b64url(ed25519_sig)>
```
- `claims_json` (canonical, sorted keys, no whitespace):
  ```json
  {"lic_id":"uuid","org_id":"uuid","tier":"team|business|enterprise",
   "seats":25,"features":["audit_logs","sso"],"nbf":1718500000,
   "exp":1726449600,"iss":"headroom-issuer-v1","kid":"ed25519-2026-06"}
  ```
- `ed25519_sig` = Ed25519 signature over the ASCII bytes `hrk1.<b64url(claims_json)>` (sign the prefix+claims, not the whole string).
- `kid` selects the verifying key (enables rotation). Reject unknown `kid`.

**Scope / files**
- **Modify** `crates/headroom-proxy/Cargo.toml`: add `ed25519-dalek = "2"`, `base64 = "0.22"` (if not present), keep `serde_json`.
- **Add** `crates/headroom-proxy/src/license/mod.rs`:
  - `verify_license_token(token: &str) -> LicenseClaims | Err` — parse `hrk1.…`, decode claims, look up `kid` → embedded `VerifyingKey`, `verify_strict` the signature, check `nbf <= now < exp`. Pure/offline.
  - Embedded public keys: `const HEADROOM_LICENSE_PUBKEYS: &[(&str, &str)]` (`kid` → hex pubkey); compiled in. Support ≥2 keys for rotation.
  - `LicenseClaims { org_id, tier, seats, features, exp, … }`.
- **Modify** `crates/headroom-proxy/src/config.rs`:
  - `LicenseTier::from_license_key`: if token starts with `hrk1.` → `license::verify_license_token` then map `tier`→`LicenseTier`; else if it matches the legacy HMAC format AND `HEADROOM_LICENSE_HMAC_SECRET` is set → existing `from_license_key_hmac` (keep for migration); else `OpenSource`.
  - **Delete the insecure path:** `from_license_key_prefix` is removed from normal builds; gate any dev shortcut behind `#[cfg(...)]` + `HEADROOM_DEV_INSECURE_LICENSE=1`, and ensure it is compiled out of `--release` (test asserts this).
  - Surface resolved `seats`/`features`/`exp` from claims (not just tier) for downstream enforcement.
- **Add** tests `crates/headroom-proxy/tests/license_verify.rs`.

**Acceptance**
- Valid `hrk1` token → correct tier/seats/features. Tampering any claim byte → rejected. Unknown `kid` → rejected. Expired (`exp` past) / not-yet-valid (`nbf` future) → rejected.
- A legacy HMAC key still validates when `HEADROOM_LICENSE_HMAC_SECRET` is set.
- An arbitrary `team-xxx` string yields `OpenSource` (the old prefix exploit is dead) — regression test.
- `cargo test -p headroom-proxy` green; release build contains no insecure path (compile-feature test).

---

### P1-2 — Ed25519 issuer (Python, proprietary)
**Branch:** `moat-c1-2-ed25519-issuer`
**Risk:** HIGH (must match the Rust verifier byte-for-byte)
**Depends on:** P1-1

**Scope / files**
- **Add** `headroom_ee/billing/license_token.py` (commercial SPDX header):
  - `sign_license(claims: dict, sk: Ed25519PrivateKey, kid: str) -> str` → emits `hrk1.…` exactly as P1-1 expects (canonical JSON, same signed bytes).
  - `verify_license(token, pubkeys) -> claims` (Python mirror, for SDK-mode clients).
  - Uses `cryptography` (already a dependency: `cryptography>=41`).
  - Key handling: private key from `HEADROOM_LICENSE_ED25519_SK` (PEM/base64) — **never** read from the repo; helper to load from env/file path only.
- **Add** `scripts/license_keygen.py` (allowlist in `.gitignore`): generate an Ed25519 keypair, print the public key as the `(kid, hex)` line to paste into the Rust `HEADROOM_LICENSE_PUBKEYS`, and the private key for the issuer secret store. Never writes the private key into the repo tree.
- **Modify** `scripts/generate_license.py`: add `--algo ed25519` (default to ed25519 going forward; keep `--algo hmac` for legacy). Build the `hrk1` token via `license_token.sign_license`.
- **Modify** `scripts/issue_license_from_webhook.py`: issue `hrk1` tokens; persist via `license_db`.

**Acceptance**
- A token signed by `license_token.sign_license` **verifies in the Rust verifier** (cross-language round-trip test: Python signs a fixture, a `cargo test` reads it from a file and verifies). This is the critical interop gate.
- `scripts/license_keygen.py` produces a keypair; the private key never lands in the repo (secret-scan test).
- HMAC issuance still works behind `--algo hmac`.

---

### P1-3 — License DB schema extension (proprietary)
**Branch:** `moat-c1-3-license-db-schema`
**Risk:** MEDIUM
**Depends on:** P1-2

**Scope / files** — extend `headroom_ee/billing/license_db.py`:
- New tables (idempotent `CREATE TABLE IF NOT EXISTS`, with a tiny migration helper):
  - `activations(lic_id, install_fingerprint, activated_at, last_seen_at, PRIMARY KEY(lic_id, install_fingerprint))`
  - `revocations(lic_id PRIMARY KEY, revoked_at, reason)`
  - `seat_leases(lease_id PRIMARY KEY, lic_id, user_pseudonym, install_fingerprint, issued_at, expires_at, released_at)`
  - `trials(install_fingerprint PRIMARY KEY, org_id, started_at, exp)`
  - extend `licenses` with `kid TEXT`, `algo TEXT DEFAULT 'hmac'`, `revoked INTEGER DEFAULT 0`.
- Accessors: `record_activation`, `is_revoked`, `revoke(lic_id, reason)`, `active_seat_count(lic_id)`, `checkout_seat`, `heartbeat_seat`, `release_seat`, `start_or_get_trial(fingerprint, org_id)`.
- A `revocation_epoch` counter (bumped on any revoke) for cheap CRL caching.

**Acceptance**
- Fresh DB and an upgrade from the current schema both succeed (migration test).
- `checkout_seat` enforces the license `seats` ceiling; `start_or_get_trial` returns the original `started_at` on repeat fingerprints (no reset).

---

### P1-4 — Activation + revocation (CRL) endpoints + client cache
**Branch:** `moat-c1-4-activation-crl`
**Risk:** HIGH
**Depends on:** P1-2, P1-3

**Endpoints** (add to `artifacts/openapi-management.yaml` + implement in `headroom/proxy/routes/` — extend `license_validation.py` or add `routes/licensing.py`; server logic delegates to `headroom_ee`):
- `POST /v1/license/activate` `{token, install_fingerprint}` → records activation (P1-3), returns a short-lived signed **entitlement lease** (`hrk1`-style, `exp` ~24h) + current `revocation_epoch`.
- `GET /v1/license/crl?since=<epoch>` → `{epoch, revoked:[lic_id,…]}`.

**Client** (Rust proxy + `headroom_ee` helpers):
- On startup and every N hours: call `/activate` (binds install) and refresh CRL; cache to `~/.headroom/` encrypted via `headroom/security/state_crypto.py`.
- **Grace window** (default 72h): a transient outage does not downgrade; after grace with no refresh → drop to `OpenSource`.
- Per-request path stays offline (uses the cached lease + CRL).

**Acceptance**
- A revoked `lic_id` is denied after CRL refresh; within grace, a simulated CRL outage does **not** downgrade (tests).
- Activation binds the install fingerprint; the endpoint is idempotent per `(lic_id, fingerprint)`.

---

### P1-5 — Server-side seat lease
**Branch:** `moat-c1-5-seat-lease`
**Risk:** MEDIUM-HIGH
**Depends on:** P1-4

**Scope / files**
- **Endpoints:** `POST /v1/seats/checkout` → lease or `409 seats_exhausted`; `POST /v1/seats/heartbeat`; `POST /v1/seats/release` (backed by P1-3).
- **Modify** `headroom_ee/seats.py`: `SeatManager` becomes a **client** of the lease API; the local Fernet file is only an offline cache of a valid lease. Seat truth = active leases server-side. Offline grace = unexpired lease keeps working.
- **Add** `headroom_ee/tests/test_seat_lease.py`.

**Acceptance**
- The (N+1)th concurrent checkout for an N-seat license → `409` (test).
- A client that stops heart-beating frees its seat after TTL (test).
- Editing/deleting the local seat file cannot exceed the server ceiling (regression test for the original exploit).

---

### P1-6 — Server-side trial
**Branch:** `moat-c1-6-server-trial`
**Risk:** MEDIUM
**Depends on:** P1-4

**Scope / files**
- **Endpoint:** `POST /v1/trial/start` `{install_fingerprint, org_id?}` → signed trial token `{started_at, exp=+14d, fingerprint}`; server remembers the fingerprint (P1-3 `trials`); repeat starts return the **original** start.
- **Modify** `headroom_ee/trial.py`: `TrialManager` verifies the signed trial token; local Fernet file is only an offline cache. Expiry → Builder tier (unchanged downgrade behavior); core compression always works.
- **Add** `headroom_ee/tests/test_server_trial.py`.

**Acceptance**
- Deleting `~/.headroom/trial_state.json` and re-starting on the same fingerprint does **not** extend the trial (regression test for the documented exploit).
- Expired trial downgrades to Builder; core compression still works.

---

### P1-7 — Management service assembly + auth
**Branch:** `moat-c1-7-mgmt-service`
**Risk:** HIGH
**Depends on:** P1-4, P1-5, P1-6

**Scope**
- Wire `/v1/license/*`, `/v1/seats/*`, `/v1/trial/*` into the Python management layer (the FastAPI app serving the routes in `headroom/proxy/routes/`), with admin auth (`HEADROOM_ADMIN_API_KEY` per `openapi-management.yaml`) and RBAC (`headroom_ee/rbac.py`) on issuance/revocation.
- Finalize `artifacts/openapi-management.yaml` for all Phase-1 endpoints.
- Self-host parity: the same endpoints run in an air-gapped deploy (`helm/`), with the issuer’s public key embedded and an optional local CRL.

**Acceptance**
- End-to-end on a local instance: keygen → issue `hrk1` → activate → checkout seat → start trial → revoke → CRL denies after refresh.
- Mutating endpoints reject missing/invalid admin auth (authz test).
- `make ci-precheck` green; leak guard green (no commercial code in the OSS wheel).

---

### P1-8 — E2E, migration, and docs
**Branch:** `moat-c1-8-e2e-migration`
**Risk:** MEDIUM
**Depends on:** P1-7

**Scope**
- **E2E test** (`e2e/` or `tests/`): spin the proxy with an `hrk1` license → entitled features available; revoke → after CRL refresh, denied; trial path; seat exhaustion.
- **Migration runbook** `docs/licensing-migration.md`: re-issue active HMAC customers as `hrk1`; dual-accept window; dated removal of the HMAC path; key-rotation procedure (publish new `kid` pubkey, sign with new key, retire old after expiry).
- **Update** `README.md` / `ENTERPRISE.md` licensing sections and `artifacts/pricing-sheet.md` references if entitlement semantics changed.

**Acceptance**
- E2E passes in CI. Migration runbook reviewed. No HMAC hard-break for existing keys.

---

## 7. Crypto & key-management appendix

- **Algorithm:** Ed25519 (`ed25519-dalek` in Rust, `cryptography` in Python). Sign over `hrk1.<b64url(claims)>`; verify with `verify_strict`.
- **Keys:** private signing key only in the issuer secret store (`HEADROOM_LICENSE_ED25519_SK`); public keys embedded in client/proxy as a `kid`-indexed map for rotation. Minimum two keys live to allow rotation without downtime.
- **Rotation:** issue under a new `kid`; clients that ship the new pubkey accept both; retire the old `kid` after all keys signed under it have expired.
- **Why not JWT:** avoid alg-confusion / `alg:none` foot-guns. The fixed `hrk1` + Ed25519 format has exactly one verification path. (PASETO v4.public is an acceptable alternative if a vetted Rust+Python pair is preferred — keep the same claims.)
- **Clock skew:** allow ±60s on `nbf`/`exp` checks.

---

## 8. Verification strategy (how the agent proves each PR)

- **Rust:** `cargo test -p headroom-proxy` (incl. the new `license_verify.rs` and the cross-language interop fixture from P1-2).
- **Python:** `pytest headroom_ee/tests/ tests/test_cli/test_license_cli.py -q` (after `make dev-ee`).
- **Interop gate (most important):** a Python-signed token fixture is committed (public test vector, **no private key**) and verified by a `cargo test`; and a Rust-independent Python verify path confirms the same. A mismatch here means the formats diverged — block merge.
- **Leak guard:** `python3 scripts/assert_oss_wheel_clean.py dist` must stay green; new server/issuer code lives in `headroom_ee/` and must not appear in the OSS wheel.
- **Secret-scan:** a test/CI step asserts no Ed25519 private key material is committed (grep for PEM markers + the env var name in tracked files).

---

## 9. Definition of done (Phase 1)

- `hrk1` Ed25519 tokens issue (Python) and verify (Rust + Python), interop-tested.
- The three original exploits are closed with regression tests: forgeable license (insecure prefix removed), resettable trial (server fingerprint), editable seats (server lease).
- Activation + revocation work with an offline grace window; per-request verification stays offline/deterministic.
- Existing HMAC keys still validate during the migration window; a documented rotation + migration path exists.
- All server/issuer code is proprietary in `headroom_ee/`; the client verifier stays Apache; the leak guard is green.

## 10. Kill / scope guards

- **Don’t rebuild commodity infra.** Stripe (`headroom_ee/billing/stripe_webhook.py`), SSO (`headroom_ee/sso.py`), SCIM (`headroom_ee/scim.py`) already exist — integrate, don’t reimplement. The moat is the licensing/seat/trial/spend logic of record, not the plumbing.
- **Don’t gold-plate the control plane.** Phase 1 is licensing only. Spend ledger (`03` C4), policy engine (`03` C5), tamper-evident audit (`03` C6), and the hosted portal (`03` C7) are **Phase 2** — start them only after Phase 1 is in production and a first design partner is live.
- **Stop if interop is flaky.** If the Python↔Rust token round-trip isn’t rock-solid, fix the format before layering activation/seats/trial on top.

---

## 11. After Phase 1

- **Phase 2 — Control plane of record:** spend ledger + policy engine + tamper-evident audit + hosted portal (`03` C4–C7).
- **Then unblock the moats that needed auth:** data-flywheel insight service (`01` A7) and team-memory service (`02` B1) can now authenticate against the licensing/org substrate built here.
