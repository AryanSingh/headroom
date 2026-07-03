# End-To-End Bug Hunt Plan

Date: 2026-07-03
Scope: UI, product features, APIs, integrations, release gates, and stub/fake
state detection.

This plan is for a fresh agent or release engineer to verify that Cutctx is
working end-to-end, not just passing isolated unit tests. Do not mark a feature
complete unless it has direct code/runtime evidence and at least one meaningful
test or manual verification artifact.

## Operating Rules

- Use `rtk` for shell commands.
- Do not restart or reload shared `com.cutctx.proxy` on port 8787.
- Use `cutctx-dev` on port 8788 for proxy iteration and restart-heavy testing.
- Keep edits atomic and update `CHANGELOG.md`, `artifacts/pending-items.md`,
  and `artifacts/release-checklist.md` when status changes.
- Do not trust previous reports. Verify from source, tests, and runtime.
- Do not hide failures by adding skips, mocks, or fake success states.
- Do not claim release readiness while commitlint, EE packaging/signing,
  versioning, or product-owner approval gates remain open.

## Regression-Prevention Rules

These rules are mandatory for every fix in this audit.

- Capture baseline before editing: `rtk git status --short --branch`,
  `rtk git diff --stat`, and the smallest relevant passing test command.
- Identify file ownership before editing. If a file changed unexpectedly or
  appears to belong to another concurrent agent, do not edit it until the owner
  or user confirms.
- Do not revert user or other-agent work unless explicitly asked.
- Write or update a regression test before fixing any behavior bug unless the
  bug is purely copy/docs.
- Prefer additive, focused tests over broad brittle snapshots.
- Never convert a failing test to `skip`, `xfail`, or a weaker assertion just
  to get green.
- Never replace live behavior with fake data or static success responses.
- Keep generated assets tied to their source command. If a dashboard bundle is
  changed, run dashboard build/E2E and stage the matching generated files.
- Keep release trackers honest. If a feature remains partial, mark it partial
  with a precise blocker instead of complete.
- Re-run the smallest affected test after every fix, then re-run the relevant
  broader gate before committing.
- Make atomic commits. Each commit should contain one coherent fix or one
  coherent documentation update.
- Leave unrelated dirty files unstaged and call them out in the final report.
- If a fix touches routing, auth, billing, telemetry, replay, assurance, or
  stats, add at least one negative-path test.
- If a fix touches UI, verify loading, empty, error, success, and responsive
  states.
- If a fix touches proxy/runtime behavior, use `cutctx-dev` and avoid shared
  port 8787.

Regression stop conditions:

- A previously passing focused test fails.
- Full Python, Rust workspace, or dashboard gates regress.
- A claimed feature is only implemented in docs or tests but not wired into
  runtime.
- A release claim becomes broader than the verified implementation.
- Any command requires restarting shared `com.cutctx.proxy` on port 8787.

When a stop condition occurs:

1. Stop editing.
2. Record the failing command and exact failure.
3. Inspect whether the failure is from your changes, concurrent changes, or the
   environment.
4. Fix only your regression or ask the user how to handle concurrent conflicts.
5. Re-run the failed command and the smallest related regression suite.

## Phase 1: Baseline And Inventory

### 1.1 Capture Workspace State

```bash
rtk git status --short --branch
rtk git log --oneline --decorate -n 20
rtk git diff --stat
```

Expected:

- Only intentional local changes are present.
- Known unrelated artifact: `dashboard-cache-ttl-main.png` may remain modified.

### 1.2 Build A Feature Inventory

Inspect:

```bash
rtk read artifacts/release-checklist.md
rtk read artifacts/pending-items.md
rtk read artifacts/savings-moat-priority-todo.md
rtk rg -n "TODO|FIXME|stub|placeholder|fake|mock|NotImplemented|pass$|return None|disabled|skip" cutctx dashboard tests docs artifacts
rtk rg -n "CUTCTX_|/v1/|@app\\.|APIRouter|Route|create_app|router" cutctx
rtk rg -n "Route|BrowserRouter|createBrowserRouter|pages|nav|Replay|Governance|Capabilities|Orchestrator" dashboard/src dashboard/e2e
```

Create or update a table with each item marked:

- `Verified`
- `Failed`
- `Partial`
- `Blocked`
- `Missing`
- `Needs Improvement`

Minimum inventory sections:

- CLI surfaces.
- Proxy API routes.
- Dashboard pages.
- Dashboard API fetchers.
- Context policy.
- Savings attribution.
- Dashboard stats/history.
- Memory export/import.
- Learn telemetry aggregation.
- Agent Context Report.
- Context Assurance.
- Session Replay.
- License and EE boundary.
- Rust proxy.
- Packaging/build.
- Docs/public claims.

## Phase 2: Stub And Fake-State Hunt

Search for incomplete behavior:

```bash
rtk rg -n "TODO|FIXME|NotImplemented|stub|placeholder|fake|dummy|mock data|coming soon|no-op|pass$|return \\{\\}|return \\[\\]|return None" cutctx dashboard docs artifacts tests
```

