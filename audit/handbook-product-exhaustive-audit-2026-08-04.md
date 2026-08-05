---
id: AUD-HANDBOOK-PRODUCT-EXHAUSTIVE-2026-08-04
kind: audit-report
title: Exhaustive handbook-driven product review
date: 2026-08-04
product: Cutctx/Headroom
revision: d1dd7cae0775ffb411b487a9e3093a38c93cb31b
scope: repository, handbook controls, deterministic local execution, dashboard browser fixtures
---

# Exhaustive handbook-driven product review

## Executive decision

The repository has substantial implementation and test coverage, but this review
does **not** support an unconditional production-ready or release-ready decision.
One reproducible product defect remains in the Graphiti partition lock under
repeated cancellation. The handbook appendix is also out of sync with the
canonical control export. Live-provider, production rollout, destructive
recovery, chaos, billing reconciliation, and production load evidence were not
available in this environment and therefore remain unevaluated. Required
controls with no trustworthy evidence are release-blocking under the handbook.

This is an exhaustive repository/local-environment review, not a claim that a
production system was exercised. Every one of the 38 canonical controls is
dispositioned below.

## Scope and method

Reviewed:

- the complete handbook `SUMMARY.md`, governance schemas, standards registry,
  38-control canonical export, 36-KPI export, checklists, prompts, examples,
  runbooks, templates, OWASP/NIST mappings, and reference appendix;
- product source and tests across `tests/`, `cutctx/`, `cutctx_ee/`, dashboard,
  SDK, desktop, plugins, extensions, SQL, Kubernetes, and release workflows;
- all 10,556 collected product tests, with the explicitly live/provider/evaluation
  network lanes separated from the deterministic run;
- deterministic handbook validation and all 12 handbook executable fixtures;
- the dashboard audit matrix at 10 routes × 4 viewports, plus the existing
  dashboard Playwright tranche;
- a static OpenCode/DeepSeek review as a second evidence pass. It was treated as
  research input only; it did not replace executed tests or runtime evidence.

No production credentials, customer data, external provider calls, production
databases, destructive migrations, chaos experiments, load generators, or live
rollouts were used.

## Command evidence

| Gate | Result |
| --- | --- |
| Handbook validator | `validate_handbook.py ... --format json` → `[]` |
| Handbook examples | `check_examples.py ... --format json` → 12/12 passed |
| Product collection | 10,556 collected, 4 collection skips |
| Isolated deterministic product sweep | 9,855 passed, 436 skipped, 17 failed, 41 setup errors in one shared process; JUnit: `/tmp/headroom-exhaustive-deterministic-junit.xml` |
| Clean-process focused rerun | install/runtime/state + provider fallback: 46 passed; webhook persistence: 13 passed; license DB: 14 passed; TOIN: 9 passed, 2 skipped; state crypto: 28 passed; savings history: 18 passed |
| Graphiti lock focused rerun | 4 passed, 1 failed: repeated-cancellation waiter does not reliably release the late file-lock acquisition |
| Dashboard audit | 43 passed after installing the declared dashboard dependencies and pointing Playwright at the installed Chromium cache |
| Existing dashboard/browser tranche | 13 passed |
| Dashboard dependency audit | `npm ci --ignore-scripts` completed; `npm audit` reports 2 vulnerabilities (1 moderate, 1 high) |

The first full product run was intentionally stopped before completion because
it opened an external HTTPS connection and touched the worktree memory database.
That run is invalid evidence. The later deterministic run redirected product
state, spend, audit, webhook, license, memory, and routing stores; focused
reruns were executed in fresh processes to prevent test-order environment
contamination.

## Control disposition

Status meanings follow the handbook. `Pass` means the local procedure and
evidence path were exercised to the stated local boundary; it is not a claim of
production behavior. `Not evaluated` is release-blocking for a required control.

