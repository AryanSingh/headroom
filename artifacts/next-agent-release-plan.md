# Next-Agent Release Plan

Date: 2026-07-03
Baseline branch: `fix/ws20-memcache-optimize`
Baseline commit: `b0a6637` (`Harden release readiness surfaces`)

This file is the execution handoff for the remaining release-readiness work.
Do not trust older audit reports without verifying directly from code, tests,
runtime behavior, and docs.

## Current Verified State

- Full backend pytest passed: `7904 passed, 260 skipped, 22 warnings`.
- Dashboard lint, build, and Playwright E2E passed.
- Live Cutctx proxy health was verified on `127.0.0.1:8787`.
- Codex websocket keepalive hardening is present in source and guarded by
  `tests/test_codex_uvicorn_keepalive.py`.
- Litellm savings-tracker resilience is present in source and guarded by
  `tests/test_savings_tracker_litellm_resilience.py`.
- WS2, WS4, WS5, WS6, WS8 alpha, dashboard accessibility/routing fixes, SSO
  body-token support, rate-limiter cleanup, and packaged-dashboard loader
  fixes are committed.
- `make ci-precheck` is blocked on the current workstation because `cargo` is
  not installed.

## Working Rules

- Use `rtk` for shell commands.
- Preserve the current passing test baseline.
- Make atomic edits and atomic commits.
- Update `CHANGELOG.md` and relevant artifact trackers with every meaningful
  status change.
- Do not mark work complete without runtime verification.
- Do not reinstall or mutate shared live proxy virtualenvs while other agents
  depend on them.
- Do not touch `dashboard-cache-ttl-main.png` unless explicitly asked; it was
  intentionally left out of commit `b0a6637`.
- Treat previous reports as hints, never proof.

## Phase 1: Rehydrate Context

Run:

```bash
rtk git fetch origin
rtk git checkout fix/ws20-memcache-optimize
rtk git pull --ff-only
rtk git status --short
```

Read:

```bash
rtk read artifacts/pending-items.md
rtk read artifacts/release-checklist.md
rtk read artifacts/savings-moat-priority-todo.md
rtk read artifacts/product-strategy-moat-analysis.md
rtk read artifacts/strategy-implementation-plan.md
rtk read artifacts/savings-moat-expansion-specs.md
```

Run a focused smoke baseline before edits:

```bash
rtk test .venv/bin/python -m pytest tests/test_codex_uvicorn_keepalive.py tests/test_savings_tracker_litellm_resilience.py tests/test_context_policy_proxy_integration.py
cd dashboard && rtk npm run lint && rtk npx playwright test e2e/
```

## Phase 2: Resolve Local Toolchain Blocker

Install or activate Rust toolchain if acceptable on the machine.

Verify:

```bash
rtk cargo --version
rtk make ci-precheck
```

If `ci-precheck` fails:

- Fix real code/test failures.
- Document environmental blockers exactly in `artifacts/release-checklist.md`.
- Do not mark release checklist green until the command passes or the blocker
  is explicitly accepted.

## Phase 3: Complete WS7 Context Assurance

WS7 is the largest remaining release gap.

Implement:

- CCR ledger with durable append-only evidence events.
- Event metadata: event IDs, timestamps, workspace/project/session IDs,
  input/output hashes, policy decisions, retrieval/compression metadata.
- Tamper-evidence or HMAC chaining if the ledger is enterprise audit evidence.
- Configurable retention policy packaging.
- Quality-verification stats exposed through CLI and/or `/stats`.
- Evidence export as JSON and markdown.

Add tests for:

- Ledger append/read behavior.
- Integrity verification.
- Retention expiry and disabled-retention behavior.
- Malformed retention config.
- Evidence export format and verification instructions.

Suggested command:

```bash
rtk test .venv/bin/python -m pytest tests/test_context_assurance.py tests/test_ccr_ledger.py tests/test_assurance_export.py
```

Acceptance criteria:

- A user can generate an evidence bundle from real local events.
- The bundle can be verified independently.
- Docs explain what is guaranteed and what is not.
- No fake compliance claims remain.

## Phase 4: Extend WS8 Session Replay Beyond Alpha

Current WS8 alpha records context-policy block/redaction decisions only.

Extend replay coverage to:

- Compression events.
- Retrieval events.
- Injection/context assembly events.
- CCR lifecycle events.
- Error and fallback states.

Implementation guardrails:

