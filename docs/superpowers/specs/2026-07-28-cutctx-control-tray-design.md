# CutCtx Control — Tray App Design

Date: 2026-07-28  
Status: Approved for implementation  
Branch: `feat/cutctx-control-tray`

## Problem

Starting CutCtx via CLI with optional feature flags, seat tokens, and client
routing is tedious and error-prone. Codex/Claude desktop users hit opaque
failures (e.g. `401 malformed token`) when the proxy is licensed but clients
never receive `X-Cutctx-User-Token`. Operators need a product control surface,
not a flag encyclopedia.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Form factor | Cross-platform tray / menu-bar app (macOS, Windows, Linux) |
| Stack | Tauri 2 (Rust) + React + Vite + TypeScript |
| v1 scope | Full control plane: lifecycle + clients + feature toggles + profiles + savings chip |
| Toggle apply | Live admin API when possible; otherwise mark restart-required and one-click restart |
| Deep UI | Existing Vite dashboard for governance/stats; tray deep-links when proxy is up |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  CutCtx Control (Tauri 2)                               │
│  ┌──────────────┐  IPC   ┌────────────────────────────┐ │
│  │ React popover│◄──────►│ Rust commands              │ │
│  │ UI           │        │  - ProxySupervisor         │ │
│  └──────────────┘        │  - FeatureCatalog          │ │
│         │                │  - ProfileStore            │ │
│         │ open           │  - SeatTokenService        │ │
│         ▼                │  - ClientRouter (Codex/…)  │ │
│  Dashboard (existing)    │  - HealthPoller            │ │
│                          └──────────┬─────────────────┘ │
└─────────────────────────────────────┼───────────────────┘
                                      │ spawn / HTTP
                                      ▼
                           cutctx proxy :8787
