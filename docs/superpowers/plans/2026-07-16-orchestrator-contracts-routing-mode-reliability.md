# Orchestrator Contracts and Routing Mode Reliability Implementation Plan

> **Execution:** use subagent-driven development task by task, with a spec-and-quality review after each implementation phase and an oracle review at the plan, phase, and final gates.

**Goal:** Make first-run contracts usable and routing-mode changes responsive, strictly acknowledged, eventually confirmed, recoverable, and fully tested.

## Global constraints

- Preserve all unrelated dirty-worktree changes. Record status and relevant hashes before each generated-asset operation.
- Do not redesign Orchestrator or change routing preset definitions.
- Do not persist the starter before explicit Save.
- Add and run a failing regression before each production behavior change.
- Every async publisher uses newest-request-wins semantics; old completions cannot mutate newer state.
- Live verification uses a temporary authenticated proxy on a non-8787 port and temporary data directory. Never stop or reconfigure the active port-8787 proxy.

## Task 0: Preflight and reproducible baselines

**Files:** `.slim/deepwork/orchestrator-contracts-routing-mode.md`

- [ ] Record `git status --short`, current branch/HEAD, dirty packaged dashboard paths, and hashes of existing generated assets.
- [ ] Record focused backend and Orchestrator Playwright baseline commands and exit codes.
- [ ] Create or resume `.superpowers/sdd/progress.md`; record task bases before dispatch.
- [ ] Confirm no implementation file overlaps an unrelated user edit; if one does, preserve and integrate it explicitly.

## Task 1: Backend starter and full contract schema parity

**Files:** `cutctx/orchestration/contracts.py`, `cutctx/orchestration/service.py`, `tests/test_orchestration_contracts.py`, `tests/test_orchestration_rollouts.py`, `tests/test_orchestration_api.py`

- [ ] Add failing parser/serializer tests proving `template` is accepted and round-tripped while unknown fields remain rejected.
- [ ] Add failing tests for the complete starter shape from the design, including objective type, accepted signals, description, TTFT `None`, fallback-cost `None`, no fallback models, and `maximum_deployments == 1`.
- [ ] Add failing service tests for precedence: durable > legacy > synthesized starter; filtered IDs; starter does not mutate revision.
- [ ] Add failing authenticated API lifecycle test: GET revision 0, PUT revision 1, subsequent GET exactly one durable contract.
- [ ] Add failing authenticated simulation test using a contract payload containing `template`.
- [ ] Run focused tests and capture RED evidence.
- [ ] Implement `WorkloadContract.template`, parser support, canonical `starter_implementation_contract()`, and service precedence.
- [ ] Run focused tests GREEN, including existing conflicts and rollouts.
- [ ] Obtain phase oracle/spec-quality review and resolve all Important/Critical findings.

## Task 2: Newest-request-wins dashboard refresh and strict mode confirmation

**Files:** `dashboard/src/lib/dashboard-context.jsx`, `dashboard/src/pages/Orchestrator.jsx`, `dashboard/e2e/orchestrator.spec.js`

- [ ] Add deterministic failing tests where initial, polling, and explicit refreshes complete out of order. Assert only the newest generation can publish `stats`, `health`, `error`, `refreshError`, and `lastUpdated`, and an old completion cannot clear newer `refreshing`.
- [ ] Add failing delayed-refresh test proving the established Orchestrator remains mounted after a mode click.
- [ ] Add failing mode tests for missing acknowledgement, mismatched acknowledgement, successful POST plus failed refresh, stale stats followed by exact confirmation, and final newest stats authority.
- [ ] Capture RED evidence.
- [ ] Implement generation-guarded loading and a structured `refresh()` result. Keep `loading` initial-only and `refreshing` owned by the newest explicit refresh. Preserve snapshots on background failure.
- [ ] Require exact mode acknowledgement. Keep optimistic mode until newest committed stats equal it; show a non-destructive pending-confirmation warning on refresh failure or stale stats.
- [ ] Run focused mode/concurrency tests GREEN.
- [ ] Obtain phase oracle/spec-quality review and resolve all Important/Critical findings.

## Task 3: Fetch timeout composition and stale-safe Routing Studio lifecycle

**Files:** `dashboard/src/lib/fetch-with-timeout.js`, `dashboard/tests/fetch-with-timeout.test.js`, `dashboard/package.json`, `dashboard/src/components/routing-studio/api.js`, `dashboard/src/components/routing-studio/RoutingStudio.jsx`, `dashboard/e2e/orchestrator.spec.js`

- [ ] Add failing Node unit tests with controlled timers/fetch for: already-aborted caller; caller abort versus internal timeout; timeout normalization only for internal timeout; cleanup after success, HTTP error, caller abort, and timeout.
- [ ] Add failing Playwright tests for timeout and Retry, retry abort silence, unmount abort silence, stale success/error/finally protection, and load-token newest-wins behavior.
- [ ] Capture RED evidence.
- [ ] Implement the reusable timeout helper and route `listContracts({signal})` through a 10-second timeout.
- [ ] Implement monotonic load tokens, previous-request abort, silent expected aborts, separate load errors, and Retry UI.
- [ ] Change contract-save reconciliation to upsert by `(id, version)`; add tests that starter save yields exactly one contract, reload is durable, and conflicts do not mutate draft/list/revision.
- [ ] Run unit and focused Playwright tests GREEN.
- [ ] Obtain phase oracle/spec-quality review and resolve all Important/Critical findings.

## Task 4: Broad validation, packaged assets, and isolated live test

**Files:** `audit/bug-report.md`, `.slim/deepwork/orchestrator-contracts-routing-mode.md`, intended generated files under `cutctx/dashboard/`

- [ ] Run focused and broad backend orchestration suites with explicit exit-code evidence.
- [ ] Run dashboard unit tests and the complete Orchestrator Playwright suite, including desktop and 390px coverage.
- [ ] Run dashboard lint and build.
- [ ] Re-record dirty status and packaged asset hashes. Sync dashboard assets, then verify the changed generated set and index references. Restore no user file; reconcile overlaps deliberately.
- [ ] Run packaged-dashboard tests.
- [ ] Start a temporary proxy on an isolated port (for example 8879) with a temporary orchestration directory/config and admin key. Record the process and terminate only this process after testing.
- [ ] Against the packaged dashboard, verify starter completeness, Save revision `0 -> 1`, exactly one durable contract after reload, authenticated simulation, Balanced/Aggressive/Off persistence, no page remount, refresh confirmation, network status, no new console errors, desktop layout, and 390px layout.
- [ ] Record loaded JS/CSS asset hashes and exact final backend mode/revision.
- [ ] Append resolved root causes, fixes, commands, exit codes, runtime evidence, and remaining limitations to `audit/bug-report.md`.
- [ ] Run `git diff --check`, inspect `git diff --stat`, and prove unrelated dirty changes remain intact.
- [ ] Obtain final oracle and whole-branch code review; resolve all Important/Critical findings.
- [ ] Run final verification after the last code change, then mark the deepwork goal complete.
