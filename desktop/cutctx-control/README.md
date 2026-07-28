# CutCtx Control

Cross-platform tray / control panel for the CutCtx proxy.

Start/stop the proxy with curated feature profiles, mint seat tokens, fix Codex
routing headers, and open the operator dashboard — without memorizing CLI flags.

## Stack

- Tauri 2 (Rust)
- React + Vite + TypeScript

## Develop

```bash
cd desktop/cutctx-control
npm install
npm test
cd src-tauri && cargo test
npm run tauri:dev
```

Requires `cutctx` on `PATH` (or set `CUTCTX_BIN`).

## Product surfaces

| Area | Actions |
|---|---|
| Power | Start / Stop / Restart / Open Dashboard |
| Clients | Fix Codex seat token, Claude env snippet, mint token |
| Profiles | Save/load, “all optional on” release profile |
| Features | Grouped toggles (restart-required until live APIs exist) |

Design: `docs/superpowers/specs/2026-07-28-cutctx-control-tray-design.md`
