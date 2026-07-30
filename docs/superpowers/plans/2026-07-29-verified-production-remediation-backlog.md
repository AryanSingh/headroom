# Verified Production Remediation Backlog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the verified production, commercial, security, reliability, accessibility, and maintainability gaps discovered by reconciling the latest audits against the current `main` source.

**Architecture:** Deliver the work in independent, reviewable streams. First make entitlement and telemetry behavior safe, then protect the monitoring plane and restore reliable release evidence. Hosted-operation, legal, and third-party-flow work has explicit external acceptance gates; do not fabricate evidence when a deployed service or counsel is required.

**Tech Stack:** Python/FastAPI, pytest, Prometheus client metrics, React/Vite, Playwright, GitHub Actions, Kubernetes, hosted billing/entitlement service.

## Global Constraints

- Base all implementation and verification on the current `main` commit; do not rely on audit claims without reproducing them.
- Use TDD: add the focused failing test before changing production behavior.
- Hosted paid/trial entitlement must fail closed when its response cannot be authenticated and validated.
- Never log, commit, print, or copy credentials from `.env.local`; rotate suspected exposed credentials out-of-band.
- Preserve the current intentional single-replica limit until state is moved from ReadWriteOnce storage to a horizontally safe external/RWX design.
- Treat checkout, SSO, alert routing, deployed portal contracts, and legal approvals as external gates: record real evidence, not assumptions.
- Use the repository's pinned quality tools, including `uvx ruff@0.9.4 check .` where linting is part of a task.

---

## File and Workstream Map

| Workstream | Primary files | Result |
|---|---|---|
| Hosted entitlements | `cutctx_ee/billing/client.py`, `cutctx_ee/trial.py`, billing tests | Valid hosted trials are accepted; unknown or failed checks do not grant access. |
| Hosted usage reporting | `cutctx/telemetry/reporter.py`, telemetry tests, deployed billing API | Reporting either reaches a supported authenticated endpoint or is explicitly unavailable. |
| Metrics safety | `cutctx/proxy/prometheus_metrics.py`, proxy metric tests | User-controlled labels cannot create unbounded Prometheus series. |
| Dashboard gate and accessibility | `dashboard/`, `tests/test_dashboard_audit.py`, dashboard E2E | Deterministic Vite-backed tests plus automated a11y coverage. |
| Release evidence | release/audit evidence docs and CI commands | A reproducible certification attached to the exact `main` SHA. |
| Hosted operations | Kubernetes/monitoring configuration and runbooks | Confirmed alert delivery, ownership, uptime checks, and incident procedure. |
| Product/commercial readiness | `TERMS.md`, website/docs, hosted staging configuration | Approved terms and verified checkout/SSO lifecycle. |
| Maintainability | dashboard components/styles, dependencies, docs | Lower-risk follow-on refactors after production blockers close. |

## Blocking Decisions Required Before Code Changes

1. **Hosted entitlement contract owner:** provide the canonical production/staging base URL, endpoint names, authentication scheme, and signed response schema. The old portal endpoint must not be inferred from existing code.
2. **Usage-reporting product decision:** choose one of: implement a supported authenticated endpoint, queue reports for later delivery, or remove hosted usage reporting from the product surface.
3. **Commercial approval:** arrange qualified legal review; an agent may prepare document diffs but cannot declare the terms approved.
4. **Operations owner:** name the alert destination/on-call owner and the staging environment used for checkout, SSO, and alert-delivery tests.

## Task 1: Make Hosted Trial Entitlements Fail Closed

**Priority:** P0

**Files:**
- Modify: `cutctx_ee/billing/client.py`
- Modify: `cutctx_ee/trial.py`
- Test: the existing billing/trial pytest module containing `start_trial` and `is_trial_active` coverage; create `tests/test_ee_billing_entitlements.py` if no focused module exists

**Interfaces:**
- Consumes: hosted entitlement response containing an authenticated trial status and expiry.
- Produces: a boolean/structured entitlement result where only a verified, unexpired active status grants a hosted trial.

- [ ] **Step 1: Locate existing billing and trial tests and write the failing parameterized cases.**