- Keep replay bounded and privacy-aware.
- Do not store raw sensitive prompts unless explicitly configured.
- Prefer hashes, summaries, and metadata by default.
- Ensure replay explains what happened without leaking secrets.

Suggested commands:

```bash
rtk test .venv/bin/python -m pytest tests/test_session_replay.py tests/test_context_policy_proxy_integration.py
cd dashboard && rtk npx playwright test e2e/replay.spec.js
```

Acceptance criteria:

- Replay timeline shows end-to-end context lifecycle.
- Dashboard handles success, empty, disabled, unauthorized, and error states.
- Replay API remains authenticated.

## Phase 5: Complete WS1-WS3 Go-To-Market Artifacts

Remaining partials:

- Quality-at-budget benchmark v1.
- Provider-native comparison.
- Outreach/demo content aligned to current positioning.

Implement:

- Runnable local benchmark command or reproducible script.
- Offline fixture dataset.
- Markdown report template.
- Honest provider-native comparison covering savings, quality, latency, and
  caveats.
- README/product-doc updates only when claims are verified.

Inspect and update as needed:

```bash
rtk read README.md
rtk read PRODUCT_GUIDE.md
rtk read artifacts/design-partner-demo-script.md
rtk read artifacts/savings-moat-priority-todo.md
```

Acceptance criteria:

- Benchmark runs locally.
- Output includes savings, quality, latency, and caveats.
- Marketing claims are reproducible or clearly qualified.

## Phase 6: EE Release Packaging

Known blocker: EE `.so` files are ignored by Git and must be rebuilt/signed
before release.

Discover:

```bash
rtk find 'ee'
rtk grep -n 'sign\|build.*so\|audit_store\|cutctx_ee'
```

Complete:

- Find EE build/signing process.
- Rebuild EE binaries from current source.
- Sign or checksum artifacts as expected.
- Verify import/runtime behavior.
- Update `artifacts/release-checklist.md`.

Acceptance criteria:

- EE package builds from source.
- Audit-chain HMAC behavior works in runtime package, not just source tests.
- Release docs state artifact provenance clearly.

## Phase 7: Branch And PR Housekeeping

Merged feature branches listed by prior agents:

- `feat/ws10-output-optimize`
- `feat/ws11-memoize`
- `feat/ws13-batch-routing`
- `feat/ws16-normalize`
- `feat/ws19-autopilot`
- `fix/audit-p0-hmac-readme-cta`

Verify before deleting:

```bash
rtk git branch --merged main
rtk git log --oneline main --decorate --all --graph -n 50
```

Only close or delete branches after confirming they are merged and no open PR
state needs preservation.

## Phase 8: Full Release Audit

After implementation, run:

```bash
rtk test .venv/bin/python -m pytest tests/
cd dashboard && rtk npm run lint
cd dashboard && rtk npm run build
cd dashboard && rtk npx playwright test e2e/
rtk .venv/bin/python -m ruff check cutctx tests
rtk .venv/bin/python scripts/check_text_hygiene.py CHANGELOG.md artifacts/pending-items.md artifacts/release-checklist.md artifacts/savings-moat-priority-todo.md artifacts/next-agent-release-plan.md
rtk git diff --check
rtk make ci-precheck
```

Live smoke, if proxy is running:

```bash
rtk curl -fsS http://127.0.0.1:8787/readyz
rtk curl -fsS http://127.0.0.1:8787/health
```

## Final Documentation Updates

Update:

- `CHANGELOG.md`
- `artifacts/pending-items.md`
- `artifacts/release-checklist.md`
- `artifacts/savings-moat-priority-todo.md`
- This file, if the plan changes.

Final report should include:

- Features completed.
- Tests added.
- Commands run.
- Exact failures fixed.
- Remaining blockers.
- Final recommendation: `Go`, `Limited Go`, or `No-Go`.

## Release Recommendation Criteria

`Go` requires:

- Full tests pass.
- Dashboard lint/build/E2E pass.
- `make ci-precheck` passes.
- EE rebuild/signing verified.
- WS7 complete.
- WS8 full replay coverage complete.
- Docs and changelog updated.

`Limited Go` means:

- OSS/dashboard scope is verified.
- Enterprise assurance, EE packaging, or release automation remains incomplete
  but is clearly documented.

`No-Go` if any of these remain:

- Critical or high runtime failure.
- Broken dashboard.
- Failed full pytest.
- Unverifiable EE artifact.
- Fake compliance or replay success path.
