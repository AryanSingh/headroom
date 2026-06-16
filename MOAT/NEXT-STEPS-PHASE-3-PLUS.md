# Headroom — Remaining Roadmap (Phase 3+): All Next Steps

**Master, agent-executable plan for everything left in the moat program.**

**Date:** 2026-06-16
**Status:** Phase 1 (licensing C1–C3) ✅ and Phase 2 (control plane C4–C7) ✅ are merged. This plan sequences and specs **all remaining work**.
**Audience:** hand directly to coding agents. One PR = one branch = one worktree; each PR lists files, schemas, tests, acceptance. Deep per-PR detail for A/B/D already lives in [`01-data-flywheel.md`](01-data-flywheel.md), [`02-memory-switching-costs.md`](02-memory-switching-costs.md), [`04-counter-positioning.md`](04-counter-positioning.md); this doc is the **current-state-grounded execution wrapper** + the tracks those specs don't cover (commercial enablement, validation, legal).

---

## 0. Where we are / what you can now build on

**Done:** open-core relicense + `headroom_ee` split + leak guard; Ed25519 `hrk1` licensing with activation/CRL + server-side seat/trial; control plane = spend ledger + signed policy (dynamic budgets) + tamper-evident audit.

**Reusable substrate (do not rebuild — wire into it):**
- **Auth / identity:** `headroom_ee/billing/license_token.py` (`sign_license`/verify, `hrk1`), activation/CRL in `headroom/proxy/routes/license*.py`. New services authenticate with the license token + admin key.
- **Tenancy:** `headroom_ee/org.py` `OrgStore` (org/workspace/project/agent). Every new table keys on these ids.
- **Server pattern:** `headroom_ee/{audit,ledger,policy}/{models,store,query,api}.py` (SQLAlchemy) + a thin **Apache** router in `headroom/proxy/routes/<x>.py` that **lazy-imports** `headroom_ee` and is mounted in `headroom/proxy/server.py`. Copy this shape for every new service.
- **Audit:** `headroom_ee/audit/store.py` (`verify_chain`, sha256 `previous_hash`/`event_hash`). Every privileged action in new services emits an audit event.
- **RBAC / SSO / SCIM:** `headroom_ee/{rbac,sso,scim}.py`.
- **Signing:** reuse the Ed25519 `prod-1` key + `sign_policy`/`sign_license` helpers for any new signed artifact (model manifests, residency proofs).
- **CI invariants:** leak guard (`scripts/assert_oss_wheel_clean.py`), ruff `0.9.4` pinned, mypy, `make dev-ee`.

---

## 1. Strategic note (read once)

The infrastructure now leads validation: there are **no design partners yet**, and ship-readiness items are open (full `pytest` + real `maturin` wheel build verified only by CI; legal: entity/CLA/counsel; no delivery pipeline for `headroom_ee`). You've chosen to build all remaining workstreams — good, but run **Track 0 (validate & ship) in parallel from day one**, and honor each phase's **kill-criteria**. Don't let Phase 4 (data flywheel) run for months without the design-partner data that proves it's a moat.

---

## 2. Master sequence & dependency graph

```
Track 0 (parallel, non-code): Validate & Ship + Legal + CI verification   ── runs throughout
Phase 3  Workstream B — Team memory (switching costs)      [BUILD FIRST]
Phase 4  Workstream A — Data flywheel (learning moat)      [LONG GAME; needs design partners]
Phase 5  Workstream D — Counter-positioning (provider-proof)
Phase 6  Commercial enablement — distribution + portal + SOC 2

Edges:
  Phase 1/2 substrate ──> B1 (memory service auth/tenant/audit)
  Phase 1/2 substrate ──> A7 (insight service auth) , A2 outcome signal ──> B2 memory value
  Track 0 design-partner data ──> A5/A6 (model training + kill-decision)
  B + A ──> Phase 6 (sell the moats)
```

