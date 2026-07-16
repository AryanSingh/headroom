# extensions/vscode/src/

## Responsibility
Implements VS Code extension activation, Cutctx proxy process control, stats polling, status-bar presentation, and configuration workflows for other AI extensions.

## Design
`extension.ts` is the composition root. `ProxyManager` spawns `cutctx proxy`, polls `/livez`, and tracks ownership. `StatsPoller` periodically reads `/stats`; `StatusBarManager` renders active/off/savings states. `AIExtensionConfigurator` applies host-specific settings or edits Continue's config.

## Flow
Activate -> read settings/create managers/register commands -> start process if configured -> readiness poll marks running -> stats poll updates cached totals -> status bar refreshes -> configuration command detects target and writes/copies proxy settings -> deactivate stops managers.

## Integration
- Compiled to `extensions/vscode/out` and loaded via the package manifest.
- Talks to localhost Cutctx endpoints and VS Code configuration/extension/clipboard APIs.