```python
@pytest.mark.parametrize("response_or_error", [
    requests.Timeout(),
    FakeResponse(status_code=405, json_data={}),
    FakeResponse(status_code=200, json_data={"active": False}),
    FakeResponse(status_code=200, json_data={"active": True, "expires_at": "2000-01-01T00:00:00Z"}),
])
def test_hosted_trial_check_does_not_grant_access_without_a_valid_active_entitlement(response_or_error):
    client = BillingClient(...)
    patch_hosted_check(client, response_or_error)
    assert client.is_trial_active("tenant-1") is False
```

- [ ] **Step 2: Run the focused test and confirm it fails against the existing fail-open behavior.**

Run: `pytest -q tests/test_ee_billing_entitlements.py -k valid_active_entitlement`

Expected: failure for timeout/non-200/invalid/expired input until the implementation is changed.

- [ ] **Step 3: Define and implement one validated response parser.**

```python
def parse_trial_entitlement(payload: Mapping[str, object], now: datetime) -> bool:
    return (
        payload.get("active") is True
        and isinstance(payload.get("expires_at"), str)
        and parse_rfc3339(payload["expires_at"]) > now
        and verify_entitlement_signature(payload)
    )
```

Call this parser only after a successful request to the contract-approved endpoint. Convert request exceptions, non-success statuses, malformed JSON, missing fields, invalid signatures, and expired responses into `False`; emit a redacted diagnostic metric/log without tenant secrets.

- [ ] **Step 4: Add a valid signed, unexpired response test and run the full focused module.**

Run: `pytest -q tests/test_ee_billing_entitlements.py`

Expected: all invalid states deny entitlement; only the valid signed fixture grants it.

- [ ] **Step 5: Commit the isolated change.**

```bash
git add cutctx_ee/billing/client.py cutctx_ee/trial.py tests/test_ee_billing_entitlements.py
git commit -m "fix: fail closed for hosted trial entitlements"
```

## Task 2: Resolve Hosted Usage Reporting

**Priority:** P0

**Files:**
- Modify: `cutctx/telemetry/reporter.py`
- Modify/create: reporter tests adjacent to existing usage-reporting tests
- Modify: hosted billing API/service only after the endpoint contract is approved

**Interfaces:**
- Consumes: validated usage event and a supported authenticated reporting endpoint.
- Produces: one of `delivered`, `unavailable`, or `retryable_failure`; it must never represent a known 405 endpoint as successful delivery.

- [ ] **Step 1: Choose and document the product decision in the PR description and configuration docs.**

The implementation must choose exactly one mode:

```python
UsageReportResult = Literal["delivered", "unavailable", "retryable_failure"]
```

- [ ] **Step 2: Write failing tests for a successful endpoint, 401/403, 405, timeout, and malformed response.**

```python
def test_usage_report_marks_known_unsupported_endpoint_unavailable(reporter, mock_post):
    mock_post.return_value = FakeResponse(status_code=405, json_data={})
    assert reporter.report_usage(event) == "unavailable"
```

- [ ] **Step 3: Implement the approved mode.**

For an implemented endpoint, authenticate the request, enforce a bounded timeout, validate the acknowledgement body, and return `delivered` only for a verified acknowledgement. For deferred support, stop POSTing to the obsolete endpoint and return `unavailable` with a single rate-limited operator warning.

- [ ] **Step 4: Run focused tests and a staging contract test.**

Run: `pytest -q <resolved-reporter-test-module>`

Expected: all response categories map to the documented result and staging accepts a real authenticated test event exactly once.

- [ ] **Step 5: Commit.**

```bash
git add cutctx/telemetry/reporter.py <resolved-reporter-test-module> <approved-api-files>
git commit -m "fix: make hosted usage reporting explicit and verifiable"
```

## Task 3: Bound Prometheus Label Cardinality

**Priority:** P1

**Files:**
- Modify: `cutctx/proxy/prometheus_metrics.py`
- Test: existing Prometheus/proxy metric tests or create `tests/test_prometheus_metrics_cardinality.py`

**Interfaces:**
- Consumes: provider, model, and request-path strings controlled in part by callers.
- Produces: stable label values `known_value` or `"other"`, plus bounded overflow counters.

- [ ] **Step 1: Write failing cardinality tests.**

