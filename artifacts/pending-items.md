# Pending Items

Date: 2026-07-03

This is the short handoff list for remaining project work. Longer branch
reconciliation notes live in `artifacts/savings-moat-priority-todo.md`.

## Progress Update Rule

When roadmap work changes status, update every relevant tracking surface in the
same change:

- `CHANGELOG.md` for shipped user-visible or operator-visible changes.
- `artifacts/pending-items.md` for short current status.
- `artifacts/savings-moat-priority-todo.md` for detailed workstream status.
- Any workstream-specific spec or audit file whose previous claim becomes stale.

## Verified Complete Or Substantially Complete

- HMAC audit-chain source and docs are fixed. `cutctx_ee/audit/store.py` uses
  HMAC-SHA256 over canonical length-prefixed fields, and
  `tests/test_ee_audit_store_hmac.py` guards the contract.
- Dashboard package asset sync is fixed. `make build-dashboard` copies Vite
  hashed assets into the proxy-mounted package directory.
- Packaged dashboard HTML loading is fixed. `get_dashboard_html(prefer_react=True)`
  now reads the fresh `cutctx/dashboard/index.html` bundle entrypoint before
  the legacy `assets/index.html` fallback, preventing stale deleted asset hashes
  from breaking package-level Playwright tests.
- Text hygiene guardrails exist through `scripts/check_text_hygiene.py` and the
  local pre-commit hook.
- WS18 Phase A is complete: `cutctx policies train/show/reset/evict-unsafe`,
  `cutctx policies train --watch`, the local SQLite policy table, bounded
  `LearnedPolicyHooks`, proxy opt-in via `--enable-learned-policies` /
  `CUTCTX_LEARNED_POLICIES=1`, `/stats` `intelligence.policies`, and the
  Overview dashboard `PoliciesPanel` are present.
- WS4 engine module is complete as a library MVP: `cutctx/context_policy.py`
  implements declarative redact/block/allow rules, per-agent budgets, and
  YAML/JSON config loading. `tests/test_context_policy.py` covers the engine.
- WS4 proxy enforcement is now wired for `/v1/messages`,
  `/v1/chat/completions`, and `/v1/responses` when `CUTCTX_CONTEXT_POLICY` is
  set. Route-level tests prove default-off preservation, redaction before
  forwarding, and block-rule 403 behavior. Per-team token budgets are now
  enforced and recorded as well as per-agent budgets.
- WS5 org-scope memory plumbing is present: memory rows carry `workspace_id` and
  `project_id`, migrations add those columns, and `cutctx memory export` can
  filter by workspace or project.
- WS5 import/export round-trip verification now exists and passes for
  `workspace_id` and `project_id`.
- WS6 local-only learn telemetry aggregation is implemented through
  `cutctx learn --aggregate`; it emits anonymized JSON summaries without model
  analysis or network egress. `CUTCTX_LEARN_SHARE=1` fails explicitly because
  sharing is not implemented.
- WS2 Agent Context Report v1 is implemented as `cutctx report agent-context`
  with markdown, HTML, and JSON output from existing savings telemetry.
- WS8 session replay alpha is implemented for context-policy decisions:
  `CUTCTX_REPLAY=1` enables bounded in-memory event capture, authenticated
  `GET /v1/sessions/{session_id}/replay`, and a dashboard Replay page with
  Playwright coverage for loaded and unavailable states.
- Codex websocket keepalive is hardened: `run_server()` now sets uvicorn
  `ws_ping_interval` and `ws_ping_timeout` to 600 seconds, with regression
  coverage in `tests/test_codex_uvicorn_keepalive.py`.
- Savings tracker litellm resilience is guarded by
  `tests/test_savings_tracker_litellm_resilience.py`; token-estimation errors
  now fail soft and buyer-report history preserves lifetime versus delta
  ghost/scaffolding token fields separately.
- WS9 artifacts exist: `artifacts/design-partner-demo-script.md` and
  `artifacts/release-checklist.md`.

## Verified Pending Or Partially Done

1. WS7 Context Assurance is not implemented. Remaining work: CCR ledger,
   retention policy packaging, quality-verification stats, and evidence export.
2. WS8 is partial beyond the alpha scope. Remaining work: extend replay beyond
   context-policy block/redaction events to compressed, retrieved, injected,
   and CCR lifecycle context.
3. WS1-WS3 are partial. README positioning and Agent Context Report v1 exist,
   but quality-at-budget benchmark v1 docs and outreach content updates still
   need completion/verification.
4. Release housekeeping remains: close/delete merged feature branches or PRs when
   confirmed safe. EE `.so` files are ignored by Git, so release packaging must
   rebuild and sign EE binaries from the fixed source before publishing.

## Latest Verification

- `rtk test .venv/bin/python -m pytest tests/`
  passed: 7904 tests, 260 skipped, 22 warnings in 279.18s.
- `rtk pytest -q tests/test_policy_learning.py tests/test_context_policy.py tests/test_cli/test_main_help_version.py tests/test_memory_bridge.py tests/test_memory_sync.py`
  passed: 103 tests.
- `.venv/bin/python -m pytest -q tests/test_context_policy_proxy_integration.py tests/cli/test_memory.py tests/test_cli_learn.py`
  passed: 45 tests.
- `.venv/bin/python -m pytest -q tests/test_context_policy.py tests/test_context_policy_proxy_integration.py tests/test_rate_limiter.py tests/test_route_modules.py -k 'context_policy or team_budget or sso or rate_limiter or replay' tests/test_agent_context_report.py tests/test_cli_learn.py tests/cli/test_memory.py tests/test_savings_buyer_report.py`
  passed: 31 selected tests from the command expression.
- `cd dashboard && npx playwright test e2e` passed: 19 tests.
- `.venv/bin/python -m pytest -q tests/test_codex_uvicorn_keepalive.py`
  passed: 1 test.
- `.venv/bin/python -m pytest -q tests/test_dashboard_capabilities_toggles_e2e.py tests/test_dashboard_governance_e2e.py tests/test_dashboard_overview_lifetime_headline.py tests/test_dashboard_savings_by_model.py tests/test_dashboard_surfaces_playwright.py tests/test_docs_page.py --tb=short`
  passed: 7 tests.
- `.venv/bin/python -m pytest -q tests/test_savings_tracker_litellm_resilience.py tests/test_savings_buyer_report.py`
  passed: 14 tests.
- `rtk .venv/bin/python -m ruff check cutctx/context_policy.py cutctx/proxy/rate_limiter.py cutctx/proxy/routes/sso.py cutctx/proxy/session_replay.py cutctx/proxy/savings_tracker.py cutctx/dashboard/__init__.py cutctx/cli/report.py cutctx/cli/learn.py cutctx/learn/aggregate.py tests/test_context_policy.py tests/test_rate_limiter.py tests/test_route_modules.py tests/test_agent_context_report.py tests/test_cli_learn.py tests/cli/test_memory.py tests/test_commercial_surface_truthfulness.py tests/test_codex_uvicorn_keepalive.py tests/test_savings_tracker_litellm_resilience.py`
  passed.
- `rtk .venv/bin/python scripts/check_text_hygiene.py CHANGELOG.md artifacts/pending-items.md artifacts/release-checklist.md artifacts/savings-moat-priority-todo.md artifacts/design-partner-demo-script.md cutctx/proxy/rate_limiter.py dashboard/e2e/ui.spec.js cutctx/dashboard/__init__.py tests/test_codex_uvicorn_keepalive.py`
  passed.
- `rtk git diff --check` passed.
- `rtk make ci-precheck` remains blocked in this workstation because `cargo` is not installed.
