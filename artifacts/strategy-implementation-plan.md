# Implementation Plan: Context Control Plane Strategy

*Executable plan for an agent to implement `artifacts/product-strategy-moat-analysis.md` — with verification gates and zero-regression protocol.*
*Date: 2026-07-02. Grounded in actual repo structure (module paths verified against the tree).*

---

## 0. Ground rules for the implementing agent

These apply to **every** task below. Do not skip them to save time.

### 0.1 Zero-regression protocol

1. **Capture a baseline before any change.** Run the full suite and record results to a file:
   ```bash
   pytest tests/ -q 2>&1 | tail -20 > /tmp/baseline-pytest.txt
   cd dashboard && npx playwright test 2>&1 | tail -10 > /tmp/baseline-e2e.txt
   ```
   Pre-existing failures are **documented, not silently fixed and not used as cover** for new failures. Any test failing after your change that passed in baseline = regression = fix before proceeding.
2. **Feature-flag everything.** All new proxy/runtime behavior ships default-OFF behind a config flag or env var (`CUTCTX_*`), so the default request path is byte-identical to before. Flags are removed only in a later, explicit "graduate to default" task.
3. **Additive-only surfaces.** New CLI flags, API routes, DB columns, and config keys are additive. Never rename or remove an existing flag/route/column in this plan. Memory DB schema changes require a forward migration **and** must not break reads from an un-migrated DB (guard with `PRAGMA user_version` or column-existence check).
4. **Respect the EE boundary.** Apache-2.0 code lives in `cutctx/`; commercial code in `cutctx_ee` (see `LICENSING.md`, `scripts/compile_ee.py`, and the shim pattern in `cutctx/retention.py`). New governance/assurance features go EE-side with an Apache shim; new engine/reporting primitives stay Apache. When unsure, follow the `cutctx/retention.py` shim pattern.
5. **Per-task gate (run after every task, before marking it done):**
   - Targeted new tests pass: `pytest tests/test_<feature>*.py -q`
   - Full suite matches baseline: `pytest tests/ -q`
   - If proxy touched: relevant e2e (`tests/e2e_*.py`, `dashboard/e2e/`) matches baseline
   - If docs/dashboard touched: the corresponding build succeeds (use the exact commands in `.github/workflows/ci.yml` — consult it rather than guessing)
   - Coverage does not drop (codecov gate; write tests alongside code, not after)
6. **Commit per task**, message referencing the task ID below (e.g. `feat(policy): P2.1 content-rule engine skeleton`). One task = one reviewable commit. Never commit with a failing gate.

### 0.2 Verification is behavioral, not just tests

For each feature, drive the real flow once (proxy request through `cutctx proxy`, CLI invocation, dashboard page load) and confirm observed behavior matches the acceptance criteria. A green unit suite alone does not close a task.

### 0.3 Scope discipline

Implement exactly what the task says. If a task reveals a needed refactor, note it in `artifacts/strategy-implementation-notes.md` and continue — do not expand scope mid-task.

---

## Phase 1 (days 0–30): package existing strengths

### WS1 — Repositioning content (no code)

**Goal:** headline shifts from "60–95% fewer tokens" to "the context control plane for AI agents"; savings become proof on line 2.

| ID | Task | Files | Acceptance |
|---|---|---|---|
| P1.1 | Rewrite README lead: tagline block, "What it does" ordering (govern/attribute/compound before compress) | `README.md` | Savings claim present but subordinate; no broken anchors (`grep -o '(#[a-z-]*)' README.md` targets all exist) |
| P1.2 | Mirror positioning in product guide §1–2, competitive §15, pitch §19 | `PRODUCT_GUIDE.md` | Sections internally consistent with README |
| P1.3 | Update docs site + wiki + llms.txt lead copy | `docs/content/docs/*.mdx`, `wiki/*.md`, `llms.txt` | Docs build passes (command from CI); `llms.txt` first paragraph matches new positioning |
| P1.4 | Update pitch deck + outreach artifacts | `artifacts/pitchdeck.md`, `artifacts/50-client-outreach-plan.md` | Same three claims (Govern/Attribute/Compound) verbatim across all assets |