| Control | Status | Evidence and boundary |
| --- | --- | --- |
| ENG-AGENT-001 | Not evaluated | Static orchestration/policy sources and adjacent workflow tests exist; no complete time-bounded tenant/tool/action/budget/escalation grant was exercised. |
| ENG-AGENT-002 | Not evaluated | Approval fields and orchestration tests exist; authoritative outcome reconciliation for consequential actions was not exercised. |
| ENG-AIEVAL-001 | Pass | Versioned offline evaluation fixture, routing evaluation tests, handbook example, and local quality benchmark paths passed. No live model quality claim. |
| ENG-AIEVAL-002 | Pass | Offline route-policy fixtures and routing/evaluation tests passed; provider safety behavior remains outside scope. |
| ENG-API-001 | Pass | Auth adversarial, client-auth, CCR admin-auth, API contract, and tenant-boundary tests passed in the deterministic suite. |
| ENG-API-002 | Pass | Idempotency, replay, orchestration, webhook, and mutation contract tests passed in clean focused runs. |
| ENG-CHAOS-001 | Not evaluated | Chaos workflow and handbook procedure exist; no approved experiment, bounded blast-radius record, abort authority, or executed fault injection was run. |
| ENG-CHAOS-002 | Not evaluated | No client-visible/business-outcome reconciliation from a chaos experiment was available. |
| ENG-CLI-001 | Pass | Non-interactive CLI contract and wrapper tests passed locally; no browser or operator credential selection was allowed. |
| ENG-CLI-002 | Pass | JSON/parseability contract tests and CLI output paths passed locally. |
| ENG-COMM-001 | Pass | Entitlement, tier, seat, trial, and governance gating tests passed locally. |
| ENG-COMM-002 | Not evaluated | Billing/usage source code and unit coverage exist; processor-side reconciliation and month-close evidence were not run. |
| ENG-CV-001 | Pass | Release evidence, artifact hash, manifest, and workflow contract tests passed locally. A real promotion was not performed. |
| ENG-CV-002 | Not evaluated | Rollout/stop/rollback control paths exist, but no production-like rollout or recovery rehearsal was executed. |
| ENG-DESKTOP-001 | Not evaluated | Desktop sources and upgrade guidance exist; interrupted upgrade/recovery evidence was not run in this environment. |
| ENG-INT-001 | Pass | Webhook signature/replay/tenant-boundary tests and clean persistence tests passed; no live provider callback was accepted. |
| ENG-INT-002 | Not evaluated | Approval-boundary implementation exists, but no high-impact external tool action was executed against an authoritative target. |
| ENG-MEM-001 | Fail | Memory isolation and route tests passed, but `tests/test_memory/test_graphiti_lock.py::test_repeatedly_cancelled_waiter_releases_a_late_filelock_acquisition` fails reproducibly. Safe concurrent memory mutation cannot be accepted until fixed. |
| ENG-MEM-002 | Not evaluated | Retention/deletion code and tests exist; residual removal across primary, index, cache, export, and future retrieval was not verified end-to-end. |
| ENG-MIGRATION-001 | Pass | SQL schema/version, resumable migration fixture, checkpoint, and migration contract tests passed locally. |
| ENG-MIGRATION-002 | Not evaluated | No production backup/restore, business reconciliation, or recovery-point rehearsal was performed. |
| ENG-OBS-001 | Pass | Telemetry, tracing, redaction, metrics, outcome, and request-trace tests passed locally. |
| ENG-OBS-002 | Not evaluated | Alert ownership/routing paths exist, but no representative failure was injected into a live alerting system. |
| ENG-PLAYWRIGHT-001 | Pass | 43-route/viewport dashboard audit passed with deterministic fixtures; 13 additional dashboard Playwright tests passed. |
| ENG-PLAYWRIGHT-002 | Pass | Browser assertions, accessibility/semantic checks, stable fixtures, and artifact paths passed locally; no customer secrets were used. |
| ENG-RELENG-001 | Pass | Release manifest, evidence, version, artifact, and workflow tests passed locally. No immutable production artifact was promoted. |
| ENG-RELENG-002 | Not evaluated | Rollback runbooks and tests exist; a cross-component rollback rehearsal was not executed. |
| ENG-RELPERF-001 | Not evaluated | No production-representative load/degradation/correctness run or accepted SLO evidence was produced. |
| ENG-RELPERF-002 | Not evaluated | No restore/replay integrity and authorization-scope rehearsal was performed. |
| ENG-ROUTE-001 | Pass | Versioned routing policy, route-mode, fallback, residency, and routing trace tests passed locally; live provider reachability was not claimed. |
| ENG-ROUTE-002 | Not evaluated | Retry/queue/dead-letter behavior was not exercised against a production-like asynchronous system. |
| ENG-SDKCOMPAT-001 | Pass | API/OpenAI Responses compatibility, SDK/CLI contract, schema, and compatibility fixture tests passed locally. |
| ENG-SDKCOMPAT-002 | Pass | Authorization, validation, tenant-boundary, and machine-readable error tests passed for supported local contracts. |
| ENG-UI-001 | Pass | Dashboard state matrix and 43 deterministic browser cases passed after dependency setup. |
| GOV-AUDIT-001 | Pass | This decision-oriented brief, evidence plan, control ledger, and reproducibility limits are recorded. |
| GOV-AUDIT-002 | Pass | Failing tests, invalid unsafe-run evidence, focused reruns, JUnit output, and explicit live limits are recorded. |
| GOV-MAP-001 | Pass | Handbook capability maps, source codemaps, control catalog, and this control-to-evidence ledger connect outcomes to owners, dependencies, signals, and tests. |
| GOV-MAP-002 | Not evaluated | Provider and feature-flag source paths were inspected; live reachability was not inferred from configuration and was not exercised. |

