# Core
- Python Cutctx product: proxy/API, Click CLI, dashboard, MCP, integrations, SDKs/plugins, deployment assets.
- Entrypoint: `cutctx` -> `cutctx.cli.main:main`; runtime proxy factory: `cutctx.proxy.server:create_app`.
- Major module maps: dashboard-specific conventions/tests: `mem:dashboard/core`; build/test commands: `mem:suggested_commands`.
- Generated embedded dashboard assets under `cutctx/dashboard/` must stay synchronized with `dashboard/dist/`.