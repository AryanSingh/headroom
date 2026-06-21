# Cutctx agent hooks

This plugin exposes lightweight startup hooks for Claude Code and GitHub Copilot CLI.

The hooks call:

```bash
cutctx init hook ensure
```

That hidden helper checks for a matching durable `cutctx init` deployment and starts it if needed.
