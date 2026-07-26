# Claude Desktop Routing Operability Design

## Outcome

Cutctx must report Claude Desktop support in terms the running app can satisfy. Claude Code and API clients that honor `ANTHROPIC_BASE_URL` can use the proxy and model router. Claude Desktop and Cowork hosted model calls cannot be repointed, so Cutctx supports them through MCP tools and an MCP tool-output gateway. The dashboard and CLI must show that boundary and the current installation state.

## Changes

1. Extend `cutctx mcp status` to inspect Claude Desktop separately from Claude Code. Report whether the app is detected, whether the Cutctx MCP server is registered, how many other stdio servers use the gateway, whether a restart is required, and that hosted model requests do not enter proxy routing.
2. Make `cutctx mcp install` print Desktop-specific next steps when Desktop is among the selected or detected registrars. Do not tell Desktop users that `ANTHROPIC_BASE_URL` routes hosted app traffic.
3. Correct dashboard capability descriptions so static cards describe supported surfaces and their limits. Add Claude Desktop MCP coverage and describe SSE as request transformation plus response passthrough, not response-stream compression.
4. Make the dashboard visual audit wait for route content before it captures screenshots. A screenshot that contains only the loading shell must fail the audit.

## Routing Policy

Keep the canonical `codex-gpt54mini-high` preset as Balanced and `economy` as Aggressive. The deterministic classifier, capability gates, provider/account proof, transport proof, pricing checks, and exact model routes remain unchanged because the current routing and benchmark suites prove the intended behavior. Claude Desktop hosted calls stay outside the router because the transport cannot be proven or redirected.

## Verification

- New CLI tests fail before implementation and pass after it.
- Claude Desktop registrar/gateway, routing, orchestration, and capability suites pass.
- The 75-case routing benchmark retains zero unsafe downgrades.
- Orchestrator Playwright tests pass at desktop and mobile widths.
- Fresh audit screenshots contain loaded Orchestrator content and no overflow, console, page, request, or asset failures.

