# Release Audit Phase 0 Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit the verified portions of Claude's audit working tree, preserve changes that need more work, and establish a repeatable source-loaded baseline for the full remediation program.

**Architecture:** Phase 0 separates generated artifacts, regression tests, production behavior changes, and local resolver churn. It commits only change groups with direct build or test evidence. It leaves the timeout, audit endpoint, retention, lockfile, and security report changes in the working tree for dedicated Phase 1 decisions.

**Tech Stack:** Git, Python 3.12, pytest, Ruff 0.9.4, Node.js test runner, Vite 8, React 19.

## Global Constraints

- Preserve all pre-existing uncommitted work and stage files by explicit path.
- Prefix shell commands with `rtk` as required by `AGENTS.md`.
- Use non-interactive Git commands with `GIT_TERMINAL_PROMPT=0`, `GIT_EDITOR=true`, and `PAGER=cat`.
- Do not stage `uv.lock`, `AUDIT_INDEPENDENT_2026-08-03.md`, `.env.example`, `cutctx/proxy/models.py`, `cutctx/proxy/routes/admin.py`, or `cutctx_ee/retention.py` in Phase 0.
- The scheduler records command output and commit IDs in `.slim/deepwork/release-audit-closeout.md`.
- A Terra oracle must approve this plan before execution.
- Every commit task starts with an empty Git index. If `rtk git diff --cached --name-only` prints a path, stop and reconcile ownership.
- Before each commit, compare the staged path list against the task's exact allowlist. Whitespace checks alone do not establish staging scope.

---

## File Structure

- `tests/test_mcp_registry/test_install.py`: pins the default proxy URL in generated MCP registration specs.
- `cutctx/dashboard/index.html`: references the packaged dashboard's generated entry chunks.
- `cutctx/dashboard/assets/*`: generated Vite chunks shipped in the Python package.
- `audit/code-review-report.md`: records the review decision for held and committable changes.
- `.slim/deepwork/release-audit-closeout.md`: local execution evidence and agent ownership ledger.

### Task 0: Establish the canonical source-loaded audit baseline

**Files:**
- Modify locally only: `.slim/deepwork/release-audit-closeout.md`

**Interfaces:**
- Consumes: `AUDIT_INDEPENDENT_2026-08-03.md`, `docs/handoff-2026-07-28.md`, commits `4a37ad9f..88093e7a`, current working-tree changes, and preserved audit evidence.
- Produces: the Phase 0 issue matrix, fixture plan, blocker-to-lane map, import-resolution proof, and the identified or explicitly unresolved “18 of 19” item.

- [ ] **Step 1: Prove Python imports resolve from this worktree**

Run:

```bash
rtk proxy uv run --frozen python -c 'import pathlib, cutctx, cutctx_ee, cutctx_ee.memory_service.api, cutctx_ee.retention; cwd=pathlib.Path.cwd().resolve(); roots=[pathlib.Path(cutctx.__file__).resolve(), pathlib.Path(cutctx_ee.__file__).resolve(), pathlib.Path(cutctx_ee.memory_service.api.__file__).resolve(), pathlib.Path(cutctx_ee.retention.__file__).resolve()]; print("\n".join(str(path) for path in roots)); assert all(path.is_relative_to(cwd) for path in roots); assert all(path.suffix == ".py" for path in roots)'
```

Expected: every printed path is under the current worktree and no inspected enterprise module resolves to `.so`.

- [ ] **Step 2: Inspect `cutctx_ai.pth` overlays**

Run:

```bash
rtk proxy uv run --frozen python -c 'import pathlib, site; roots=[pathlib.Path(path) for path in site.getsitepackages()+[site.getusersitepackages()]]; matches=[path for root in roots for path in root.glob("cutctx_ai.pth")]; print("\n".join(f"{path}: {path.read_text().strip()}" for path in matches) or "no cutctx_ai.pth"); cwd=pathlib.Path.cwd().resolve(); assert all(not path.read_text().strip() or pathlib.Path(path.read_text().strip()).resolve() == cwd for path in matches)'
```

