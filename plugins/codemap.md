# plugins/

## Responsibility
Integrates Cutctx compression/retrieval and proxy routing into agent runtimes, coding assistants, gateway stacks, and optional upstream authentication.

## Design
Runtime-specific bundles favor hooks and declarative manifests: OpenCode compresses tool/history data; OpenClaw owns context assembly and proxy lifecycle; Codex/Claude/agent hook bundles register MCP or shell hooks; Hermes exposes CCR retrieval; OAuth2 middleware mints upstream credentials. Install scripts/manifests keep host configuration separate from core algorithms.

## Flow
Host runtime loads a plugin/hook -> plugin starts or locates the proxy and registers lifecycle/tool callbacks -> outbound context is compressed or routed through Cutctx -> CCR markers can be resolved through registered retrieval tools -> failures generally preserve original host behavior.

## Integration
- Uses the TypeScript SDK, Cutctx CLI/MCP server, proxy HTTP endpoints, and host-specific plugin APIs.
- Child maps detail `cutctx-opencode/` and `openclaw/`; sibling bundles cover Codex, Claude Code, generic agents, Hermes, OAuth2, and shell/plugin packaging.