**Recommended parallelism (3 agents):**
- Agent-1 → **Phase 3 (B)** end to end.
- Agent-2 → **Track 0** CI/ship items + **Phase 6** distribution scaffolding.
- Agent-3 → **Phase 4 (A) A1–A4** (local capture + DP egress; no model training until design-partner data exists).

---

## 3. Operating rules (all phases)

Same as Phases 1–2. The ones that bite here:
1. **Boundary:** new **service logic** (memory intelligence, insight corpus, training, residency proofs) is proprietary → `headroom_ee/`. The **client/proxy hooks** (memory injection, telemetry capture, egress firewall) stay Apache. Routers lazy-import EE. Leak guard must stay green.
2. **Request-path determinism + latency:** no per-request control-plane/network calls; cache + refresh out-of-band (the Phase-2 stale-while-revalidate pattern). Telemetry/memory writes are async/non-blocking.
3. **Privacy is a test:** every egress path ships a blocking test asserting no raw values leave (see `01` A4).
4. **Eval-gate every model** (`01` A6): promote only on offline-eval win + shadow retrieval-rate win.
5. **Flag-default-off** for every new collection/sync/egress feature; explicit opt-in.
6. Green per PR: `make ci-precheck`, `cargo test -p <crate>`, `pytest`, ruff 0.9.4 + mypy, leak guard.

---

## TRACK 0 — Validate & Ship (parallel, mostly non-code)

**Goal:** turn "built" into "proven + sellable." Run continuously.

- **T0-1 CI truth:** push; confirm CI green end-to-end — `lint` (ruff 0.9.4 pinned), `build-wheel` (maturin), **leak guard**, all `pytest` shards, `cargo test`. Fix real failures (the "8.5/10, 7,767 tests" audit number is self-reported and unverified — CI is the arbiter).
- **T0-2 Real artifact check:** in CI, `unzip -l dist/*.whl | grep headroom_ee` is empty; `maturin build` + `import headroom._core` smoke passes on the manylinux floor.
- **T0-3 Legal (gates revenue):** set the real legal entity in `LICENSE-COMMERCIAL`/`NOTICE`/`headroom_ee` headers (replace "Headroom Labs" placeholder); contributor CLA/copyright audit for relicensed modules; counsel review of `LICENSE-COMMERCIAL`. Confirm already-published Apache releases remain Apache (irrevocable).
- **T0-4 Design partners:** recruit 3–5 from AI-heavy eng teams (per `00-overview` + `03` Phase 2 of GTM). Goal: validated ROI numbers + ≥1 case study + the **traffic** Phase 4 needs.
- **T0-5 Reproducible benchmarks** (`04` D4): publish head-to-head vs LLMLingua-2 / Morph Compact / lean-ctx **and** vs provider-native caching across providers.

**Acceptance:** CI green on `main`; legal sign-off; ≥1 signed design partner; public benchmark page.

---

## PHASE 3 — Workstream B: Team Memory (switching costs)  [BUILD FIRST]

**Why first:** cheapest real moat; co-created memory that can't leave with the customer. Full spec: [`02-memory-switching-costs.md`](02-memory-switching-costs.md). Current surface to build on: `headroom/memory/{store,models,sync,storage_router,extractor,budget,core,system}.py`, `headroom/memory/sync_adapters/`, `headroom/proxy/memory_{ranker,injection,decision,handler,query}.py`, `headroom/learn/{analyzer,scanner,registry}.py`.

**Dependency graph:** B1 → B2 → B3 → {B4, B5, B6}. B2 also consumes A2's outcome signal.

