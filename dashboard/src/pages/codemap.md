# dashboard/src/pages/

## Responsibility
Owns route-level operator experiences for overview diagnostics, savings attribution, orchestration/routing, capabilities, governance, firewall, memory, replay, playground requests, and embedded documentation.

## Design
Each page is a self-contained React composition over shared dashboard context and components. Read-heavy pages derive tables, trends, and summaries with memoized pure helpers; mutating pages keep bounded local form/pending state and surface unsupported, loading, empty, and error states explicitly.

## Flow
React Router supplies the active page and optional search query -> pages read polled snapshots or fetch feature-specific endpoints -> derived view models drive panels -> user actions patch flags, routing mode, governance/security settings, replay sessions, or send playground requests -> results and refresh state are rendered in place.

## Integration
- Registered in `src/App.jsx`.
- Uses `src/components/` for common panels/workbenches and `src/lib/` for auth, APIs, formatting, period stats, and savings semantics.
- Maps directly to Cutctx proxy operational and administrative API surfaces.
