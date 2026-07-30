# Control Credential Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let CutCtx Control authenticate its own status requests and open an already-authenticated local dashboard without exposing a license or provider key to the browser.

**Architecture:** The proxy will exchange a Control-authenticated request for one short-lived, single-use opaque dashboard session. Control opens that opaque bootstrap URL; the proxy exchanges it for a `HttpOnly`, same-site cookie and redirects to `/dashboard`. The dashboard uses the cookie for its existing admin requests. Control adds the saved license to its `/stats` probe and retains the existing managed-runtime provider-key bridge.

**Tech Stack:** FastAPI/Python proxy, Rust/Tauri Control app, pytest, Rust unit tests, Playwright dashboard tests.

## Global Constraints

- Do not put a license, admin key, or upstream provider key in a URL, browser storage, cookie value, manifest, process argument, or log.
- Bootstrap sessions are loopback-only, opaque, single-use, and expire after 60 seconds.
- The dashboard session cookie is `HttpOnly`, `SameSite=Strict`, scoped to `/`, and expires after eight hours.
- Existing header and SSO admin authentication remain unchanged.
- Follow red-green-refactor: each production behavior starts with a focused failing test.

---

### Task 1: Proxy dashboard-session contract

**Files:**
- Modify: `cutctx/proxy/server.py`
- Test: `tests/test_runtime_app_admin_auth.py`

**Interfaces:**
- `POST /admin/dashboard-sessions` requires existing admin/license auth and returns `{"bootstrap_token": "..."}`.
- `GET /dashboard/connect?token=...` exchanges the token for an authenticated cookie and redirects to `/dashboard`.

- [ ] Add a failing integration test that an authenticated request creates an opaque token, browser connection succeeds without a key header, and subsequent `/stats` succeeds through the cookie.
- [ ] Run that test and observe the missing endpoint failure.
- [ ] Implement an in-memory, expiry-checked single-use token registry inside `create_app`, a protected mint endpoint, and a loopback-only exchange endpoint that sets the dashboard cookie.
- [ ] Run the focused test and observe pass.

### Task 2: Control-authenticated probe and handoff

**Files:**
- Modify: `desktop/cutctx-control/src-tauri/src/lib.rs`
- Modify: `desktop/cutctx-control/src-tauri/src/dashboard_link.rs`
- Test: unit tests in `desktop/cutctx-control/src-tauri/src/dashboard_link.rs`

**Interfaces:**
- `probe_tokens_saved(port, license)` includes `X-Cutctx-Admin-Key` only when a saved license is available.
- `dashboard_url` mints a bootstrap token with the saved license and returns `/dashboard/connect?token=...`.

- [ ] Add failing tests for a tokenized control deep link and for preserving the token as opaque rather than a credential.
- [ ] Run Cargo tests and observe the expected failure.
- [ ] Implement the minimal Control HTTP calls; never return the license to the web frontend or include it in the browser URL.
- [ ] Run focused Cargo tests and observe pass.

### Task 3: Dashboard cookie-only behavior and end-to-end verification

**Files:**
- Modify: `dashboard/src/lib/admin-auth.js`
- Modify: `dashboard/e2e/auth.spec.js`
- Test: `dashboard/e2e/auth.spec.js`

- [ ] Add a failing dashboard test that an existing authenticated cookie loads the dashboard with no persisted admin key.
- [ ] Run the focused Playwright test and observe failure.
- [ ] Ensure admin-auth reads only legacy explicit keys while cookie-backed requests need no copied secret; retain manual entry as a fallback for direct browser access.
- [ ] Run focused Python, Rust, Node, and Playwright checks; scan the diff for synthetic secrets.
