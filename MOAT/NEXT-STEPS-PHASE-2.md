# Headroom — Next Steps: Phase 2 Execution Plan

**Control Plane of Record (MOAT Workstream C, PRs C4–C7)**

**Date:** 2026-06-16
**Status:** Ready for implementation (Phase 1 licensing C1–C3 is merged)
**Audience:** written to be handed directly to coding agents. One PR = one branch = one worktree; each PR lists exact files, schemas, endpoints, tests, and acceptance criteria.

> Phase 1 (Ed25519 licensing + activation/CRL + server-side seat/trial) is done. This plan builds the **system of record** on top of it. Broader rationale is in [`03-control-plane-of-record.md`](03-control-plane-of-record.md); read [`00-overview.md`](00-overview.md) for the moat thesis and [`NEXT-STEPS.md`](NEXT-STEPS.md) for the Phase 1 record.

---

## 1. Why this is Phase 2 (the moat mechanic)

Licensing made Headroom **sellable**. The control plane makes it **un-removable**: once finance budgets against the **spend ledger** and compliance exports the **tamper-evident audit log**, Headroom stops being a tool and becomes infrastructure. The switching cost is organizational (lost history + re-instrumentation + re-certification), not technical. This is the embedding moat from `00-overview.md` §3.

**Phase 2 goal:** ship, on the Phase-1 org/auth substrate —
1. a durable, multi-tenant **spend ledger** (tokens + cost + savings per org/workspace/project/agent/model/day),
2. a **policy engine of record** (versioned budgets / model allowlists / compression levels / rate limits, enforced at the proxy),
3. a **tamper-evident audit log** (hash-chained, exportable for SOC 2),
4. a **hosted + self-hostable control plane** that surfaces all of the above.

---

## 2. Current state (grounded — verified 2026-06-16)

Build on what exists; do not greenfield.

- **Metrics (spend inputs) — exist, but ephemeral.** Rust: `crates/headroom-proxy/src/observability/{proxy_metrics.rs, compression_ratio.rs, cache_hit_rate.rs, prometheus.rs, otel.rs, metric_names.rs}`. Python: `headroom/observability/{metrics.py, tracing.py}`. These expose token counts / compression ratios to Prometheus/OTel but there is **no durable, queryable, per-tenant ledger**.
- **Pricing — exists.** `headroom/pricing/{registry.py, anthropic_prices.py, openai_prices.py, litellm_pricing.py}`. `headroom/cost_forecast.py` already has `CostEstimator` (pre-task USD estimate) **and** a `PolicyEngine` (budget-driven compression-strategy selection). Phase 2 **extends** these — it does not replace them.
- **Tenancy — exists.** `headroom_ee/org.py` `OrgStore` (SQLite: `organizations / workspaces / projects / agents`, with indexes). Reuse as the tenant key everywhere.
- **Audit — partial.** `headroom_ee/audit.py` has `AuditAction`, `AuditEvent`, `AuditLogger.log()/async_log()`. **No `prev_hash` / chain / verify** yet.
- **Control-plane DB — exists.** `headroom_ee/billing/license_db.py` (licenses/activations/revocations/seat_leases/trials, `get_crl()`). Spend gets its **own** store (different lifecycle), keyed by the same tenant ids.
- **App assembly — known.** FastAPI app in `headroom/proxy/server.py` (~line 1715); routers mounted via `app.include_router(...)` (`create_admin_router` in `headroom/proxy/routes/admin.py` (tags `enterprise`, has auth deps); `license_router` in `headroom/proxy/routes/license_validation.py`). Add Phase-2 routers the same way.
- **Enforcement hook — known.** `crates/headroom-proxy/src/proxy.rs` dispatch is where policy is enforced. Per-request must stay deterministic/offline (policy cached at startup/refresh).
- **Portal seed + deploy.** `artifacts/license-portal.html`, `artifacts/openapi-management.yaml`, `helm/`.

**Gaps Phase 2 closes:** no durable spend ledger; policy is local/compression-only (not centralized, versioned, or enforced for budgets/allowlists/rate limits at the proxy); audit is not tamper-evident or centralized; no portal tying it together.

---

## 3. Operating rules for the implementing agent

Same as Phase 1 (see `NEXT-STEPS.md` §3). Highlights that bite in Phase 2:

