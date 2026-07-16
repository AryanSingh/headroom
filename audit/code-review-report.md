# Fresh Main Integration Code Review — 2026-07-16

## Scope

Fresh review of the combined `main` integration at `20687eb3`, including the production/commercial audit remediation commit `c3f025c2`, the capability-routing safeguard commits `a24b35bf` and `8426019b`, and all source branches already contained by that history. The previous contents of this report were not used as evidence.

## Verdict

**Approved for merge and push.** No Critical or High correctness, security, compatibility, or release issue was found in the combined committed source history.

## Review findings

### Blocking findings

None after remediation and verification.

### Resolved during integration

1. `cutctx/proxy/handlers/openai/responses.py` conflicted between remote-compaction passthrough and capability-safe routing. The resolution preserves the remote-compaction bypass while passing inferred capabilities to normal routing.
2. `cutctx/proxy/handlers/anthropic.py` contained an unsorted merged import block. It was reformatted and re-linted.
3. The VS Code extension archive omitted its license. The Apache 2.0 license is now present in the VSIX.
4. Two audit markdown files contained trailing blank-line defects. They were normalized before commit.

### Reviewed but intentionally not merged

| State | Decision | Rationale |
|---|---|---|
| `origin/gh-pages` | Keep separate | Deployment artifact history has no merge base with source `main`; merging it would corrupt source history. |
| Uncommitted `codex/capability-routing-overhaul` worktree draft | Preserve, do not merge | Contains unverified future model identifiers and deletes `cutctx_ee/watermark.py`; it is not committed branch history and is not release-safe. |
| Four worktree-only `cutctx_ee/watermark.py` deletions | Preserve, do not merge | Would remove enterprise leak-traceability security functionality. |
| Two detached red-test drafts | Preserve, do not merge | Superseded/duplicated by tests already committed on `main`; neither worktree has a branch or production implementation. |

## Code-quality assessment

- Error handling: new routing and security paths fail closed and retain deterministic error classification.
- API compatibility: provider request bodies and compatibility routes retain existing defaults; capability checks only abstain from unsafe downgrades.
- Performance: wrapped-session hot paths preserve the audited 4096-byte ML tool-output inference budget and remote-compaction passthrough.
- Security: client auth, WebSocket origins, webhook SSRF, egress allowlisting, installer integrity, and release publication controls have regression coverage.
- Maintainability: hierarchical codemaps cover 820 production files; merged routing behavior has focused documentation and tests.
- Type safety: the critical changed security/performance/pricing/installer subset is mypy-clean. Repository-wide annotation debt remains a documented Medium risk.

## Fresh verification evidence

- Python: 8,649 passed, 454 skipped in 482.12 seconds.
- Rust: 1,404 passed, 3 ignored across 51 suites.
- Routing/integration focused suite after conflict resolution: 263 passed.
- Release/installer focused suite: 64 passed.
- Dashboard: 7 unit tests passed; ESLint and production build passed.
- OpenCode plugin: 9 tests, typecheck, build, and high-severity npm audit passed.
- VS Code extension: compile, VSIX packaging, license inclusion, and high-severity npm audit passed.
- Python Ruff and secret-pattern scan: clean.
- Wheel and sdist: built successfully for 0.31.0.
- Diff whitespace check: clean.

## Residual non-blocking risks

- Repository-wide mypy debt remains substantial and should be reduced with a ratcheted baseline.
- Dashboard JavaScript remains a 500.31 kB minified chunk (143.35 kB gzip); route-level code splitting is recommended.
- PyO3 emits deprecation warnings during release builds.
- Credentialed external-provider staging remains a release-operation gate rather than a locally verifiable code gate.

## Final recommendation

Push the reviewed `main` history. Keep `gh-pages` and the unsafe/uncommitted worktree drafts separate. Do not delete those worktrees without explicit confirmation from their owner.
