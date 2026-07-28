# desktop/

## Responsibility

Native desktop control surfaces for CutCtx operators. Primary app:
`cutctx-control` — Tauri 2 tray/control panel for proxy lifecycle, feature
profiles, seat tokens, and Codex/Claude routing.

## Design

Rust core modules (`catalog`, `argv`, `profiles`, `codex_config`, `seat`,
`health`, `supervisor`) sit behind Tauri commands. React popover UI invokes
those commands and deep-links the existing web dashboard when the proxy is up.

## Flow

App start → load profile → poll `/health` → Start spawns `cutctx proxy` with
catalog-derived argv → toggles mark restart-required → Fix seat token mints
`ctu1` token and injects Codex `http_headers` without changing `model_provider`.

## Integration

- Spawns PATH/`CUTCTX_BIN` `cutctx`
- Writes `~/.cutctx/control/profiles` and `seat.json`
- Updates `~/.codex/config.toml` CutCtx blocks
- Opens `http://127.0.0.1:{port}/` dashboard