```python
def test_unrecognized_models_share_the_other_metric_bucket(metrics):
    for index in range(500):
        metrics.record_request(provider="unknown", model=f"attacker-{index}", ...)
    assert metrics.requests_by_model["other"] == 500
    assert len(metrics.requests_by_model) <= metrics.MAX_DISTINCT_MODELS + 1
```

Add equivalent tests for providers and inbound paths, including an approved allowlist value that remains distinct.

- [ ] **Step 2: Run the focused test and confirm current code creates distinct entries.**

Run: `pytest -q tests/test_prometheus_metrics_cardinality.py`

Expected: failure before the cap/bucketing implementation.

- [ ] **Step 3: Implement a single bounded-label helper.**

```python
def bounded_label(value: str, known: set[str], seen: set[str], limit: int) -> str:
    if value in known or value in seen:
        return value
    if len(seen) >= limit:
        return "other"
    seen.add(value)
    return value
```

Apply it before every update to `requests_by_provider`, `requests_by_model`, and `inbound_requests_by_path`; use a finite path template/route name rather than raw IDs/query strings.

- [ ] **Step 4: Run focused tests, proxy metric tests, and lint.**

Run: `pytest -q tests/test_prometheus_metrics_cardinality.py && uvx ruff@0.9.4 check cutctx/proxy/prometheus_metrics.py`

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add cutctx/proxy/prometheus_metrics.py tests/test_prometheus_metrics_cardinality.py
git commit -m "fix: bound prometheus metric label cardinality"
```

## Task 4: Restore a Deterministic Dashboard Test Gate

**Priority:** P1

**Files:**
- Modify: `tests/test_dashboard_audit.py`
- Modify: dashboard Playwright/Vite configuration discovered from `dashboard/package.json` and the dashboard E2E configuration
- Test: dashboard audit and E2E suite

**Interfaces:**
- Consumes: a reserved local port, Vite startup command, and readiness URL.
- Produces: a started server or a test failure containing Vite stderr, startup command, port, and elapsed time.

- [ ] **Step 1: Reproduce the server-start failure and retain the raw stderr as test evidence.**

Run the existing dashboard audit command with verbose subprocess logging enabled. Do not label this a product regression until the Vite process and exact baseline have been compared.

- [ ] **Step 2: Add a failing readiness diagnostic test.**

```python
def test_vite_start_failure_includes_stderr_and_command(tmp_path):
    result = start_dashboard(command=["false"], timeout_seconds=1)
    assert "command" in result.error
    assert "stderr" in result.error
```

- [ ] **Step 3: Implement deterministic process lifecycle handling.**

Use a free port selected before startup, wait for a bounded HTTP readiness probe, retain stdout/stderr, and terminate/wait the child process in `finally`. Do not rely on fixed ports or sleep-only readiness checks.

- [ ] **Step 4: Run the dashboard audit suite twice in a clean environment.**

Run: `pytest -q tests/test_dashboard_audit.py` twice, with a clean Vite process list between runs.

Expected: no setup errors and identical pass/fail results. Any remaining application assertions are separate defects.

- [ ] **Step 5: Commit.**

```bash
git add tests/test_dashboard_audit.py dashboard
git commit -m "test: make dashboard audit server startup deterministic"
```

## Task 5: Add Automated Accessibility Coverage

**Priority:** P2

**Files:**
- Modify: `dashboard/package.json` and lockfile only if an accessibility runner is not already available
- Modify/create: dashboard Playwright specs
- Modify: dashboard components only for reproduced violations

**Interfaces:**
- Consumes: running dashboard routes and authenticated/fixture data.
- Produces: an automated accessibility report with known, justified exclusions kept at zero or explicitly documented.

- [ ] **Step 1: Add a failing accessibility smoke test for the dashboard overview.**

```ts
test("overview has no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""))).toEqual([]);
});
```

- [ ] **Step 2: Execute it locally and capture exact violations.**

Run: `npm --prefix dashboard run test:e2e -- --grep "accessibility"`

Expected: baseline report lists reproducible violations or passes with evidence.

- [ ] **Step 3: Fix only reproduced violations and add keyboard coverage.**

Require a test that reaches the primary navigation, skip link, main content, dashboard controls, dialogs, and chart alternatives using `Tab`, `Shift+Tab`, `Enter`, and `Escape` as applicable.

- [ ] **Step 4: Run the full dashboard browser suite.**

Run: `npm --prefix dashboard run test:e2e`

Expected: PASS with no critical/serious axe violations on the covered routes.

- [ ] **Step 5: Commit.**

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/e2e dashboard/src
git commit -m "test: add dashboard accessibility coverage"
```

