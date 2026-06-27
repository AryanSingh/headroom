# Dashboard Command Center QA

Use this checklist to verify the redesigned dashboard and the protected
multimodal Playground flow end to end.

## Prerequisites

1. Start the proxy with a known admin key:
   `CUTCTX_ADMIN_API_KEY=headroom-local-admin cutctx proxy --memory --port 8787`
2. Start the dashboard dev server:
   `cd dashboard && npm run dev -- --host 127.0.0.1 --port 4173`

## Browser Flow

1. Open the dashboard.
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
3. Confirm the savings attribution rail does not hide compression savings when
   top-level token counters are non-zero.
