# Code Review Report: Claude Audit Working Tree

**Date:** 2026-08-04  
**Branch:** `audit-fixes-2026-08-03`  
**Scope:** Uncommitted files present after Claude's product release audit session

## Summary

The working tree contains several independent changes. The MCP registry test corrections are useful backfilled coverage but need a registrar write/rewrite/read-back test before they verify the reported boundary failure. The packaged dashboard assets match a local build but need a package-server runtime traversal test before commit. The retention, audit-verification response, and timeout-default changes need more evidence or corrective work. `uv.lock` contains a broad local resolver rewrite and should stay out of these commits.

Focused verification completed:

- Python: 73 passed in `test_proxy_resilience_hardening.py`, `test_audit_chain_verify.py`, `test_retention.py`, and `test_mcp_registry/test_install.py`.
- Dashboard: 31 tests passed; Vite production build completed.
- Packaged dashboard: generated `dashboard/dist` files match the files under `cutctx/dashboard`, excluding Python package-only files.
- Ruff 0.9.4: affected Python files passed.
- Git whitespace check: passed.

## Findings

### [P1] Retention dry-run claims global safety but only protects the audit database

**Files:** `cutctx_ee/retention.py`, `tests/test_retention.py`

`RetentionConfig.dry_run` says that every cleanup task counts candidates and removes nothing. `run_cleanup()` still calls the CCR, spend-ledger, and episodic cleanup implementations without a dry-run guard. Enabling `CUTCTX_RETENTION_DRY_RUN` can therefore delete CCR entries, spend events, and episodic files while the operator expects a preview.

The current tests do not cover `dry_run`, `audit_db_path`, numeric epochs stored as text, or environment precedence. The change should not be committed until failing tests establish those contracts and the implementation protects each enabled backend.

### [P1] A bare retention manager still targets the operator's default audit database

**File:** `cutctx_ee/retention.py`

`resolve_audit_db_path()` makes the selected path inspectable, but `RetentionManager()` still falls back to `~/.cutctx/audit.db` and `run_cleanup()` executes against it. The new comments describe protection from silently targeting the operator database, but the runtime does not require an explicit path, preview, or acknowledgement.

The remediation plan must choose and test one contract: require an explicit path for destructive audit cleanup, default retention to dry-run when the path is implicit, or retain the fallback with a clear operator-facing warning and status field.

### [P1] Audit verification changes the monitoring contract without endpoint tests

**File:** `cutctx/proxy/routes/admin.py`

The uncommitted route returns HTTP 200 with `ok: false` for a detected tamper. The committed behavior used an HTTP failure for a broken chain. Either contract can work, but monitoring clients may rely on the status code. Existing tests exercise `AuditLogger.verify_chain()` and do not call `GET /audit/verify` for clean, tampered, unavailable, and verifier-error cases.

Add endpoint-level tests and document the response contract before committing the change. Update the OpenAPI artifact if the public response shape changes.

### [P2] The 120-second request deadline lacks evidence for changing the default

**Files:** `.env.example`, `cutctx/proxy/models.py`

The total deadline feature and validation already have regression coverage. The uncommitted change lowers the default from 300 seconds to 120 seconds, but no test pins the new default and the comments cite an observed completion-time bound without preserved evidence. This may terminate supported batch or agentic requests.

Keep the configuration knob. Commit the default change only after a product decision defines the supported request-duration envelope and a test pins it.

### [P2] MCP registry test correction is valid backfilled unit coverage

**File:** `tests/test_mcp_registry/test_install.py`

The production implementation already emits `CUTCTX_PROXY_URL` for the default URL. The updated tests match the in-memory `ServerSpec` behavior. All twelve focused tests pass, but they do not execute a registrar write, default-port rewrite, and parsed read-back. Add that boundary test before classifying the historical registrar failure as verified. The existing assertions cannot provide a witnessed RED result for production code committed before this review.

### [P2] Packaged dashboard assets match the current source build but need runtime provenance

**Files:** `cutctx/dashboard/index.html`, `cutctx/dashboard/assets/*`

The new hashed assets match a fresh Vite build from `dashboard/`. The package index references the generated JavaScript and CSS entry chunks. Dashboard tests and bundle-size checks pass. Before commit, run an isolated HTTP test against the Python package server that fetches the packaged index, entry assets, and each imported JavaScript chunk. Commit the runtime test, index, asset deletions, and asset additions as one generated-artifact change.

### [P3] `uv.lock` is unrelated resolver churn

**File:** `uv.lock`

The diff rewrites more than one thousand lines of environment markers and dependencies. Repository instructions describe this lockfile as locally regenerated and not committed. It does not belong in any audit-remediation commit without a dedicated dependency update and matrix validation.

### [P3] Independent audit report needs a publication decision

**File:** `AUDIT_INDEPENDENT_2026-08-03.md`

The report is useful release evidence but contains detailed security findings, local paths, upstream request identifiers, and credential-shaped examples. Review and scrub it before deciding whether the public repository should track it. Keep it uncommitted during implementation planning.

## Commit Recommendation

Create two commits after the Deepwork oracle accepts the added boundary evidence:

1. MCP registry backfilled unit tests plus registrar write/rewrite/read-back coverage.
2. Packaged dashboard build artifacts plus package-server runtime traversal coverage.

Hold the timeout, audit endpoint, retention, lockfile, and independent audit report for separate TDD or publication decisions.