```

### Boundaries

- **Tray owns:** process lifecycle, profiles, toggles, seat token mint/inject,
  client routing (Codex/Claude/Cursor), tray icon state, open-dashboard.
- **Dashboard owns:** audit, spend, policy studios, heavy charts, playground.
- **Proxy owns:** compression runtime, admin APIs, license/seat enforcement.

### Process model

- Rust `ProxySupervisor` spawns `cutctx proxy` with argv derived from the
  active profile. Prefer PATH `cutctx`; allow override path in Advanced.
- Health poll every 2s against `GET /health` (and `/stats` when healthy).
- Stop uses graceful SIGTERM/taskkill then force-kill after timeout.
- Only one supervised child; if an external proxy already owns the port,
  attach in “external” mode (stop disabled or “Stop external” opt-in).

## UI

### Tray icon

| State | Meaning |
|---|---|
| Green | Healthy + optimizing |
| Amber | Up with restart pending / degraded |
| Red | Down or seat/auth failure |
| Grey | Starting / stopping |

### Popover (~360×520)

1. Status strip — port, plan, latency, savings chip  
2. Power — Start / Stop / Restart / Open Dashboard  
3. Clients — Codex, Claude, Cursor: route toggle, Fix seat token, Copy header  
4. Features — grouped toggles with Live vs Restart-required badges  
5. Profiles — save / load / delete named configs  
6. Footer — seat subject, version, Quit  

Visual direction: instrument-panel density, distinctive typography, no purple
gradient “AI slop”. CSS variables; light-first with high-contrast status.

## Feature catalog

Each toggle maps to a CLI flag and/or env var. `apply: live | restart`.

v1 curated groups (not every CLI flag — product-facing subset):

| Group | Keys (examples) | Default apply |
|---|---|---|
| Optimization | `optimize`, `mode` (token/cache), `cache`, `rate_limit` | restart |
| CCR | `ccr_inject_tool`, `ccr_marker`, `ccr_proactive_expansion` | restart |
| Memory | `memory`, `memory_tools`, `memory_context`, `learn` | restart |
| Engines | `kompress`, `memoize`, `drain3`, `difftastic`, `code_aware`, `code_graph` | restart |
| Intelligence | `context_budget`, `task_aware`, `semantic_dedup`, `cross_session`, `multi_agent`, `autopilot`, `learned_policies` | restart |
| Security | `firewall`, `subscription_tracking` | restart |
| Routing | `model_routing_preset` | restart |

Live apply is opportunistic: if an admin endpoint exists for a key, mark
`apply: live`; otherwise `restart`. Catalog is data-driven in Rust so the UI
does not hardcode argv.

Profiles persist under `~/.cutctx/control/profiles/*.json`.

## Client setup

### Seat token

- Mint via `cutctx license token` (or in-process EE issuer when available).
- Persist latest token path/metadata under `~/.cutctx/control/seat.json`
  (token itself mode `0600`).
- Actions: Mint, Copy header (`X-Cutctx-User-Token: …`), Inject into Codex.

### Codex inject

Write/update `~/.codex/config.toml`:

1. Keep/replace CutCtx marker block for `openai_base_url` / `base_url`.
2. Ensure `[model_providers.openai]` `http_headers` includes
   `X-Cutctx-User-Token` without selecting a custom `model_provider` (avoids
   session-history fragmentation).

### Claude inject

Set/clear routing guidance: prefer writing a small snippet the user can
apply, plus when possible update env via documented Claude config paths.
v1 minimum: copy `ANTHROPIC_BASE_URL` + user-token header lines; best-effort
file inject if a stable Claude config path exists.

### Cursor

Point OpenAI base URL override instructions / write known settings keys when
detectable; otherwise copy values.

## Data flow

1. App start → load last profile → poll health.  
2. Start → build argv from catalog → spawn → wait healthy or surface stderr.  
3. Toggle → if live: PATCH/POST admin; else set dirty + amber “Restart required”.  
4. Restart → stop supervised child → spawn with updated profile.  
5. Fix seat token → mint → inject Codex headers → verify with probe optional.  
6. Open Dashboard → `http://127.0.0.1:{port}/` (or `/dashboard`) in browser.

## Error handling

| Failure | UX |
|---|---|
| `cutctx` not on PATH | Clear install CTA; path picker |
| Port in use (external) | Attach mode; show PID if known |
| Spawn fails | Show last 30 lines of stderr |
| Health timeout | Red state + Restart |
| Seat mint fails (no license) | Explain builder vs paid; link activate |
| Codex config write fails | Show path + permission error; Copy as fallback |
| Live apply fails | Fall back to restart-required |

Never log raw tokens or API keys.

## Testing (TDD)

- **Rust unit tests first** for: argv builder, feature catalog, profile
  serialize/roundtrip, Codex config inject/strip, seat header format,
  health state machine.
- **TS/React tests** for view-model mapping (status → icon/color) and toggle
  dirty-state.
- **No full GUI E2E required for v1 merge**; smoke script optional.
- Existing repo suites must remain green (no regression).

## Packaging

- Lives at `desktop/cutctx-control/` in the monorepo.
- Dev: `npm run tauri dev` from that package.
- CLI bridge later: `cutctx control` opens the app (follow-up).
- CI: Rust tests + frontend unit tests on PR; platform package builds follow-up.

## Non-goals (v1)

- Replacing the dashboard
- Cloud multi-tenant admin
- Editing every obscure CLI timeout flag in the popover
- Auto-updating CutCtx Python install

## Success criteria

1. From cold start, user can Start proxy with “all optional features” profile
   without typing CLI flags.
2. Codex ChatGPT-auth path through licensed proxy works after one “Fix seat
   token” click (no `malformed token`).
3. Toggle that needs restart shows amber + Restart; after Restart, flag is
   reflected in process argv / env.
4. Open Dashboard works when proxy is healthy.
5. Unit tests cover catalog, argv, Codex inject, profiles; main repo tests
   still pass.
