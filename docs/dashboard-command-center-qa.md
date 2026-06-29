# Dashboard Command Center QA

Use this checklist to verify the redesigned dashboard and the protected
multimodal Playground flow end to end.

## Prerequisites

1. Start the proxy with a known admin key:
   `CUTCTX_ADMIN_API_KEY=headroom-local-admin cutctx proxy --memory --port 8787`
2. Start the dashboard dev server:
   `cd dashboard && CUTCTX_ADMIN_API_KEY=headroom-local-admin npm run dev -- --host 127.0.0.1 --port 4173`
3. Open the React dashboard at:
   `http://127.0.0.1:4173/dashboard`

Notes:
- The Vite app is mounted with a router basename of `/dashboard`, so loading `http://127.0.0.1:4173/` by itself is expected to render a blank shell.
- The dev server proxies `/health`, `/stats`, and `/v1/*` to the local proxy and uses `CUTCTX_ADMIN_API_KEY` as its default admin header when the browser has not stored one yet.

## Browser Flow

1. Open `http://127.0.0.1:4173/dashboard`.
2. Enter `headroom-local-admin` in the top-bar `Optional admin key for protected actions` field.
3. Visit:
   - `Command Center`
   - `Capabilities`
   - `Security`
   - `Memory`
   - `Playground`
4. Confirm each route renders without blank states, overlays, or console errors.

## Playground Flow

1. Open `Playground`.
2. Click `Load sample multimodal image`.
3. Paste or keep a long prompt.
4. Click `Run live compression`.
5. Verify:
   - the request succeeds without `401`
   - `Compressed request payload` is populated
   - `Applied steps` shows at least one transform
   - `Image savings` is greater than zero

## Command Center Follow-Up

1. Return to `Command Center`.
2. Confirm the overview metrics refresh.
3. Confirm `Money saved` includes provider-cache savings when the cost
   breakdown shows non-zero cache savings.
4. Confirm `Active compression` uses compressible-token savings rate rather
   than subtracting from all-layer savings.
5. Confirm the trend panel shows a loading state while `/stats-history` is in
   flight, and a visible error state if `/stats-history` fails.
6. Confirm historical buckets do not double-count requests when both rollups
   and live recent requests are available.
7. If the recent-requests table falls back to synthetic durable history rows,
   unknown fields should render as `—`, not `0`.

## Enterprise Surface Follow-Up

1. Visit `Governance` and confirm RBAC assignments render for a read-only
   operator surface instead of failing as if the page were write-only.
2. Visit `Security` and confirm:
   - `Patterns` is populated when the firewall is enabled.
   - `Blocks` shows `—` plus an explanatory note when block counters are not
     tracked by the runtime yet.
