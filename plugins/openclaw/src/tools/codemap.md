# plugins/openclaw/src/tools/

## Responsibility
Defines the OpenClaw `cutctx_retrieve` tool for recovering original content behind CCR markers.

## Design
`createCutctxRetrieveTool` validates the proxy origin once and returns a host-compatible JSON-schema tool. Execution strictly validates 24-character hex hashes, supports an optional search query, applies a timeout, and returns structured JSON errors instead of throwing into the agent runtime.

## Flow
Agent supplies hash/query -> validate hash -> GET the proxy retrieval endpoint -> stringify returned content/metadata -> on HTTP, timeout, or expiry failure return actionable error JSON.

## Integration
- Registered by `src/plugin/index.ts` once a proxy URL is available.
- Calls `/v1/retrieve/{hash}` on the active Cutctx proxy.
