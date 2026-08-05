# Release Audit Phase 1 — Safety Contracts Implementation Plan

## Goal

Close the three held release-safety changes from Phase 0 without absorbing unrelated dirty work:

1. make retention `dry_run` globally side-effect-free and make its target/result semantics honest;
2. distinguish completed audit-integrity verdicts from verifier failures at the HTTP boundary;
3. preserve the established 300-second total-timeout default until a separately evidenced workload-envelope decision supports a narrower default.

Every production behavior change follows a witnessed RED → minimal GREEN → refactor cycle. Each task is implemented by a fresh Luna lane and reviewed independently by Terra before integration.

## Global constraints

- Branch: `audit-fixes-2026-08-03`.
- Keep the Git index empty between tasks.
- Preserve and do not stage `audit/bug-report.md`, `uv.lock`, and `AUDIT_INDEPENDENT_2026-08-03.md`.
- Use temporary homes, SQLite databases, files, and fakes. Never target the operator's real `~/.cutctx` data.
- Reconfirm imported Python modules resolve to `.py` files under the authoritative root if the environment changes.
- Use pinned `ruff==0.9.4`.
- Do not claim that a characterization/backfill test is a witnessed RED production fix.
- The Phase 0 plan's original dashboard import-regex sample is superseded by commit `a6772cc`, which handles Vite backticks and requires a nonempty fetched lazy-chunk set.

## Task 0 — Preflight and ownership boundary

### Files

- Read only: current Git status, `.venv/lib/python3.12/site-packages/cutctx_ai.pth`, affected modules.
- Record locally: `.slim/deepwork/release-audit-closeout.md`.

### Steps

1. Run `rtk git diff --cached --name-only`; require no output.
2. Record the current unstaged paths and distinguish the three Phase 1 product groups from unrelated preserved work.
3. With `uv run --frozen`, import `cutctx.proxy.models`, `cutctx.proxy.routes.admin`, and `cutctx_ee.retention`; require each resolved path to be a `.py` file under the authoritative root using `Path.is_relative_to`.
4. Confirm `cutctx_ai.pth` points at the authoritative root.

## Task 1 — Retention dry-run, path, and timestamp safety

### Owned files

- `cutctx_ee/retention.py`
- `cutctx/cache/compression_store.py`
- `tests/test_retention.py`
- Optional only if required by the final public contract: narrow retention entries in `docs/content/docs/configuration.mdx`.

`.env.example` is exclusively owned by Task 3 in this phase.

### Contract

- `dry_run=True` counts candidates for audit, CCR, spend, and episodic cleanup while performing no mutation, maintenance operation, unlink, or mutating store call.
- Candidate counts are returned for the invocation, but cumulative `*_deleted` statistics remain unchanged. Stats expose `dry_run` and the resolved audit path.
- Audit path precedence is explicit config > `CUTCTX_RETENTION_AUDIT_DB_PATH` > `CUTCTX_AUDIT_DB_PATH` > documented home default.
- The implicit home default remains supported; resolution is inspectable, not falsely described as protective.
- Audit timestamp handling supports SQLite numeric epochs, strict numeric text, and canonical ISO timestamps. Malformed or unrecognized text is retained rather than lexically deleted.
- Spend DB configuration mismatch is not silently broadened into this commit. Record it as a separate bounded follow-up unless the task's RED evidence proves a minimal compatibility fix is necessary.

### RED tests — add before production edits

Add isolated tests for:

1. explicit audit path winning over both env paths;
2. retention-specific env winning over canonical audit env;
3. canonical audit env and documented home fallback;
4. `from_env()` loading audit path and dry-run;
5. audit dry-run counting old rows without mutation or maintenance;
6. explicit audit DB isolation when canonical env points elsewhere;
7. mixed INTEGER, REAL, strict numeric TEXT, and canonical ISO old/recent timestamps;
8. malformed multi-dot, signed/scientific/whitespace numeric text, NULL, offset ISO, and future values following the documented retain-or-parse policy;
9. spend dry-run counting without DELETE/VACUUM;
10. episodic dry-run counting without unlinking;
11. CCR dry-run never calling mutating cleanup/truncation APIs;
12. aggregate dry-run returning candidate counts without incrementing actual deletion statistics and exposing mode/path.

Run the focused new slice and capture failures. At minimum, the CCR, spend, episodic, and aggregate-stat tests must fail against the current dirty patch before production changes.

### Minimal GREEN

1. Centralize candidate selection so normal and dry-run paths use the same predicate.
2. Add non-mutating preview paths for every backend. For CCR, add a public lock-protected `CompressionStore.preview_cleanup(...)` API and a normal cleanup API that share one candidate-key definition for expiration plus max-entry enforcement.
3. Keep per-run candidate counts separate from cumulative deletion counters.
4. Expose `dry_run` and resolved audit DB path in stats.
5. Replace permissive SQLite text casting with deterministic strict classification. If portable SQL cannot express the policy safely, select candidate IDs and parse timestamps in Python inside a bounded transaction.
6. Correct comments that imply the resolver alone prevents destructive targeting.

