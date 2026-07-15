# Task 4 Report: Migrate Configuration, Security, and Memory Surfaces

## Scope

Implemented Task 4 in the linked worktree with the clarified E2E split:

- created `dashboard/e2e/quiet-command-center.spec.js` for the new Memory
  semantic assertion
- left the named route specs focused on their existing interaction coverage
- refreshed the `Capabilities`, `Governance`, `Firewall`, and `Memory` pages to
  use the quiet-command-center header and state patterns without changing API,
  toggle, copy, search, or scan behavior

## Files Changed

- `dashboard/e2e/quiet-command-center.spec.js`
  - Added a dedicated Playwright spec that verifies the enterprise Memory state
    is exposed as a semantic status surface via
    `data-testid="memory-enterprise-state"`.
- `dashboard/src/pages/Memory.jsx`
  - Added `PageHeader`.
  - Replaced the enterprise gate card with a `StatePanel` carrying the new test
    hook and semantic role.
  - Kept memory fetching, polling, filtering, and table rendering behavior
    intact.
- `dashboard/src/pages/Capabilities.jsx`
  - Added `PageHeader`.
  - Replaced alert banners and empty search feedback with `StatePanel`.
  - Applied summary/data panel variants without changing toggle behavior or the
    live config write path.
- `dashboard/src/pages/Governance.jsx`
  - Added `PageHeader`.
  - Replaced status/error banners with `StatePanel`.
  - Preserved feature row structure, toggle/copy behavior, entitlement logic,
    and governance polling.
- `dashboard/src/pages/Firewall.jsx`
  - Added `PageHeader`.
  - Replaced load/scan/config feedback banners with `StatePanel`.
  - Switched the no-events table state to a semantic empty/info panel while
    preserving scan submission and result rendering behavior.
- `dashboard/src/index.css`
  - Added styling for the Memory enterprise state, firewall scan result summary,
    and embedded state panels inside the governance feature list.

## Verification

Red phase:

```text
CI=true npx playwright test e2e/quiet-command-center.spec.js --project=chromium
```

Expected failure observed:

- `getByTestId('memory-enterprise-state')` was missing before implementation.

Green verification:

```text
CI=true npm run lint
CI=true npx playwright test e2e/capabilities.spec.js e2e/governance.spec.js e2e/firewall.spec.js e2e/quiet-command-center.spec.js e2e/dashboard-audit.spec.js
CI=true npm run build
```

Results:

- `npm run lint`: PASS
- Focused Playwright suite: `53 passed`
- `npm run build`: PASS

## Notes

- The unrelated deletion of `cutctx_ee/watermark.py` was left untouched.
- No Task 4 changes were made to the named route specs beyond running them for
  verification; the new semantic assertion lives in the dedicated
  `quiet-command-center` spec as requested.
