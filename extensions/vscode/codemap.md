# extensions/vscode/

## Responsibility
Packages the VS Code/Cursor Cutctx extension for proxy lifecycle, status/savings display, and AI-extension proxy configuration.

## Design
The manifest contributes four commands and port/auto-start/binary settings. TypeScript compiles from `src/` to `out/`; extension activation owns `ProxyManager`, `StatsPoller`, and `StatusBarManager` instances.

## Flow
VS Code activates on startup -> initialize managers from settings -> register commands/status item -> optionally spawn proxy and wait for liveness -> poll stats and render token/cost savings -> deactivate stops polling/process.

## Integration
- Uses VS Code APIs, Node child-process/http/fs modules, and the external `cutctx` binary.
- Can configure VS Code/Cursor HTTP proxy, Copilot overrides, Cline guidance, and Continue configuration.