| PR | Branch | Build (grounded) | Acceptance |
|----|--------|------------------|------------|
| **B1 Team Memory Service** | `moat-b1-team-memory-svc` | New **proprietary** `headroom_ee/memory_service/{models,store,sync,api}.py` (mirror `headroom_ee/ledger` shape). Multi-tenant via `OrgStore`; delta-sync protocol; client side in `headroom/memory/sync.py` + `storage_router.py` (route to service when configured, else local). Add `workspace_id`/`project_id`/`provenance`/`value_score` to `headroom/memory/models.py`. Apache router `headroom/proxy/routes/memory.py` (lazy EE import), mounted in `server.py`; auth via license token; **`/v1/memory/sync`**, **`/v1/memory/query`** added to `artifacts/openapi-management.yaml`. | Two clients in one project converge after sync; concurrent edits → supersession chain (no lost write); tenant isolation (authz test); default off → no network. |
| **B2 Provenance + value scoring** | `moat-b2-memory-value` | `headroom/memory/value.py` (`ValueModel`): EWMA value from the **outcome signal** (A2). Stamp `Provenance` on every memory in `learn/*` + `extractor.py`. Decay + auto-archive below floor. | Cited-before-success memory rises; uncited decays/archives; provenance on all 4 sources; idempotent per outcome. |
| **B3 Load-bearing injection + measured impact** | `moat-b3-memory-impact` | `headroom/proxy/memory_ranker.py` rank by `value×relevance` (within `memory/budget.py`); add `headroom/evals/runners/memory_impact_runner.py` (matched-pair with/without injection); surface `memory_impact` in `headroom/observability` → dashboard. Deterministic injection (no in-request value mutation). | Value-weighted order within budget; impact runner yields success-rate + token deltas; determinism test. |
| **B4 Curation & governance** | `moat-b4-curation` | `headroom_ee/memory_service` review states (proposed→approved→deprecated); `headroom_ee/rbac.py` role `memory_curator`; every transition emits a **Phase-2 audit-chain** event. | Non-curator can't approve; transitions audited (`verify_chain` passes); cross-project promotion scoped. |
| **B5 Portability policy** | `moat-b5-portability` | `headroom/memory/export.py` `export_raw()` (content+provenance portable; value model / graph edges / embeddings / curation **not** exported). `docs/memory-portability.md`. | Round-trips content; omits intelligence-layer fields (test). |
| **B6 Value dashboard** | `moat-b6-value-dashboard` | `headroom/dashboard/` "Team Memory" view + `headroom/reporting/` export: accumulated value, $-saved-via-memory, success lift, top memories. | Renders real metrics from B3; CSV/PDF export. |

**Phase-3 DoD / kill:** memory syncs team-wide, value-scored, with a **measured** success/cost lift (the load-bearing proof) and a deliberate portability asymmetry. **Kill:** if the impact runner shows no stable lift, memory isn't load-bearing — stop adding memory features.

---

## PHASE 4 — Workstream A: Data Flywheel (learning moat)  [LONG GAME]

**Why later/parallel-capture:** the only durable *technical* moat, but it needs **design-partner traffic** (Track 0) before training is meaningful. Full spec: [`01-data-flywheel.md`](01-data-flywheel.md). Surface: `headroom/telemetry/{toin,beacon,collector,models,reporter}.py` (+`backends/`), `headroom/ccr/{batch_store,context_tracker,response_handler}.py`, `headroom/evals/*`, `headroom/models/{registry,ml_models,config}.py`, `crates/headroom-core/src/signals/*` + `relevance/*`.

**Sequence:** A1 → A2 → A3 → A5 → A6 → A8 (model loop); A4 → A7 (privacy egress + hosted corpus, needs Phase-1 auth). **Start A1–A4 now** (local capture + DP egress, no training); gate A5+ on design-partner data.