1. **One PR = one branch = one worktree** (`moat-c4-…`). Respect the graph in §5.
2. **Boundary (enforced by CI leak guard `scripts/assert_oss_wheel_clean.py`):** the **ledger, policy store, and audit-chain logic are proprietary** → live in `headroom_ee/`. The **Rust emitter + policy enforcement** live in the Apache proxy. API route handlers in `headroom/proxy/routes/` stay Apache and **import `headroom_ee` lazily** (community edition must still import the module; only calling the enterprise path raises). Never add commercial code to the OSS wheel.
3. **Request path determinism:** the proxy enforces policy from a **locally cached, signed policy doc**; no control-plane call per request. Spend emission is **async/non-blocking** — a slow/down ledger must never add request latency.
4. **Fail-safe:** unreachable policy source → fall back to the last-known-good signed policy. Unreachable ledger → buffer locally, never block.
5. **Every PR ends green:** `make ci-precheck`, `cargo test -p headroom-proxy`, `pytest` for touched packages, ruff `0.9.4` + mypy, and the leak guard.
6. **Pin parity:** use `ruff==0.9.4` (matches `.pre-commit-config.yaml` and the pinned CI step).

---

## 4. Step 0 — Gate before building

1. Phase 1 is pushed and **CI is green** (lint pinned to ruff 0.9.4; leak guard passing).
2. `make dev-ee` works (`docs/dev-setup-ee.md`) — `headroom_ee` importable, `cargo test -p headroom-proxy` runs.
3. Tag `pre-controlplane-baseline`.

---

## 5. Phase 2 dependency graph

```
P2-1 spend event + Rust emitter ──> P2-2 ledger store ──> P2-3 spend query/export + dashboard
                                          │
P2-4 policy model + versioned store ──────┤(budget actions read rollups)
        │                                 │
        └──> P2-5 Rust policy cache + enforcement
P2-6 tamper-evident audit ──> P2-7 wire audit emitters (license/seat/trial/policy)
                                          │
        (all) ───────────────────────────┴──> P2-8 hosted control-plane + portal ──> P2-9 E2E + docs
```
Critical path: P2-1 → P2-2 → P2-3, and P2-4 → P2-5, converging at P2-8 → P2-9. P2-6/P2-7 parallel. P2-4 can start immediately (parallel to P2-1).

---

## 6. PR-by-PR plan

### P2-1 — Spend event schema + Rust spend emitter
**Branch:** `moat-c4-1-spend-emitter`
**Risk:** MEDIUM (touches request path; must be non-blocking)
**Depends on:** Step 0

**Spend event (emitted per upstream call):**
```json
{"ts":1718500000,"org_id":"…","workspace_id":"…","project_id":"…","agent_id":"…",
 "model":"claude-sonnet-4-6","provider":"anthropic","auth_mode":"payg",
 "input_tokens":50000,"output_tokens":2000,"tokens_saved":41000,
 "est_cost_usd":0.153,"est_cost_saved_usd":0.123,"request_id":"…"}
```

**Scope / files**
- **Add** `crates/headroom-proxy/src/observability/spend_emitter.rs`:
  - At response completion, assemble the event from existing counters (`proxy_metrics.rs`, `compression_ratio.rs`) + tenant ids from headers/config + model/provider.
  - **Async, bounded queue → batched POST** to `/v1/spend/events`; drop-with-warn on overflow; **never block or fail the request** on emitter error.
- **Modify** `crates/headroom-proxy/src/proxy.rs`: invoke the emitter after dispatch (behind `--spend-ledger` / `HEADROOM_SPEND_LEDGER_URL`, default off).
- **Modify** `crates/headroom-proxy/src/config.rs`: add the flag + URL + tenant-id resolution (org/workspace/project/agent from headers `X-Headroom-{Org,Workspace,Project,Agent}` or config).
- **Add** tests `crates/headroom-proxy/tests/spend_emitter.rs`.

**Acceptance**
- A request emits exactly one well-formed event with correct token counts + cost (unit test against a recorded fixture).
- **Latency invariant:** with the ledger endpoint stubbed to hang, p99 request latency is unchanged (load test asserts the emitter is off the hot path).
- Default off → zero network calls.

---

### P2-2 — Spend ledger store (proprietary)
**Branch:** `moat-c4-2-ledger-store`
**Risk:** HIGH (the embedding — must be accurate + durable)
**Depends on:** P2-1, Phase-1 `OrgStore`

