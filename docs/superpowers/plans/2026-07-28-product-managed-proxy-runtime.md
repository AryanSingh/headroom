# Product-Managed Proxy Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the product installs and maintains a persistent CutCtx proxy with reversible code compression explicitly enabled.

**Architecture:** Add a product-runtime manifest builder and idempotent ensure operation above the existing persistent-service installer.  The desktop Control app invokes that operation at startup, attaching to a healthy external service and never reclaiming its port.  Existing install/runtime code remains the only creator of platform service artifacts.

**Tech Stack:** Python Click installer, existing CutCtx deployment manifest/supervisor modules, Tauri/Rust Control app, pytest and cargo test.

## Global Constraints

- Preserve any healthy existing listener and its active WebSocket sessions.
- Use the platform supervisor; do not create a second competing background process.
- Set `CUTCTX_REVERSIBLE_CODE=1` and `--enable-reversible-code` explicitly.
- Do not store or print credentials in manifests, tests, or logs.

---

### Task 1: Product deployment manifest

**Files:**
- Modify: `cutctx/install/planner.py`
- Test: `tests/test_install_planner.py`

**Interfaces:**
- Produces: `build_product_manifest(port: int, backend: str) -> DeploymentManifest`
- Consumes: `build_manifest(...)`

- [ ] Write tests asserting the product manifest uses `persistent-service`, user scope, a loopback port, `CUTCTX_REVERSIBLE_CODE=1`, and `--enable-reversible-code`.
- [ ] Run the focused tests and observe failure because `build_product_manifest` does not exist.
- [ ] Implement `build_product_manifest` by composing `build_manifest`, then explicitly add the reversible-code environment variable and argv only once.
- [ ] Run the focused tests and observe pass.

### Task 2: Idempotent managed-runtime ensure command

**Files:**
- Modify: `cutctx/cli/install.py`
- Test: `tests/test_cli_install.py`

**Interfaces:**
- Produces: `cutctx install ensure-product-runtime --port PORT --backend BACKEND`
- Consumes: `load_manifest`, `probe_ready`, `install_supervisor`, `_start_deployment`

- [ ] Write tests for: healthy listener returns attach without mutation; missing profile installs and starts; a different existing profile is reported as restart-required and is not stopped.
- [ ] Run the focused tests and observe the command is unavailable.
- [ ] Implement the command with an explicit `--apply` mutation boundary; non-apply mode only reports the action, and Control calls apply after its healthy-listener guard.
- [ ] Run focused tests and observe pass.

### Task 3: Control startup integration

**Files:**
- Modify: `desktop/cutctx-control/src-tauri/src/supervisor.rs`
- Modify: `desktop/cutctx-control/src-tauri/src/lib.rs`
- Test: unit tests in `supervisor.rs`

**Interfaces:**
- Produces: `ProxySupervisor::ensure_product_runtime(&self, profile: &ProxyProfile) -> Result<(), String>`
- Consumes: product ensure CLI command and `probe_health`

- [ ] Write a focused command-plan test asserting the supervisor invokes `install ensure-product-runtime --apply` with the profile port and does not invoke it when health is already established.
- [ ] Run cargo test and observe the new test fails.
- [ ] Implement a command-plan helper and startup call which probes first, then requests product-runtime ensure, waits for health, and does not call port reclamation.
- [ ] Run focused cargo tests and observe pass.

### Task 4: Release verification and docs

**Files:**
- Modify: `desktop/cutctx-control/README.md`
- Modify: `docs/reversible-code-compression.md`

- [ ] Document the managed startup model, upgrade behavior, and no-interruption rule.
- [ ] Run Python target tests, Rust tests, `cargo fmt --check`, `cargo clippy -- -D warnings`, package build, and repository formatting checks.
