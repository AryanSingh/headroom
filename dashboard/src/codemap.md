# dashboard/src/

## Responsibility
Implements the dashboard application runtime, routing shell, styles, reusable components, data adapters, and feature pages.

## Design
`main.jsx` is the DOM entry point and `App.jsx` is a provider-wrapped SPA shell. State and HTTP concerns live in `lib/`; display metadata in `data/`; reusable UI and operator workbenches in `components/`; route-level behavior in `pages/`.

## Flow
Browser startup mounts `App`, chooses a basename, initializes theme/dashboard providers, and renders the responsive shell. Router state and shared polling data flow into pages; page actions return through library request helpers and trigger refreshes.

## Integration
- Parent application: `dashboard/` Vite bundle.
- Children: `components/`, `data/`, `lib/`, and `pages/`.
- Talks to the local or configured Cutctx proxy and persists theme/admin-key state in browser storage.
