---
id: AUD-OPENCODE-STATIC-2026-08-04-01
kind: audit-report-static
title: OpenCode Exhaustive Static Control Audit of Cutctx/Headroom
date: 2026-08-04
product: Cutctx/Headroom
revision: d1dd7cae0775ffb411b487a9e3093a38c93cb31b
criteria: dist/audit-current/control-catalog.csv (38 canonical controls) cross-referenced against engineering-handbook/ checklist front matter and the product source tree
state: COMPLETE — static evidence only; no tests or binaries executed; no runtime or live-provider behavior claimed; no product code modified; nothing committed
---

# OpenCode Exhaustive Static Control Audit

## Scope and method

This audit is **static and evidence-based**. For each of the 38 canonical controls in
`dist/audit-current/control-catalog.csv` (verified byte-identical to
`dist/control-catalog.csv`), I located:

- the authoritative control record in `engineering-handbook/checklists/*.md` front matter
  (the handbook designates checklist front matter, not the appendix, as the authoritative
  control record),
- product source implementing the requirement, and
- automated test paths exercising it.

Only paths verified to exist in the tree are cited. **No product code was modified, no
tests or binaries were run, no runtime or live-provider behavior is claimed, and nothing
was committed** (`git status --porcelain` empty; audited revision `d1dd7cae`).

## Status vocabulary applied (from `engineering-handbook/appendices/control-catalog.md`)

| Status | Static meaning used here |
| --- | --- |
| Pass | Implementation in product source **and** automated tests in the tree were found (presence of evidence; behavior NOT verified — see Limits). |
| Fail | No implementation and/or no test automation found in the tree for the stated requirement. |
| Exception | No registered, time-bounded approved exception records were found anywhere in the tree (see Finding F-4); no control is marked Exception. |
| Not applicable | No control: every applicability condition is present in this product. |
| Not evaluated | The control's core evidence is runtime/live/production-only (load, recovery, chaos outcomes, billing reconciliation, alert exercising, live reachability). Automation or source may exist; no static claim of compliance is made. |

"Not evaluated" is a static-ethics position, not a defect claim: per the handbook, an
unverifiable required control is treated as failing for release purposes.

## Findings

### F-1 — Catalog and appendix control IDs disagree (required by this audit to be documented)

The CSV catalog (38 controls) matches the authoritative checklist front matter for all
38 IDs. `engineering-handbook/appendices/control-catalog.md` (40 rows) disagrees with
both on naming and content:

| CSV / checklist front matter | Appendix alternative | Disagreement |
| --- | --- | --- |
| `GOV-AUDIT-001/002` | `ENG-AUDIT-001/002` | ID family renamed (CSV+checklists vs appendix). |
| `GOV-MAP-001/002` | `ENG-DISCOVERY-001/002` | ID family renamed. |
| `ENG-CV-001/002` | `ENG-CVRA-001/002` | ID family renamed. |
| `ENG-INT-001/002` | `ENG-INTEGRATION-001/002` | ID family renamed. |
| `ENG-MEM-001/002` | `ENG-MEMORY-001/002` | ID family renamed. |
| `ENG-ROUTE-001/002` | `ENG-ROUTING-001/002` | ID family renamed. |
| `ENG-UI-001` | `ENG-DASHBOARD-001/002` | 1 CSV control vs 2 appendix controls, different IDs. |
| `ENG-DESKTOP-001` | `ENG-DESKTOP-001/002` | Appendix adds `ENG-DESKTOP-002` (IPC allowlist) with no CSV counterpart. |
| `ENG-CLI-001/002` | `ENG-CLI-001/002` | Shared IDs, but **requirement text differs for CLI-002**: CSV = "Machine-readable CLI output is parseable and free of human diagnostics"; appendix = "Production-impacting CLI action is authorized". |
| 23 controls (AGENT, AIEVAL, API, CHAOS, COMM, MIGRATION, OBS, PLAYWRIGHT, RELENG, RELPERF, SDKCOMPAT) | same | IDs and requirements agree. |