| PR | Branch | Build (grounded) | Acceptance |
|----|--------|------------------|------------|
| **A1 Episode store** | `moat-a1-episode-store` | `headroom/telemetry/episodes.py` (SQLite `~/.headroom/episodes.db`): `CompressionEpisode` (kept/dropped **span offsets**, never text) + `RetrievalLabel`. Emit from `ccr/response_handler.py` (compress) + `ccr/context_tracker.py` (retrieve). Local-only. | compress→retrieve makes 1 episode + 1 label; **no raw payload in DB** (sentinel-grep test). |
| **A2 Outcome signal** | `moat-a2-outcome-signal` | `headroom/telemetry/outcome.py`; hook `headroom/learn/scanner.py` terminal events → success/fail/unknown. **Feeds B2.** | green-test session → success; revert → fail; unknown excluded. |
| **A3 Label builder** | `moat-a3-label-builder` | `headroom/training/{schema,label_builder}.py` → keep/drop training examples (retrieved span = SHOULD_KEEP; never-retrieved under success = SAFE_TO_DROP). | retrieved→keep, unused-under-success→drop; deterministic golden test. |
| **A4 DP egress (opt-in)** | `moat-a4-dp-egress` | `headroom/telemetry/dp.py` (Laplace/Gaussian + ε budget) + `backends/https_beacon.py` (signed, queued, license-token auth). Only patterns/labels leave; k-anon enforced server-side (A7). Federated mode = aggregate deltas only. Default OFF. | **blocking privacy test** (sentinels never egress); ε enforced; off → zero calls. |
| **A5 Train keep/drop model** | `moat-a5-train-keepdrop` | `headroom/training/{dataset,train_keepdrop,export_onnx}.py`; phase-1 span classifier over `relevance/*` features → ONNX int8; phase-2 `kompress-agent-*`. Split by org pseudonym. **Gate on Track-0 data.** | smoke-train emits signed ONNX + card; no pseudonym leak across splits. |
| **A6 Rollout gate + registry channel** | `moat-a6-rollout-gate` | `headroom/evals/runners/keepdrop_eval.py` + shadow retrieval-rate; `headroom/models/registry.py` `agent-tuned` channel, signature-verified, **entitlement-gated** (`kompress-agent-*` Team+; base stays open). | regressor rejected; unsigned rejected; agent model refuses without entitlement. |
| **A7 Insight service (corpus)** | `moat-a7-insight-svc` | **proprietary** `headroom_ee/insight/{models,store,api}.py`: ingest DP contributions, **k-anonymity admission**, dedup → versioned corpus. Apache router lazy-import; auth via license token (Phase 1). | sub-k pattern excluded; no-values schema enforced (422); ε per pseudonym enforced. |
| **A8 Rust learned scorer** | `moat-a8-rust-learned-scorer` | `crates/headroom-core/src/signals/learned_scorer.rs` loads promoted ONNX at startup; falls back to `line_importance.rs`. `--keepdrop-model` flag. | no model → byte-identical to today (golden); determinism (100 runs); cache-safety SHA-256 intact. |

**Phase-4 DoD / kill:** closed loop on **one design partner** (episodes→labels→k≥5 corpus→agent model→eval+shadow gate→Rust loads it); agent model proprietary, base open; privacy tests green. **Kill:** across ≥10 orgs, if the agent model can't beat `kompress-v2-base` on held-out eval AND cut live retrieval rate → A is not a moat; double down on B + Phase 6.

---

## PHASE 5 — Workstream D: Counter-Positioning (provider-proof)

Roadmap items providers structurally won't copy. Full spec: [`04-counter-positioning.md`](04-counter-positioning.md). Build after B (and alongside A).

