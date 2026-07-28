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

Requires the released `cutctx-ai` package (the Control app resolves `cutctx`
from `CUTCTX_BIN` or PATH). On startup, Control installs or attaches to a
user-scoped managed proxy service. The service starts at login and restarts on
failure; it preserves a healthy proxy already serving a Codex/WebSocket
session rather than replacing it.

The managed profile records the selected Control features and explicitly turns
on reversible code compression. Saved Control credentials and the local seat
token are made available to the login-started runtime without being printed or
stored in the deployment manifest.

## Product surfaces

| Area | Actions |
|---|---|
| Power | Start / Stop / Restart / Open Dashboard |
| Clients | Fix Codex seat token, Claude env snippet, mint token |
| Profiles | Save/load, “all optional on” release profile |
| Features | Grouped toggles (restart-required until live APIs exist) |

Design: `docs/superpowers/specs/2026-07-28-cutctx-control-tray-design.md`
