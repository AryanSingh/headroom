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

---

## File Structure

- `tests/test_mcp_registry/test_install.py`: pins the default proxy URL in generated MCP registration specs.
- `cutctx/dashboard/index.html`: references the packaged dashboard's generated entry chunks.
- `cutctx/dashboard/assets/*`: generated Vite chunks shipped in the Python package.
- `audit/code-review-report.md`: records the review decision for held and committable changes.
- `.slim/deepwork/release-audit-closeout.md`: local execution evidence and agent ownership ledger.

### Task 1: Commit the MCP registry regression correction

**Files:**
- Modify: `tests/test_mcp_registry/test_install.py`

**Interfaces:**
- Consumes: `cutctx.mcp_registry.install.build_cutctx_spec(proxy_url: str = DEFAULT_PROXY_URL) -> MCPServerSpec`
- Produces: regression coverage that requires `CUTCTX_PROXY_URL` for default and custom non-empty URLs while preserving the empty-string opt-out.

- [ ] **Step 1: Inspect the isolated diff**

Run:

```bash
rtk git diff -- tests/test_mcp_registry/test_install.py
```

Expected: three test changes only; no production file appears.

- [ ] **Step 2: Run the focused tests**

Run:

```bash
rtk proxy uv run --frozen python -m pytest -q tests/test_mcp_registry/test_install.py
```

Expected: `12 passed`.

- [ ] **Step 3: Run the pinned linter**

Run:

```bash
rtk proxy uvx ruff@0.9.4 check tests/test_mcp_registry/test_install.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Stage only the regression file**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git add tests/test_mcp_registry/test_install.py
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git diff --cached --check
```

Expected: no whitespace errors and no other staged path.

- [ ] **Step 5: Commit**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git commit -m "test(mcp): preserve default proxy binding"
```

Expected: one-file commit.

### Task 2: Commit the packaged dashboard build

**Files:**
- Modify: `cutctx/dashboard/index.html`
- Delete: old hashed files under `cutctx/dashboard/assets/`
- Create: new hashed files under `cutctx/dashboard/assets/`

**Interfaces:**
- Consumes: Vite build output from `dashboard/dist/`.
- Produces: package assets loaded by the Python dashboard server and browser fixtures.

- [ ] **Step 1: Run dashboard unit and bundle tests**

Run:

```bash
CI=true rtk npm test
```

Working directory: `dashboard/`.

Expected: `31` tests pass and the production bundle budget test passes.

- [ ] **Step 2: Build the dashboard**

Run:

```bash
CI=true rtk npm run build
```

Working directory: `dashboard/`.

Expected: Vite completes and emits `index-hSP-yi6y.js` plus `index-C-C-76c9.css`.

- [ ] **Step 3: Compare generated and packaged web files**

Run:

```bash
rtk proxy diff -qr dashboard/dist/assets cutctx/dashboard/assets
rtk proxy diff -q dashboard/dist/index.html cutctx/dashboard/index.html
```

Expected: both commands produce no differences.

- [ ] **Step 4: Verify package asset references**

Run:

```bash
rtk grep -n 'index-hSP-yi6y.js\|index-C-C-76c9.css' cutctx/dashboard/index.html
```

Expected: one JavaScript reference and one CSS reference.

- [ ] **Step 5: Stage only the packaged dashboard**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git add -A cutctx/dashboard/index.html cutctx/dashboard/assets
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git diff --cached --check
```

Expected: the staged diff contains the package index and hashed asset replacements only.

- [ ] **Step 6: Commit**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git commit -m "build(dashboard): refresh packaged audit assets"
```

Expected: one generated-artifact commit.

### Task 3: Commit the working-tree review record

**Files:**
- Create: `audit/code-review-report.md`

**Interfaces:**
- Consumes: focused pytest, Ruff, dashboard test/build, package comparison, and Git diff evidence.
- Produces: a review record that defines which Claude changes Phase 1 must address.

- [ ] **Step 1: Verify the report contains each held file**

Run:

```bash
rtk grep -n 'retention.py\|routes/admin.py\|proxy/models.py\|uv.lock\|AUDIT_INDEPENDENT' audit/code-review-report.md
```

Expected: the report names every held change group and explains why it remains uncommitted.

- [ ] **Step 2: Check the report diff**

Run:

```bash
rtk git diff --check -- audit/code-review-report.md
rtk git diff -- audit/code-review-report.md
```

Expected: no whitespace error; the report contains no secret values.

- [ ] **Step 3: Stage and commit the report**

Run:

```bash
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git add audit/code-review-report.md
GIT_TERMINAL_PROMPT=0 GIT_EDITOR=true PAGER=cat rtk git commit -m "docs: review Claude audit working tree"
```

Expected: one documentation-file commit.

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