## Task 6: Produce Current-SHA Release Evidence

**Priority:** P0

**Files:**
- Create: `audit/release-evidence-<current-main-sha>.md`
- Modify: release checklist/audit index only if it references an obsolete certification

- [ ] **Step 1: Record the immutable target.**

Run: `git rev-parse main && git status --short`

Expected: evidence names the exact `main` SHA and begins from a clean dedicated verification worktree.

- [ ] **Step 2: Run Python, Rust, dashboard, and security gates defined by the repository CI.**

At minimum, run the project test commands, `uvx ruff@0.9.4 check .`, `pip-audit` through the repository's pinned CI path, `cargo audit`, and the repaired dashboard suite. Use the exact CI commands rather than a weaker substitute.

- [ ] **Step 3: Write evidence with command, SHA, UTC timestamp, exit code, duration, and failure links.**

```markdown
| Gate | Command | SHA | Result | Evidence |
|---|---|---|---|---|
| Dashboard audit | `pytest -q tests/test_dashboard_audit.py` | `<sha>` | PASS | `<log path>` |
```

Do not mark a failed, skipped, or environment-blocked gate as passing.

- [ ] **Step 4: Commit the evidence only after all required gates pass.**

```bash
git add audit/release-evidence-<current-main-sha>.md
git commit -m "docs: certify release gates for <current-main-sha>"
```

## Task 7: Complete Hosted Operations Controls

**Priority:** P1/P2; requires operations owner

**Files:**
- Modify: `k8s/prometheus-rules.yaml` only for approved additional alerts
- Create/modify: operational runbook under existing operations/docs location
- Modify: deployment configuration only after alert receiver, uptime provider, and ownership are approved

- [ ] **Step 1: Inventory every current alert rule, receiver, route, runbook link, and owner.**

Acceptance: a table maps each alert to severity, threshold, notification destination, acknowledgement expectation, and named owner.

- [ ] **Step 2: Add missing production signals after confirming metrics exist.**

Cover availability, high latency, error/upstream failure spikes, storage/disk risk, certificate expiry, and service/WebSocket saturation where each applies to the deployed topology.

- [ ] **Step 3: Send a staging test alert to the real destination and record acknowledgement.**

Acceptance: on-call receives it, acknowledges it, and follows the runbook without relying on a developer's local machine.

- [ ] **Step 4: Establish uptime and status communication.**

Acceptance: synthetic checks cover public critical paths and the incident procedure identifies when/how customers receive status updates.

- [ ] **Step 5: Commit configuration/runbooks separately from application code.**

```bash
git add k8s docs
git commit -m "ops: document alert delivery and incident response"
```

## Task 8: Close Commercial and Hosted-Flow Readiness Gates

**Priority:** P0/P2; requires legal and staging access

**Files:**
- Modify: `TERMS.md`, privacy/billing/refund documents only with approved legal text
- Modify: website pricing/checkout docs only for verified flow behavior
- Test: staging checkout, webhook, subscription, cancellation/refund, and SSO provisioning flows

- [ ] **Step 1: Obtain legal-approved versions of customer-facing terms.**

Acceptance: `TERMS.md` no longer labels itself as a draft template and document ownership/effective date are recorded.

- [ ] **Step 2: Execute the staging checkout lifecycle.**

Test a new purchase, payment verification, duplicate webhook, delayed webhook, failed payment, activated subscription, cancellation, and refund. Record external transaction IDs only in the approved secure system, not in repository evidence.

- [ ] **Step 3: Execute the staging SSO lifecycle.**

Test login, tenant assignment, deprovisioning, invalid assertion, and authorization failure. Verify no tenant can obtain another tenant's entitlement.

- [ ] **Step 4: Publish only verified product copy.**

Ensure pricing/CTA claims match the verified lifecycle; standardize public spelling to `CutCtx` and link users to setup, troubleshooting, and purchase paths.