**Regression guard:** content-only; run docs build + `dashboard/e2e/ui.spec.js` (it asserts on some copy — check before/after).

### WS2 — Agent Context Report v1

**Goal:** one command emits a monthly, CFO/CISO-forwardable report assembling existing telemetry.

Existing scaffolding: `cutctx/reporting/generator.py`, `cutctx/savings/` (orchestrator, types), `cutctx/agent_savings.py`, `cutctx/audit.py`, accuracy-guard stats in the pipeline, `cutctx/learn/analyzer.py`.

| ID | Task | Detail | Acceptance |
|---|---|---|---|
| P1.5 | Define report data model | `cutctx/reporting/models.py` (new): sections = savings-by-source (5-source attribution), accuracy-guard verification stats, memory activity, learn corrections applied, audit/policy events count | Dataclasses serialize to JSON; unit tests with fixture data |
| P1.6 | Collectors | Extend `cutctx/reporting/generator.py` to pull each section from its existing store (savings tracker DB, audit log, learn scanner). Each collector degrades gracefully (section = "no data") if the source is absent | Collector unit tests: populated + empty-source cases |
| P1.7 | Renderers | Markdown + self-contained HTML output in `cutctx/reporting/renderers.py` (new) | Golden-file tests (`tests/fixtures/report_*`) |
| P1.8 | CLI | `cutctx report [--period 30d] [--format md\|html] [--out PATH]` in `cutctx/cli/` | `cutctx report` on a fresh install produces a valid "no data yet" report, exit 0 |
| P1.9 | Tests + docs | `tests/test_reporting_report.py`; docs page under `docs/content/docs/` | Per-task gate passes |

**Regression guard:** reporting is read-only over existing stores — assert no collector opens any DB in write mode (test it).

### WS3 — Quality-at-budget benchmark v1

**Goal:** public, reproducible eval: answer quality at N-token budget, comparing Cutctx compressors vs raw context vs provider-native compaction.

Existing scaffolding: `cutctx/evals/` (suite_runner, benchmark_runner, benchmark_report, metrics, datasets), `benchmarks/`, `benchmark_results.md`.

| ID | Task | Detail | Acceptance |
|---|---|---|---|
| P1.10 | Budget-sweep harness | New runner in `cutctx/evals/runners/` sweeping token budgets (e.g. 2k/8k/32k) per dataset, recording answer-quality metric from `metrics.py` | Deterministic under fixed seed/fixtures; unit tests mock the LLM call |
| P1.11 | Provider-native baseline | Adapter that applies provider-side compaction/context-editing as a comparison arm (behind `--baseline provider-native`; skip cleanly when no API key) | Runs offline in CI with recorded fixtures |
| P1.12 | Report + methodology | Generate `benchmarks/quality-at-budget.md` with methodology section (datasets, metrics, seeds, versions) so third parties can reproduce | Regenerating from fixtures is byte-stable |
| P1.13 | CI smoke | Add a small fixture-only benchmark run to CI so the harness can't rot | CI job < 5 min, no network |

**Regression guard:** evals are isolated from the runtime pipeline; verify `pip install cutctx-ai` (no `[evals]`) still imports cleanly (`python -c "import cutctx"`).

---

## Phase 2 (days 31–60): governance + org memory

### WS4 — Context policy engine MVP

**Goal:** declarative rules at the proxy — redact/block/allow by content type, destination provider, team — plus **cumulative per-agent/per-team token budgets** (existing `cutctx/proxy/budget.py` is per-request only).

Existing scaffolding: `cutctx/proxy/routes/policy.py` (EE router factory with admin-auth/RBAC deps), `cutctx/proxy/interceptors/`, `cutctx/proxy/budget.py`, `cutctx/rbac.py`, `cutctx/audit.py`, `cutctx/proxy/egress.py`, `cutctx/security/`.