Expected: no overlay, or an overlay that resolves to this worktree. A different worktree is a blocker, not a warning.

- [ ] **Step 3: Record the fixture and environment isolation plan**

Add a Phase 0 section to `.slim/deepwork/release-audit-closeout.md` that records:

- temporary homes for CLI, registrar, desktop, and agent configuration tests;
- temporary SQLite databases for audit, spend, memory, and replay tests;
- local capture servers for provider and firewall assertions;
- disposable containers for deployment checks;
- which live canaries remain blocked on credentials or external services.

- [ ] **Step 4: Build the canonical issue matrix**

Add one row for each C1-C7, H1-H19, Medium/Low item, section 8 area, and material section 9 defect. Every row must contain:

```text
ID | claim | current commit/code path | decisive command or missing evidence | status | blocker | bounded owner/phase
```

Use only these closure states: `Verified`, `Fixed`, `Unsupported by design`, `Blocked`, or `Unresolved`. Record skips as missing or limited evidence. Mark the inferred “18 of 19” item as inference unless repository evidence identifies it directly.

- [ ] **Step 5: Map blockers to bounded lanes**

Assign each `Unresolved` or `Blocked` row to one phase and one non-overlapping file or verification owner. Record external prerequisites without converting them to implementation work.

- [ ] **Step 6: Ask the Terra oracle to review the baseline**

Provide the source paths, overlay result, fixture plan, matrix, and lane map. Expected: `APPROVED` or actionable changes before Task 1.

### Task 1: Commit the MCP registry regression correction

**Files:**
- Modify: `tests/test_mcp_registry/test_install.py`
- Modify: `tests/test_mcp_registry/test_codex_registrar.py`

**Interfaces:**
- Consumes: `cutctx.mcp_registry.install.build_cutctx_spec(proxy_url: str = DEFAULT_PROXY_URL) -> ServerSpec` and registrar read/write boundaries.
- Produces: backfilled regression coverage for the in-memory spec plus boundary evidence that a default-port re-registration preserves the default `CUTCTX_PROXY_URL` in a temporary Codex configuration.

- [ ] **Step 1: Require an empty Git index**

Run:

```bash
rtk git diff --cached --name-only
```

Expected: no output. If paths are present, stop and reconcile ownership.

- [ ] **Step 2: Add the registrar-boundary regression test**

Modify `tests/test_mcp_registry/test_codex_registrar.py` to import `DEFAULT_PROXY_URL` and `build_cutctx_spec`, then add:

```python
def test_force_reregister_default_preserves_proxy_env(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    reg.register_server(
        build_cutctx_spec("http://127.0.0.1:9999"),
    )

    result = reg.register_server(build_cutctx_spec(), force=True)

    assert result.status == RegisterStatus.REGISTERED
    parsed = tomllib.loads(_config_path(tmp_path).read_text())
    assert parsed["mcp_servers"]["cutctx"]["env"] == {
        "CUTCTX_PROXY_URL": DEFAULT_PROXY_URL,
    }
```

This test validates the reported write, rewrite, and parse lifecycle. It is backfilled verification for production behavior committed before this plan; do not label it a witnessed RED fix.

- [ ] **Step 3: Inspect the isolated diff**

Run:

```bash
rtk git diff -- tests/test_mcp_registry/test_install.py tests/test_mcp_registry/test_codex_registrar.py
```

Expected: `test_install.py` corrections plus the Codex registrar-boundary test; no production file appears.

- [ ] **Step 4: Run the complete MCP registry suite**

Run:

```bash
rtk proxy uv run --frozen python -m pytest -q tests/test_mcp_registry
```

Expected: no failures. Record the exact pass and skip counts.

- [ ] **Step 5: Run the pinned linter**

Run:

```bash
rtk proxy uvx ruff@0.9.4 check tests/test_mcp_registry/test_install.py tests/test_mcp_registry/test_codex_registrar.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Stage only the regression files**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git add tests/test_mcp_registry/test_install.py tests/test_mcp_registry/test_codex_registrar.py
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git diff --cached --check
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git diff --cached --name-only
```

