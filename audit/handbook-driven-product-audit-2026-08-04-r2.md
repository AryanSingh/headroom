---
id: AUD-2026-08-04-02
kind: audit-report
title: Fresh Handbook-Driven Product Audit of Cutctx/Headroom
date: 2026-08-04
product: Cutctx/Headroom
revision: d3574bab
criteria: engineering-handbook/SUMMARY.md and its control, checklist, OWASP, NIST, KPI, and runbook assets
state: COMPLETE — fresh local executable audit; live-production controls remain outside scope
---

# Fresh Handbook-Driven Product Audit

## Decision summary

The current product revision passed all fresh local executable checks selected from
the engineering handbook: **75 API/security/routing/migration tests, 148
CLI/retention/release/AI-evaluation tests, 13 dashboard/browser tests, and 12
handbook fixture examples**. The handbook validator also returned no findings.

This is a local engineering-confidence decision, not a production-release approval.
Live provider calls, production recovery, destructive chaos injection, real billing
reconciliation, and full load testing were not run and remain `Not evaluated`.

## Audit basis

The audit used:

- `engineering-handbook/SUMMARY.md`
- `engineering-handbook/appendices/control-catalog.md`
- `engineering-handbook/governance/evidence-standard.md`
- `engineering-handbook/governance/risk-severity-model.md`
- domain checklists for CLI, API, integrations, routing, memory/security, reliability,
  release, Playwright, migrations, AI evaluation, compatibility, observability, and
  continuous verification
- OWASP/NIST mappings, scorecards, runbooks, and executable handbook fixtures

Reviewed revision: `d3574bab` (`docs: reconcile handbook audit evidence`).

## Control disposition

| Handbook domain | Fresh evidence | Result |
| --- | --- | --- |
| CLI contracts and auth | 19 selected tests | Pass |
| API, proxy auth, and compatibility | 37 selected tests | Pass |
| Routing and orchestration | 16 selected tests | Pass |
| Observability | 4 selected tests | Pass |
| Database migrations | 15 selected tests | Pass |
| Memory and retention | 14 selected tests | Pass |
| Release workflows and manifests | 48 selected tests | Pass |
| AI evaluation and routing quality | 20 selected tests | Pass |
| Dashboard and browser journeys | 13 selected tests | Pass |
| Handbook executable examples | 12 fixtures | Pass |
| Live production/provider/billing/recovery/chaos/load controls | No safe local evidence | Not evaluated |

## Fresh command evidence

All commands ran from the audited worktree with the project `.venv` after:

```text
uv sync --extra ee --extra dev --locked
```

### Handbook integrity

```text
.venv/bin/python engineering-handbook/automation/validate_handbook.py engineering-handbook --format json
=> []

.venv/bin/python engineering-handbook/automation/check_examples.py engineering-handbook --format json
=> 12 passed
```

### Product tranche A — API, security, routing, migration, observability

```text
.venv/bin/python -m pytest -q \
  tests/test_auth_adversarial.py \
  tests/test_ccr_admin_auth.py \
  tests/test_proxy_client_auth.py \
  tests/test_agent_client_auth.py \
  tests/test_routing_modes_e2e.py \
  tests/test_observability_tracing.py \
  tests/test_sql_migrations.py \
  tests/test_openai_responses_subscription_compat.py
=> 75 passed in 11.56s
```

### Product tranche B — CLI, memory, release, AI evaluation

```text
.venv/bin/python -m pytest -q \
  tests/test_cli/test_main_help_version.py \
  tests/test_cli/test_auth.py \
  tests/test_cli/test_global_routing.py \
  tests/test_cli/test_routing_status.py \
  tests/test_cli/test_proxy_client_credentials.py \
  tests/test_retention.py \
  tests/test_quality_retention.py \
  tests/test_release_evidence.py \
  tests/test_release_workflows.py \
  tests/test_release_manifest.py \
  tests/test_model_routing_evals.py \
  tests/test_model_routing_quality_benchmark.py
=> 148 passed in 7.76s
```

### Product tranche C — dashboard and browser journeys

```text
.venv/bin/python -m pytest -q \
  tests/test_dashboard_surfaces_playwright.py \
  tests/test_dashboard_cache_ttl_playwright.py \
  tests/test_dashboard_governance_e2e.py \
  tests/test_dashboard_orchestrator_policy_e2e.py \
  tests/test_dashboard_capabilities_toggles_e2e.py
=> 13 passed in 21.27s
```

The browser suite ran after the project `dev` extra and Chromium were provisioned;
no browser suite was silently treated as passing while skipped.

## Findings

### No new Critical, High, or Medium product defect reproduced

The fresh local evidence pass did not reproduce a product failure in the exercised
controls. The prior environment reproducibility issue is fixed and remains covered
by the declared `pytest-asyncio` dependency and the passing retention suite.

### Low — existing Starlette/httpx deprecation warning

The product test harness still emits Starlette's warning that using `httpx` with
`starlette.testclient` is deprecated in favor of `httpx2`. It does not currently
fail the tests, but it should be migrated before a dependency upgrade makes it a
hard failure.

## Not evaluated

The following handbook controls require authority, credentials, or isolated
production-like infrastructure and were not claimed as passing:

- live paid-provider and upstream outage behavior
- production backup restore, recovery-point validation, and safe replay
- destructive or production-like chaos experiments
- full load, burst, dependency-latency, and worker-loss testing
- commercial billing and entitlement reconciliation against a payment processor

## Next actions

1. Keep the fresh tranches in CI as the local handbook gate.
2. Migrate the deprecated Starlette test-client path.
3. Run the excluded production controls only in approved isolated environments,
   retaining the evidence artifacts required by the handbook runbooks.