| ID | Task | Detail | Acceptance |
|---|---|---|---|
| P2.1 | Rule schema + evaluator | EE-side `ContextRule` (match: content-type/provider/team/agent; action: allow/block/redact; precedence) + pure evaluator function. Apache shim per `cutctx/retention.py` pattern | Property-style unit tests on precedence and matching; evaluator is pure (no I/O) |
| P2.2 | Interceptor wiring | New interceptor in `cutctx/proxy/interceptors/` invoked in the pipeline **before** compression; default-OFF via `CUTCTX_POLICY_ENGINE=1` | With flag off: request bytes to upstream identical to baseline (add a golden proxy test asserting this) |
| P2.3 | Redaction actions | Reuse existing secret/PII detection in `cutctx/security/` for `redact`; `block` returns a structured 4xx with policy ID | e2e proxy test: seeded secret is redacted upstream, event audited |
| P2.4 | Cumulative budgets | Extend budget module: per-agent and per-team rolling windows persisted in the existing stats store; hard/warn modes mirroring `BudgetConfig` | Test: third request over budget is truncated/refused; window resets correctly |
| P2.5 | CRUD + audit | Wire rules into the existing `create_policy_router` factory (keeps admin-auth/RBAC); every rule mutation and every enforcement action writes to `cutctx/audit.py` | `tests/test_admin_surface_guards.py` still passes; new route tests cover authz denial |
| P2.6 | Dashboard surface | Policy list + enforcement-events panel in `dashboard/src/pages/Governance.jsx` | `dashboard/e2e/` extended; existing specs unchanged |

**Regression guard:** the golden "flag-off byte-identical" test from P2.2 is the contract — it must stay in the suite permanently.

### WS5 — Org-scope memory + export/import

**Goal:** ORG scope above USER in the memory hierarchy; RBAC-governed; portable.

Existing scaffolding: `cutctx/memory/` (backends, adapters, bridge), hierarchy USER→SESSION→AGENT→TURN, `cutctx/reporting/memory_export.py`, `cutctx/org.py`, `cutctx/rbac.py`, `cutctx/proxy/routes/memory.py`, `tests/test_memory_route_permissions.py`.

| ID | Task | Detail | Acceptance |
|---|---|---|---|
| P2.7 | ORG scope | Add ORG level to the scope enum + injection ranking (`cutctx/proxy/memory_ranker.py`, `memory_injection.py`); schema migration with `user_version` bump; old DBs read fine | Migration test: open pre-migration fixture DB, read + write succeed |
| P2.8 | RBAC on memories | ORG-scope writes require role via existing `cutctx/rbac.py`; route guards in `proxy/routes/memory.py` | `tests/test_memory_route_permissions.py` extended and green |
| P2.9 | Export/import | Extend `reporting/memory_export.py` with import: JSONL round-trip preserving provenance, supersession chains, embeddings-optional (re-embed on import) | Round-trip test: export→import→export is stable; dedup fires on colliding imports |
| P2.10 | CLI + docs | `cutctx memory export/import --scope org` + docs page | Fresh-install behavioral check per §0.2 |

**Regression guard:** memory injection latency budget — add a perf assertion (existing <50ms target) so ORG lookup doesn't slow the hot path; default behavior with no ORG memories is unchanged.

### WS6 — Learn telemetry aggregation (design + opt-in scaffolding)

**Goal:** patterns-only, anonymized cross-project aggregation; consent-first. This phase ships the local half only — no network egress.

| ID | Task | Detail | Acceptance |
|---|---|---|---|
| P2.11 | Design doc | `docs/content/docs/learn-telemetry.mdx`: what is collected (pattern templates only, never content), consent model, threat model | Reviewed against `PRIVACY.md`; no contradiction |
| P2.12 | Local aggregation | `cutctx learn --aggregate` merges pattern statistics across projects already scanned by `cutctx/learn/scanner.py` into one local summary | Unit tests on anonymization: no file contents, no paths outside allow-listed shapes, in output |
| P2.13 | Consent flag | `CUTCTX_LEARN_SHARE=1` + explicit CLI confirmation; default absolutely off; egress **not implemented yet** (stub raises `NotImplementedError`) | Test asserts no network call exists in the aggregate path (no httpx/requests import in module) |

