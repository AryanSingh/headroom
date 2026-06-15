# Workstream C — Control Plane of Record

**Moat type:** Switching costs + workflow/organizational embedding.
**Thesis:** Become the system of record for AI-agent **spend, policy, and audit** across an org — and, on the way, fix licensing so we can actually charge. Once finance budgets against our spend ledger and compliance exports our audit log for SOC 2, Headroom stops being a tool and becomes infrastructure. Removal cost becomes organizational (lost history, re-instrumentation, re-certification), not just technical. This server is also the auth + tenancy substrate that Workstreams A (insight) and B (team memory) depend on.

**What already exists (build on, don't rebuild):**
- Rust: `crates/headroom-proxy/src/config.rs` — `LicenseTier` enum + `from_license_key_hmac` (optional symmetric HMAC) + `from_license_key_prefix` (insecure fallback: `ent-`/`biz-`/`team-`).
- Python: `headroom/entitlements.py` (`EntitlementTier`, `FEATURE_TIERS`), `headroom/trial.py` (Fernet machine-key state), `headroom/seats.py` (Fernet machine-key state), `headroom/billing/{license_db.py,stripe_webhook.py}`, `headroom/org.py` (`Org>Workspace>Project>Agent` SQLite), `headroom/rbac.py`, `headroom/scim.py`, `headroom/sso.py`, `headroom/audit.py`, `headroom/retention.py`.
- `headroom/observability/` + `crates/headroom-proxy/src/observability/{proxy_metrics.rs,compression_ratio.rs,prometheus.rs,otel.rs}` — metrics exist but are ephemeral, not a durable multi-tenant ledger.
- `artifacts/openapi-management.yaml` (seed API), `artifacts/license-portal.html` (seed UI).

**The gap:**
1. **Licensing is forgeable.** HMAC is symmetric (secret must exist somewhere; leak = forge), optional (falls back to prefix), with no revocation, no server-side expiry, no activation.
2. **Trial/seat truth is client-side.** Fernet only obfuscates; deleting/editing local state still defeats it. No server of record.
3. **No spend ledger.** Metrics are ephemeral; there is no durable, queryable, per-(org/workspace/project/agent/model/day) token+cost record with attribution/chargeback.
4. **No policy engine of record.** Budgets/model-allowlists/compression-levels/rate-limits aren't centrally defined, versioned, distributed, and enforced.
5. **No tamper-evident, exportable audit** for compliance.
6. **No hosted control plane** tying these together (with a self-host/air-gap option).

---

## Dependency graph

```
C1 (Ed25519 licensing) ──> C2 (seat lease) ──> C3 (server-side trial)
        │                       │
        └──> C7 (hosted control plane) <── C4 (spend ledger) <── (proxy observability)
                  ▲                         C5 (policy engine) ──┘
                  └──────────────────────── C6 (tamper-evident audit)
```
C1 first (unblocks revenue + is auth for A7/B1). C2/C3 after C1. C4/C5/C6 parallel after C1. C7 integrates all.

---

## PR-C1 — Asymmetric (Ed25519) signed license tokens + activation + revocation

**Branch:** `moat-C1-ed25519-licensing`
**Risk:** HIGH (gates all paid features; security-critical)
**Depends on:** none (highest priority — also unblocks A7, B1)

### Scope
Replace forgeable HMAC/prefix licensing with **asymmetric** signed license tokens. The signing **private key never leaves our issuer**; clients embed only the **public key** and verify offline. Add online activation (binds a license to an org + install fingerprint) and a revocation list with offline grace.

### Token format
Compact signed token (PASETO v4.public or a minimal Ed25519-over-JSON; prefer PASETO to avoid JWT alg-confusion pitfalls). Claims:
```json
{
  "lic_id": "uuid",
  "org_id": "uuid",
  "tier": "team|business|enterprise",
  "seats": 25,
  "features": ["audit_logs","sso","..."],
  "nbf": 1718500000,
  "exp": 1726449600,
  "iss": "headroom-issuer-v1"
}
```
- **Offline verify:** signature (Ed25519 public key baked into client), `nbf`/`exp`, tier/seats/features. Forgery is infeasible without the private key.
- **Online activation:** `POST /v1/license/activate {lic_id, install_fingerprint}` → records activation server-side, returns a short-lived **entitlement lease** (signed, e.g. 24h) + current revocation epoch. Enables real seat/trial truth and revocation.
- **Revocation:** `GET /v1/license/crl?since=epoch` → revoked `lic_id`s; cached locally; **grace window** (default 72h) so brief outages don't brick paying customers; after grace with no refresh, downgrade to `OpenSource`.

### Files
**Rust (verify path):**
- **Modify** `crates/headroom-proxy/src/config.rs` — replace `from_license_key_hmac`/`from_license_key_prefix` with `verify_license_token()` using `ed25519-dalek` (add dep to `Cargo.toml`). Keep the function signature returning `LicenseTier`. Remove the insecure prefix fallback (or guard it behind a `HEADROOM_DEV_INSECURE_LICENSE=1` dev-only flag that logs a loud warning and is compiled out of release builds).
- **Add** `crates/headroom-proxy/src/license/mod.rs` — token parse/verify, lease cache, CRL cache + grace logic, fingerprint.
- **Add** tests `crates/headroom-proxy/tests/license_verify.rs`.

**Python (issuer + client helpers):**
- **Modify** `headroom/billing/license_db.py` — issue/sign tokens (private key from KMS/secret, **never in repo**), store `lic_id↔org`, activations, revocations.
- **Add** `headroom/security/license_token.py` — sign/verify (client verify mirrors Rust for SDK mode), fingerprint helper.
- **Modify** `headroom/entitlements.py` — `EntitlementTier.from_token(claims)` replaces `from_str` for licensed paths.

### Acceptance criteria
- A tampered token (any claim edited) fails verification in both Rust and Python (tests).
- Removing the HMAC secret no longer grants any tier; an arbitrary string yields `OpenSource` (the old `team-`-prefix exploit is dead — regression test).
- Revoked `lic_id` is denied after CRL refresh; within grace, a transient CRL outage does not downgrade (tests).
- Private signing key is absent from the repo and from client artifacts (CI secret-scan + test).

---

## PR-C2 — Server-side seat lease

**Branch:** `moat-C2-seat-lease`
**Risk:** MEDIUM–HIGH
**Depends on:** C1

### Scope
Make seat count real: seats are **leased** from the server (checkout/heartbeat/release), server is the source of truth, with offline grace. `headroom/seats.py` becomes a client of the lease API instead of trusting local Fernet state.

### Mechanics
- `POST /v1/seats/checkout {org_id, user_pseudonym, install_fingerprint}` → `200` lease (signed, TTL e.g. 1h) or `409` seats_exhausted.
- `POST /v1/seats/heartbeat {lease_id}` renews; missed heartbeats expire the lease server-side (frees the seat).
- `POST /v1/seats/release {lease_id}`.
- Offline grace: a valid unexpired lease keeps working without network for the grace window; beyond it, block paid features (not core compression).
- Seat truth = active leases server-side; editing local files can't inflate it.

### Files
**Modify:** `headroom/seats.py` (lease client), `headroom/billing/license_db.py` (lease tables + seat ceiling from license claims).
**Add:** endpoints in control-plane service (C7) + `headroom/tests/test_seat_lease.py`.

### Acceptance criteria
- The (N+1)th concurrent checkout for an N-seat org returns `409` (test).
- A client that stops heartbeating frees its seat after TTL (test).
- Editing/deleting local seat state cannot exceed the server ceiling (test).

---

## PR-C3 — Server-side trial

**Branch:** `moat-C3-server-trial`
**Risk:** MEDIUM
**Depends on:** C1

### Scope
Record trial start **server-side**, keyed to org + install fingerprint, so deleting `~/.headroom/trial_state.json` can't reset it. Client verifies a signed trial token.

### Mechanics
- `POST /v1/trial/start {install_fingerprint, org_id?}` → signed trial token `{started_at, exp = +14d, fingerprint}`; server remembers the fingerprint.
- Re-starting on the same fingerprint returns the **original** start (no reset).
- `headroom/trial.py` verifies the signed token; absence/expiry → Builder tier features only (unchanged downgrade behavior).

### Files
**Modify:** `headroom/trial.py` (token verify; keep Fernet only as offline cache of the signed token), `headroom/billing/license_db.py` (trial fingerprints).
**Add:** `headroom/tests/test_server_trial.py`.

### Acceptance criteria
- Deleting local trial state and re-starting on the same fingerprint does **not** extend the trial (regression test for the documented exploit).
- Expired trial downgrades to Builder; core compression still works.

---

## PR-C4 — Spend ledger (system of record)

**Branch:** `moat-C4-spend-ledger`
**Risk:** HIGH (this is the embedding — must be accurate + durable)
**Depends on:** C1 (auth/tenancy)

### Scope
A durable, append-only, multi-tenant ledger of token spend and cost, rolled up per `(org, workspace, project, agent, model, day)`, ingested from proxy observability, queryable, exportable, with chargeback attribution. This is the number finance comes to depend on.

### Data model
```
fact_spend_event(   -- append-only, partitioned by day
  org_id, workspace_id, project_id, agent_id,
  model, provider, auth_mode,
  input_tokens, output_tokens,
  tokens_saved, est_cost_usd, est_cost_saved_usd,
  ts
)
rollup_spend_daily( org_id, workspace_id, project_id, agent_id, model, day,
  input_tokens, output_tokens, tokens_saved, cost_usd, cost_saved_usd )
```
- Cost via a per-provider/model price table (reuse/extend `headroom/pricing/` + `headroom/cost_forecast.py`).
- Ingestion: the Rust proxy already computes per-request token + compression metrics (`observability/compression_ratio.rs`, `proxy_metrics.rs`); add a batched emitter to the ledger ingestion endpoint. Backpressure-safe; never blocks the request path.
- Storage: Postgres (hosted) / SQLite (self-host), partitioned, append-only; rollups materialized hourly.

### Endpoints (add to `openapi-management.yaml`)
- `POST /v1/spend/events` — batched ingestion (auth via license token).
- `GET /v1/spend/rollup?group_by=project&from=&to=` — query.
- `GET /v1/spend/export?format=csv|json` — finance export.

### Files
**Add:** `services/control-plane/spend/` (models, ingestion, rollup job, query), `crates/headroom-proxy/src/observability/spend_emitter.rs`, tests.
**Modify:** `headroom/pricing/` (price table), `headroom/cost_forecast.py` (read from ledger), `artifacts/openapi-management.yaml`.

### Acceptance criteria
- Ingested events roll up correctly per dimension (golden-file test).
- Query returns per-project/agent/model spend + savings over a range.
- Ingestion failure or slowness **never** affects proxy latency (load test asserts request path unaffected when ingestion endpoint is down).
- Export matches rollups (reconciliation test).

---

## PR-C5 — Policy engine of record

**Branch:** `moat-C5-policy-engine`
**Risk:** MEDIUM–HIGH (enforces in hot path; must be deterministic + fail-open-safe)
**Depends on:** C1, C4

### Scope
Centrally define, version, distribute, and enforce policies: per-scope **budgets** (with action on breach: warn / downgrade-compression / block), **model allowlists**, **compression levels**, **rate limits**. Every decision audited. Policies are scoped to org/workspace/project and versioned.

### Mechanics
- Policy doc (versioned, signed) distributed to proxies at startup + on change (pull or push); proxy enforces from local cache (deterministic, no per-request server call).
- Budget breach actions reference C4 rollups (e.g., "if project month-to-date > $X → force max compression / block non-allowlisted models").
- Enforcement lives in `crates/headroom-proxy/src/proxy.rs` dispatch; decisions emit audit events (C6).

### Endpoints
- `GET/PUT /v1/policy/{scope}` — versioned CRUD (RBAC-gated).
- `GET /v1/policy/effective?org=&workspace=&project=` — resolved policy for a scope.

### Files
**Add:** `services/control-plane/policy/` (versioned store, resolver, signer), `crates/headroom-proxy/src/policy/mod.rs` (cache + enforce), tests.
**Modify:** `crates/headroom-proxy/src/proxy.rs` (enforcement hook), `headroom/rbac.py` (policy-admin perms).

### Acceptance criteria
- A project over budget triggers the configured action (test for warn/downgrade/block).
- A non-allowlisted model is blocked with a clear error (test).
- Policy resolution is deterministic and cached (no per-request control-plane call; determinism test).
- Misconfigured/unreachable policy source **fails safe** to the last-known-good signed policy (test).

---

## PR-C6 — Tamper-evident, exportable audit log

**Branch:** `moat-C6-audit-chain`
**Risk:** MEDIUM
**Depends on:** C1

### Scope
Upgrade `headroom/audit.py` to a **hash-chained** (tamper-evident) log, centralized in the control plane, exportable for SOC 2 / customer compliance, with optional WORM. Audited events: license/seat/trial changes, policy edits, memory curation (B4), admin actions, budget-breach enforcement.

### Mechanics
- Each event stores `prev_hash`, `hash = H(prev_hash || canonical(event))`; periodic signed checkpoints. Any mutation breaks the chain → detectable.
- Centralized ingestion + per-tenant export (`/v1/audit/export?from=&to=`).
- Self-host: local chain + optional S3 WORM sink.

### Files
**Modify:** `headroom/audit.py` (chain + verify), wire emitters from C1/C2/C3/C5 + B4.
**Add:** `services/control-plane/audit/` (ingestion, export, checkpoint signer), `headroom/tests/test_audit_chain.py`.

### Acceptance criteria
- `verify_chain()` passes on an intact log and **fails** on any altered/removed event (test).
- Export produces a complete, verifiable per-tenant range.
- Privileged actions across C1/C2/C3/C5/B4 all emit audit events (coverage test).

---

## PR-C7 — Hosted control plane (assemble) + portal + self-host

**Branch:** `moat-C7-control-plane`
**Risk:** HIGH (productionizes the service)
**Depends on:** C1–C6

### Scope
One FastAPI service implementing `openapi-management.yaml` + license/seat/trial (C1–C3) + spend (C4) + policy (C5) + audit (C6) + insight (`01`/A7) + team memory (`02`/B1). Turn `artifacts/license-portal.html` into the admin UI (license issuance, seats, spend dashboards, policy editor, audit export). Ship a **self-host / air-gap** deployment (Helm chart already exists at `helm/`).

### Files
**Add:** `services/control-plane/` (compose all routers, authn/z via license token + RBAC + SSO/SCIM from `headroom/{sso.py,scim.py,rbac.py}`), `services/control-plane/Dockerfile`, `services/control-plane/tests/`.
**Modify:** `artifacts/license-portal.html` → real portal wired to the API; `helm/` (control-plane chart); `docker-compose.yml`; `artifacts/openapi-management.yaml` (finalize).

### Acceptance criteria
- End-to-end: issue license → activate → checkout seat → ingest spend → set budget policy → breach triggers action → audit chain records all of it → export verifies.
- Self-host deploy via Helm works offline (air-gap test) with local Postgres/SQLite.
- AuthN/Z enforced on every mutating endpoint (authz coverage test).
- `make ci-precheck` green; service image builds and passes smoke tests.

---

## Definition of done (Workstream C)
- The three documented security holes (forgeable license, resettable trial, editable seats) are closed and have regression tests.
- A spend ledger answers "what did org/workspace/project/agent/model cost and save, over time" and exports for finance.
- Policies (budgets/allowlists/levels/limits) are versioned, distributed, enforced deterministically, and audited.
- Audit log is tamper-evident and exportable for SOC 2.
- All of it runs hosted **and** self-hosted/air-gapped.
- **Kill check:** don't rebuild commodity auth/billing — if a workstream item is "reimplement Stripe/SSO," stop and integrate the existing vendor path (`billing/stripe_webhook.py`, `sso.py`). The moat is the ledger/policy/audit of record, not the plumbing.