Net: 15 CSV IDs absent from the appendix, 17 appendix IDs absent from the CSV, 1 shared
ID with divergent requirement text (`ENG-CLI-002`). The CSV agrees with the checklist
front matter (the handbook's authoritative control records); the appendix is the
outlier and should be regenerated in step with `engineering-handbook/automation/export_catalogs.py`.

### F-2 — CSV schema deviates from `engineering-handbook/governance/control-schema.md`

The CSV `title` column is empty for all 38 rows, and `title` is not a schema field
(`engineering-handbook/governance/control-schema.md` requires: id, requirement, applicability, procedure, expected_result,
evidence, automation, owner, frequency, failure_action, standards). The CSV omits
procedure, expected_result, evidence, automation, and failure_action entirely, and uses
`standard` (singular) instead of the schema's `standards` list. The CSV is a read-only
projection for indexing; it is not a conforming control record and cannot, alone, satisfy
the handbook's evidence requirements.

### F-3 — `ENG-CLI-002` requirement text divergence (see F-1 table)

The appendix's `ENG-CLI-002` ("Production-impacting CLI action is authorized") is a
different control than the CSV's `ENG-CLI-002` (machine-readable output). Audit of the
CSV/checklist version below. The appendix's CLI-002 semantics appear nowhere in the CSV.

### F-4 — No registered exceptions in tree

`engineering-handbook/governance/exception-management.md` defines the exception process, but no
time-bounded, approved exception records (no `EXC-` records, no approved-waiver artifacts)
were found in `audit/`, `dist/`, or `engineering-handbook/`. Hence no control is marked
Exception. Absence of a registered exception means unverified required controls must be
treated as failing for release.

### F-5 — Reproducibility limit: compiled EE variants

`cutctx_ee/` ships `.so` compiled variants (e.g., `entitlements.cpython-312-darwin.so`,
`rbac.cpython-312-darwin.so`, `retention.cpython-312-darwin.so`) alongside `.py` sources.
This audit read the `.py` sources; if the shipped `.so` differs from the `.py`, static
path citations for those modules describe the source tree, not necessarily the deployed
binary.

## Control disposition (38 canonical controls, one row each)

Legend: S = source path evidence; T = test path evidence; L = explicit limits.
All paths are relative to repo root and were verified to exist.

| ID | Status | Source paths | Test paths | Limits |
| --- | --- | --- | --- | --- |
| ENG-AGENT-001 | Not evaluated | `cutctx_ee/policy/models.py:15-29` (budget/rate/allowed-model policy), `cutctx_ee/policy/resolver.py:32-93` (dynamic budget enforcement, PR-P2-5), `cutctx/orchestration/workflow.py` (task lease/owner model) | Adjacent only: `tests/test_orchestration_workflow.py:21-93` (claims, idempotency, cancellation) | Partial implementation found (budget dimension); no time-bounded grant covering tenant/tool/action/escalation and no dedicated grant test found; grant semantics are runtime. |
| ENG-AGENT-002 | Pass | `cutctx/orchestration/workflow.py:53,73-74,331` (`requires_approval`, `approval_granted`, `awaiting_approval`), `cutctx/proxy/routes/orchestration.py`, `cutctx/mcp_registry/cursor.py`, `cutctx/mcp_registry/json_registrar.py` | `tests/test_orchestration_workflow.py:40-93` (idempotent submission, cancellation terminal, single-owner claims) | Static presence only; no claim that approval-to-outcome chains reconcile against live authoritative systems. |
| ENG-AIEVAL-001 | Pass | `cutctx/evals/` (23 modules: `cutctx/evals/suite_runner.py`, `cutctx/evals/prompt_comparison.py`, `cutctx/evals/cost_tracker.py`, `cutctx/evals/memory/runner.py`, `cutctx/evals/batch_compression_eval.py`), `.github/workflows/eval.yml` | `tests/test_model_routing_evals.py` (19 tests), `tests/test_model_routing_quality_benchmark.py:6` | No evaluation results or baseline comparisons in tree; datasets/score reports are runtime artifacts. |
| ENG-AIEVAL-002 | Pass | `cutctx/proxy/model_routing_evals.py`, `cutctx/proxy/server.py` (route decision path), `cutctx_ee/policy/resolver.py` | `tests/test_model_routing_evals.py` (shadow sampling stable/bounded, defaults off), `tests/test_routing_modes_e2e.py:81-100` | Independent route verification at runtime not executed here. |
| ENG-API-001 | Pass | `cutctx/proxy/server.py:3637,3812,3818,4286` (admin/agent/hosted auth guards), `cutctx_ee/rbac.py`, `cutctx_ee/entitlements.py` | `tests/test_auth_adversarial.py:10,25`, `tests/test_proxy_client_auth.py` (9 tests), `tests/test_agent_client_auth.py` (8), `tests/test_ccr_admin_auth.py` (3) | Tenant/resource resolution semantics not exercised in this audit. |
| ENG-API-002 | Pass | `cutctx/orchestration/workflow.py` (idempotent submission), `cutctx/mcp_registry/base.py`, `cutctx/mcp_registry/codex.py` | `tests/test_orchestration_workflow.py:40` (idempotency key survives restart), `tests/test_webhooks.py:51` (idempotent subscribe) | Payment/provisioning idempotency against external processors is runtime-only. |
| ENG-CHAOS-001 | Not evaluated | `.github/workflows/chaos-testing.yml` (kind cluster + deploy + synthetic load & pod evictions, line 45), `engineering-handbook/checklists/chaos-engineering.md`, runbooks | None found | Automation exists; experiment plan/approval/abort-authority artifacts are runtime records; no executed experiment evidence in tree. |
| ENG-CHAOS-002 | Not evaluated | `engineering-handbook/runbooks/data-recovery.md` (RB-DATA-002), `engineering-handbook/checklists/chaos-engineering.md` | None found | Outcome reconciliation (client-visible vs business ledger) is runtime; no reconciliation fixture in tree. |
| ENG-CLI-001 | Pass | `cutctx/cli.py`, `cutctx/cli/` (42 modules), `cutctx/cli/config.py`, `cutctx/cli/auth.py` | `tests/test_cli/` (29 files: `tests/test_cli/test_main_help_version.py`, `tests/test_cli/test_auth.py`, `tests/test_cli/test_global_routing.py`, `tests/test_cli/test_routing_status.py`, `tests/test_cli/test_proxy_client_credentials.py`, ...) | Non-interactive completion not re-executed here; tests are subprocess-based and headless. |
| ENG-CLI-002 | Pass | `cutctx/cli/capabilities.py:254,277` (`--json` flag, `json.dumps` payload emission) | `tests/test_cli/test_init_cli.py` (JSON/`--json` coverage); output-contract tests in `tests/test_cli/` | Parseability verified only statically; see F-1/F-3 for appendix's divergent CLI-002 definition. |
| ENG-COMM-001 | Pass | `cutctx_ee/entitlements.py`, `cutctx_ee/billing/license_db.py`, `cutctx_ee/seats.py`, `cutctx_ee/trial.py` | `tests/test_billing_integration.py` (27 tests: tier mapping, seats), `tests/test_cli/test_proxy_entitlement_tier.py` (2), `tests/test_dashboard_governance_e2e.py:248` (entitlement error gating) | Enforcement at every background/worker boundary not exercised here. |
| ENG-COMM-002 | Not evaluated | `cutctx_ee/ledger/{api,models,pricing,query,store}.py`, `cutctx_ee/billing/stripe_webhook.py`, `cutctx_ee/billing/pitchtoship_client.py` | Adjacent only: `tests/test_billing_integration.py` (tier/seat mapping) | Ledger-to-invoice reconciliation against a payment processor is runtime; no reconciliation fixture in tree. |
| ENG-CV-001 | Pass | `.github/workflows/product-release-evidence.yml:4-33` (PR/push/workflow_dispatch/workflow_call gates), `scripts/evaluate_release_evidence.py:10` | `tests/test_release_evidence.py:51,79` (eligibility, hash-mismatch rejection), `tests/test_release_workflows.py:15` (53 tests, workflow YAML validity) | Promotion gating behavior not executed; CI outcomes are runtime evidence. |
| ENG-CV-002 | Pass | `.github/workflows/release.yml`, `.github/workflows/release-please.yml`, `scripts/evaluate_release_evidence.py` | `tests/test_orchestration_rollouts.py:56-122` (evidence-gated promotion, canary activation, rollback) | Rollout/rollback execution is runtime; only automation presence is evidenced. |
| ENG-DESKTOP-001 | Not evaluated | `desktop/cutctx-control/` (Tauri app: `src/`, `src-tauri/src/credentials.rs`, `src-tauri/src/lib.rs`) | `desktop/cutctx-control/src/lib/status.test.ts`, `desktop/cutctx-control/src/lib/credentials.test.ts` | Upgrade/interruption recovery is runtime; no upgrade-interruption automation found in tree. |
| ENG-INT-001 | Pass | `cutctx_ee/billing/stripe_webhook.py:54-83` (`verify_stripe_signature`: constant-time HMAC, replay tolerance, `hmac.compare_digest`) | `tests/test_webhooks.py:51-168` (idempotent subscribe, event-type/org filters, fire/enqueue) | No direct unit test for `verify_stripe_signature` found; provider/tenant-binding verification runtime. |
| ENG-INT-002 | Not evaluated | `cutctx/orchestration/workflow.py:53,73-74` (approval fields), `cutctx/mcp_registry/cursor.py`, `cutctx/cli/mcp.py`, `cutctx/cli/wrap.py` | Adjacent only: `tests/test_orchestration_workflow.py` | Explicit user-owned approval at the execution boundary is runtime; no dedicated approval-boundary test found. |
| ENG-MEM-001 | Pass | `cutctx/memory/adapters/sqlite.py`, `cutctx/memory/backends/graphiti.py`, `cutctx/memory/backends/graphiti_ledger.py`, `cutctx/memory/tools.py`, `cutctx_ee/memory_service/{api,models,store}.py` | `tests/test_retention.py` (12 tests), `tests/test_quality_retention.py` (16), `tests/test_memory_system.py` | Cross-tenant/revocation retrieval verdicts not re-verified. |
| ENG-MEM-002 | Pass | `cutctx_ee/retention.py`, `cutctx_ee/memory_service/store.py` | `tests/test_retention.py` (12 tests, defaults/env/init/stats), `tests/test_quality_retention.py` (16, error/anomaly retention) | Per-layer (index/cache/export) deletion timing is runtime. |
| ENG-MIGRATION-001 | Pass | `sql/create_dashboard_summary.sql`, `sql/create_proxy_telemetry_v2.sql`, `sql/upgrade_dashboard_v2.sql`, `sql/upgrade_telemetry_cache_bust.sql`, `sql/upgrade_telemetry_stack_context.sql` | `tests/test_sql_migrations.py` (11 tests: manifest coverage, no duplicates, base-before-upgrade, telemetry precedence) | No checkpoint/resume or interruption tests found; destructive-change decision boundary is runtime. |
| ENG-MIGRATION-002 | Not evaluated | `engineering-handbook/runbooks/failed-migration.md`, `engineering-handbook/runbooks/data-recovery.md` | None found (no restore/reconciliation test in tree) | Backup-restore rehearsal and tenant-scoped reconciliation are runtime; runbook procedure present only. |
| ENG-OBS-001 | Pass | `cutctx/proxy/server.py` (tracing), `cutctx/proxy/prometheus_metrics.py` | `tests/test_observability_tracing.py:21,36,64,71` (trace endpoint, spans, default-off, explicit enable) | Correlation/redaction verified only statically. |
| ENG-OBS-002 | Not evaluated | `k8s/prometheus-rules.yaml:4-50` (cutctx-alerts: HighErrorRate, HighLatency, UpstreamFailureSpike, WebSocketCapacityRejections), `cutctx/proxy/prometheus_metrics.py` | None found | Alert ownership/routing/exercising is runtime; earlier `audit/go-no-go-assessment.md:161` recorded a thin rule set, since grown to 4 rules in tree. |
| ENG-PLAYWRIGHT-001 | Pass | `dashboard/src/App.jsx:90-99` (critical journeys: governance, security, memory, replay, playground) | `tests/test_dashboard_surfaces_playwright.py:76`, `tests/test_dashboard_cache_ttl_playwright.py` (1), `tests/test_dashboard_governance_e2e.py:164,248`, `tests/test_dashboard_orchestrator_policy_e2e.py:448-547`, `tests/test_dashboard_capabilities_toggles_e2e.py` (13 tests total) | Browser results not re-run; recorded evidence is `dist/visual-qa/` (final/pilot ledgers). |
| ENG-PLAYWRIGHT-002 | Pass | `dashboard/src/` (state handling), `dist/visual-qa/final-ledger.json`, `dist/visual-qa/pilot-ledger.json` (retained artifacts) | `tests/test_dashboard_audit.py:422-479` (keyboard Tab, `/`, Escape interaction) | Accessibility assertions are partial; artifact redaction review is runtime. |
| ENG-RELENG-001 | Pass | `scripts/evaluate_release_evidence.py:10`, `scripts/build_ee_manifest.py`, `.github/workflows/sign-artifacts.yml`, `.github/workflows/publish.yml` | `tests/test_release_evidence.py:79` (hash mismatch rejection), `tests/test_release_manifest.py` (4 tests) | Artifact immutability/attribution at promotion is runtime/CI evidence. |
| ENG-RELENG-002 | Pass | `.github/workflows/product-release-evidence.yml`, `scripts/evaluate_release_evidence.py` | `tests/test_orchestration_rollouts.py:122` (canary activation and rollback), `engineering-handbook/runbooks/rollback.md` (procedure) | Rollback execution and stop-threshold behavior are runtime. |
| ENG-RELPERF-001 | Not evaluated | `benchmarks/_cutctx_adapter.py`, `benchmarks/adversarial_ccr_tests.py`, `benchmarks/agent_cost_benchmark.py`, `scripts/compression_benchmark.py`, `scripts/generate_benchmark_release_manifest.py`, `.github/workflows/benchmark.yml`, `.github/workflows/release-benchmark-evidence.yml` | `tests/test_model_routing_quality_benchmark.py:6` | Harness present; production-representative load/degradation evidence is runtime-only. |
| ENG-RELPERF-002 | Not evaluated | `engineering-handbook/runbooks/data-recovery.md` (RB-DATA-002: recovery point, integrity, scope, replay), `engineering-handbook/runbooks/rollback.md` | None found | Restore execution, integrity/scope verification, and safe replay are runtime. |
| ENG-ROUTE-001 | Pass | `cutctx/proxy/model_routing_evals.py`, `cutctx/proxy/server.py`, `cutctx/proxy/models.py`, `cutctx_ee/policy/resolver.py` (policy versioning/budgets) | `tests/test_routing_modes_e2e.py:81-100` (5 tests), `tests/test_anthropic_model_routing.py`, `tests/test_anthropic_model_routing_override.py`, `tests/test_anthropic_openai_fallback.py`, `tests/test_gemini_fallback.py`, `tests/test_firewall_runtime_routes.py:7` | Policy predicates through fallback not re-verified at runtime. |
| ENG-ROUTE-002 | Pass | `cutctx/orchestration/workflow.py` (cancellation/idempotency/claims), `cutctx/proxy/session_replay.py` | `tests/test_orchestration_workflow.py:74,93` (cancellation terminal, single-owner claims) | Dead-letter/queueing behavior is runtime. |
| ENG-SDKCOMPAT-001 | Pass | `sdk/go`, `sdk/python`, `sdk/typescript`, `cutctx/client.py` | `tests/test_openai_responses_subscription_compat.py` (26 tests), `tests/parity/fixtures/`, `tests/parity/recorder.py`, `tests/test_agent_client_auth.py` (8) | Consumer matrix/documentation not re-verified; versioned behavior is runtime. |
| ENG-SDKCOMPAT-002 | Pass | `cutctx/proxy/server.py` (auth guards), `cutctx_ee/rbac.py`, `cutctx_ee/entitlements.py` | `tests/test_openai_responses_subscription_compat.py` (26 tests), `tests/test_agent_client_auth.py` (8) | Error-semantic preservation across supported versions is runtime. |
| ENG-UI-001 | Pass | `dashboard/src/App.jsx:90-99` (all critical routes), `dashboard/src/main.jsx` | `tests/test_dashboard_surfaces_playwright.py:76`, `tests/test_dashboard_governance_e2e.py:248` (entitlement/authorization boundary), `tests/test_dashboard_orchestrator_policy_e2e.py:527` (feature-flag gating), `tests/test_dashboard_cache_ttl_playwright.py` | Loading/empty/error states not re-run in this audit. |
| GOV-AUDIT-001 | Pass | `audit/handbook-driven-product-audit-2026-08-04.md` (AUD-2026-08-04-01), `audit/handbook-driven-product-audit-2026-08-04-r2.md` (AUD-2026-08-04-02) — front matter briefs (id/kind/title/date/revision/criteria/state) | `engineering-handbook/automation/validate_handbook.py`, `engineering-handbook/automation/check_examples.py` (reproducibility machinery) | Briefs exist as artifacts; their approval status is a process record. |
| GOV-AUDIT-002 | Pass | `audit/handbook-driven-product-audit-2026-08-04-r2.md:56-120` (exact commands + revision), `audit/release-evidence-2668582c35da84acc38a7396eabc4eceb32eedd4.md` | `tests/test_audit_evidence.py:7,38,57` (inventory source lines, evidence index, stable JSON artifact) | Reproducibility asserted only statically; re-runs are runtime. |
| GOV-MAP-001 | Pass | `audit/product-capability-map-2026-06-22.md` (code-grounded map: entry points, owners, deps, data, signals, evidence), `audit/manual-verification/07-feature-inventory.md` | `engineering-handbook/automation/export_catalogs.py` (inventory extractor) | Map freshness is dated (2026-06-22); not re-validated against current source. |
| GOV-MAP-002 | Pass | `audit/manual-verification/2026-07-26-adversarial-live/SUMMARY.md` (observed PASS/blocked per live surface), `cutctx/memory/backends/graphiti.py:11` (reachability requirement), `cutctx/proxy/feature_flags.py:1-51` (desired-state vs runtime flags) | `tests/test_firewall_runtime_routes.py:7`, `tests/test_dashboard_orchestrator_policy_e2e.py:527` (flag-off path) | Classification artifacts were produced by prior runtime work (2026-07-26); not re-observed in this static audit. |

## Not evaluated summary

Controls whose core evidence is runtime/live/production-only (automation or runbook may
exist, but no static claim of compliance is made): ENG-AGENT-001, ENG-CHAOS-001,
ENG-CHAOS-002, ENG-COMM-002, ENG-DESKTOP-001, ENG-INT-002, ENG-MIGRATION-002,
ENG-OBS-002, ENG-RELPERF-001, ENG-RELPERF-002.

## Explicit audit limits

1. **Static only.** No test, binary, server, or provider was executed. "Pass" means the
   implementation and test automation exist in the tree, not that behavior was observed.
2. **Live-provider and production behavior are not claimed** for any control, including
   Pass rows (reconciliation, rollback, load, chaos outcomes, alert exercise, recovery).
3. **Compiled EE variants.** `cutctx_ee/*.so` files may differ from the `.py` sources
   cited; citations describe the source tree (F-5).
4. **Path verification.** Every cited path was checked for existence at revision
   `d1dd7cae`; line numbers are from greps at audit time and may drift with edits.
5. **ID disagreement** between catalog and appendix is documented in F-1/F-3; the CSV
   and checklist front matter agree, so the disposition table above is anchored to the
   CSV/checklist IDs as instructed.
6. **No exception records** were found (F-4); per the handbook, unverified required
   controls must be treated as failing for release decisions.
7. **No product code was modified** and **nothing was committed**; the working tree is
   clean (`git status --porcelain` empty).
