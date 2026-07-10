# Suggested Commands
- AGENTS.md requires prefixing shell commands with `rtk`; use `rtk pytest tests/...`, `rtk proxy uv run ...`, `rtk proxy npm run ...`.
- Dashboard: `cd dashboard && rtk proxy npm run lint`; `rtk proxy npm run build`; Node Playwright config starts Vite on port 4123.
- Use `rtk git status`, `rtk git diff --check`; do not use destructive resets.