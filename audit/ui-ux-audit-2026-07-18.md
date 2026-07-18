# UI/UX & Functional Audit — 2026-07-18

**Method:** live interactive audit of the real dashboard (vite dev server against
the latest proxy build on :8899 with real production data), driven end-to-end in
a browser — every route navigated, controls actually clicked, failures actually
triggered — plus Playwright e2e pinning for every fix. Fixes landed in commit
`9d9b9356`; all verification commands below were executed, not assumed.

## Surface inventory (all reviewed)

| Surface | Status |
|---|---|
| Auth gate (admin key screen) | ✅ Verified — renders, blocks data until key, clear copy |
| Dashboard/Overview (stats, trend, recent requests, savings mix, quick links) | ✅ Verified (2 fixes) |
| Savings & Attribution (period tabs, created/observed, by source/model, tokens/cost toggle) | ✅ Verified (1 fix) |
| Orchestrator (Routing Studio contracts/simulator/rollouts/evidence, control plane tabs, routing mode, Safe Savings panel*) | ✅ Verified (2 fixes) |
| Capabilities (live evidence cards, capability groups) | ✅ Verified |
| Governance (rate limit, budget, feature toggles, tier gating, audit/RBAC surfaces) | ✅ Verified (1 fix) |
| Security/Firewall (posture, event tape, live scanner, rule sets) | ✅ Verified — honest disabled states |
| Memory (tier-gated business feature panel) | ✅ Verified |
| Replay (session loader, timeline empty states) | ✅ Verified |
| Playground (compression request builder, output panes) | ✅ Verified |
| Docs (TOC, CLI reference, env tables) | ✅ Verified |
| Request-trace inspector (drawer) | ✅ Verified (2 backend fixes) |
| Sidebar (collapse, mobile drawer), topbar (search, shortcut, theme, status pill) | ✅ Verified |

\* Safe Savings panel is flag-gated (`CUTCTX_SAFE_SAVINGS_EXPERIENCE`); its
behavior is pinned by 4 dedicated Playwright tests.

## Findings and fixes (all verified end-to-end)

### 1. Gated feature toggles failed silently — **High / fixed**
- **Location:** Governance → feature toggles; `dashboard/src/pages/Governance.jsx`
- **Root cause:** `handleToggle` had no catch; the proxy's 403
  `feature_not_available` response was swallowed.
- **Repro:** builder-tier proxy → click "Enable Episodic memory" → nothing happens.
- **Fix:** `patchDashboardConfig` now attaches the structured error `detail`;
  the row renders a `role="alert"`: *"This feature requires the Business tier
  (current tier: Builder). Configure a license key to unlock it."*
- **Verified:** live click-through + new e2e
  `test_gated_toggle_surfaces_entitlement_error_when_proxy_refuses`.
  (Primary defense — proactive disabled toggle with tier label when
  `/entitlements` is reachable — was already present and is e2e-pinned.)

### 2. Trace inspector froze the entire proxy — **Critical / fixed (backend)**
- **Location:** `GET /transformations/traces/{id}`;
  `cutctx/proxy/request_logger.py`, `cutctx/proxy/server.py`
- **Root cause (three layers):** single-trace lookup tailed 10,000
  full-message entries from a 251 MB shared JSONL log; `_tail_lines`
  re-split its whole accumulated buffer per 64 KB chunk (quadratic); all of
  it ran synchronously on the event loop. One dashboard click stalled all
  live proxy traffic for minutes and cascaded into `/health` failures.
- **Fix:** bounded lookup window (500 entries) + linear incremental tail
  with a 32 MB hard byte cap + `asyncio.to_thread` in the endpoint.
- **Verified:** unknown-id lookup went from **infinite hang → 404 in 16 ms**
  on the live proxy; inspector opens and renders the decision receipt;
  `tests/test_request_logger_tail.py` pins boundedness (<2 s on a 40 MB log).

