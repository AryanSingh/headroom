# Release Checklist

Pre-release verification for the current worktree (`fix/ws20-memcache-optimize`).

## Test suite

- [ ] Full pytest run: `.venv/bin/python -m pytest tests/ -x --tb=short`
- [ ] Dashboard lint: `cd dashboard && npm run lint`
- [ ] Dashboard e2e: `cd dashboard && npx playwright test e2e/`
- [ ] Ruff check: `.venv/bin/python -m ruff check cutctx/ tests/`
- [ ] No pre-existing test failures beyond the documented ones (dashboard
      docs flakiness, EE HMAC pre-existing debt)

## Build

- [ ] Dashboard rebuild: `make build-dashboard` (Vite bundle →
      `cutctx/dashboard/assets/`)
- [ ] EE binary rebuild: run the EE build script, sign the `.so` files
- [ ] `make ci-precheck` passes (lint + test + build)

## Documentation

- [ ] `CHANGELOG.md`: verify all entries under `[Unreleased]` are accurate
- [ ] `artifacts/pending-items.md`: update completed/in-progress status
- [ ] `artifacts/savings-moat-priority-todo.md`: update WS18/WS4/WS5 status
- [ ] Docs reflect current behavior (no stale copy)

## Feature verification

### WS18 — Learned policies
- [ ] `cutctx policies train --watch` starts and trains on JSONL events
- [ ] `cutctx policies train --help` shows `--watch` and `--poll-interval`
- [ ] Dashboard `PoliciesPanel` shows Active/Disabled state correctly
- [ ] `/stats` returns `intelligence.policies` with count/distribution
- [ ] `LearnedPolicyHooks.compute_biases()` applies bounded biases
- [ ] `cutctx policies evict-unsafe` removes unsafe rows

### WS4 — Context policy engine
- [ ] `ContextPolicyEngine` evaluates block rules before redaction
- [ ] Redact rules mask matching content
- [ ] Allow rules filter non-matching content
- [ ] Agent budget enforcement prevents over-limit requests
- [ ] YAML config loading: `load_context_policy()` works
- [ ] All 16 tests in `tests/test_context_policy.py` pass

### WS5 — Org-scope memory
- [ ] `SQLiteMemoryStore._init_db()` creates `workspace_id` / `project_id`
      columns
- [ ] Schema migration: existing databases get new columns without error
- [ ] `cutctx memory export --workspace-id X` filters correctly
- [ ] `cutctx memory export --project-id Y` filters correctly
- [ ] Round-trip: export → import preserves workspace_id/project_id

## Version

- [ ] `pyproject.toml` version bumped if this is a release
- [ ] `CHANGELOG.md` has a `[Unreleased]` → `[X.Y.Z]` - YYYY-MM-DD
      section if releasing

## Branch cleanup

- [ ] `feat/ws10-output-optimize` — merged, can be deleted
- [ ] `feat/ws11-memoize` — merged, can be deleted
- [ ] `feat/ws13-batch-routing` — merged, can be deleted
- [ ] `feat/ws16-normalize` — merged, can be deleted
- [ ] `feat/ws19-autopilot` — merged, can be deleted
- [ ] `integration/merge-ws-branches` — already deleted
