# dashboard/

## Responsibility
Vite/React operator console for inspecting and administering a running Cutctx proxy: health, savings, routing, capabilities, governance, firewall, memory, replay, and interactive request diagnostics.

## Design
`src/App.jsx` supplies the routed shell, responsive navigation, theme, authentication gate, and error boundary. A polling context centralizes proxy snapshots; feature pages compose shared state panels and specialized studios. Vite builds the static application served beneath `/`, `/admin`, or `/dashboard`.

## Flow
`main.jsx` mounts `App` -> providers adopt any admin key and poll `/stats`, `/health`, `/stats-history`, and optional flags -> React Router selects a page -> pages derive view models and call administrative endpoints for mutations -> explicit refreshes reconcile the new proxy state.

## Integration
- Consumes the Cutctx proxy's public and admin HTTP APIs through `src/lib/`.
- `src/components/` contains reusable controls and routing/orchestration workbenches; `src/pages/` owns product surfaces; `src/data/` supplies capability metadata.
- Built and tested with Vite, React Router, Lucide, and Playwright.
