# Release Pipeline Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore all repository-owned release gates so the authenticated staging blocker can run against one qualified commit.

**Architecture:** Repair environment wiring before product behavior, then regenerate derived artifacts and repair publication workflows. Each subsystem keeps its own regression test and commit so failures remain attributable and reversible.

**Tech Stack:** Python 3.10-3.14, pytest, FastAPI, mypy 1.15, Ruff 0.9.4, React/Vite, Playwright, Rust/Cargo, GitHub Actions, maturin.

## Global Constraints

- Prefix shell commands with `rtk`; use `rtk proxy` when unfiltered output is required.
- Keep enterprise routes fail-closed when an entitlement is absent.
- Do not weaken required checks or expand the mypy baseline.
- Do not update a visual snapshot without inspecting the rendered difference.
- Do not publish, delete, or overwrite a release while repairing the candidate.
- PyPI account-level trusted-publisher configuration remains an external owner action.

---

### Task 1: Repair CI dependency and package topology

**Files:**
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_release_workflows.py`

**Interfaces:**
- Consumes: CI job definitions for Graphiti and native wrappers.
- Produces: jobs that install direct test dependencies and select OSS-only or EE-inclusive topology explicitly.

- [ ] Add workflow contract assertions requiring `pytest-asyncio` in the Graphiti install step and project runtime installation before native-wrapper pytest commands.
- [ ] Run `rtk pytest tests/test_release_workflows.py -q` and confirm the new assertions fail against the current workflow.
- [ ] Update `.github/workflows/ci.yml` with the minimal installation changes.
- [ ] Re-run `rtk pytest tests/test_release_workflows.py -q` and confirm it passes.
- [ ] Commit with `fix(ci): install release gate dependencies`.

### Task 2: Restore deterministic dashboard evidence

**Files:**
- Modify: `dashboard/e2e/orchestrator.spec.js`
- Modify: `dashboard/e2e/overview.spec.js`
- Modify only after inspection: `dashboard/e2e/visual-identity.spec.js-snapshots/overview-shell-dark-chromium-linux.png`
- Test: dashboard Playwright suite.

**Interfaces:**
- Consumes: dashboard accessibility roles and deterministic mocked API responses.
- Produces: stable browser evidence that does not rely on ambiguous text or stale metric labels.

- [ ] Run the three failing Playwright tests locally and capture each failure.
- [ ] Scope `Required capabilities` to the heading role.
- [ ] Align Overview assertions with the current metric contract or fix the source if the displayed value is wrong.
- [ ] Render the dark overview screenshot, inspect it, and update the Linux baseline only when the difference matches intentional source output.
- [ ] Run the three focused tests and then `npm --prefix dashboard run test:e2e -- --project=chromium`.
- [ ] Commit with `fix(dashboard): stabilize release evidence`.

### Task 3: Restore entitlement and installed-package contracts

**Files:**
- Modify as required: `cutctx/proxy/routes/entitlement_gate.py`
- Modify as required: `cutctx/proxy/server.py`
- Modify as required: route modules under `cutctx/proxy/routes/`
- Modify: `.github/workflows/ci.yml`
- Test: `tests/test_entitlement_bypass_regression.py`
- Test: `tests/test_route_modules.py`
- Test: `tests/test_dsr_endpoints.py`

**Interfaces:**
- Consumes: license tier, feature mapping, route metadata, and OSS/EE package availability.
- Produces: protected routes return `403` without their required entitlement in both source and installed-wheel environments.

- [ ] Reproduce representative `200` versus expected `403` failures in a clean test process.
- [ ] Add or tighten a focused regression for the shared failure boundary if the existing tests do not isolate it.
- [ ] Trace route registration through the entitlement middleware and correct the first boundary that bypasses enforcement.
- [ ] Configure CI tests that require `cutctx_ee` to install the workspace package; keep explicit OSS-wheel leak checks separate.
- [ ] Run entitlement, route-module, compatibility-smoke, and installed-wheel focused tests.
- [ ] Commit with `fix(auth): enforce enterprise route entitlements`.

### Task 4: Close type, OpenAPI, and auxiliary CI drift

**Files:**
- Modify: files reported by `scripts/mypy_ratchet.py`
- Modify: `artifacts/openapi.json`
- Modify as required: native installer test setup.
- Test: `scripts/mypy_ratchet.py`
- Test: `tests/test_openapi_drift.py`

**Interfaces:**
- Consumes: corrected route topology from Task 3.
- Produces: zero new mypy errors and a deterministic OpenAPI artifact.

- [ ] Clear `.mypy_cache`, run the ratchet, and group errors by root cause.
- [ ] Fix types at source without baseline additions or blanket ignores.
- [ ] Run `scripts/generate_openapi.py` after entitlement behavior is stable.
- [ ] Run the ratchet, OpenAPI drift test, Python compatibility smoke, and native installer tests.
- [ ] Commit with `fix(ci): close release type and schema drift`.

### Task 5: Fix the Rust stale-reader race

**Files:**
- Modify: the in-memory CCR backend under `crates/cutctx-core/src/ccr/`
- Test: existing `expired_get_does_not_wipe_concurrent_refresh` regression.

**Interfaces:**
- Consumes: cache entry observed by an expired reader.
- Produces: conditional removal that cannot delete a newer refresh.

- [ ] Run the failing test repeatedly to confirm the race.
- [ ] Bind removal to the observed entry generation or value identity.
- [ ] Run the regression at least 100 times and then run `rtk cargo test -p cutctx-core --lib`.
- [ ] Commit with `fix(cache): preserve concurrent refreshes`.

### Task 6: Repair release signing and publication contracts

**Files:**
- Modify: `.github/workflows/sign-artifacts.yml`
- Modify: `tests/test_release_workflows.py`
- Modify as required: `scripts/sign_artifacts.py`

**Interfaces:**
- Consumes: a GitHub Release tag containing uploaded assets.
- Produces: an isolated release-asset directory, secret/path scan, signed manifest, and hash verification.

- [ ] Add workflow contract tests requiring `gh release download`, an isolated asset directory, a non-empty asset check, and absence of whole-repository scanning.
- [ ] Run the workflow tests and confirm failure.
- [ ] Update the signing workflow and any narrow script behavior needed for archives or binaries.
- [ ] Run workflow tests plus manifest/signature unit tests.
- [ ] Confirm `release.yml` declares `environment: pypi` and `id-token: write`; document the exact external PyPI publisher claims without embedding credentials.
- [ ] Commit with `fix(release): sign actual release assets`.

### Task 7: Final release verification and remote CI

**Files:**
- Modify: `audit/launch-readiness-report.md` with fresh evidence only.

**Interfaces:**
- Consumes: all prior task commits.
- Produces: one candidate SHA with local and GitHub evidence.

- [ ] Run Ruff 0.9.4 check and format validation.
- [ ] Run the mypy ratchet with a clean cache.
- [ ] Run focused Python release tests and the full non-live suite.
- [ ] Run dashboard unit, lint, build, full Chromium E2E, and accessibility checks.
- [ ] Run Rust workspace tests and package build/leak verification.
- [ ] Run workflow validation and release contract tests.
- [ ] Update the readiness report with exact commands, counts, failures, and remaining external PyPI action.
- [ ] Push the candidate and inspect every GitHub Actions workflow for its exact SHA.
- [ ] If fixture evidence passes, dispatch Product Release Evidence with `require_staging=true` and record the result.