**Scope / files** — new `headroom_ee/ledger/` (commercial SPDX headers):
- `headroom_ee/ledger/models.py` — `SpendEvent`, `SpendRollup`.
- `headroom_ee/ledger/store.py` — append-only `fact_spend_event` + materialized `rollup_spend_daily(org,workspace,project,agent,model,day → input/output tokens, tokens_saved, cost_usd, cost_saved_usd)`. SQLite (self-host) / Postgres (hosted) via a small DB-URL switch. WAL; partition/prune by day via `headroom_ee/retention.py`.
- `headroom_ee/ledger/pricing.py` — thin adapter over `headroom/pricing/registry.py` (+ `anthropic_prices`/`openai_prices`/`litellm_pricing`) to compute `est_cost_usd`/`est_cost_saved_usd` if the emitter didn't (single source of truth for prices).
- `headroom_ee/ledger/rollup.py` — hourly rollup job (idempotent upsert; safe to re-run).
- Tenant keys validated against `headroom_ee/org.py` `OrgStore`.

**Acceptance**
- Ingested events roll up correctly per dimension (golden-file test).
- Rollup is idempotent (run twice → same totals).
- Unknown/ချmissing tenant ids are recorded under an `"unattributed"` bucket, never dropped (test).

---

### P2-3 — Spend query + export API + dashboard
**Branch:** `moat-c4-3-spend-api`
**Risk:** MEDIUM
**Depends on:** P2-2

**Endpoints** (add `headroom/proxy/routes/spend.py` Apache router, lazy-import `headroom_ee.ledger`; mount in `server.py`; document in `artifacts/openapi-management.yaml`):
- `POST /v1/spend/events` — batched ingestion (auth: license token / admin key).
- `GET /v1/spend/rollup?group_by=project&from=&to=` — query.
- `GET /v1/spend/export?format=csv|json&from=&to=` — finance export.

**Scope / files**
- **Add** `headroom/proxy/routes/spend.py`; **modify** `headroom/proxy/routes/__init__.py` + `headroom/proxy/server.py` (`include_router`).
- **Modify** `headroom/cost_forecast.py` — `CostEstimator` reads realized prices from `headroom_ee.ledger.pricing` where available (keep estimator usable without EE).
- **Modify** `headroom/dashboard/` — add a "Spend" view (per project/agent/model; tokens saved; $ saved) and an exportable report via `headroom/reporting/`.

**Acceptance**
- Query returns per-project/agent/model spend + savings over a range; export reconciles to rollups (test).
- Ingestion endpoint rejects malformed events `422`; auth enforced (authz test).
- Community edition (no `headroom_ee`) imports the router fine; calling spend endpoints returns a clear "commercial component required" error.

---

### P2-4 — Policy model + versioned store (proprietary)
**Branch:** `moat-c5-4-policy-store`
**Risk:** MEDIUM-HIGH
**Depends on:** Step 0 (parallel to P2-1/2/3)

**Policy doc (versioned, signed):**
```json
{"version":7,"scope":{"org_id":"…","workspace_id":null,"project_id":null},
 "budgets":[{"window":"month","limit_usd":5000,"on_breach":"downgrade|warn|block"}],
 "model_allowlist":["claude-*","gpt-4o"],"compression_floor":"balanced",
 "rate_limits":[{"unit":"req/min","limit":600}],"updated_by":"user@org","updated_at":…}
```
Reuse the **existing** `cost_forecast.PolicyEngine` for the compression-strategy decision; Phase 2 generalizes it into a versioned, scoped, signed document that also covers budgets/allowlists/rate limits.

**Scope / files** — new `headroom_ee/policy/`:
- `models.py` (PolicyDoc + sub-rules), `store.py` (versioned CRUD per org/workspace/project; immutable history), `signer.py` (Ed25519-sign the resolved policy with the Phase-1 issuer key; clients verify offline — reuse `headroom_ee/billing/license_token.py` helpers), `resolver.py` (resolve effective policy for a scope: project ⊃ workspace ⊃ org).
- Budget evaluation reads `headroom_ee/ledger` month-to-date rollups (P2-2).

