# Release Audit - 2026-07-04

## Summary

Recommendation: **Limited Go for OSS/local release candidate**.

The verified code/runtime gates are green after the release-readiness pass.
Final commercial release still needs release-owner work for EE packaging/signing,
versioning, commit-history policy, and product-owner approval of external claims.

## Work Completed In This Pass

- Removed a dead duplicate `_create_app_legacy` block from
  `cutctx/proxy/server.py`. It was not referenced by runtime callers and was
  carrying stale/broken route and middleware definitions that made CI-pinned
  Ruff report 190 `F821` undefined-name errors.
- Restored live request-id and firewall middleware hooks in the real
  `create_app()` path:
  - `_request_id_middleware`
  - `_firewall_scan_middleware`
  - `X-Request-ID` propagation
  - `request.state.cutctx_request_id`
- Fixed the remaining correctness-class Ruff findings in:
  - `cutctx/cli/evals.py`
  - `cutctx/graph/watcher.py`
  - `cutctx/mcp_server.py`
  - `cutctx/proxy/handlers/anthropic.py`
  - `cutctx/graph/graphify.py`
  - `cutctx/cli/stack_graph.py`
  - `cutctx/cli/bench.py`
  - `cutctx/transforms/drain3_compressor.py`
- Added documented Ruff per-file ignore policy for test fixtures, benchmark
  fixtures, scratch scripts, and re-export modules where strict runtime-style
  linting is inappropriate.
- Ran `ruff format .` with CI-pinned Ruff. This reformatted 322 files and made
  the CI format gate green.

## Verified Gates

- `uvx --from ruff==0.9.4 ruff check .`
  - Result: passed.
- `uvx --from ruff==0.9.4 ruff format --check .`
  - Result: passed, `1208 files already formatted`.
- `python -m compileall -q cutctx`
  - Result: passed.
- Focused regression set:
  - Command:
    `python -m pytest tests/test_proxy_healthchecks.py tests/test_context_policy_proxy_integration.py tests/test_dashboard_filter.py tests/test_savings_tracker_litellm_resilience.py tests/test_graphify_index.py tests/test_cli_capabilities.py tests/test_openai_responses_t3_replay_regression.py`
  - Result: `61 passed, 2 warnings`.
- Failed-test rerun:
  - Command:
    `python -m pytest tests/test_pipeline_integration.py::TestRequestIdMiddleware tests/test_pipeline_integration.py::TestFeatureFlagWiring::test_firewall_middleware_present -q`
  - Result: `4 passed`.
- Full Python regression:
  - Command: `python -m pytest tests scripts/tests`
  - Result: `7960 passed, 258 skipped, 22 warnings in 304.95s`.
- Rust workspace tests:
  - Command: `cargo test --workspace --quiet`
  - Result: exited `0`.
- Rust clippy:
  - Command: `cargo clippy --workspace --quiet -- -D warnings`
  - Result: exited `0`.
- Dashboard lint:
  - Command: `npm run lint` in `dashboard/`
  - Result: passed.
- Dashboard production build:
  - Command: `npm run build` in `dashboard/`
  - Result: passed.
- Dashboard E2E:
  - Command: `npx playwright test e2e` in `dashboard/`
  - Result: passed.
- Whitespace check:
  - Command: `git diff --check`
  - Result: passed.

## Skipped Tests

The 258 skipped Python tests remain expected environment-gated skips:

- Missing live-provider credentials.
- Optional local dependencies and provider runtimes.
- Explicit live proxy smoke tests.
- EE source-inspection paths when Cython binaries are loaded.

## Remaining Non-Code Release Items

- Commitlint/history cleanup requires explicit approval if the release process
  requires conventional commit history.
- EE release packaging/signing/provenance remains a release-owner task.
- Version/changelog release cut remains open.
- Product-owner approval is still required for external campaign launch and
  public commercial claims.
- Branch cleanup remains open until PR/release owner confirms merged feature
  branches can be deleted.

## Final Recommendation

**Limited Go** for an OSS/local release candidate after review of the large
formatting diff. **No-Go** for final commercial/enterprise release until the
non-code release-owner items above are complete.