- [ ] **Step 5: Commit documentation/site changes after external acceptance evidence is attached to the PR.**

## Task 9: Assess Migration and Scaling Readiness

**Priority:** P2

**Files:**
- Inspect: `scripts/migrate.py`, schema/storage modules, Kubernetes manifests, backup/runbook docs
- Create: migration-and-scaling verification record in `audit/`

- [ ] **Step 1: Test an upgrade from the oldest supported persisted schema to current.**

Acceptance: data preserved, version recorded, repeat invocation is idempotent, and a failure leaves an actionable recovery path.

- [ ] **Step 2: Test backup/restore and document a rollback decision.**

Acceptance: restore is demonstrated in staging and the team explicitly documents whether downgrade is supported or restore-from-backup is required.

- [ ] **Step 3: Preserve the one-replica deployment constraint unless state architecture changes.**

Acceptance: `k8s/hpa.yaml` continues to explain why `maxReplicas: 1` is required. If multi-replica support is desired, create a separate design/implementation plan for RWX or external state, session ownership, and load/failure tests.

## Task 10: Perform Lower-Risk Documentation, Dependency, and Dashboard Refactors

**Priority:** P3; start only after Tasks 1–6 are accepted

**Files:**
- Modify: relevant documentation pages and website assets
- Modify: dashboard metric/status components, overview modules, and styles only with behavior-preserving tests
- Modify: dependency manifests/lockfile only after confirming `sqlitedict` is unnecessary or optional

- [ ] **Step 1: Add documentation cross-links for install, configure, evaluate, troubleshoot, deploy, and buy.**

Acceptance: each journey is discoverable from the primary documentation landing page and links pass the documentation build/link checker.

- [ ] **Step 2: Isolate `sqlitedict` dependency ownership.**

Acceptance: identify the dependency chain; remove it if unused, or constrain it to the smallest optional/dev extra that needs it. Run lockfile and dependency audits after any change.

- [ ] **Step 3: Refactor one dashboard unit at a time.**

Start with a single repeated metric/status pattern. Add component tests, extract one focused component, run dashboard tests, then commit. Do not combine CSS reorganization with behavior changes in one commit.

- [ ] **Step 4: Split oversized dashboard CSS/overview responsibilities only when each extracted module has a focused responsibility and coverage.**

Acceptance: no visual regression in the dashboard suite and no loss of existing landmarks, skip link, or active navigation semantics.

## Explicitly Rejected or Closed Audit Claims

Do not reopen these without a fresh reproduction against `main`:

- Buyer-report caveat ordering: current output already puts caveat/eligibility context before combined savings.
- CLI help grouping: current help already groups getting started, daily use, and optimization/evaluation journeys.
- Missing client `from_env()`: implemented and tested.
- Missing error-remediation hints: implemented and tested.
- Missing dashboard navigation labels, landmarks, skip link, or active-page semantics: implemented.
- No Sentry/error tracking: optional configured support exists.
- Only two Prometheus alerts: there are three; alert delivery/coverage is the actual open question.
- No WebSocket/session caps: bounded structures already exist.
- Dependency audits are advisory-only: CI runs strict Python and Rust audit commands.
- `maxReplicas: 1` is inherently broken: it is an intentional storage-safety constraint.

## Completion Gate

The backlog is complete only when:

1. Tasks 1–6 pass on the exact release candidate SHA.
2. The hosted billing and usage contracts are verified against staging, not merely mocked.
3. Legal and operations owners provide their external approvals/evidence.
4. Every remaining P2/P3 item is either delivered or represented by an owned, scheduled issue with acceptance criteria.
5. The final audit/release evidence distinguishes verified facts, externally blocked items, and intentionally deferred roadmap work.

## Self-Review

- **Coverage:** Every verified P0/P1/P2/P3 item from the reconciled list maps to a task or external gate above.
- **Removed false positives:** The rejected-claims section prevents agents from spending time re-fixing already resolved work.
- **Dependencies:** Hosted contract, legal, staging, and operations ownership are explicit blockers rather than implicit implementation assumptions.
- **Verification:** Each code workstream has a focused test cycle and the release gate records actual commands/results for the exact SHA.
