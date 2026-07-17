# Watermark AV Hardening Design

## Goal

Retain enterprise build identity and local license traceability while removing
the runtime source mutation and arbitrary binary scanning patterns that cause
endpoint protection products to flag `cutctx_ee/watermark.py`.

## Decision

The shipped module becomes read-only. It retains `Watermark`, marker
serialization/parsing, deterministic local traceability verification, and a
new manifest-oriented extraction function. It no longer edits package source
or scans arbitrary binaries.

## API

- Keep: `Watermark.to_marker()`, `Watermark.from_marker()`, and
  `verify_watermark_traceability()`.
- Add: `watermark_manifest(watermark: Watermark) -> dict[str, str | int]`.
  This produces serializable release metadata for a separately controlled,
  signed build manifest.
- Add: `extract_watermark_from_manifest(manifest: Mapping[str, object]) ->
  Watermark | None`.
- Remove from the shipped module: `embed_watermark_in_source()` and
  `extract_watermark_from_binary()`.

## Constraints

- No network, process execution, dynamic execution, package-file writes, or
  arbitrary binary reads in `cutctx_ee.watermark`.
- Do not reintroduce `CUTCTX_INTERNAL_*` or other leak-canary strings.
- Preserve marker compatibility for previously issued `CTXWM:` markers.
- A malformed manifest or marker returns `None`; it never raises during
  inspection.
- SQLite verification stays explicit and read-only (`SELECT 1`).
- Tests assert that the removed runtime mutation/scanning APIs are absent.

## Migration

Release engineering writes a signed manifest outside the Python package at
build time. Existing builds can still be inspected by parsing their stored
marker through `Watermark.from_marker`; binary forensics is deliberately moved
out of the runtime distribution.

## Verification

- Marker round-trip and invalid marker tests pass.
- Manifest round-trip and malformed-manifest tests pass.
- Focused software-protection and release-coverage tests pass.
- Static source checks prove the module contains neither write calls nor binary
  reads and does not import network/process modules.
