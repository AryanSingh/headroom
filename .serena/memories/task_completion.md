# Task Completion
- Scope verification to changed modules, then run broader checks proportional to blast radius.
- For dashboard changes: lint + Vite build + embedded asset-reference check + fixture-backed Playwright/Python dashboard tests.
- For proxy/CLI changes: targeted pytest plus relevant integration tests; run `rtk git diff --check` before final.