**Endpoints** (`headroom/proxy/routes/policy.py`, lazy EE import):
- `GET/PUT /v1/policy/{scope}` (RBAC-gated via `headroom_ee/rbac.py`), `GET /v1/policy/effective?org=&workspace=&project=`.

**Acceptance**
- Effective-policy resolution is correct and deterministic (project overrides workspace overrides org) — golden test.
- A PUT bumps `version` and preserves history (immutable; test).
- The resolved policy is Ed25519-signed and verifies with the embedded public key.

---

### P2-5 — Rust policy cache + enforcement
**Branch:** `moat-c5-5-policy-enforce`
**Risk:** HIGH (request path; deterministic + fail-safe)
**Depends on:** P2-4

**Scope / files**
- **Add** `crates/headroom-proxy/src/policy/mod.rs`: load + **verify** the signed effective policy at startup; refresh out-of-band (pull every N min or on SIGHUP); cache in memory. Enforce per request:
  - **model allowlist** → reject non-allowlisted models with a clear error;
  - **budget breach** (read a cached month-to-date figure refreshed out-of-band) → apply `on_breach` (warn header / force `compression_floor` / block);
  - **rate limits** → token-bucket per scope.
- **Modify** `crates/headroom-proxy/src/proxy.rs`: enforcement hook before upstream dispatch; emit an audit event (P2-6) on every block/downgrade.
- **Modify** `crates/headroom-proxy/src/config.rs`: `--policy-url` / `HEADROOM_POLICY_URL`, default off (no policy → today's behavior).

**Acceptance**
- Over-budget project triggers the configured action; non-allowlisted model blocked; rate limit returns `429` (tests).
- Enforcement is **deterministic** for a fixed policy + request (100-run determinism test); unreachable/ð invalid policy source → **last-known-good** signed policy (fail-safe test).
- With no policy configured, behavior is byte-identical to today (regression test vs golden fixtures + cache-safety SHA-256).

---

### P2-6 — Tamper-evident audit log (proprietary)
**Branch:** `moat-c6-6-audit-chain`
**Risk:** MEDIUM
**Depends on:** Step 0 (parallel)

**Scope / files** — upgrade `headroom_ee/audit.py`:
- Each event stores `prev_hash` and `hash = sha256(canonical(prev_hash || event))`; periodic **signed checkpoints** (Ed25519). Any insert/edit/delete in the middle breaks the chain → detectable.
- `verify_chain()` walks the log and validates hashes + checkpoints.
- Centralized ingestion + per-tenant export; self-host writes a local chain with an optional S3-WORM sink.
- **Endpoints:** `headroom/proxy/routes/audit.py` (lazy EE import) — `GET /v1/audit/export?from=&to=`, `POST /v1/audit/events` (internal).

**Acceptance**
- `verify_chain()` passes on an intact log and **fails** on any altered/removed event (test).
- Export produces a complete, verifiable per-tenant range.

---

### P2-7 — Wire audit emitters
**Branch:** `moat-c6-7-audit-emitters`
**Risk:** LOW-MEDIUM
**Depends on:** P2-6 (and P2-5 for policy events)

**Scope:** emit hash-chained audit events from every privileged action — license issue/activate/revoke (`headroom_ee/billing/*`), seat checkout/release (`headroom_ee/seats.py`), trial start (`headroom_ee/trial.py`), policy edits (P2-4), and proxy policy enforcement (block/downgrade, P2-5).

**Acceptance**
- Coverage test: each privileged action across billing/seats/trial/policy/enforcement appends exactly one verifiable audit event.

---

### P2-8 — Hosted control-plane assembly + portal + self-host
**Branch:** `moat-c7-8-control-plane`
**Risk:** HIGH (productionizes)
**Depends on:** P2-3, P2-5, P2-7

**Scope / files**
- Assemble the routers (`spend`, `policy`, `audit`, plus Phase-1 license/seat/trial) behind the FastAPI app in `headroom/proxy/server.py`, with admin auth (`HEADROOM_ADMIN_API_KEY`) + RBAC (`headroom_ee/rbac.py`) + optional SSO/SCIM (`headroom_ee/{sso,scim}.py`).
- Turn `artifacts/license-portal.html` into the admin portal: license issuance, seats, **spend dashboards**, **policy editor**, **audit export**.
- Self-host/air-gap: `helm/` chart for the control plane + local SQLite; `docker-compose.yml` profile. Finalize `artifacts/openapi-management.yaml`.

**Acceptance**
- End-to-end on a local instance: issue license → set a project budget policy → drive spend past it → enforcement triggers (block/downgrade) → audit chain records license + policy + enforcement events → finance export reconciles → `verify_chain()` passes.
- Self-host deploy works offline (air-gap test). Mutating endpoints reject missing/invalid auth.
- `make ci-precheck` + leak guard green.

---

### P2-9 — E2E, docs, boundary verification
**Branch:** `moat-c7-9-e2e-docs`
**Risk:** MEDIUM
**Depends on:** P2-8

**Scope**
- E2E test in `e2e/` covering the full flow above.
- Docs: `docs/control-plane.md` (operate), `docs/spend-ledger.md`, `docs/policies.md`, `docs/audit-compliance.md` (SOC 2 export).
- **Boundary check:** confirm `scripts/assert_oss_wheel_clean.py` still passes (no `headroom_ee` in the OSS wheel) and that all new ledger/policy/audit logic carries the `LicenseRef-Headroom-Commercial` SPDX header; route shims are Apache + lazy-import.

**Acceptance**
- E2E green in CI; leak guard green; SPDX/boundary check green; docs reviewed.

---

## 7. Appendices

**Signed policy format:** reuse the Phase-1 `hrk1`-style Ed25519 signing (`headroom_ee/billing/license_token.py`) over the canonical JSON of the resolved policy; proxy verifies with the embedded `prod-1` public key. Rotate via the same `kid` mechanism.

**Audit hash chain:** `hash_n = sha256(hash_{n-1} || canonical_json(event_n))`; checkpoint every K events with an Ed25519 signature over `(K, hash_K, ts)`. Store checkpoints alongside the log; `verify_chain()` recomputes and checks signatures.

**Pricing source of truth:** all cost math goes through `headroom/pricing/registry.py` (+ provider tables). The ledger never hardcodes prices; it records the price-table version used so historical rows are reproducible.

---

## 8. Verification strategy

- **Rust:** `cargo test -p headroom-proxy` (spend emitter latency invariant; policy determinism + fail-safe; cache-safety SHA-256 unchanged with no policy).
- **Python:** `pytest headroom_ee/ledger/tests headroom_ee/policy/tests headroom_ee/tests/test_audit_chain.py tests/test_spend_api.py` (after `make dev-ee`), ruff `0.9.4` + mypy clean on new files.
- **Leak guard:** `python3 scripts/assert_oss_wheel_clean.py dist` stays green; new server logic in `headroom_ee/` only.
- **Determinism + latency:** explicit tests that (a) the spend emitter is off the hot path and (b) policy enforcement is deterministic and fail-safe.

---

## 9. Definition of done (Phase 2)

- A durable, multi-tenant **spend ledger** answers "what did each org/workspace/project/agent/model cost and save, over time," with finance export that reconciles.
- **Policies** (budgets / allowlists / compression floor / rate limits) are versioned, signed, scoped, distributed, enforced **deterministically** at the proxy, and **fail safe**.
- A **tamper-evident** audit log records every privileged action and exports for SOC 2; `verify_chain()` detects tampering.
- All of it runs **hosted and self-hosted/air-gapped**; the OSS wheel stays clean (leak guard green).

## 10. Kill / scope guards

- **Don't rebuild commodity infra.** Reuse `headroom/pricing/*`, `cost_forecast.PolicyEngine`, `OrgStore`, `rbac.py`, Stripe/SSO/SCIM. The moat is the ledger/policy/audit **of record**, not the plumbing.
- **Latency is sacred.** If spend emission or policy enforcement ever shows up in p99, stop and move it off the hot path. A control plane that slows the proxy will be ripped out.
- **Don't gold-plate the portal.** A usable spend dashboard + policy editor + audit export is enough for the first design partner; defer multi-region/HA until there's demand.

## 11. After Phase 2 — unblock the moats

With trusted org identity (Phase 1) + a control plane (Phase 2), the two compounding moats can finally land on real infrastructure:
- **Data-flywheel insight service** — [`01-data-flywheel.md`](01-data-flywheel.md) PR-A7 (opt-in telemetry corpus + agent-tuned model).
- **Team-memory service** — [`02-memory-switching-costs.md`](02-memory-switching-costs.md) PR-B1 (co-created, value-scored memory as switching cost).