---

## Phase 3 (days 61–90): assurance + replay

### WS7 — Context Assurance package (EE)

**Goal:** audit-grade answer to "what did the model see, and can you prove nothing was lost?"

Existing scaffolding: `cutctx/ccr/store.py` + `context_tracker.py`, accuracy guard, `cutctx/retention.py` (EE), `cutctx/audit.py`.

| ID | Task | Detail | Acceptance |
|---|---|---|---|
| P3.1 | CCR ledger | Append-only ledger per request: content hash in, compressed hash out, algorithm, guard verdict; chained hashes (each entry includes previous entry's hash) for tamper evidence | Ledger verification tool detects a mutated entry in tests |
| P3.2 | Retention integration | Ledger + CCR cache lifecycle governed by existing EE retention policies | Expiry test: content purged on schedule, ledger entry (hashes only) retained |
| P3.3 | Evidence export | `cutctx audit export --period` → signed bundle (ledger slice + guard stats + policy events) | Bundle verifies with the public key; golden-file test |
| P3.4 | Docs + report hook | Assurance section added to the Agent Context Report (WS2) | Report renders with and without EE installed |

### WS8 — Session replay alpha

**Goal:** time-travel view of one agent session: compressed / retrieved / memory-injected / policy-blocked events on a timeline.

Existing scaffolding: `cutctx/proxy/probe_recorder.py`, `request_logger.py`, `cutctx/observability/`, `cutctx/proxy/debug_introspection.py`, dashboard app.

| ID | Task | Detail | Acceptance |
|---|---|---|---|
| P3.5 | Event stream | Unified per-session event log (reuse probe recorder events; add memory/policy event types), behind `CUTCTX_REPLAY=1`, bounded size + retention-aware | Flag off: zero new writes (assert in test) |
| P3.6 | Replay API | Read-only route `GET /v1/sessions/{id}/replay` behind admin auth | Route test incl. authz denial |
| P3.7 | Dashboard page | Timeline view in `dashboard/src/pages/` wired via `use-dashboard-data.js` | New Playwright spec; existing specs green |

### WS9 — Design-partner readiness (gate, not code)

| ID | Task | Acceptance |
|---|---|---|
| P3.8 | End-to-end demo script: wrap → policy block → report → assurance export → replay, on a clean machine | Script runs green from `pip install`; recorded in `wiki/testing/manual-testing-guide.md` |
| P3.9 | Update `RELEASE_STATUS.md` + `CHANGELOG.md`; version bump per repo convention | Release checklist in `audit/` pattern followed |

---

## Global verification matrix (run at each phase boundary)

| Check | Command / source | Pass condition |
|---|---|---|
| Unit + integration | `pytest tests/ -q` | Matches or beats baseline; zero new failures |
| Proxy e2e | `tests/e2e_*.py` (see `E2E_TESTING.md`) | Baseline parity |
| Dashboard e2e | `cd dashboard && npx playwright test` | Baseline parity + new specs green |
| Docs build | exact command from `.github/workflows/ci.yml` | Green |
| TS SDK | `sdk/typescript` build + tests per CI | Green |
| Import hygiene | `python -c "import cutctx"` on minimal install (no extras) | No error |
| Flag-off parity | P2.2 golden test + P3.5 zero-write test | Byte-identical / zero-write |
| EE split | `scripts/compile_ee.py` completes; Apache tree has no EE imports outside shims | Green |
| Perf | memory-injection latency assertion (P2.7); proxy overhead spot-check | Within existing targets |

## Definition of done

Every task committed with its gate green; phase-boundary matrix green; all new behavior flag-gated with defaults off; `artifacts/strategy-implementation-notes.md` lists deferred refactors and any pre-existing baseline failures untouched. If a gate cannot be made green without expanding scope, stop and surface it — do not force-merge.
