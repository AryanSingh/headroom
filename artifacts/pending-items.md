# Pending Items

Date: 2026-07-03
Branch: `fix/ws20-memcache-optimize`

## Current Verified State

- Full Python regression passed: `7918 passed, 258 skipped, 22 warnings`.
- Rust workspace tests, Rust clippy, Rust fmt, dashboard lint/build/E2E, text
  hygiene, and diff whitespace checks passed.
- WS7 local Context Assurance is implemented and tested: SQLite evidence
  ledger, HMAC-SHA256 chain verification, ledger stats, Agent Context Report
  assurance status, and `cutctx report assurance` JSON/markdown export with
  `--verify`.
- WS8 replay now covers more than policy block/redaction events. With
  `CUTCTX_REPLAY=1`, `ReplayPipelineExtension` records compression,
  retrieval, injection, CCR lifecycle, response, error, and fallback events.
- Rust license verification regression is fixed. `cargo test -p cutctx-proxy
  --test license_verify` passes.
- Codex websocket keepalive and litellm savings-tracker resilience fixes remain
  covered by regression tests.
- End-to-end UI/API/feature bug-hunt plan exists at
  `artifacts/end-to-end-bug-hunt-plan.md`.

## Remaining Release Items

1. Commitlint/history cleanup remains open. The branch contains non-conventional
   commit subjects. Fixing this requires explicit approval to rewrite/reword
   commits.
2. EE release packaging/signing remains open for release-owner signoff. Do not
   claim a final EE release until ignored binary artifacts are rebuilt, signed,
   and provenance is documented.
3. Version/changelog release cut remains open. If publishing a final release,
   bump the version and move `[Unreleased]` notes into a dated section.
4. WS1-WS3 product/marketing docs are present for release review:
   quality-at-budget benchmark framing and current outreach positioning.
   Product-owner approval is still required before external campaign launch.
5. Future outbound learn telemetry remains intentionally disabled until
   security/product review approves it.
6. Branch cleanup remains open until release/PR owner confirms merged branches
   can be deleted.

## Skipped Test Summary

The 258 skipped Python tests are primarily live-provider, optional dependency,
or environment-gated tests:

- Missing API credentials: Gemini, OpenAI, Anthropic, Google, AWS/Bedrock.
- Optional local runtimes/tools: Ollama, spaCy, difftastic, Drain3, GPU/Kompress
  paths.
- Live proxy smoke tests that require explicit opt-in.
- Compiled EE source-inspection paths skipped when Cython binaries are loaded.

## Operational Guardrail

Do not run proxy restart/reload loops against shared `com.cutctx.proxy` on port
8787. Use `cutctx-dev` on port 8788 for proxy iteration and restart-heavy
verification.
