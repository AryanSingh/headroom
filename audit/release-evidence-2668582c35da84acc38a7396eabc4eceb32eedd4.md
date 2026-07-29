# Release Evidence — `2668582c35da84acc38a7396eabc4eceb32eedd4`

- **Repository:** `headroom` (worktree `verified-production-remediation`)
- **SHA under certification:** `2668582c35da84acc38a7396eabc4eceb32eedd4`
- **Verification start (UTC):** 2026-07-29T18:51:42Z
- **Verification end (UTC):** 2026-07-29T19:00:55Z
- **Working tree at start:** clean except one expected untracked file, `docs/superpowers/plans/2026-07-29-verified-production-remediation-backlog.md` (verified via `git status --short` before any gate ran; unchanged after all gates ran — no code was modified to produce this evidence).
- **Recent history:** `2668582c` (`fix: honor hosted trial start failure in TrialManager`) sits on top of the Task 1–5 remediation commits (`e2bf38a4`, `da6f41ff`, `52ff4e0d`, `b9035ee9`, `5b87ca9b`, ...), confirmed via `git log --oneline -15`.
- **Local environment:** macOS (darwin 25.2.0, arm64), Python 3.12.12 (`.venv`), Node v22.22.3 / npm 10.9.8, cargo/rustc 1.96.0. `uv run --extra dev` / `uv run --with <tool>` used where a tool was declared in `pyproject.toml` but not preinstalled in the checked-in `.venv`.
- **Evidence logs:** `audit/evidence-2668582c/*.log` (referenced per row below). Note: the repository's `.gitignore` matches `*.log` globally, so these raw logs are **not** part of this commit — they exist only in this local worktree for anyone re-running the same session. The tables below therefore also inline the literal pass/fail signal (exit code and key output line) so this document is self-contained from git history alone.

Commands were sourced directly from `.github/workflows/ci.yml` (`lint`, `security-audit`) and `.github/workflows/product-release-evidence.yml` (`fixture-evidence`), and from `.github/workflows/rust.yml` (`audit`), preferring the exact CI invocation over a weaker substitute. Deviations from the literal CI job are called out explicitly in the Evidence column.

## Verified PASS