### Verification

```bash
rtk proxy uv run --frozen python -m pytest -q tests/test_retention.py
rtk proxy uv run --frozen python -m pytest -q tests/test_retention.py tests/test_audit_chain_verify.py tests/test_proxy_resilience_hardening.py
rtk proxy uvx ruff@0.9.4 check cutctx_ee/retention.py cutctx/cache/compression_store.py tests/test_retention.py
rtk git diff --check
```

### Staging and commit

Stage only the executable allowlist and commit:

```bash
rtk git diff --cached --name-only
rtk git add cutctx_ee/retention.py cutctx/cache/compression_store.py tests/test_retention.py
# Only when the retention contract required a documentation edit:
rtk git add docs/content/docs/configuration.mdx
rtk git diff --cached --check
rtk git diff --cached --name-only
rtk git commit -m "fix(retention): make preview cleanup side-effect free"
```

The staged name list must contain only `cutctx_ee/retention.py`, `cutctx/cache/compression_store.py`, `tests/test_retention.py`, and optional `docs/content/docs/configuration.mdx`.

## Task 2 — Audit verification HTTP verdict/error contract

### Owned files

- `cutctx/proxy/routes/admin.py`
- `tests/test_audit_chain_verify.py`
- generated `artifacts/openapi.json`
- only narrowly necessary audit endpoint docs; packaged dashboard assets are a separate generated-artifact task if docs source changes require them.

### Contract

- Clean completed verification: HTTP 200 with typed `ok=true`, `status="valid"`, `valid=true`.
- Detected tamper: HTTP 200 with typed `ok=false`, `status="tampered"`, `valid=false`, plus stable offending-event fields when available.
- Missing audit logger: HTTP 503.
- Lightweight/hash verifier exception or malformed result: HTTP 500 with a stable generic body; internal details are logged, not exposed.
- Authentication and entitlement behavior remains unchanged.
- OpenAPI documents the typed 200 response and 422/500/503 cases. The separate management `/v1/audit/verify/{tenant_id}` route is not silently claimed to be the same contract.

### RED tests — add before production edits

Add endpoint-level temporary-app tests for:

1. hash-chain verifier exception returning 500 rather than the dirty patch's 200/tampered;
2. malformed lightweight output returning 500;
3. malformed hash-chain output returning 500;
4. clean typed 200 verdict;
5. directly tampered row returning typed negative 200 verdict rather than the committed old 500/detail shape;
6. tenant scoping;
7. unavailable logger 503;
8. auth/entitlement guards;
9. OpenAPI response schema and documented statuses.

Witness the exception/malformed tests fail against the current dirty patch. The tamper test may already pass because it backfills the intended behavior; label it accordingly.

### Minimal GREEN

1. Define a response model for the verdict.
2. Validate lightweight results are mappings with a boolean `ok` and validate hash verifier results against its documented boolean contract.
3. Let verifier exceptions reach a controlled 500 handler/log path; do not synthesize a negative verdict.
4. Preserve stable top-level and nested fields for completed checks.
5. Regenerate OpenAPI in a fresh CI-equivalent core + `dev` dependency environment. Do not generate from the reusable environment when optional `datasets`/`llmlingua` extras are installed.
6. Assert the generated artifact contains no optional `/v1/orchestration` paths before staging, then update only contract-relevant docs.

### Verification

```bash
rtk proxy uv run --frozen python -m pytest -q tests/test_audit_chain_verify.py
rtk proxy uv run --frozen python -m pytest -q tests/test_admin_runtime_helpers.py tests/test_admin_surface_guards.py tests/test_runtime_app_admin_auth.py tests/test_management_api_entitlements.py
rtk proxy uv run --isolated --frozen --group dev python scripts/generate_openapi.py
rtk proxy python -c "import json; from pathlib import Path; paths=json.loads(Path('artifacts/openapi.json').read_text())['paths']; assert not any(p.startswith('/v1/orchestration') for p in paths), sorted(p for p in paths if p.startswith('/v1/orchestration'))"
rtk proxy uv run --frozen python -m pytest -q tests/test_openapi_schema.py tests/test_openapi_drift.py
rtk proxy uv run --frozen python -m pytest -q tests/test_audit*.py tests/test_dashboard_audit.py tests/test_management_api_entitlements.py tests/test_runtime_app_admin_auth.py tests/test_admin_runtime_helpers.py tests/test_openapi_*.py
rtk proxy uvx ruff@0.9.4 check cutctx/proxy/routes/admin.py tests/test_audit_chain_verify.py
rtk git diff --check
```

### Staging and commit

Stage only the endpoint, focused tests, generated OpenAPI, and explicitly required endpoint docs. Verify the executable allowlist and commit:

