# extensions/

## Responsibility
Supplies IDE integrations that manage a local Cutctx proxy, expose savings/status controls, and help route supported AI extensions through it.

## Design
The VS Code extension is TypeScript with command/status/polling/configurator modules. The JetBrains plugin is Kotlin with persistent settings, an application proxy service, startup activity, actions, configurable UI, and status-bar widget. Both treat the proxy as an external process/API.

## Flow
IDE activates extension -> read settings and optionally start `cutctx proxy` -> poll liveness/stats -> update status UI -> commands start/stop/show stats or configure AI provider proxy URLs -> IDE shutdown stops owned resources.

## Integration
- Targets VS Code-compatible editors and JetBrains Platform IDEs.
- Integrates with the Cutctx CLI `/livez`/`/stats` endpoints and settings for Copilot, Cline, Continue, global HTTP, or JetBrains AI providers.
