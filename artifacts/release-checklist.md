# Release Checklist

Date: 2026-07-03
Branch: `fix/ws20-memcache-optimize`

## Verified Closed

- [x] Full Python regression: `rtk test .venv/bin/python -m pytest tests/`
  passed with `7918 passed, 258 skipped, 22 warnings`.
- [x] Rust workspace tests: `rtk test cargo test --workspace` passed.
- [x] Rust clippy: `rtk cargo clippy --workspace -- -D warnings` passed.
- [x] Rust format: `rtk cargo fmt --all -- --check` passed.
- [x] Dashboard lint/build/E2E:
  `cd dashboard && rtk npm run lint && rtk npm run build && rtk npx playwright test e2e/`
  passed with 19 Playwright tests.
- [x] Focused WS7/WS8/Codex/litellm regression set passed:
  `tests/test_assurance.py`, `tests/test_agent_context_report.py`,
  `tests/test_context_policy_proxy_integration.py`,
  `tests/test_codex_uvicorn_keepalive.py`, and
  `tests/test_savings_tracker_litellm_resilience.py`.
- [x] Text hygiene passed for current release-tracking docs and touched source
  files.
- [x] `rtk git diff --check` passed.
- [x] WS2 Agent Context Report v1 is implemented.
- [x] WS4 Context Policy Engine and proxy enforcement are implemented for the
  verified MVP scope.
- [x] WS5 org-scoped memory export/import round-trip is verified.
- [x] WS6 local-only learn telemetry aggregation is implemented; outbound share
  remains intentionally unimplemented.
- [x] WS7 local Context Assurance is implemented and focused-tested: SQLite
  evidence ledger, HMAC-SHA256 chain verification, quality stats, Agent Context
  Report assurance section, and `cutctx report assurance` JSON/markdown export
  plus `--verify`.
- [x] WS8 replay has context-policy replay API/dashboard coverage and
  `CUTCTX_REPLAY=1` / `ReplayPipelineExtension` coverage for compression,
  retrieval, injection, CCR lifecycle, response, error, and fallback timeline
  events.
- [x] Rust Ed25519 license verification regression is fixed:
  `cargo test -p cutctx-proxy --test license_verify` passes after seeding a
  fresh empty CRL cache in the test/debug path.
- [x] Codex websocket keepalive regression coverage is present.
- [x] Savings tracker litellm resilience regression coverage is present.

## Still Open For Final Release

- [ ] Commitlint gate is not green for the branch range from `origin/main` to
  `HEAD`. Several existing commit subjects are non-conventional. Closing this
  requires commit history rewrite/reword approval.
- [ ] EE binary release packaging/signing needs explicit release-owner signoff.
  Source/runtime tests for HMAC assurance are green, but ignored binary
  artifacts must be rebuilt and signed as part of the final release process.
- [ ] Versioning decision is still open. If this is the final release cut,
  bump `pyproject.toml` as appropriate and move `[Unreleased]` changelog notes
  to a dated release section.
- [ ] Security/product review must approve any future `CUTCTX_LEARN_SHARE`
  outbound telemetry path before it is enabled.
- [ ] Enterprise positioning must decide whether the OSS-side local assurance
  ledger is sufficient for release claims or whether claims require EE-only
  packaging language.
- [x] WS1-WS3 go-to-market polish docs are present for release review:
  quality-at-budget benchmark framing and current outreach positioning.
- [ ] Product-owner approval is still required before external campaign launch.
- [ ] Branch cleanup can proceed only after PR/release owner confirmation for
  merged feature branches.

## Operational Guardrail

Do not run proxy restart/reload loops against shared `com.cutctx.proxy` on port
8787. Use `cutctx-dev` on port 8788 for proxy iteration and restart-heavy
verification.
