# dashboard/src/lib/

## Responsibility
Supplies the dashboard's HTTP, authentication, polling, context, formatting, savings-attribution, time-window, timeout, and theme infrastructure.

## Design
`dashboard-context.jsx` owns generation-aware current/history polling and exposes it through `dashboard-context-value.js`/`use-dashboard-data.js`. `api.js` resolves proxy URLs; `admin-auth.js` keeps an admin key in memory/storage and request headers. Pure helpers normalize formats, period buckets, and created-versus-observed savings. Theme state is an independent context.

## Flow
Provider startup adopts a URL key, concurrently fetches health/stats, optionally loads flags, and polls current/history data on separate intervals. Consumers read context, derive metrics with pure helpers, and use authenticated fetch/patch helpers; request generations prevent stale responses from overwriting newer snapshots.

## Integration
- Used by `App.jsx`, all feature pages, and stateful components.
- Calls proxy health, stats, history, configuration, routing, memory, replay, and security APIs.
- Uses browser storage, `fetch`, abort signals, and React context/hooks.