| PR | Branch | Build (grounded) | Acceptance |
|----|--------|------------------|------------|
| **D1 Spend-bounded cross-provider router** | `moat-d1-spend-router` | `crates/headroom-proxy/src/routing/spend_router.rs` (decision in `proxy.rs`); quality bar via `headroom/evals`; cost via **Phase-2 ledger**; honor **Phase-2 policy** allowlist. | cheapest model clearing the bar chosen; respects allowlist; A/B shows cost down at equal quality. |
| **D2 Verifiable no-egress proof** | `moat-d2-no-egress-proof` | `headroom/security/firewall.py` enforce + record; `headroom/security/residency_proof.py` signed periodic attestation tied to the **Phase-2 audit chain**. `docs/data-residency.md`. | rogue-sink blocked + audited; residency proof verifies/exports. |
| **D3 Provider failover/portability** | `moat-d3-provider-portability` | `crates/headroom-proxy/src/routing/failover.rs` + format translation across `sse/*` + `bedrock/*`; reuse `headroom-parity` for round-trip. | simulated outage fails over with translation; parity preserves tool calls + streaming. |
| **D4 Positioning & benchmarks** | (non-code, Track 0) | Lead with cross-provider control + reversible fidelity + local-first governance; publish the benchmarks from T0-5. | benchmarks live; messaging shipped. |

**Guiding test:** "Would a rational provider refuse to build this (loses them money/lock-in)?" Yes → prioritize. No → match, don't lead.

---

## PHASE 6 — Commercial Enablement (turn "built" into "sellable")

The control plane exists; now make it deliverable and certifiable.

- **P6-1 `headroom_ee` distribution pipeline.** Build + publish the commercial wheel from `packaging/headroom-ee/` to a **private index** (or license-server-gated download); never to public PyPI. Add a release workflow (separate from `release.yml`) gated on a valid entitlement. Document install: `pip install headroom-ee --index-url <private>`. **Acceptance:** a customer with a license can install `headroom_ee`; public PyPI never receives it (leak guard + index separation).
- **P6-2 Finish the admin portal** (`artifacts/license-portal.html` → real UI on the management API): license issuance, seats, spend dashboards, policy editor, audit export. **Acceptance:** issue→activate→set budget→view spend→export audit, all from the portal.
- **P6-3 Self-host / air-gap** Helm chart for the control plane (`helm/`) + local SQLite; offline deploy test.
- **P6-4 SOC 2 Type II** kickoff: map the tamper-evident audit (`headroom_ee/audit`) + RBAC + retention to controls; start the audit window (6–9 mo, gates regulated buyers).
- **P6-5 Billing wiring:** confirm `headroom_ee/billing/stripe_webhook.py` issues `hrk1` licenses on subscription events end-to-end (re-use, don't rebuild).

---

## 4. Verification strategy (every phase)

- **Rust:** `cargo test -p headroom-proxy` / `-p headroom-core` (determinism, fail-safe, cache-safety SHA-256 unchanged when features off).
- **Python:** `pytest headroom_ee/<svc>/tests headroom/<area>/tests` after `make dev-ee`; ruff `0.9.4` + mypy clean on new files; **SPDX commercial header on every new `headroom_ee/*` file** (Phase 1/2 repeatedly missed this — make it a checklist item and grep for it).
- **Boundary:** `python3 scripts/assert_oss_wheel_clean.py dist` green; new service logic in `headroom_ee/`; routers lazy-import.
- **Privacy/determinism/latency:** explicit blocking tests per `01` A4 + the Phase-2 latency invariant.

## 5. Definition of done (program)

- A **team-memory** moat with measured outcome lift (Phase 3).
- A **data flywheel** with a proprietary agent-tuned model that beats base on real traffic — or an honest kill decision (Phase 4).
- **Counter-positioning** shipped (router, no-egress proof, failover) + public benchmarks (Phase 5).
- `headroom_ee` **deliverable** to paying customers, portal usable, SOC 2 underway (Phase 6).
- Throughout: CI green, leak guard green, legal closed, ≥1 design partner validating the assumptions (Track 0).

## 6. Standing guardrails

- Don't out-build validation — Track 0 runs in parallel; honor kill-criteria.
- Reuse the substrate (auth/tenant/ledger/policy/audit/signing) — the moat is the data + switching costs, not re-plumbing.
- Latency is sacred; privacy is a test; determinism on the request path.
- Every new proprietary file gets the `LicenseRef-Headroom-Commercial` SPDX header and stays out of the OSS wheel.