For every hit:

1. Decide whether it is intentional test scaffolding or product behavior.
2. If product behavior, write a failing test that captures expected behavior.
3. Implement the smallest fix.
4. Update docs if the feature remains intentionally partial.

Examples of unacceptable release states:

- UI shows successful save when backend failed.
- API returns a static object for a claimed live feature.
- Dashboard chart uses fake values when stats endpoint has no data.
- Docs claim an endpoint or command exists when `--help` does not show it.
- Feature is only implemented as a class but never wired into runtime.

## Phase 3: Backend And CLI Verification

Run focused local checks first:

```bash
rtk test .venv/bin/python -m pytest tests/test_assurance.py tests/test_agent_context_report.py tests/test_context_policy_proxy_integration.py tests/test_codex_uvicorn_keepalive.py tests/test_savings_tracker_litellm_resilience.py
rtk test cargo test -p cutctx-proxy --test license_verify
rtk cargo fmt --all -- --check
rtk cargo clippy --workspace -- -D warnings
rtk test cargo test --workspace
```

Then run the full Python suite:

```bash
rtk test .venv/bin/python -m pytest tests/
```

Collect skip reasons:

```bash
rtk proxy .venv/bin/python -m pytest tests/ -rs > /tmp/cutctx-pytest-rs.log 2>&1
python3 - <<'PY'
from pathlib import Path
import re
from collections import Counter
text = Path('/tmp/cutctx-pytest-rs.log').read_text(errors='replace')
reasons = []
for line in text.splitlines():
    if line.startswith('SKIPPED'):
        m = re.match(r'SKIPPED \\[\\d+\\] .*?:\\d+: (.*)', line)
        reasons.append(m.group(1) if m else line)
for reason, count in Counter(reasons).most_common(80):
    print(f'{count}\\t{reason}')
PY
```

Expected:

- Skips are live-provider, optional dependency, hardware, or explicit opt-in
  tests.
- No core local feature is skipped to hide an incomplete implementation.

## Phase 4: Dashboard UI And UX Audit

### 4.1 Static And Build Gates

```bash
cd dashboard && rtk npm run lint
cd dashboard && rtk npm run build
cd dashboard && rtk npx playwright test e2e/
```

Expected:

- Lint passes with `--max-warnings=0`.
- Build succeeds.
- All dashboard E2E tests pass.

### 4.2 Screen Inventory

Visit and screenshot these states:

- Dashboard overview.
- Recent requests with populated data.
- Recent requests empty state.
- Savings by source/client/model.
- Orchestrator toggles success/failure.
- Capabilities toggles success/failure.
- Governance policy state.
- Security page.
- Memory page.
- Playground page.
- Docs page.
- Replay page loaded state.
- Replay page unavailable/disabled state.
- Unknown route redirect.
- Mobile sidebar open/close.
- Mobile Escape focus restoration.

For each screen check:

- Text is readable.
- No overflow or clipping at desktop/tablet/mobile widths.
- Loading states do not flash forever.
- Empty states explain what to do next.
- Error states show actionable copy.
- Toggle failures do not silently revert.
- Tables align and do not truncate important identifiers unexpectedly.
- Search, nav, keyboard focus, and Escape behavior work.
- Color contrast is acceptable.

### 4.3 Browser-Driven Interaction Scenarios

Use Playwright or the in-app browser. Test:

- Navigate every sidebar item.
- Toggle every feature flag control.
- Force config update failure and confirm alert is visible.
- Load stats with empty history.
- Load stats with realistic history.
- Load stats with malformed payload and confirm safe error state.
- Open Replay with a session that exists.
- Open Replay with a session that does not exist.
- Verify unknown route redirects.
- Verify responsive layout at `390x844`, `768x1024`, and desktop.

## Phase 5: Runtime Feature Flows

Use `cutctx-dev` on port 8788, not shared 8787.

### 5.1 Context Policy

```bash
cat > /tmp/context-policy.yaml <<'YAML'
redaction_rules:
  - name: mask_api_keys
    pattern: "sk-[A-Za-z0-9]+"
    replacement: "sk-***"
    scope: content
block_rules:
  - name: block_passwd_files
    pattern: "/etc/passwd"
    reason: "Password file access blocked by security policy"
YAML
```

Verify:

- Default-off requests are preserved.
- Redacted requests are redacted before upstream.
- Blocked requests return policy failure.
- Team and agent budgets enforce limits.
- Replay records policy events when enabled.

### 5.2 Savings And Dashboard Stats

Verify:

- A request creates/update savings history.
- Money saved changes when new savings rows are recorded.
- Lifetime totals do not regress when current session is smaller.
- Recent requests show routed model truthfully.
- Savings source totals do not double-count provider cache and Cutctx
  compression.
- `/stats` and `/stats-history` are not confused by dashboard fetch mocks.

### 5.3 Agent Context Report

```bash
rtk .venv/bin/python -m cutctx.cli report agent-context --format markdown --days 7
rtk .venv/bin/python -m cutctx.cli report agent-context --format json --days 7
```

Verify:

