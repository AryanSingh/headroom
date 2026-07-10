# Conventions
- Preserve user/other-agent changes; do not revert unrelated work.
- Use `apply_patch` for manual repo edits.
- Proxy route contracts are authoritative for dashboard fixtures; period-scoped dashboard values must not fall back to lifetime values.
- Dashboard build output is served through `cutctx/dashboard/index.html` and `cutctx/dashboard/assets`; test the embedded bundle, not only Vite source.