Expected path allowlist, exactly:

```text
tests/test_mcp_registry/test_codex_registrar.py
tests/test_mcp_registry/test_install.py
```

- [ ] **Step 7: Commit**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git commit -m "test(mcp): preserve default proxy binding"
```

Expected: two-test-file commit.

### Task 2: Commit the packaged dashboard build

**Files:**
- Modify: `cutctx/dashboard/index.html`
- Delete: old hashed files under `cutctx/dashboard/assets/`
- Create: new hashed files under `cutctx/dashboard/assets/`
- Modify: `tests/test_proxy_dashboard_html_auth_bypass.py`

**Interfaces:**
- Consumes: Vite build output from `dashboard/dist/`.
- Produces: package assets with source-build equality and an HTTP runtime test that follows the packaged entry and lazy JavaScript chunks.

- [ ] **Step 1: Require an empty Git index**

Run:

```bash
rtk git diff --cached --name-only
```

Expected: no output. If paths are present, stop and reconcile ownership.

- [ ] **Step 2: Add the packaged-runtime asset traversal test**

Add these imports to `tests/test_proxy_dashboard_html_auth_bypass.py`:

```python
import re
from collections import deque
```

Add this test:

```python
def test_dashboard_runtime_serves_entry_and_imported_chunks(client):
    html_response = client.get("/dashboard")
    assert html_response.status_code == 200

    asset_urls = set(
        re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', html_response.text)
    )
    assert asset_urls

    pending = deque(sorted(url for url in asset_urls if url.endswith(".js")))
    visited: set[str] = set()
    while pending:
        asset_url = pending.popleft()
        if asset_url in visited:
            continue
        visited.add(asset_url)
        response = client.get(asset_url)
        assert response.status_code == 200, asset_url
        for chunk in re.findall(r'(?:from|import\()\s*["\']\./([^"\']+\.js)', response.text):
            pending.append(f"/assets/{chunk}")

    for asset_url in sorted(asset_urls - visited):
        response = client.get(asset_url)
        assert response.status_code == 200, asset_url
```

This test runs against the Python proxy's package-serving boundary and follows JavaScript imports without a live provider.

- [ ] **Step 3: Run dashboard unit and bundle tests**

Run:

```bash
CI=true rtk npm test
```

Working directory: `dashboard/`.

Expected: `31` tests pass and the production bundle budget test passes.

- [ ] **Step 4: Build the dashboard**

Run:

```bash
CI=true rtk npm run build
```

Working directory: `dashboard/`.

Expected: Vite completes and emits `index-hSP-yi6y.js` plus `index-C-C-76c9.css`.

- [ ] **Step 5: Compare generated and packaged web files**

Run:

```bash
rtk proxy diff -qr dashboard/dist/assets cutctx/dashboard/assets
rtk proxy diff -q dashboard/dist/index.html cutctx/dashboard/index.html
```

Expected: both commands produce no differences after the Vite build. Python-only files live outside `cutctx/dashboard/assets` and do not affect this comparison.

- [ ] **Step 6: Run packaged dashboard tests**

Run:

```bash
rtk proxy uv run --frozen python -m pytest -q tests/test_dashboard_embedded_build.py tests/test_dashboard_asset_sync.py tests/test_dashboard_regression.py tests/test_proxy_dashboard_html_auth_bypass.py
```

Expected: no failures; the HTTP runtime test fetches the entry assets and each imported JavaScript chunk.

- [ ] **Step 7: Stage only the packaged dashboard and runtime test**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git add -A cutctx/dashboard/index.html cutctx/dashboard/assets tests/test_proxy_dashboard_html_auth_bypass.py
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git diff --cached --check
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git diff --cached --name-only
```

Expected: only `cutctx/dashboard/index.html`, paths under `cutctx/dashboard/assets/`, and `tests/test_proxy_dashboard_html_auth_bypass.py`.

