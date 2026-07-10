# Dashboard
- React router exposes 10 operator routes from `dashboard/src/App.jsx`: overview, savings, orchestrator, capabilities, governance, firewall, memory, replay, playground, docs.
- Shared fetch/context layer: `dashboard/src/lib/dashboard-context.jsx`, `use-dashboard-data.js`.
- Embedded proxy runtime reads `cutctx/dashboard/index.html`, which must reference a present hashed asset in `cutctx/dashboard/assets`.
- Existing UI coverage combines `dashboard/e2e/*.spec.js` and Python Playwright tests under `tests/test_dashboard*.py`.