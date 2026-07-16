# cutctx/providers/

## Responsibility
Defines provider protocols, model endpoint adapters, route registration, installation discovery, and agent-host integrations.

## Design
Base/registry abstractions normalize Anthropic, OpenAI, Google, Cohere, LiteLLM, and compatible APIs. Provider cost fallbacks use the canonical pricing registry and surface unknown models explicitly. Installation registry selects child provider installers/runtimes for agent tools; proxy routes expose normalized destinations.

## Flow
Provider/model configuration resolves an adapter; requests are translated and sent upstream; responses normalize back to callers. Setup/wrap flows select a child integration and apply or launch provider-specific configuration.

## Integration
Consumed by proxy routing, SDK clients, installation, and CLI. Child maps cover Aider, Claude, Codex, Copilot, Cursor, Gemini, OpenClaw, OpenCode, Windsurf, Zed, and Antigravity.
