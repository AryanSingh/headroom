# Release audit remediation status — 2026-08-05

Branch: `audit-fixes-2026-08-03`

## Current decision

All locally actionable unresolved and unverified audit areas have been remediated and re-verified. Independent Terra and Luna reviews found one additional local release blocker: the current branch failed the CI-pinned Ruff lint and format gates. That blocker has now been corrected and re-verified. Live Anthropic provider acceptance remains an external partial item: authentication is valid, but neither the direct nor CutCtx-wrapped bounded canary returned a successful model response.

The original Claude audit is retained as a historical baseline in `AUDIT_INDEPENDENT_2026-08-03.md`; it is not the current branch status.

## Remediation added in the final closeout

- `974623d` migrates desktop credentials to the OS keychain with metadata-only files and one-way legacy migration.
- `482c897` adds real proxy-restart resume coverage for OpenCode, completing the Codex/Claude/OpenCode protocol matrix.
- `23f66f9` fixes non-root Kubernetes startup by setting a writable home in raw and Helm manifests.
- `558d377` clears dashboard build dependency advisories and refreshes packaged assets.
- `eddccb8` fixes VS Code and JetBrains extensions that silently read an obsolete `/stats` schema.
- `eeb12d7` inventories all 123 CLI leaves and fixes experimental intercept help discovery.
- `f3f971d` makes desktop lifecycle failures accessible and adds failure/retry recovery coverage.
- `77cc5b6` preserves typed entitlement-denial details across CLI/API/dashboard surfaces.
- `29dd3ca` makes lazy CLI registration recover correctly in long-lived embedding/test hosts.
- `551e1a3` replaces stale competitive claims with a dated, primary-source review.
- The final dependency closeout refreshes `uv.lock` so it contains the already-committed `graphiti-core` and `httpx2` requirements instead of relying on a stale pre-change resolution.
- The independent-review closeout applies the CI-pinned Ruff formatter to 20 previously unformatted files, fixes seven lint findings, and preserves behavior across the directly affected test slices.

## Verification evidence

- Full Python suite baseline after the audit fixes: 10,329 passed, 458 skipped, 0 failed.
- Final post-fix combined CLI/governance/memory/orchestration sweep: 583 tests collected and the process exited 0. The order-dependent lazy-load defect was first witnessed after 581 passes, then fixed and pinned by a focused cached-module re-registration regression.
- Broader CLI/install/provider slice before the final lazy-load hardening: 480 passed.
- Desktop: 14 frontend tests passed; TypeScript/Vite production build and oxlint passed; Rust desktop crate 54 passed.
- Extensions: VS Code parser tests 2 passed, compile passed, `npm audit` reported zero; JetBrains parser tests passed and `buildPlugin` succeeded.
- Agent replay: 20 passed across Codex, Claude, and OpenCode restart/resume fixtures.
- Deployment: local arm64 image smoke passed; disposable kind rollout, authenticated stats, upgrade, and known-good rollback passed; 27 deployment/operator tests passed.
- Java SDK: 7 tests passed with Java 17 compiling the Java 11 target. Python, Go, and TypeScript SDK verification also passed in their locally runnable matrices.
- Dependency lock: `uv lock --check` and deterministic regeneration passed; Graphiti/docs/release-workflow verification passed 119 tests with one expected skip.
- Independent-review remediation: `uvx ruff@0.9.4 check .` and `uvx ruff@0.9.4 format --check .` pass; 131 directly affected CLI/audit/retention/dashboard/operator/proxy/transform tests pass.
- Final direct full-suite rerun after the independent-review cleanup collected 10,633 tests (with one collection-time skip) and exited 0. The repository's filtered `rtk pytest tests/` shortcut incorrectly reported no collection, so that wrapper result was discarded; the evidence here is from `uv run --no-sync pytest tests/ -q`.
- The CLI inventory discrepancy reported from fresh reviewer worktrees was not reproducible in the primary built environment: all 123 leaves loaded with no `_LOAD_FAILURES`, and both committed inventory tests passed. The reviewer worktrees lacked required installed dependencies/native build state, so their 118-leaf result is retained as environment-sensitive evidence rather than a production regression.

## Remaining external handoffs

1. Rerun the live Claude acceptance canary when the provider session is responsive:

   ```bash
   uv run --python 3.12 --no-sync cutctx wrap claude --no-proxy --no-context-tool --no-mcp --no-serena -- -p 'Reply with exactly CUTCTX_LIVE_OK and nothing else.'
   ```

   `claude auth status` now reports a valid `claude.ai` team session. A direct `claude -p` probe produced no response within a bounded 75-second window, while the wrapped probe reached the local CutCtx gateway but did not complete and surfaced an HTTP 500 gateway error when stopped. This separates authentication from provider/proxy acceptance: login is no longer the blocker, but a successful live completion is still not verified.

2. Terra and Luna independent reviews completed in isolated worktrees. Both verified the lockfile and substantial portions of the remediation, including the built wheel/native extension, desktop credential tests, deployment manifests, packaged dashboard assets, and extension packaging. They independently identified the Ruff gate failure fixed in this closeout. Both also observed a 118-leaf CLI inventory in under-provisioned worktrees; the primary built environment exposes the audited 123 leaves and passes the inventory suite, so release verification must continue to use the documented built environment.

3. Hosted Windows/Linux keychain execution, signed release bundles, marketplace IDE journeys, hosted TypeScript integrations, published multi-architecture images, and managed Kubernetes distributions remain release/distribution canaries. Their local contracts and failure boundaries are covered; they require their respective external hosts.

## Working-tree note

The previously held `uv.lock` was independently reviewed rather than discarded. It is a valid deterministic refresh for requirements already present in committed `pyproject.toml`, and is included only after the focused dependency and release-contract verification passed.
