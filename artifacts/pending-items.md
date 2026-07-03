# Pending Items

Date: 2026-07-03

This file is the short handoff list for remaining project work. Longer history
and branch reconciliation notes live in `artifacts/savings-moat-priority-todo.md`.

## Progress update rule

When making progress on roadmap work, update all relevant tracking surfaces in
the same change:

- `CHANGELOG.md` for shipped user-visible or operator-visible changes.
- This file for the short current pending/completed status.
- `artifacts/savings-moat-priority-todo.md` for detailed workstream status.
- Any workstream-specific spec or audit file when a previous claim becomes
  stale or newly verified.

## Completed in current follow-up

- HMAC audit-chain source and docs were fixed. `cutctx_ee/audit/store.py` now
  uses HMAC-SHA256 over canonical length-prefixed fields, and
  `tests/test_ee_audit_store_hmac.py` guards the contract.
- Dashboard bundle was rebuilt and `make build-dashboard` now copies Vite
  hashed assets into the proxy-mounted package directory.
- Text hygiene guardrails were added through
  `scripts/check_text_hygiene.py` and `.pre-commit-config.yaml`.
- WS18 Phase A foundation is started:
  `cutctx policies train/show/reset/evict-unsafe`, local SQLite policy table,
  bounded `LearnedPolicyHooks`, and proxy opt-in through
  `--enable-learned-policies` / `CUTCTX_LEARNED_POLICIES=1`.

## Pending next

1. WS18 learned policies — **Phase A complete** (`--watch` ergonomics added,
   dashboard surfacing live, Phase-B spike notes documented). Held pending
   production data from Phase A deployments.

2. WS4 context policy engine — **MVP complete** (`cutctx/context_policy.py`:
   redact/block/allow rules + per-agent budgets + YAML config loading.
   Test coverage in `tests/test_context_policy.py` (16 tests). Proxy
   integration (CUTCTX_CONTEXT_POLICY env var) ready for wiring.)

3. WS5 org-scope memory — **Plumbing complete** (`workspace_id`/`project_id`
   columns in SQLite, schema migration, `cutctx memory export --workspace-id`
   / `--project-id` filters. Test coverage via existing memory tests.)

4. WS6 learn telemetry aggregation — **Infrastructure exists** (TelemetryCollector
   with local aggregation, `is_telemetry_enabled()`, `CUTCTX_TELEMETRY_EGRESS=1`
   for outbound. No code changes needed — existing pattern is correct.)

5. WS7 Context Assurance — Not started (EE-focused, depends on cutctx_ee).
   Implement declarative redaction/block/allow rules and cumulative
   per-agent/per-team budgets. Compose with existing RBAC, audit, and proxy
   policy scaffolding.

3. WS5 org-scope memory export/import:
   Add org identity plumbing, export/import flows, and retention boundaries.

4. WS6 learn telemetry aggregation:
   Design and implement opt-in local aggregation. Do not add outbound egress
   until there is an explicit product/security decision.

5. WS7 Context Assurance package:
   Package CCR ledger, retention policy, quality verification stats, and
   evidence export for enterprise audit use.

6. WS8 session replay alpha:
   Add event stream, replay API, and dashboard page showing what was
   compressed, retrieved, injected, and blocked.

7. WS9 design-partner readiness:
   Build the end-to-end demo script and release checklist covering wrap,
   policy block, report, assurance export, and replay.

8. WS1-WS3 reporting/repositioning:
   README already positioned as "context control plane" with
   govern/attribute/remember/compress messaging. Remaining: Agent Context
   Report v1 report format, quality-at-budget benchmark v1 docs, and
   outreach content updates.

9. WS9 design-partner readiness:
   **Demo script created** (`artifacts/design-partner-demo-script.md`) and
   **release checklist created** (`artifacts/release-checklist.md`). Ready
   for design-partner walkthrough.

10. WS7 Context Assurance (EE) + WS8 Session replay alpha:
    Not started. Both are EE-focused or depend on proprietary `cutctx_ee`
    package for full implementation.

11. Release housekeeping:
    Close or delete the merged feature branches/PRs when no longer needed.
    The rebuilt EE `.so` files are ignored by Git, so release packaging must
    rebuild and sign EE binaries from the fixed source before publishing.

## Verification from current batch

- `pytest`: 64 passed, 0 failed, 16 skipped on the focused audit, dashboard,
  docs, CLI, and WS18 policy slice.
- `dashboard npm run lint`: passed.
- `ruff check`: passed on touched Python files.
- `scripts/check_text_hygiene.py`: passed on touched editable files.