### 3. `/health` flapped 503s — **High / fixed (backend)**
- **Location:** `_check_upstream`, `cutctx/proxy/server.py`
- **Root cause:** successful upstream probes never set `expires_at`, so every
  poll fired a live HEAD upstream; a single transient failure was cached for
  the full 30 s TTL → 503 bursts that read as proxy outages (pager noise,
  k8s probe restarts, dashboard stuck on "connecting" with the wrong
  fallback version shown).
- **Fix:** cache both outcomes; failures retry after ≤10 s.
- **Verified:** 6/6 stable 200s on the live proxy (was 6/6 503s during a
  flap window); 2 new tests pin the caching contract.

### 4. Raw reason codes in Recent requests — **Medium / fixed**
- **Location:** Overview routing column (`no_route_for_model` on every row).
- **Fix:** shared operator copy (same titles as the Safe Savings API/CLI) with
  the raw code kept in the tooltip; unknown codes humanize gracefully.
- **Verified:** live ("No exact route configured") + trace-inspector e2e
  updated to pin the humanized label.

### 5. Dev-proxy allowlist gaps → in-UI error banners — **Medium / fixed**
- **Location:** `dashboard/vite.config.js` (`/policy`, `/transformations`,
  `/entitlements` missing → SPA HTML returned to API calls; Orchestrator
  showed "/policy/status returned non-JSON response").
- **Verified:** all three proxy 200 JSON through :5173; panels render data.

### 6. Broken-looking currency `$0.000` — **Low / fixed**
- `formatCurrency`: exact zero → `$0.00`; sub-millidollar → `< $0.01`.

### 7. `WHEN` header wrapped mid-word — **Low / fixed** (`white-space: nowrap`).

### 8. Roles tab rendered blank when empty — **Low / fixed** with a real
  empty state explaining what roles do.

### False alarms investigated and closed (not bugs)
- Theme toggle "dead" / light-mode "hybrid": browser-pane stale-frame
  artifacts; DOM probes proved theme flips, persists, and light mode is
  fully coherent. Light theme verified premium on desktop + mobile.
- "Run live  compression" double space: screenshot artifact; DOM is correct.
- Version mismatch v0.31.0 vs v0.32.0: intended (build-time canonical vs
  next-release runtime version); visible only during the now-fixed health
  flap window.

## Journeys executed
First-load auth gate → authenticated dashboard; period/metric toggles; theme
toggle + persistence; sidebar collapse + mobile drawer; `/` keyboard shortcut
focuses search; search filters Governance; trace inspector open/read; gated
toggle refusal (403) with actionable copy; backend killed mid-session →
graceful banner + per-panel fallbacks + zero crashes → backend restored →
**automatic recovery** with no reload; Playwright-pinned: Safe Savings panel
render/blocked/off/failure, governance toggles, capabilities toggles, savings
period/metric/attribution, orchestrator policy/binding editor, trace inspector.

## Accessibility notes
Strong baseline: aria-labels on all icon controls ("Toggle sidebar", "Switch
to light mode", per-toggle "Enable X"/"Copy Y"), `role="alert"`/`role="status"`
used for feedback (new entitlement error included), skip-to-content link
present, focus-visible ring global, checkbox grid grouped (`role="group"`,
fixed earlier this cycle), light-theme contrast previously measured ≥5.8:1.
Disabled search input exposes a `title` explaining unavailability.

## Performance notes
Single-worker proxy overhead p50 2.5 ms / p95 3.1 ms (measured earlier this
cycle); trace-inspector event-loop stall eliminated (finding 2); no console
errors on any route; page-chunk code splitting active (largest chunk
Overview ~67 KB gz).

## Release readiness assessment
**Dashboard: ready.** Every route renders with real data in both themes and
three viewports; every interactive control exercised works or explains
itself; failure modes are honest and self-healing; the two production-grade
backend reliability bugs the UI surfaced (2, 3) are fixed and test-pinned.
Remaining recommendations (not blockers): link tier-locked panels to the
plans page; add virtualization if Recent requests ever exceeds ~50 rows;
consider surfacing the Safe Savings flag in Governance for discoverability.

**Verification totals for this audit:** 28 dashboard e2e + 46 backend tests
+ 12 JS unit tests green; dashboard lint clean; bundle rebuilt and synced.
