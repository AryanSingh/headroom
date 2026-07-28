# CutCtx Control Tray Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a cross-platform Tauri 2 tray app that starts/stops CutCtx with feature profiles, fixes seat tokens for Codex/Claude, and deep-links the existing dashboard.

**Architecture:** Rust core library modules (catalog, argv, profiles, Codex inject, health FSM) behind Tauri commands; React popover UI; spawn `cutctx proxy` as supervised child.

**Tech Stack:** Tauri 2, Rust, React 19, Vite, TypeScript, Vitest (frontend), `cargo test` (Rust).

## Global Constraints

- Path: `desktop/cutctx-control/`
- Spec: `docs/superpowers/specs/2026-07-28-cutctx-control-tray-design.md`
- TDD: no production code without a failing test first
- Do not break existing repo Python/dashboard tests
- Never log seat tokens or API keys
- Platforms: macOS, Windows, Linux tray

---

## File map

| Path | Responsibility |
|---|---|
| `desktop/cutctx-control/package.json` | Frontend + Tauri scripts |
| `desktop/cutctx-control/src/` | React popover UI |
| `desktop/cutctx-control/src-tauri/Cargo.toml` | Rust crate |
| `desktop/cutctx-control/src-tauri/src/catalog.rs` | Feature catalog + apply mode |
| `desktop/cutctx-control/src-tauri/src/argv.rs` | Profile → CLI argv/env |
| `desktop/cutctx-control/src-tauri/src/profiles.rs` | Profile store under ~/.cutctx/control |
| `desktop/cutctx-control/src-tauri/src/codex_config.rs` | Codex toml inject |
| `desktop/cutctx-control/src-tauri/src/seat.rs` | Token mint/header helpers |
| `desktop/cutctx-control/src-tauri/src/health.rs` | Health/status FSM |
| `desktop/cutctx-control/src-tauri/src/supervisor.rs` | Spawn/stop proxy |
| `desktop/cutctx-control/src-tauri/src/lib.rs` | Tauri command surface |
| `desktop/cutctx-control/src/lib/status.ts` | UI status mapping |
| `desktop/cutctx-control/src/App.tsx` | Popover shell |

---

### Task 1: Scaffold package + failing catalog test

- [ ] Create `desktop/cutctx-control` Tauri/Vite/React/TS skeleton
- [ ] Write failing `catalog` unit test for known feature keys + restart apply
- [ ] Implement minimal catalog to pass
- [ ] Commit

### Task 2: Argv builder (TDD)

- [ ] Failing tests: optimize off → `--no-optimize`; memory on → `--memory`; preset → `--model-routing-preset`
- [ ] Implement `argv.rs`
- [ ] Commit

### Task 3: Profiles (TDD)

- [ ] Failing tests: save/load/roundtrip in temp dir
- [ ] Implement `profiles.rs`
- [ ] Commit

### Task 4: Codex config inject (TDD)

- [ ] Failing tests: inject base_url markers; inject http_headers token; idempotent re-inject
- [ ] Implement `codex_config.rs`
- [ ] Commit

### Task 5: Health FSM + seat header (TDD)

- [ ] Failing tests: state transitions; `X-Cutctx-User-Token` header format
- [ ] Implement `health.rs`, `seat.rs`
- [ ] Commit

### Task 6: Supervisor + Tauri commands

- [ ] Failing tests around command parsing / dry-run spawn plan
- [ ] Wire supervisor + commands
- [ ] Commit

### Task 7: React UI + status mapping tests

- [ ] Vitest for status → icon color
- [ ] Build popover sections per spec
- [ ] Commit

### Task 8: Validation

- [ ] `cargo test` in src-tauri
- [ ] Frontend unit tests
- [ ] Spot-check main repo unaffected (`uvx ruff@0.9.4` not required unless Python touched)
- [ ] Update deepwork file + summary