```bash
rtk git diff --cached --name-only
rtk git add cutctx/proxy/routes/admin.py tests/test_audit_chain_verify.py artifacts/openapi.json
# Only if changed for this endpoint contract:
rtk git add docs/audit-compliance.md docs/control-plane.md
rtk git diff --cached --check
rtk git diff --cached --name-only
rtk git commit -m "fix(audit): separate integrity verdicts from verifier errors"
```

The staged name list must contain only the three required paths plus optional `docs/audit-compliance.md` and `docs/control-plane.md`. Dashboard source/assets are not owned by this task.

## Task 3 — Preserve the supported timeout default and document real semantics

### Owned files

- `.env.example`
- `cutctx/proxy/models.py`
- `tests/test_proxy_resilience_hardening.py`
- `tests/test_proxy_streaming_resilience.py`; do not change streaming production behavior in this task.

### Decision and contract

- Preserve 300 seconds as the established configurable default for both upstream inter-byte read timeout and total non-streaming request budget until measured product evidence supports a narrower workload envelope.
- `CUTCTX_REQUEST_TOTAL_TIMEOUT_SECONDS=0` continues to disable the non-streaming/header budget.
- Documentation must state that the total budget covers the non-streaming retry/backoff exchange and streaming response-header acquisition. The streamed body remains governed by the inter-byte read timeout; do not call the current setting a proven absolute full-stream deadline.
- A future absolute streamed-body deadline is a separate TDD task because its post-first-byte error semantics require a product decision.

### RED tests — add before production edits

1. With timeout env vars absent, assert production `ProxyConfig` uses the approved 300-second read and total defaults. This must fail against the dirty 120-second edit.
2. Assert `.env.example` describes the same defaults and distinguishes read/inter-byte, non-streaming total, and streaming-header/body semantics.
3. Preserve validation coverage for zero, negative, and non-integer total timeout values.
4. Add the named characterization test `test_stream_body_continues_past_total_budget_when_chunks_arrive_before_read_timeout` in `tests/test_proxy_streaming_resilience.py`. Its fake upstream must return headers immediately, emit periodic chunks more frequently than the read timeout, take longer than the configured total budget to finish, and demonstrate the observed post-header behavior. Label this characterization/backfill evidence, not a witnessed RED production fix.
5. Retain tests showing the non-streaming budget spans retries/backoff and streaming header acquisition is bounded.

### Minimal GREEN

1. Restore the total default to 300.
2. Remove unsupported claims about observed frontier-model duration and 120 seconds covering all legitimate workloads.
3. Keep the useful distinction between inter-byte read timeout and request budget.
4. Document the precise streaming limitation and override behavior.

### Verification

```bash
rtk proxy uv run --frozen python -m pytest -q tests/test_proxy_resilience_hardening.py tests/test_proxy_streaming_resilience.py tests/test_openai_codex_ws_timeout.py tests/test_proxy_scalability.py
rtk proxy uv run --frozen python -m pytest -q tests -k "timeout or duration or stream or retry"
rtk proxy uvx ruff@0.9.4 check cutctx/proxy/models.py tests/test_proxy_resilience_hardening.py tests/test_proxy_streaming_resilience.py
rtk git diff --check
```

### Staging and commit

Stage only `.env.example`, `cutctx/proxy/models.py`, and the two owned timeout tests. Verify the executable allowlist and commit:

```bash
rtk git diff --cached --name-only
rtk git add .env.example cutctx/proxy/models.py tests/test_proxy_resilience_hardening.py tests/test_proxy_streaming_resilience.py
rtk git diff --cached --check
rtk git diff --cached --name-only
rtk git commit -m "fix(proxy): preserve supported timeout defaults"
```

The staged name list must contain only `.env.example`, `cutctx/proxy/models.py`, `tests/test_proxy_resilience_hardening.py`, and `tests/test_proxy_streaming_resilience.py`.

## Task 4 — Phase 1 integration verification

1. Confirm the index is empty and unrelated held files remain unstaged.
2. Run the combined retention, audit, timeout, admin, OpenAPI, and proxy-resilience suites.
3. Run pinned Ruff on every changed Python file.
4. Run `rtk git diff --check`.
5. Record exact commits, RED commands/failures, GREEN counts, skips, warnings, and remaining audit rows in the Deepwork ledger and canonical matrix.
6. Send the phase result and review packages to Terra. Do not begin Phase 2 until Terra returns `APPROVED`.

## Out of scope for these three commits but retained in the audit backlog

- spend DB env-name compatibility (`CUTCTX_SPEND_LEDGER_DB` vs `CUTCTX_SPEND_DB_URL`);
- an absolute deadline for the entire streamed response body and post-first-byte client semantics;
- `/v1/audit/verify/{tenant_id}` management-plane parity;
- unrelated `audit/bug-report.md`, `uv.lock`, and publication decision for `AUDIT_INDEPENDENT_2026-08-03.md`.
