# Release audit remediation status — 2026-08-05

Branch: `audit-fixes-2026-08-03`

## Current decision

All locally actionable unresolved and unverified audit areas have been remediated and re-verified. The sole remaining partial item is live Anthropic provider acceptance: the installed Claude Code session is expired and must be re-authenticated by the operator before the final live canary can pass.

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

## Remaining external handoffs

1. Run `claude login` interactively, then rerun:

   ```bash
   uv run --python 3.12 --no-sync cutctx wrap claude --no-proxy --no-context-tool --no-mcp --no-serena -- -p 'Reply with exactly CUTCTX_LIVE_OK and nothing else.'
   ```

   Current evidence is a fast, explicit exit 1 in 7.35 seconds: `OAuth session expired and could not be refreshed`. This verifies the original infinite-retry UX defect is fixed, but not provider acceptance.

2. Terra/Luna independent review could not be completed because the collaboration service returns `unsupported call` and the app thread bridge hangs. Existing user-visible task IDs were retained, but no oracle response was received; do not represent this work as independently agent-reviewed.

3. Hosted Windows/Linux keychain execution, signed release bundles, marketplace IDE journeys, hosted TypeScript integrations, published multi-architecture images, and managed Kubernetes distributions remain release/distribution canaries. Their local contracts and failure boundaries are covered; they require their respective external hosts.

## Working-tree note

The previously held `uv.lock` was independently reviewed rather than discarded. It is a valid deterministic refresh for requirements already present in committed `pyproject.toml`, and is included only after the focused dependency and release-contract verification passed.