- [ ] **Step 8: Commit**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git commit -m "build(dashboard): refresh packaged audit assets"
```

Expected: one generated-artifact and package-runtime regression commit.

### Task 3: Validate the committed working-tree review record

**Files:**
- Read: `audit/code-review-report.md`

**Interfaces:**
- Consumes: focused pytest, Ruff, dashboard test/build, package comparison, and Git diff evidence.
- Produces: confirmation that commit `30fc32d` records each held change and that the canonical matrix carries the same dispositions.

- [ ] **Step 1: Verify the report contains each held file**

Run:

```bash
rtk grep -n '\.env.example\|retention.py\|routes/admin.py\|proxy/models.py\|uv.lock\|AUDIT_INDEPENDENT' audit/code-review-report.md
```

Expected: the report names every held change group and explains why it remains uncommitted.

- [ ] **Step 2: Confirm the report is committed and clean**

Run:

```bash
rtk git log -1 --oneline -- audit/code-review-report.md
rtk git diff -- audit/code-review-report.md
```

Expected: the latest commit is `30fc32d` or a later deliberate report update, and the working-tree diff is empty.

- [ ] **Step 3: Reconcile the report with the canonical matrix**

Confirm that `.env.example`, `cutctx/proxy/models.py`, `cutctx/proxy/routes/admin.py`, `cutctx_ee/retention.py`, `uv.lock`, and `AUDIT_INDEPENDENT_2026-08-03.md` each have a canonical-matrix row with the review report's hold reason and required Phase 1 decision or evidence path.

### Task 4: Establish the Phase 0 verification baseline

**Files:**
- Modify locally only: `.slim/deepwork/release-audit-closeout.md`

**Interfaces:**
- Consumes: committed audit remediations and the remaining working-tree changes.
- Produces: focused baseline evidence for the Phase 1 issue matrix.

- [ ] **Step 1: Run the committed remediation regression set**

Run:

```bash
rtk proxy uv run --frozen python -m pytest -q tests/test_ccr_markers.py tests/test_lossy_route_disclosure.py tests/test_memory_tenant_isolation.py tests/test_proxy_resilience_hardening.py tests/test_entitlement_bypass_regression.py tests/test_firewall_inline_enforcement.py tests/test_savings_accounting_c7.py tests/test_credential_redaction.py tests/test_retention.py tests/test_audit_chain_verify.py tests/test_cli_exit_codes.py tests/test_audit_residual_fixes.py tests/test_mcp_registry/test_install.py
```

Expected: no failures. Record passes and skips without translating skips into passes.

- [ ] **Step 2: Run affected Python static checks**

Run:

```bash
rtk proxy uvx ruff@0.9.4 check cutctx/proxy/models.py cutctx/proxy/routes/admin.py cutctx_ee/retention.py tests/test_mcp_registry/test_install.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Confirm held files remain unstaged**

Run:

```bash
rtk git status --short
```

Expected: `.env.example`, `cutctx/proxy/models.py`, `cutctx/proxy/routes/admin.py`, `cutctx_ee/retention.py`, `uv.lock`, and `AUDIT_INDEPENDENT_2026-08-03.md` remain unstaged.

- [ ] **Step 4: Record results in the Deepwork ledger**

Append the exact commit IDs, test counts, skip counts, held paths, and unresolved review findings to `.slim/deepwork/release-audit-closeout.md`.

### Task 5: Phase result review

**Files:**
- Modify locally only: `.slim/deepwork/release-audit-closeout.md`

**Interfaces:**
- Consumes: Phase 0 commits and validation evidence.
- Produces: oracle decision and approved entry into Phase 1.

- [ ] **Step 1: Send the phase result to the Terra oracle**

Provide the oracle with:

- this plan;
- `audit/code-review-report.md`;
- the Phase 0 commit IDs;
- focused test and build output;
- the current unstaged-path list.

Expected: approval or actionable findings.

- [ ] **Step 2: Address review findings**

For documentation or staging errors, correct the bounded issue and repeat the affected validation. Production-code findings move to a Phase 1 TDD task and remain uncommitted.

- [ ] **Step 3: Update the Deepwork ledger**

Record the oracle decision and the accepted Phase 1 entry conditions.