No control is marked `Exception` or `Not applicable`; no approved exception
record was found, and the product contains applicable provider, persistence,
release, and operator workflows.

## Findings and required disposition

### F-1 — Reproducible Graphiti lock cancellation defect — release blocker

Repeated cancellation of an async waiter can leave the underlying file lock held
long enough that the next acquisition times out. The focused test reproduces it
in a fresh process: 4 passed, 1 failed. Fix the cancellation compensation path,
then rerun the focused test, the memory suite, and the full deterministic suite.

### F-2 — Handbook appendix catalog is inconsistent with the canonical export

The canonical export contains 38 IDs, while
`engineering-handbook/appendices/control-catalog.md` contains 40 rows and uses
stale families (`ENG-AUDIT`, `ENG-DISCOVERY`, `ENG-CVRA`, `ENG-INTEGRATION`,
`ENG-MEMORY`, `ENG-ROUTING`, and `ENG-DASHBOARD`). It also diverges on CLI-002
semantics and adds `ENG-DESKTOP-002` without a canonical record. Regenerate the
appendix from the canonical catalog before relying on it for release decisions.

### F-3 — Dashboard dependency supply-chain risk

The declared dashboard dependency tree was absent from the checkout, so 43
visual tests initially errored at Vite startup. Installing the lockfile-defined
dependencies made all 43 pass. `npm audit` reports one moderate and one high
vulnerability; triage, pin, or formally accept them before a production release.

### F-4 — Full-suite isolation is not safe by default

The initial unisolated full run opened an external HTTPS connection and touched
the worktree memory database. It was stopped and excluded from evidence. The
audit harness must set every product state path and must block or stub external
network access before future full-suite runs.

### F-5 — Production evidence gap

Chaos outcomes, alert exercise, production load and recovery, payment-side
reconciliation, live provider reachability, real rollout/rollback, and
destructive migration recovery remain unevaluated. These are not converted into
passes by the local tests or handbook fixture examples.

## Recommended next actions

1. Fix and retest F-1 first.
2. Regenerate and validate the handbook appendix/catalog projection (F-2).
3. Triage the two dashboard dependency vulnerabilities and commit the intended
   lockfile/dependency state (F-3).
4. Add a network-deny/full-suite harness guard and rerun all deterministic lanes
   without shared-process environment leakage (F-4).
5. Obtain separately approved staging/production-like evidence for the controls
   marked `Not evaluated`; do not use this local report as a production release
   approval.