- Output contains savings attribution.
- Assurance status matches ledger existence.
- Replay status matches `CUTCTX_REPLAY`.
- Empty telemetry produces honest no-data copy.

### 5.4 Context Assurance

```bash
rtk .venv/bin/python -m cutctx.cli report assurance --format markdown
rtk .venv/bin/python -m cutctx.cli report assurance --format json
rtk .venv/bin/python -m cutctx.cli report assurance --verify
```

Verify:

- JSON parses.
- Markdown includes verification instructions.
- `--verify` returns `chain_broken: false` for intact ledger.
- Direct DB tamper is detected by tests.

### 5.5 Session Replay

Verify:

- `CUTCTX_REPLAY=1` enables replay store.
- Replay API requires admin auth.
- Missing sessions return honest unavailable/not-found state.
- Pipeline extension is discoverable in editable/local installs.
- Compression/retrieval/injection/CCR lifecycle events record when metadata is
  emitted.

### 5.6 Memory

Verify:

- Export all memories.
- Export by `workspace_id`.
- Export by `project_id`.
- Import/export round-trip preserves scope IDs.
- Empty memory store has clear output.

### 5.7 Learn Telemetry

Verify:

- `cutctx learn --aggregate` emits local anonymized summaries.
- No outbound network egress occurs.
- `CUTCTX_LEARN_SHARE=1` fails explicitly until approved.

## Phase 6: API Contract Hunt

For each route:

- Check auth requirement.
- Check happy path.
- Check malformed JSON.
- Check missing required fields.
- Check disabled feature behavior.
- Check upstream error behavior.
- Check timeout behavior.
- Check response schema stability.

Route families:

- Health/readiness.
- Stats/history.
- Admin stats reset.
- Context policy.
- Replay.
- SSO validation.
- Memory routes.
- Secrets routes.
- Proxy request routes.
- WebSocket `/v1/responses`.
- Report/export commands where applicable.

## Phase 7: Release Claim Audit

Check active docs and marketing surfaces for claims:

```bash
rtk rg -n "SOC 2|guarantee|always|never|best|enterprise|assurance|replay|HMAC|audit|savings|90%|provider-native|billing|portal|checkout" README.md PRODUCT_GUIDE.md docs artifacts marketing wiki
```

For each claim:

- Verify code support.
- Verify test coverage.
- Verify runtime behavior.
- Downgrade wording if unproven.

No release claim should depend on unavailable credentials, fake data, or a
manual-only untested path.

## Phase 8: Final Gates

Run:

```bash
rtk test .venv/bin/python -m pytest tests/
rtk test cargo test --workspace
rtk cargo clippy --workspace -- -D warnings
rtk cargo fmt --all -- --check
cd dashboard && rtk npm run lint && rtk npm run build && rtk npx playwright test e2e/
rtk .venv/bin/python scripts/check_text_hygiene.py CHANGELOG.md artifacts/pending-items.md artifacts/release-checklist.md artifacts/end-to-end-bug-hunt-plan.md
rtk git diff --check
```

Do not run `make ci-precheck` in an environment that might restart shared
`com.cutctx.proxy` on port 8787. If running it, use an isolated dev proxy setup.

## No-Regression Signoff

Before marking the bug hunt complete, confirm:

- [ ] No unrelated dirty files were staged.
- [ ] Every changed source file has a matching focused test or documented
  reason why test coverage is not applicable.
- [ ] Every changed UI file has at least one browser/E2E or screenshot-backed
  verification path.
- [ ] No new skips, xfails, fake data paths, or static success states were
  introduced.
- [ ] Full local Python suite still passes.
- [ ] Rust workspace tests, clippy, and fmt still pass.
- [ ] Dashboard lint, build, and E2E still pass.
- [ ] Text hygiene and `git diff --check` still pass.
- [ ] Release trackers accurately list remaining open items.
- [ ] Shared proxy on port 8787 was not restarted or used for restart-heavy
  iteration.

## Final Report Template

The final bug-hunt report must include:

- Feature inventory with status.
- UI screen inventory with status.
- API route inventory with status.
- Stubs/fake states found and fixed.
- Tests added or updated.
- Commands run and exact results.
- Screenshots or Playwright traces for UI issues.
- Skipped tests grouped by reason.
- Remaining blocked items.
- Final recommendation: `Go`, `Limited Go`, or `No-Go`.

## Release Recommendation Criteria

`Go`:

- Full local Python/Rust/dashboard gates pass.
- Commitlint/history is clean.
- EE packaging/signing is complete if shipping EE.
- Version/changelog release cut is complete.
- No critical/high UI, API, or feature gaps remain.

`Limited Go`:

- OSS/local product scope is verified.
- Remaining issues are explicitly release-owner decisions, not broken product
  behavior.

`No-Go`:

- Any critical/high runtime failure remains.
- Dashboard has broken navigation, stale/fake data, or inaccessible core flows.
- Claimed feature is stubbed or not wired.
- Release gates fail without accepted waiver.
- Docs claim unverified compliance, billing, assurance, or savings behavior.
