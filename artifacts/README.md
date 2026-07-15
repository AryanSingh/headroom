# Cutctx Evidence Artifacts

This directory contains retained, reviewable evidence and selected commercial
materials. It is not a source of product claims by itself: each result must
identify its corpus, baseline, scorer, provenance, date, and limitations.

## Current evaluation evidence

- `provider-backed-openai-codesearchnet-2026-07-15/` — 50-case
  original-versus-compressed CodeSearchNet preservation run (30% compression).
- `subscription-cli-pilot-2026-07-15.json` — redacted authenticated Claude
  Code and Codex CLI transport pilot. One case per dataset; not statistically
  powered.
- `downstream-task-quality/` — deterministic local downstream-task outcomes.
- `model-routing-quality.json` — routing-quality fixture result.

The canonical testing procedure, safe handling rules, and known BFCL limitation
live in `docs/content/docs/benchmarks.mdx` and `docs/release-evidence-runbook.md`.

## Retention rules

- Retain only evidence that is reproducible, redacted, and tied to a specific
  repository state.
- Delete generated reports that contain fixed loader failures, stale hashes,
  credentials, session files, customer inputs, or unsupported product claims.
- Keep provider API results and subscription-CLI results in separate artifacts.
- Regenerate release manifests rather than editing their hashes by hand.
