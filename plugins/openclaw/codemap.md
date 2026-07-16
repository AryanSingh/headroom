# plugins/openclaw/

## Responsibility
Provides an OpenClaw context-engine plugin that compresses assembled agent context, manages a Cutctx proxy, reroutes selected gateway providers, and registers CCR retrieval.

## Design
`src/plugin/` is host registration; `CutctxContextEngine` owns lifecycle/assembly/statistics; `ProxyManager` securely probes or starts only local proxies; conversion and gateway-config modules isolate host/provider formats. `src/tools/` exposes retrieval, while `hook-shim/` satisfies link-hook packaging compatibility.

## Flow
OpenClaw loads manifest/plugin -> engine schedules proxy discovery/start -> proxy-ready callback rewrites configured in-memory provider base URLs -> context assembly converts agent messages, compresses through `cutctx-ai`, and converts back -> retrieval tool resolves CCR hashes -> dispose stops owned proxy.

## Integration
- Registers with OpenClaw context engine, tool, and gateway-start APIs.
- Uses `cutctx-ai`, Node subprocess/fetch APIs, the Cutctx proxy, and the plugin schema in `openclaw.plugin.json`.
