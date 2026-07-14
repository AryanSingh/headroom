# UI and Routing Operational Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` for every behaviour change. Each task has an explicit red–green cycle.

**Goal:** Remove the production dashboard navigation defect, make clipboard actions reliable and observable, and accurately expose the existing learned-routing rollout path without introducing unsupported distributed infrastructure.

**Architecture:** Dashboard internal navigation must be owned by React Router so the dynamically selected `/dashboard` basename is preserved. Copy controls must report both success and failure accessibly. The existing JSON artifact scorer remains fail-closed and dependency-free; its production rollout is documented rather than replaced with an untrained or unavailable model. Redis/Postgres state sharing remains a separately deployable infrastructure project.

**Tech Stack:** React 19, React Router, Playwright, Python/pytest, existing model-routing artifact tooling.

## Global Constraints

- Preserve the current fail-closed routing semantics.
- Do not add a model dependency, model weights, Redis, or Postgres without a configured deployment target.
- Test every production behaviour before changing its implementation.
- Keep the dashboard mountable both at `/` and `/dashboard`.

---

### Task 1: Preserve the dashboard basename for governance routing

**Files:**
- Modify: `dashboard/e2e/governance.spec.js`
- Modify: `dashboard/src/pages/Governance.jsx`

- [x] Write a browser test that visits `/dashboard/governance`, clicks **Open routing page**, and expects `/dashboard/orchestrator` plus the Orchestrator heading.
- [x] Run the test and confirm it fails because the current anchor has `href="/orchestrator"`.
- [x] Replace the raw internal anchor with React Router's `Link to="/orchestrator"`.
- [x] Re-run the focused test and the complete dashboard suite.

### Task 2: Make governance copy actions report failure accessibly

**Files:**
- Modify: `dashboard/e2e/governance.spec.js`
- Modify: `dashboard/src/pages/Governance.jsx`

- [x] Write a browser test that rejects `navigator.clipboard.writeText`, clicks a configuration copy button, and expects an accessible failure message.
- [x] Run the test and confirm it fails because the existing promise has no rejection handler.
- [x] Add a local copy-status state with a non-blocking `role="status"` message; retain the current success confirmation.
- [x] Re-run the focused test and the complete dashboard suite.

### Task 3: Correct the operational record for the complexity-scorer gap

**Files:**
- Modify: `audit/orchestration-production-audit-2026-07-14.md`
- Modify: `docs/content/docs/model-routing-presets.mdx`
- Test: `tests/test_model_routing_training.py`

- [x] Retain the existing artifact test coverage; it already proves opt-in loading, invalid-artifact fallback, holdout gates, and segment thresholds.
- [x] Verify `LinearRoutingArtifact`, `LinearCalibratedTaskComplexityScorer`, holdout safety gates, and `CUTCTX_MODEL_ROUTING_SCORER_ARTIFACT` are covered by `tests/test_model_routing_training.py`.
- [x] Amend the audit to distinguish the already implemented calibrated scorer from the remaining rollout work: collect representative evidence, train an artifact, validate the holdout gates, deploy the artifact path, and monitor evidence.
- [x] Confirm the operator documentation already describes the same safe rollout procedure without claiming an untrained scorer is live.

### Task 4: Verify release safety

**Files:**
- Verify: `dashboard/e2e/**/*.spec.js`
- Verify: `tests/test_model_router.py`, `tests/test_model_routing_training.py`, `tests/test_orchestration_*.py`

- [x] Run focused red–green tests after each task.
- [x] Run dashboard lint, production build, all browser tests, and the relevant Python routing/orchestration tests.
- [x] Perform a live `/dashboard/governance` click through the proxy and confirm the link remains under `/dashboard`.
- [x] Inspect `git diff --check` and leave unrelated local artifacts untouched.

## Deferred infrastructure work

Shared workflow/evidence state requires a chosen Redis or Postgres deployment, migration strategy, TTL/retention policy, credentials, monitoring, and multi-worker test environment. It is intentionally not represented by a local-only abstraction or a stub; it should be designed and implemented as a separate infrastructure project.