| Gate | Command | SHA | Result | Evidence |
|---|---|---|---|---|
| Hosted entitlement fail-closed (Task 1) | `pytest -q tests/test_ee_billing_entitlements.py` | `2668582c` | PASS (part of combined run below) | `audit/evidence-2668582c/focused-remediation-suites.log` |
| Prometheus label cardinality bound (Task 3) | `pytest -q tests/test_prometheus_metrics_cardinality.py` | `2668582c` | PASS (part of combined run below) | `audit/evidence-2668582c/focused-remediation-suites.log` |
| Usage reporter result contract (Task 2) | `pytest -q tests/test_usage_reporter_results.py` | `2668582c` | PASS (part of combined run below) | `audit/evidence-2668582c/focused-remediation-suites.log` |
| Combined focused remediation suites | `pytest -q tests/test_ee_billing_entitlements.py tests/test_prometheus_metrics_cardinality.py tests/test_usage_reporter_results.py` | `2668582c` | PASS — 38 passed, 0 failed, exit 0 | `audit/evidence-2668582c/focused-remediation-suites.log` |
| Dashboard audit (Task 4, deterministic Vite lifecycle) | `pytest -q tests/test_dashboard_audit.py` (per `product-release-evidence.yml` `fixture-evidence` job) | `2668582c` | PASS — 43 passed, 0 failed, exit 0 | `audit/evidence-2668582c/dashboard-audit-pytest.log` |
| Broader regression sweep of every file touched by Tasks 1–3 (billing, trial, telemetry/usage-reporter, prometheus/observability metrics) | `pytest -q tests/test_prometheus_metrics_cardinality.py tests/test_prometheus_stage_timing_concurrency.py tests/test_proxy_cache_ttl_metrics.py tests/test_observability_metrics.py tests/test_backend_streaming_cache_metrics.py tests/test_trial.py tests/test_usage_reporter_results.py tests/test_telemetry.py tests/test_telemetry_context.py tests/test_telemetry_warning.py tests/test_proxy_telemetry_env.py tests/test_ee_billing_entitlements.py cutctx_ee/tests/test_billing_client.py` | `2668582c` | PASS — 198 passed, 0 failed, exit 0 (confirmed twice, second run's real exit code captured directly) | `audit/evidence-2668582c/broader-regression-suite.log` |
| Ruff lint (CI `lint` job, pinned version) | `uvx ruff@0.9.4 check .` | `2668582c` | PASS — "All checks passed!", exit 0 | `audit/evidence-2668582c/ruff-check.log` |
| mypy ratchet (CI `lint` job; `mypy` installed via `uv run --extra dev` since the checked-in `.venv` lacked it) | `uv run --extra dev python scripts/mypy_ratchet.py` | `2668582c` | PASS — "mypy: all current errors are accounted for in baseline (no new errors)", exit 0 | `audit/evidence-2668582c/mypy-ratchet.log` |
| Python compile smoke (CI `lint` job) | `python -m compileall -q cutctx cutctx_ee` | `2668582c` | PASS — no output, exit 0 | `audit/evidence-2668582c/compileall.log` |
| Repo hygiene (CI `lint` job) | `python scripts/check_repo_hygiene.py` | `2668582c` | PASS — exit 0 | `audit/evidence-2668582c/repo-hygiene.log` |
| Secret pattern scan (CI `lint` job) | `python scripts/check_secret_patterns.py` | `2668582c` | PASS — exit 0 | `audit/evidence-2668582c/secret-patterns.log` |
| Dashboard unit tests (CI `fixture-evidence` job) | `npm test` (`dashboard/`) | `2668582c` | PASS — 29/29 Node test-runner cases passed, exit 0 | `audit/evidence-2668582c/dashboard-npm-test.log` |
| Dashboard lint (CI `fixture-evidence` job) | `npm run lint` (`dashboard/`, `eslint . --max-warnings=0`) | `2668582c` | PASS — 0 warnings/errors, exit 0 | `audit/evidence-2668582c/dashboard-npm-lint.log` |
| Dashboard production build (CI `fixture-evidence` job) | `npm run build` (`dashboard/`) | `2668582c` | PASS — Vite build succeeded, all chunks emitted, exit 0 | `audit/evidence-2668582c/dashboard-npm-build.log` |
| `cutctx_ee` billing client suite (modified file) | `pytest -q cutctx_ee/tests/test_billing_client.py` | `2668582c` | PASS — 27 passed, exit 0 | `audit/evidence-2668582c/ee-billing-client-pytest.log` |
| Rust dependency audit (`rust.yml` `audit` job) | `cargo-audit audit` (v0.22.2, installed to `~/.cargo/bin`, not on PATH by default) | `2668582c` | PASS — 0 vulnerabilities; 3 "unmaintained" advisories (`fxhash`, `number_prefix`, `paste`) + 1 yanked-crate warning (`num-bigint`), all warnings not errors, matching the repo's documented "unwaived, warnings-only" policy for this job | `audit/evidence-2668582c/cargo-audit.log` |
| Python dependency audit — **scoped substitute**, see note below | `uv run --with pip-audit pip-audit --strict --local` | `2668582c` | PASS — "No known vulnerabilities found", exit 0 | `audit/evidence-2668582c/pip-audit.log` |

**Note on the pip-audit scope deviation:** CI's `security-audit` job builds the release wheel with `maturin`, installs only the runtime wheel, then freezes and audits that exact runtime dependency set (excluding `cutctx-ai` itself) via `pip-audit --strict -r <frozen-requirements>`. Reproducing that requires a full Rust wheel build. Running `pip-audit --strict -r <frozen requirements>` locally against this worktree's `.venv` also failed for an unrelated, environment-specific reason: pip-audit's requirement-file mode creates an ephemeral virtualenv per dependency and `ensurepip` aborted with `SIGABRT` inside that ephemeral venv (`audit/evidence-2668582c/pip-audit.log` retains the traceback from that first attempt before the fallback was used). As a scoped substitute, `pip-audit --strict --local` was run directly against the installed dev environment (177 packages, `cutctx-ai` excluded from the frozen freeze file that was prepared but not ultimately needed by `--local` mode). This covers the dev dependency set, which is a superset of the runtime set, but is not an exact reproduction of the CI job's isolated runtime-only audit.

## FAIL — do not ship without addressing

| Gate | Command | SHA | Result | Evidence |
|---|---|---|---|---|
| Ruff format check (CI `lint` job) | `uvx ruff@0.9.4 format --check .` | `2668582c` | **FAIL** — exit 1: "Would reformat: `tests/test_ee_billing_entitlements.py`" (1 file would be reformatted, 1510 already formatted) | `audit/evidence-2668582c/ruff-format-check.log` |

`tests/test_ee_billing_entitlements.py` was added in the Task 1 commit (`b9035ee9`) and has not been run through `ruff format`. This is a real, reproducible CI-gate failure at this exact SHA and is reported as FAIL, not silently fixed, so this evidence reflects the SHA as committed.

## SKIPPED / BLOCKED (environment) — not run, not claimed as passing

| Gate | Command (per CI) | Reason not run |
|---|---|---|
| Full core pytest gate with coverage (`ci.yml` `test-gate`) | `pytest tests -k "not slow and not real_llm and not live and not e2e" --cov=cutctx --cov-branch --cov-fail-under=70` | Requires a fresh `maturin build --profile ci` of the Rust extension, a CPU-only Torch install, and an offline HuggingFace model cache identical to CI's `prefetch-model` job — infeasible to reproduce faithfully in this session's time budget. Not run; not claimed as passing. |
| Sharded full test matrix (`ci.yml` `test`, 4 shards) | `pytest tests scripts/tests --splits 4 --group N` | Same wheel/torch/model-cache dependency as above. Not run. |
| SDK TypeScript typecheck/test (`product-release-evidence.yml` `fixture-evidence`) | `npm run typecheck` / `npm test -- --run` (`sdk/typescript/`) | `sdk/typescript/node_modules` is not installed in this worktree and no file under `sdk/` is part of this diff; installing and running was judged out of scope for this SHA's evidence given the time budget. Not run. |
| Dashboard Playwright e2e + multi-viewport visual audit (`product-release-evidence.yml` `fixture-evidence`) | `npx playwright test --project=chromium`; `npx playwright test dashboard-audit.spec.js --project=dashboard-audit-{375,768,1280,1720}` | Not run in this pass; the equivalent Python-side dashboard audit (`tests/test_dashboard_audit.py`, which also drives Playwright) was run and passed (see PASS table). The browser-driven JS Playwright suite itself was deferred for time. Not claimed as passing. |
| Docker-native / init / wrap e2e (`ci.yml` `docker-native-e2e`) | `bash e2e/docker-native-install.sh`, `docker compose ... up`, wrap/init Docker builds | Requires building and running Docker images; not exercised locally in this pass. |
| Windows/macOS native installer wrapper tests (`ci.yml` `windows-native-wrapper`, `macos-native-wrapper`) | `pytest tests/test_install/test_native_installers.py -q` | Cross-OS CI-runner-specific packaging test; this darwin host can run the macOS variant in principle but it was not exercised in this pass — deferred for time, not claimed as passing. |
| Redis orchestration integration (`ci.yml` `redis-orchestration-integration`) | `pytest tests/test_orchestration_redis.py -q` (against a live `redis:7-alpine` service) | No Redis service was started in this session. Not run. |
| `cargo deny check licenses` (`rust.yml` `audit` job) | `cargo deny check licenses` | CI itself marks this step `continue-on-error: true` (non-blocking advisory). `cargo-deny` is not installed locally and was not installed for this pass. Not run. |
| Workflow validation (`ci.yml` `workflow-validation`) | `bash scripts/validate-workflows.sh` (needs `actionlint`, `act`) | Neither tool is installed locally; not installed for this pass. Not run. |
| Authenticated staging release blocker (`product-release-evidence.yml` `staging-release-blocker`) | `scripts/run_remote_hosted_smoke.py`, `scripts/run_staged_gateway_smoke.py`, `scripts/run_staging_dashboard_smoke.py` against real staging secrets | Requires live staging credentials (`CUTCTX_STAGED_*`, `CUTCTX_HOSTED_*`). Per the repository's explicit policy, hosted/staging flows are external gates that must not be fabricated locally. Not run. |

## Intentionally deferred (roadmap, not this SHA's gate)

- Task 7 (hosted operations/alerting), Task 8 (commercial/legal/staging checkout+SSO lifecycle), and Task 9 (migration/scaling readiness) are explicitly out of scope for this evidence file — they require an operations owner, legal approval, and/or live staging access per `docs/superpowers/plans/2026-07-29-verified-production-remediation-backlog.md`.
- Task 10 (lower-risk docs/dependency/dashboard refactors) is explicitly gated on Tasks 1–6 being accepted first and was not attempted here.

## Summary

- **38/38** focused Task 1–3 remediation tests pass.
- **198/198** broader regression tests across every file the Task 1–3 fixes touch pass.
- **43/43** dashboard audit pytest cases (Task 4) pass.
- **29/29** dashboard Node unit tests pass; dashboard lint and production build both pass.
- `ruff check .` (pinned 0.9.4) passes; **`ruff format --check .` FAILS** on one test file — recorded as FAIL above, not remediated as part of this evidence pass.
- mypy ratchet, compileall, repo hygiene, and secret-pattern gates all pass.
- `cargo audit` reports zero vulnerabilities (warnings only, matching repo policy). `pip-audit` reports no known vulnerabilities against the local dev environment (scoped substitute — see note).
- Full CI-matrix jobs that require a from-scratch Rust wheel build, GPU-less Torch + offline HF model cache, Docker, multi-OS runners, a live Redis service, or authenticated staging credentials were not reproduced in this pass; they are listed as SKIPPED/BLOCKED above rather than claimed as passing.
