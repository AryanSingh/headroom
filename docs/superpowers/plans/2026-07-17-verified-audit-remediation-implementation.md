# Verified Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the defects independently reproduced from the July 17 audit while preserving current CCR and episodic-memory runtime behavior.

**Architecture:** Extend existing release scripts and local safety boundaries rather than adding new services. Keep each change inside the component that owns the invariant: release scripts own version alignment, `ContentRouter` owns direct-call non-inflation, the RTK installer owns its pin and checksums, and the audit CLI owns query serialization.

**Tech Stack:** Python 3.12, pytest, FastAPI/httpx, GitHub Actions YAML, Helm YAML, Kubernetes YAML.

## Global Constraints

- Keep `ccr_inject_tool`, `ccr_handle_responses`, and `ccr_context_tracking` enabled by default.
- Keep `episodic_memory_enabled` disabled by default.
- Do not add provider-request entitlement denials.
- Treat `pyproject.toml` version `0.31.0` as canonical for checked-in manifests.
- Continue accepting system-installed RTK binaries without rejection or replacement.

---

### Task 1: Deployment version synchronization and CI coverage

**Files:**
- Modify: `scripts/tests/test_version_sync.py`
- Modify: `scripts/verify-versions.py`
- Modify: `scripts/version-sync.py`
- Modify: `tests/test_release_workflows.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `helm/cutctx/Chart.yaml`
- Modify: `helm/cutctx/values.yaml`
- Modify: `k8s/deployment.yaml`

**Interfaces:**
- Consumes: canonical version from `pyproject.toml`.
- Produces: `update_deployment_versions(root: Path, version: str) -> None` and deployment entries in the existing verification map.

- [ ] **Step 1: Extend the temporary release fixture and assertions**

Add Helm chart, Helm values, and Kubernetes deployment files at `0.5.25` to `temp_project`. Assert an explicit sync to `0.7.0` rewrites all four deployment fields.

- [ ] **Step 2: Run the focused sync test and confirm RED**

Run: `rtk proxy .venv/bin/pytest scripts/tests/test_version_sync.py::test_version_sync_explicit_version -q`

Expected: FAIL because deployment manifests remain `0.5.25`.

- [ ] **Step 3: Implement deployment synchronization**

Add one helper that uses anchored substitutions for:

```python
helm/cutctx/Chart.yaml: version, appVersion
helm/cutctx/values.yaml: image.tag
k8s/deployment.yaml: ghcr.io/cutctx/cutctx:v<version>
```

Require exactly one match for each field and call the helper from the full sync path, not `--plugin-manifests-only`.

- [ ] **Step 4: Extend verification and workflow tests**

Parse the deployment versions into `versions` in `verify-versions.py`. Add assertions that CI's `code` and `e2e` filters include both `helm/**` and `k8s/**`.

- [ ] **Step 5: Sync the repository and verify GREEN**

Run:

```bash
rtk proxy .venv/bin/python scripts/version-sync.py --version 0.31.0
rtk proxy .venv/bin/python scripts/verify-versions.py
rtk proxy .venv/bin/pytest scripts/tests/test_version_sync.py tests/test_release_workflows.py -q
```

Expected: all manifests report `0.31.0`; tests pass.

### Task 2: Direct ContentRouter non-inflation guard

**Files:**
- Modify: `tests/test_transforms_content_router.py`
- Modify: `cutctx/transforms/content_router.py`

**Interfaces:**
- Consumes: `RouterCompressionResult` returned by pure or mixed routing.
- Produces: `_revert_inflated_result(result, original) -> RouterCompressionResult` behavior inside `compress()`.

- [ ] **Step 1: Add the reproduced mixed-content regression**

Use this payload:

```python
content = (
    "Explanation line with enough prose words to be detected.\n"
    "```python\nprint(1)\n```\n"
) * 100
```

Assert `result.compressed == content`, byte length does not increase,
`strategy_used is PASSTHROUGH`, token totals are equal, and
`diagnostics["inflation_guard"] == "reverted"`.

- [ ] **Step 2: Run the regression and confirm RED**

Run: `rtk proxy .venv/bin/pytest tests/test_transforms_content_router.py -q -k inflation_guard`

Expected: FAIL with an 8,198-byte result for an 8,000-byte input.

- [ ] **Step 3: Implement the byte guard**

After the empty-output guard and before observation, compare UTF-8 byte lengths. On inflation, return a passthrough result whose routing decision uses equal word counts and whose diagnostics retain `attempted_strategy` plus `inflation_guard: reverted`.

- [ ] **Step 4: Verify router and library safety tests**

Run:

```bash
rtk proxy .venv/bin/pytest tests/test_transforms_content_router.py tests/test_compression_safety_rails.py -q
```

Expected: PASS.

### Task 3: Managed RTK pin and diagnostics

**Files:**
- Modify: `tests/test_rtk_installer.py`
- Modify: `cutctx/rtk/__init__.py`
- Modify: `cutctx/rtk/installer.py`

**Interfaces:**
- Consumes: upstream RTK release tag and SHA-256 asset digests.
- Produces: `RTK_VERSION = "v0.43.0"`; `get_rtk_version(path: Path) -> str | None` for diagnostics.

- [ ] **Step 1: Add pin, checksum, and system-selection tests**

Assert the pin equals `v0.43.0`, the five supported target digests equal the published GitHub asset digests, and a system binary remains selected even when its reported version differs.

- [ ] **Step 2: Run tests and confirm RED**

Run: `rtk proxy .venv/bin/pytest tests/test_rtk_installer.py -q`

Expected: FAIL on the old pin/checksums.

- [ ] **Step 3: Update the pin and checksums**

Use the upstream release digests:

```text
aarch64-apple-darwin          8a17e49acbd378997eb21d0eb6f7f861111f35b4fc9b1c74edf4c7448e576c65
aarch64-unknown-linux-gnu    5519f7ca12e5c143a609f0d28a0a77b97413a8dce31c2681f1a41c24519a8731
x86_64-apple-darwin          a85f60e2637811be68366208b8d8b9c5ba1b748cb5df4477ab20cd73d3c5d9f8
x86_64-pc-windows-msvc       7c5e4a2ef816a4d4ed947ddd74ca3df851fc39ea87d49a3ca2bf3abc515a016b
x86_64-unknown-linux-musl    ff8a1e7766496e175291a85aeca1dc97c9ff6df33e51e5893d1fbc78fea2a609
```

Keep `get_rtk_path()` order unchanged. Make version inspection return `None` on timeout, execution failure, or unparseable output.

- [ ] **Step 4: Verify GREEN**

Run: `rtk proxy .venv/bin/pytest tests/test_rtk_installer.py -q`

Expected: PASS.

### Task 4: Structured audit CLI parameters

**Files:**
- Create: `tests/test_cli_audit.py`
- Modify: `cutctx/cli/audit.py`

**Interfaces:**
- Consumes: Click `action`, `actor`, `limit`, and `format` options.
- Produces: dictionaries passed through `httpx.get(..., params=params)`.

- [ ] **Step 1: Add mocked HTTP argument tests**

Invoke `audit list`, `audit export`, and `audit stats` through `CliRunner`. Patch `httpx.get` and assert the URL has no query string and `params` contains the exact option values, including an action string containing `&limit=9999` as literal data.

- [ ] **Step 2: Run tests and confirm RED**

Run: `rtk proxy .venv/bin/pytest tests/test_cli_audit.py -q`

Expected: FAIL because the CLI passes no `params` argument.

- [ ] **Step 3: Replace string concatenation**

Build dictionaries for each command and pass them to `httpx.get`. Preserve headers, timeout values, rendering, and exception handling.

- [ ] **Step 4: Verify GREEN**

Run: `rtk proxy .venv/bin/pytest tests/test_cli_audit.py -q`

Expected: PASS.

### Task 5: CCR entitlement metadata alignment

**Files:**
- Modify: `tests/test_entitlements.py`
- Modify: `cutctx_ee/entitlements.py`

**Interfaces:**
- Consumes: documented Builder feature set from `PRODUCT_GUIDE.md`.
- Produces: `FEATURE_TIERS["ccr"]` and `FEATURE_TIERS["ccr_marker"]` set to `BUILDER`.

- [ ] **Step 1: Change the entitlement expectation first**

Replace the Builder denial test with a Builder entitlement test. Keep episodic-memory Business tests unchanged.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `rtk proxy .venv/bin/pytest tests/test_entitlements.py::TestEntitlementChecker::test_builder_entitled_to_ccr -q`

Expected: FAIL.

- [ ] **Step 3: Align the feature map**

Change only the two CCR entries from `TEAM` to `BUILDER`.

- [ ] **Step 4: Verify entitlement boundaries**

Run:

```bash
rtk proxy .venv/bin/pytest tests/test_entitlements.py tests/test_entitlement_boundaries.py tests/test_management_api_entitlements.py -q
```

Expected: PASS; episodic toggle remains denied to Builder.

### Task 6: Evidence note and final verification

**Files:**
- Create: `audit/verified-remediation-2026-07-17.md`

**Interfaces:**
- Consumes: current source and executed command output.
- Produces: a concise status table with Confirmed, Narrowed, and Refuted verdicts.

- [ ] **Step 1: Write the evidence note**

Cover package release ordering, deployment drift, entitlement intent, direct
router inflation, RTK release status, request traces, compliance disclosures,
and audit CLI parameter handling. Include exact source paths and commands.

- [ ] **Step 2: Run formatting and focused regression checks**

Run:

```bash
rtk ruff check scripts/version-sync.py scripts/verify-versions.py cutctx/transforms/content_router.py cutctx/rtk cutctx/cli/audit.py tests/test_cli_audit.py tests/test_rtk_installer.py
rtk ruff format --check scripts/version-sync.py scripts/verify-versions.py cutctx/transforms/content_router.py cutctx/rtk cutctx/cli/audit.py tests/test_cli_audit.py tests/test_rtk_installer.py
rtk proxy .venv/bin/pytest scripts/tests/test_version_sync.py tests/test_release_workflows.py tests/test_transforms_content_router.py tests/test_compression_safety_rails.py tests/test_rtk_installer.py tests/test_cli_audit.py tests/test_entitlements.py tests/test_entitlement_boundaries.py tests/test_management_api_entitlements.py -q
rtk proxy .venv/bin/python scripts/verify-versions.py
```

Expected: all commands pass and version verification reports `0.31.0`.

- [ ] **Step 3: Review the final diff**

Run: `rtk git diff --check && rtk git status --short && rtk git diff --stat`

Expected: no whitespace errors; only scoped remediation files plus the user's pre-existing files appear.
