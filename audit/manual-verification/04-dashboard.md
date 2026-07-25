# Dashboard Operator UI Checklist

Use Chromium plus one current Firefox/WebKit-equivalent where supported. Run at 1440×900 and 390×844; keyboard-only every interactive control. Seed successful, failed, cached, routed, memory, replay, and governance activity first.

### UI-001 — Shell, authentication, navigation, and theme

**Priority:** P0. **Actions:** open `/`, `/dashboard`, and configured basename with no admin key, invalid key, viewer/operator/admin key; navigate every sidebar/mobile menu destination; toggle theme; refresh/deep-link/back-forward. **Expected:** auth gate/permissions are clear, active route and title update, no console error/blank page, theme persists without exposing key. **Negative:** proxy down, malformed stored key, unauthorized deep link. **Cleanup:** clear test browser storage. **Pass:** each route is reachable only to the appropriate role and has no navigation trap.

### UI-002 — Loading, empty, error, stale, and refresh states

**Priority:** P0. **Actions:** throttle API, return empty arrays, inject 401/403/404/500/timeout, change configured proxy URL during a request, use manual refresh and polling. **Expected:** distinct loading/empty/error/retry states, stale result does not overwrite newer response, disabled controls prevent duplicate mutation. **Pass:** no raw exception or silently misleading zero-state.

### UI-003 — Overview, health, diagnostics, and capability views

**Priority:** P0. **Actions:** validate overview/health/diagnostics/capabilities against `/health`, `/stats`, `/stats-history`, flags and version; toggle a safe test feature flag. **Expected:** figures/timestamps/status labels reconcile; unsupported feature displays unavailable state; mutation requires admin and refreshes canonical response. **Negative:** invalid flag/unauthorized toggle. **Pass:** screenshot plus matching API payload for each displayed metric.

### UI-004 — Savings, attribution, filters, and time windows

**Priority:** P0. **Actions:** create known compression/cache/routing/RTK events; visit savings/analytics pages; apply all filters, date windows, sort/pagination/export controls. **Expected:** source totals do not double-count and match API; empty filter state is understandable. **Negative:** invalid time range, no data, partially missing metric series. **Pass:** at least one hand-calculated event agrees across UI and API.

### UI-005 — Routing/orchestration studio

**Priority:** P0. **Actions:** list/select contract, edit draft, validate error, simulate, inspect decision/evidence, shadow/canary/pause/rollback/promote; provider account/model/credential actions; workflow/outcome/receipt panels. **Expected:** role restrictions and confirmation/pending state, server-side validation message, canonical reload after mutation. **Negative:** stale version, invalid contract, failed provider test, forbidden route. **Cleanup:** rollback/delete `RUN_ID` entities. **Pass:** UI state never claims deployment before server accepts it.

### UI-006 — Memory, replay, firewall and governance surfaces

**Priority:** P0. **Actions:** use memory search/detail/filters, session replay/detail, firewall/governance/security setting pages with seeded data and permissions. **Expected:** sensitive fields are redacted where appropriate; replay is read-only unless clearly labeled; tenant/role bounds apply. **Negative:** missing session/memory, 403, backend failure, malformed query. **Pass:** data matches source API and protected actions are unavailable/blocked correctly.

### UI-007 — Admin pages and all remaining page routes

**Priority:** P1. **Actions:** enumerate routes in `dashboard/src/App.jsx` and page files (including playground, docs/embedded docs, configuration, audit/spend/licensing/SSO/residency where present). For each: direct URL, primary action, empty/error state, unauthorized state, mobile view. **Expected:** no orphan route/component and every action maps to a documented API. **Evidence:** page inventory with route, role, action, API, results. **Pass:** every registered page is accounted for.

### UI-008 — Playground/request composer

**Priority:** P1. **Actions:** submit valid OpenAI/Anthropic/Gemini sample requests, stream where supported, alter model/config, copy/reset; then invalid JSON/oversize/timeout. **Expected:** request body warnings, formatted response/stream/error, no admin/client secret displayed. **Cleanup:** clear form/history. **Pass:** behavior agrees with direct proxy case.

### UI-009 — Accessibility baseline

**Priority:** P1. **Actions:** keyboard tab/shift-tab/enter/escape through shell, dialog, menus, forms, tables; test visible focus, labels, error announcement, semantic heading order, contrast/theme, zoom 200%, screen-reader smoke. **Expected:** controls have names and usable focus; modal focus is contained/restored; charts/tables have text alternatives where required. **Pass:** no blocking keyboard flow or critical inaccessible admin action.

### UI-010 — Responsive and resilience baseline

**Priority:** P1. **Actions:** repeat UI-001–006 at narrow/mobile, intermediate/tablet, desktop; rotate/rescale; simulate slow/offline/reconnect. **Expected:** navigation/actions remain discoverable, no clipped controls/overlapping text, reconnection refreshes accurately. **Pass:** screenshots show no release-blocking layout/interaction defect.

### UI-011 — Browser security and data handling

**Priority:** P0. **Actions:** inspect network/storage after admin login/logout; inject script-like strings into search/form fields; open external/replay/export data. **Expected:** key storage behavior matches docs, logout clears it, rendered values are escaped, no secret in URL/console/download unless explicitly intended and protected. **Pass:** no stored/reflected XSS or credential disclosure observed.

### UI-012 — Polling and concurrency

**Priority:** P1. **Actions:** keep two tabs/users open; mutate settings in one; delay/abort responses; change proxy target. **Expected:** generation-aware polling prevents stale overwrite; conflicts receive clear refresh/error; requests are bounded. **Pass:** canonical server state wins without data loss.

### UI-013 — Visual regression evidence

**Priority:** P2. **Actions:** capture approved screenshots for shell, health, savings, routing, memory, governance, replay, playground in light/dark plus mobile. **Expected:** release candidate aligns with approved design and no missing assets. **Pass:** visual diffs are reviewed and accepted.

### UI-014 — Dashboard/proxy version compatibility

**Priority:** P1. **Actions:** test dashboard artifact with current proxy and one supported prior/current upgrade combination. **Expected:** capability detection degrades gracefully for unavailable endpoints; no mutation against unknown schema. **Pass:** compatibility claim is evidenced or version restriction documented.

### UI-015 — Network/API reconciliation sweep

**Priority:** P1. **Actions:** for every dashboard API helper in `dashboard/src/lib/api.js` and routing-studio API module, execute its user action and compare request method/path/body/response handling to proxy route. **Expected:** auth header and error mapping correct. **Pass:** helper inventory attached with test result.

### UI-016 — Operational handoff

**Priority:** P2. **Actions:** log out, reopen as viewer/operator/admin, export only permitted evidence, and clear local test data. **Expected:** least privilege remains after refresh and evidence is sanitized. **Pass:** UI test run leaves no active admin session.
